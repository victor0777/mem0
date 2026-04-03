#!/usr/bin/env python3
"""Self-contained sync/search helper for project mem0 knowledge base.

Scans all .md files under docs/ recursively AND .mem0/imported/ (cross-project
context from collaboration MCP). Chunks by ## headings, indexes into local
FAISS via mem0.

Usage:
    python .mem0/sync.py rebuild              # (re)index all docs + imported
    python .mem0/sync.py ensure               # rebuild only if docs changed
    python .mem0/sync.py search "query"       # search indexed knowledge (auto-ensures)
    python .mem0/sync.py search "query" --top_k 10
    python .mem0/sync.py refresh-imported     # pull cross-project context from collaboration MCP
    python .mem0/sync.py ensure-imported      # refresh only if TTL expired
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

USER_ID = "project_context"
IMPORTED_TTL_SECONDS = 21600  # 6 hours

# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def _split_by_headings(text: str) -> list[tuple[str, str]]:
    """Split markdown by ## headings -> [(title, section_text), ...]."""
    parts = re.split(r"(?=^## )", text, flags=re.MULTILINE)
    sections = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^## (.+)", part)
        title = m.group(1).strip() if m else ""
        sections.append((title, part))
    return sections


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _detect_doc_type(rel_path: str) -> str:
    rel_lower = str(rel_path).lower()
    name = Path(rel_path).name.lower()
    # Imported types
    if ".mem0/imported/" in rel_lower:
        if "/requests/" in rel_lower:
            return "request"
        if "/reports/" in rel_lower:
            return "report"
        if "/insights/" in rel_lower:
            return "insight"
        return "imported"
    # Local types
    if "findings" in name:
        return "finding"
    if "lessons" in name:
        return "lesson"
    if "diaries" in rel_lower or "diary" in name:
        return "diary"
    if "adr" in rel_lower:
        return "adr"
    if "backlog" in name:
        return "backlog"
    if "roadmap" in name:
        return "roadmap"
    return "doc"


def _detect_source_layer(rel_path: str) -> str:
    return "imported" if ".mem0/imported/" in str(rel_path) else "local"


def _jaccard_similarity(text_a: str, text_b: str) -> float:
    """Word-level Jaccard similarity between two texts."""
    words_a = set(text_a.lower().split())
    words_b = set(text_b.lower().split())
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)


JACCARD_DEDUP_THRESHOLD = 0.8


def _get_doc_files(project_dir: Path) -> list[Path]:
    """Return all indexable .md files: docs/ + .mem0/imported/."""
    files = []
    # Local docs
    docs_dir = project_dir / "docs"
    if docs_dir.is_dir():
        files.extend(
            f for f in docs_dir.rglob("*.md")
            if f.name.lower() != "readme.md"
        )
    # Imported context
    imported_dir = project_dir / ".mem0" / "imported"
    if imported_dir.is_dir():
        files.extend(imported_dir.rglob("*.md"))
    return sorted(files)


def collect_chunks(project_dir: Path) -> list[dict]:
    """Collect all chunks from local docs + imported context."""
    chunks = []

    for f in _get_doc_files(project_dir):
        text = f.read_text(encoding="utf-8", errors="replace")
        rel = str(f.relative_to(project_dir))
        doc_type = _detect_doc_type(rel)
        source_layer = _detect_source_layer(rel)

        # Read imported metadata if available
        imported_meta = {}
        if source_layer == "imported":
            meta_file = f.with_suffix(".json")
            if meta_file.exists():
                try:
                    imported_meta = json.loads(meta_file.read_text())
                except Exception:
                    pass

        sections = _split_by_headings(text)
        if len(sections) <= 1 and text.strip():
            meta = {
                "file": rel,
                "doc_type": doc_type,
                "source_layer": source_layer,
                "section": "",
                "hash": _content_hash(text),
            }
            meta.update(imported_meta)
            chunks.append({"text": text.strip(), "metadata": meta})
        else:
            for i, (title, section_text) in enumerate(sections):
                if len(section_text.strip()) < 20:
                    continue
                meta = {
                    "file": rel,
                    "doc_type": doc_type,
                    "source_layer": source_layer,
                    "section": title,
                    "hash": _content_hash(section_text),
                }
                meta.update(imported_meta)
                chunks.append({"text": section_text, "metadata": meta})

    # Dedup: remove near-duplicate chunks (Jaccard > 0.8)
    # Ref: Omni-SimpleMem (arXiv:2604.01007) text_processor.py
    if len(chunks) > 1:
        deduped = [chunks[0]]
        dedup_count = 0
        for chunk in chunks[1:]:
            is_dup = False
            # Only compare against recent chunks (same file or nearby)
            for existing in deduped[-10:]:
                if _jaccard_similarity(chunk["text"], existing["text"]) > JACCARD_DEDUP_THRESHOLD:
                    is_dup = True
                    dedup_count += 1
                    break
            if not is_dup:
                deduped.append(chunk)
        if dedup_count > 0:
            chunks = deduped

    return chunks


