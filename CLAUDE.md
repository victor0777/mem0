# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Mem0 (`mem0ai` on PyPI) is a memory layer for AI agents/assistants. It provides long-term memory with add/search/update/delete operations, backed by pluggable vector stores, LLMs, embedding providers, graph databases, and rerankers.

## Build & Development Commands

```bash
# Environment setup (uses hatch)
hatch env create                 # Create default env
hatch shell dev_py_3_11          # Activate dev environment (3.9/3.10/3.11/3.12)
pre-commit install               # Install pre-commit hooks (ruff + isort)

# Testing
make test                        # Run tests (default Python)
make test-py-3.11                # Run tests for specific Python version
pytest tests/test_main.py -v     # Run a single test file
pytest tests/test_main.py::TestClassName::test_method -v  # Single test

# Code quality (all go through hatch)
make format                      # Format with ruff
make sort                        # Sort imports with isort
make lint                        # Lint with ruff

# Build & publish
make build                       # Build package (hatchling)
make publish                     # Publish to PyPI
```

## Architecture

### Core Memory Flow

The `add()` operation in `Memory` (mem0/memory/main.py) follows this pipeline:
1. Parse input messages → extract text/vision content
2. Call LLM to extract structured "facts" from the conversation
3. For each fact: embed it, search vector store for similar existing memories
4. Call LLM again to decide: ADD new memory, UPDATE existing, DELETE obsolete, or NOOP
5. Execute the decided actions against vector store (and optionally graph store)
6. Record all changes in SQLite history (mem0/memory/storage.py)

`search()` embeds the query, retrieves from vector store (and optionally graph store), then optionally reranks results.

### Factory Pattern (`mem0/utils/factory.py`)

All pluggable components use factory classes with provider name → class mappings:
- **`LlmFactory`** — 20+ providers (openai, anthropic, groq, together, litellm, ollama, gemini, deepseek, xai, etc.)
- **`EmbedderFactory`** — 14+ providers (openai, huggingface, ollama, fastembed, gemini, etc.)
- **`VectorStoreFactory`** — 28+ stores (qdrant, chroma, pinecone, pgvector, milvus, redis, mongodb, elasticsearch, etc.)
- **`GraphStoreFactory`** — Neo4j, Memgraph, Kuzu, Apache AGE, Neptune
- **`RerankerFactory`** — Multiple reranker implementations

Each factory dynamically imports provider modules via `load_class()`. When adding a new provider, you need: a provider module (e.g., `mem0/llms/newprovider.py`), a config class (in `mem0/configs/llms/configs.py`), and a factory mapping entry.

### Configuration (`mem0/configs/`)

- **`base.py`** — `MemoryConfig` pydantic model that nests provider-specific configs.
- **`prompts.py`** — System prompts for memory extraction, update, and retrieval. These prompts drive the LLM's fact extraction and deduplication logic.
- Subdirectories (`llms/`, `embeddings/`, `vector_stores/`, `graphs/`, `rerankers/`) contain per-provider config models.

### Client (`mem0/client/`)

HTTP client for the hosted Mem0 cloud platform. `MemoryClient` / `AsyncMemoryClient` use API key auth (`MEM0_API_KEY` env var) against `https://api.mem0.ai`.

### Proxy (`mem0/proxy/`)

OpenAI-compatible proxy that intercepts chat completion calls and automatically adds memory context. Wraps the OpenAI client to transparently enhance conversations with relevant memories.

### Server (`server/`)

FastAPI self-hosted deployment. Docker support via `docker-compose.yaml`.

### TypeScript SDK (`mem0-ts/`)

Separate npm package `mem0ai`. Built with tsup. Has its own test suite (Jest).

## Key Conventions

- **Python**: 3.9–3.12. Line length 120. Ruff for linting/formatting, isort with black profile.
- **Pre-commit hooks**: ruff check (with --fix) and isort run automatically on commit.
- **Excluded directories**: `embedchain/` and `openmemory/` are excluded from ruff and are legacy/separate projects within this repo.
- **Testing**: pytest with pytest-mock and pytest-asyncio. Tests mirror source structure under `tests/`.
- **Dependencies**: Core deps are minimal (qdrant-client, pydantic, openai, posthog, sqlalchemy). Provider-specific deps are in optional extras (`[graph]`, `[vector_stores]`, `[llms]`, `[extras]`).
- **Async**: Most core classes have sync and async variants (e.g., `Memory`/`AsyncMemory`, `MemoryClient`/`AsyncMemoryClient`).

## Git Repository

- **Origin**: https://github.com/mem0ai/mem0.git (upstream open-source project)
