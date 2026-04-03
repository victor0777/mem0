# ADR-006: Cross-Project Knowledge 통합 검색
**Date**: 2026-04-02
**Status**: Accepted
**Participants**: Claude vs Codex (gpt-5.4)
**Debate Style**: constructive (2 rounds: architecture + embedding unification)
**Confidence**: 8/10

## Context

18개 프로젝트의 knowledge가 2개 독립 레이어로 분산. 통합 검색 불가, cross-project ADR/diary/guide가 검색 사각지대.

## Decision

### Architecture: A-lite + B-lite Hybrid

**"One search API, two retrieval layers, explicit authority by source"**

| 레이어 | 역할 | Embedding | 검색 도구 |
|--------|------|-----------|-----------|
| Collaboration-wide | cross-project discovery | bge-m3 (1024d, gateway) | `semantic_search_knowledge()` |
| Per-project .mem0 | local freshness + offline | bge-small-en-v1.5 (384d, local) | `sync.py search` |
| **unified_search()** | **통합 인터페이스** | **양쪽 동시 검색** | **MCP tool** |

### Embedding: Phase 1은 분리 유지

다른 embedding space → score 비교 불가 → 섹션 분리 반환.
Phase 2에서 `multilingual-e5-large` (FastEmbed) 또는 `bge-m3` (HuggingFace) 로컬 통합 검토 예정.

## unified_search() Spec

```
Parameters: query, scope (auto|local|cross|all), project, doc_types, limit
Output: {sections: {current_project, cross_project, cached_imported}, degraded_mode, meta}
```

### Scope Resolution (auto)
- 다른 프로젝트명, "compare", "across", "upstream" 포함 → all
- 기본값 → all

### Authority Rules
- 현재 프로젝트 docs: local authoritative
- 다른 프로젝트 docs: collaboration authoritative
- imported cache: collaboration 불가 시만 사용

### Degraded Mode
- Gateway 불가 시: cross_project=[], cached_imported 사용, degraded_mode=true

## Collaboration Chunker 확장

`_chunk_project_docs()`: `TARGET_DOCS` 4개 → `docs/**/*.md` 전체 (README, templates, archive 제외)

| Before | After |
|--------|-------|
| 495 chunks | **2081 chunks** |
| findings, lessons, roadmap, backlog only | **+ ADR, diary, guide, 모든 .md** |

## Debate Summary

### Round 1: Architecture
- Option A (collaboration only) 위험: gateway SPOF, reconcile 시간 폭증
- Option C (per-project 제거) 위험: offline 불가
- **A-lite + B-lite 합의**: 두 레이어 유지, unified API로 통합

### Round 2: Embedding Unification
- Phase 1: 분리 유지 (ADR-005 안정화 우선)
- Phase 2: `multilingual-e5-large` vs `bge-m3` 벤치마크 후 결정
- GPU 활용 가능 (par02 RTX 4090), 모델 캐시 호스트당 1회

## Action Items
- [x] Collaboration chunker 확장 (docs/**/*.md, 495→2081 chunks)
- [x] sync.py --json 출력 추가 + 18개 프로젝트 재배포
- [x] unified_search() MCP 도구 구현
- [ ] Collaboration reconcile 실행 (2081 chunks 인덱싱)
- [ ] Embedding 벤치마크 (Phase 2)

## Explicitly NOT Doing
- Score normalization across embedding spaces
- FAISS sharding (2081 chunks는 단일 인덱스로 충분)
- Federated search (D option rejected)
- 다른 서버 배포 (테스트 후 진행)

## Consequences
- 모든 프로젝트의 docs가 cross-project 검색 가능 (ADR, diary, guide 포함)
- unified_search()로 단일 검색 인터페이스 제공
- 두 embedding space 공존 → 섹션 분리로 혼란 방지
- Gateway 불가 시에도 로컬 + cached imported로 검색 가능