# ---------------------------------------------------------------------------
# Imported context management
# ---------------------------------------------------------------------------

def _get_project_name(project_dir: Path) -> str:
    """Detect project name from directory or config."""
    return project_dir.name


def _get_imported_state(project_dir: Path) -> dict:
    """Read .mem0/imported/state.json."""
    state_path = project_dir / ".mem0" / "imported" / "state.json"
    if state_path.exists():
        try:
            return json.loads(state_path.read_text())
        except Exception:
            pass
    return {}


def _is_imported_stale(project_dir: Path) -> bool:
    """Check if imported context TTL has expired."""
    state = _get_imported_state(project_dir)
    expires = state.get("ttl_expires_at", "")
    if not expires:
        return True
    try:
        from datetime import datetime
        exp_time = datetime.fromisoformat(expires)
        return datetime.now() > exp_time
    except Exception:
        return True


def cmd_refresh_imported(project_dir: Path) -> bool:
    """Pull cross-project context from collaboration MCP export_project_context()."""
    project_name = _get_project_name(project_dir)
    imported_dir = project_dir / ".mem0" / "imported"

    print(f"Refreshing imported context for '{project_name}'...")

    # Call collaboration MCP via its Python module
    try:
        collab_root = Path.home() / "projects" / "collaboration"
        if not collab_root.exists():
            print("  Collaboration project not found. Skipping imported refresh.")
            return False
        sys.path.insert(0, str(collab_root))
        from mcp_server import export_project_context
        result_str = export_project_context(project_name)
        result = json.loads(result_str)
    except Exception as e:
        print(f"  Failed to call export_project_context: {e}")
        print("  Keeping existing imported cache (if any).")
        return False

    items = result.get("items", [])
    if not items:
        print("  No items to import.")
        # Still update state to reset TTL
        _write_imported_state(project_dir, result, 0)
        return True

    # Atomic write: write to temp dir, then swap
    tmp_dir = Path(tempfile.mkdtemp(prefix="mem0_import_", dir=project_dir / ".mem0"))
    try:
        _write_imported_files(tmp_dir, items)

        # Swap: remove old imported dir contents (keep state.json update for after)
        if imported_dir.exists():
            for sub in imported_dir.iterdir():
                if sub.name == "state.json":
                    continue
                if sub.is_dir():
                    shutil.rmtree(sub)
                else:
                    sub.unlink()

        # Move new files into imported dir
        imported_dir.mkdir(parents=True, exist_ok=True)
        for sub in tmp_dir.iterdir():
            dest = imported_dir / sub.name
            if sub.is_dir():
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.move(str(sub), str(dest))
            else:
                shutil.move(str(sub), str(dest))

        _write_imported_state(project_dir, result, len(items))
        print(f"  Imported {len(items)} items to {imported_dir}")
        return True
    finally:
        # Cleanup temp dir
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)


def _write_imported_files(target_dir: Path, items: list[dict]):
    """Write imported items as individual .md + .json files."""
    for item in items:
        item_type = item.get("type", "unknown")
        item_id = item.get("id", "unknown").replace("/", "_")
        relation = item.get("relation", "")
        body = item.get("body", "")

        # Determine subdirectory
        if item_type == "request":
            sub_dir = target_dir / "requests"
        elif item_type == "report":
            if relation == "self_report":
                sub_dir = target_dir / "reports" / "self"
            elif relation == "upstream_report":
                sub_dir = target_dir / "reports" / "upstream" / item.get("origin_project", "unknown")
            elif relation == "downstream_report":
                sub_dir = target_dir / "reports" / "downstream" / item.get("origin_project", "unknown")
            else:
                sub_dir = target_dir / "reports"
        elif item_type == "insight":
            sub_dir = target_dir / "insights"
        else:
            sub_dir = target_dir / "other"

        sub_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{item_id}.md"
        (sub_dir / filename).write_text(body, encoding="utf-8")

        # Write metadata sidecar
        meta = {k: v for k, v in item.items() if k != "body"}
        meta["origin_system"] = "collaboration"
        meta["synced_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        (sub_dir / f"{item_id}.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def _write_imported_state(project_dir: Path, result: dict, item_count: int):
    """Write .mem0/imported/state.json with TTL info."""
    from datetime import datetime, timedelta
    ttl = result.get("ttl_seconds", IMPORTED_TTL_SECONDS)
    state = {
        "project": result.get("project", ""),
        "synced_at": datetime.now().isoformat(),
        "ttl_expires_at": (datetime.now() + timedelta(seconds=ttl)).isoformat(),
        "ttl_seconds": ttl,
        "item_count": item_count,
        "dependencies": result.get("dependencies", {}),
        "snapshot_at": result.get("snapshot_at", ""),
    }
    state_path = project_dir / ".mem0" / "imported" / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def cmd_ensure_imported(project_dir: Path) -> bool:
    """Refresh imported context only if TTL expired."""
    if _is_imported_stale(project_dir):
        return cmd_refresh_imported(project_dir)
    else:
        state = _get_imported_state(project_dir)
        print(f"Imported context is fresh (expires: {state.get('ttl_expires_at', '?')}).")
        return False


# ---------------------------------------------------------------------------
# mem0 integration
# ---------------------------------------------------------------------------

def _load_config(project_dir: Path) -> dict:
    cfg_path = project_dir / ".mem0" / "config.json"
    if not cfg_path.exists():
        print(f"Error: {cfg_path} not found. Run setup_project_mem0.py first.", file=sys.stderr)
        sys.exit(1)
    return json.loads(cfg_path.read_text())


def _get_memory(project_dir: Path):
    """Create a mem0 Memory instance from project config."""
    os.environ.setdefault("OPENAI_API_KEY", "sk-1234")
    from mem0 import Memory
    cfg = _load_config(project_dir)
    vs_cfg = cfg.get("vector_store", {}).get("config", {})
    if "path" in vs_cfg and not Path(vs_cfg["path"]).is_absolute():
        vs_cfg["path"] = str(project_dir / vs_cfg["path"])
    return Memory.from_config(cfg)


def cmd_rebuild(project_dir: Path):
    """Rebuild the entire FAISS index from docs + imported."""
    chunks = collect_chunks(project_dir)
    if not chunks:
        print("No documents found to index.")
        print(f"  Looked in: {project_dir / 'docs'}/**/*.md + .mem0/imported/**/*.md")
        return

    m = _get_memory(project_dir)

    # Clear existing index
    faiss_dir = project_dir / ".mem0" / "faiss_index"
    if faiss_dir.exists():
        shutil.rmtree(faiss_dir)
        faiss_dir.mkdir(parents=True)

    m = _get_memory(project_dir)

    print(f"Indexing {len(chunks)} chunks...")
    for i, chunk in enumerate(chunks):
        m.add(
            chunk["text"],
            user_id=USER_ID,
            metadata=chunk["metadata"],
            infer=False,
        )
        if (i + 1) % 10 == 0 or (i + 1) == len(chunks):
            print(f"  [{i + 1}/{len(chunks)}] indexed")

    # Count by source layer
    local_count = sum(1 for c in chunks if c["metadata"].get("source_layer") == "local")
    imported_count = sum(1 for c in chunks if c["metadata"].get("source_layer") == "imported")
    print(f"Done. {len(chunks)} chunks indexed ({local_count} local + {imported_count} imported)")

    _write_manifest(project_dir, chunks)


# ---------------------------------------------------------------------------
# Manifest-based staleness check
# ---------------------------------------------------------------------------

MANIFEST_PATH_SUFFIX = ".mem0" + os.sep + "manifest.json"


def _compute_manifest(project_dir: Path) -> dict:
    """Compute current state of all indexable files."""
    state = {}
    for f in _get_doc_files(project_dir):
        rel = str(f.relative_to(project_dir))
        st = f.stat()
        state[rel] = {"mtime_ns": st.st_mtime_ns, "size": st.st_size}
    return state


def _write_manifest(project_dir: Path, chunks: list[dict] | None = None):
    """Write manifest.json with current state."""
    manifest = {
        "synced_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "chunk_count": len(chunks) if chunks else 0,
        "files": _compute_manifest(project_dir),
    }
    mf_path = project_dir / MANIFEST_PATH_SUFFIX
    mf_path.write_text(json.dumps(manifest, indent=2) + "\n")


def _is_stale(project_dir: Path) -> bool:
    """Check if any indexed files have changed since last rebuild."""
    mf_path = project_dir / MANIFEST_PATH_SUFFIX
    faiss_dir = project_dir / ".mem0" / "faiss_index"

    if not mf_path.exists() or not faiss_dir.exists():
        return True
    if not any(faiss_dir.iterdir()):
        return True

    try:
        old = json.loads(mf_path.read_text())
        old_files = old.get("files", {})
    except (json.JSONDecodeError, OSError):
        return True

    current = _compute_manifest(project_dir)

    if set(current.keys()) != set(old_files.keys()):
        return True
    for rel, info in current.items():
        old_info = old_files.get(rel, {})
        if info["mtime_ns"] != old_info.get("mtime_ns") or info["size"] != old_info.get("size"):
            return True

    return False


def cmd_ensure(project_dir: Path) -> bool:
    """Rebuild only if docs/imported have changed since last sync."""
    if _is_stale(project_dir):
        print("Docs changed — rebuilding index...")
        cmd_rebuild(project_dir)
        return True
    else:
        print("Index is up to date.")
        return False


def _make_canonical_key(project_dir: Path, rel_path: str) -> str:
    """Generate canonical key for dedup across layers."""
    project = _get_project_name(project_dir)
    return f"project_doc:{project}:{rel_path}"


def _make_doc_id(canonical_key: str) -> str:
    """Generate stable doc_id from canonical key."""
    return hashlib.sha1(canonical_key.encode()).hexdigest()[:16]


def cmd_search(project_dir: Path, query: str, top_k: int = 5, json_output: bool = False):
    """Search the indexed knowledge base. Auto-ensures freshness."""
    # Auto-ensure imported (non-blocking: skip on failure)
    if _is_imported_stale(project_dir):
        if not json_output:
            print("(auto) Imported context expired — attempting refresh...")
        try:
            cmd_refresh_imported(project_dir)
        except Exception as e:
            if not json_output:
                print(f"  Imported refresh failed ({e}), using cached data.")

    # Auto-ensure local + imported docs
    if _is_stale(project_dir):
        if not json_output:
            print("(auto-ensure) Docs changed — rebuilding before search...")
        cmd_rebuild(project_dir)

    m = _get_memory(project_dir)
    results = m.search(query, user_id=USER_ID, limit=top_k)

    if isinstance(results, dict):
        items = results.get("results", results.get("memories", []))
    else:
        items = results

    if json_output:
        project_name = _get_project_name(project_dir)
        json_items = []
        for item in items:
            meta = item.get("metadata", {})
            rel_path = meta.get("file", "")
            source_layer = meta.get("source_layer", "local")
            canonical_key = _make_canonical_key(project_dir, rel_path)
            doc_id = _make_doc_id(canonical_key)
            json_items.append({
                "doc_id": doc_id,
                "canonical_key": canonical_key,
                "project": project_name,
                "path": rel_path,
                "doc_type": meta.get("doc_type", ""),
                "source_layer": source_layer,
                "section": meta.get("section", ""),
                "score": item.get("score", 0),
                "snippet": (item.get("memory", "")[:300]).replace("\n", " "),
                "hash": meta.get("hash", ""),
            })
        print(json.dumps({
            "query": query,
            "project": project_name,
            "results": json_items,
            "count": len(json_items),
        }, ensure_ascii=False))
        return

    if not items:
        print("No results found.")
        return

    for i, item in enumerate(items):
        score = item.get("score", "?")
        meta = item.get("metadata", {})
        memory = item.get("memory", "")
        source = meta.get("file", "?")
        section = meta.get("section", "")
        doc_type = meta.get("doc_type", "")
        layer = meta.get("source_layer", "?")

        header = f"[{i + 1}] score={score:.4f}" if isinstance(score, float) else f"[{i + 1}]"
        layer_tag = f" [{layer}]" if layer != "local" else ""
        print(f"\n{header}  ({doc_type}{layer_tag}) {source}")
        if section:
            print(f"    Section: {section}")
        preview = memory[:200].replace("\n", " ")
        if len(memory) > 200:
            preview += "..."
        print(f"    {preview}")


def main():
    parser = argparse.ArgumentParser(description="Sync and search project docs with mem0")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("rebuild", help="Rebuild index from docs/ + imported/")
    sub.add_parser("ensure", help="Rebuild only if docs changed since last sync")
    sub.add_parser("refresh-imported", help="Pull cross-project context from collaboration MCP")
    sub.add_parser("ensure-imported", help="Refresh imported only if TTL expired")

    sp_search = sub.add_parser("search", help="Search indexed knowledge (auto-ensures freshness)")
    sp_search.add_argument("query", help="Search query")
    sp_search.add_argument("--top_k", type=int, default=5, help="Number of results (default: 5)")
    sp_search.add_argument("--json", action="store_true", help="Output results as JSON")

    args = parser.parse_args()
    project_dir = Path(__file__).resolve().parent.parent

    if args.command == "rebuild":
        cmd_rebuild(project_dir)
    elif args.command == "ensure":
        cmd_ensure(project_dir)
    elif args.command == "refresh-imported":
        cmd_refresh_imported(project_dir)
    elif args.command == "ensure-imported":
        cmd_ensure_imported(project_dir)
    elif args.command == "search":
        cmd_search(project_dir, args.query, args.top_k, json_output=args.json)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()


