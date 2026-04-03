# ADR-005: Per-Project mem0 데이터 소스 범위 및 주기적 동기화
**Date**: 2026-04-02
**Status**: Accepted
**Participants**: Claude vs Codex (gpt-5.4)
**Debate Style**: constructive
**Confidence**: 8/10

## Context

Per-project mem0 knowledge base가 로컬 `docs/` 디렉토리만 인덱싱하여 대부분 10-20 chunks 수준으로 검색 품질이 낮음. 17개 프로젝트에 `.mem0/`가 설정되어 있지만 대부분 stale 또는 비어있음. Cross-project 검색은 collaboration-wide layer (495 chunks)에서만 가능하지만 gateway 의존성이 있어 불안정.

## Decision

**Option A+**: 로컬 docs + collaboration에서 프로젝트 관련 데이터를 bounded subset으로 import.

핵심 원칙: imported context는 **read-only materialized cache** (collaboration이 source of truth).

### Source Inclusion Rules

- **Local**: `docs/**/*.md` 전체 (README.md 제외)
- **Imported** (collaboration MCP `export_project_context()`):
  - Requests: from/to this project (open 전부 + closed 90일)
  - Self reports: 최근 20건
  - Upstream/downstream dependency reports: dependency별 최근 5건 (90일)
  - Tagged insights: 최근 10건 (90일)
- **Not imported**: 다른 프로젝트의 ADR, diaries, backlog, roadmap, 일반 mentions

### File Layout

```
.mem0/
  config.json
  manifest.json
  faiss_index/
  imported/
    state.json                     # TTL, synced_at, dependencies
    requests/REQ-*.md + .json      # metadata sidecar
    reports/self/*.md + .json
    reports/upstream/{project}/*.md + .json
    reports/downstream/{project}/*.md + .json
    insights/*.md + .json
```

### Refresh Triggers

- **SessionStart hook**: imported cache가 6h(TTL) 이상이면 refresh
- **Search-time**: auto-ensure local docs + imported TTL 체크
- **Cron/dual-write**: MVP에서 불필요

### Failure Modes

- MCP/gateway 불가: 기존 imported cache 계속 사용 (stale 표시)
- Imported cache 없음: local docs만으로 검색 (degraded mode)
- Atomic write: temp dir → rename 패턴으로 partial write 방지

## Debate Summary

| 옵션 | 판정 | 이유 |
|------|------|------|
| A: Local docs only | 부족 | 10-20 chunks로 검색 품질 낮음 |
| B: Local + 전체 cross-project | 과다 | 데이터 중복, freshness 관리 복잡 |
| C: Per-project 제거 | 위험 | Gateway 불안정 시 검색 불가 |
| D: 모든 .md 인덱싱 | 노이즈 | CLAUDE.md, config 등 불필요한 데이터 |
| **A+: Local + bounded import** | **채택** | **적절한 corpus + 관련성 높은 cross-project context** |

Codex 핵심 주장: duplication은 "materialized view"로 관리하면 acceptable. 단 freshness를 2-model로 분리 (local: manifest, imported: TTL).

Claude 핵심 주장: federated search 없이 통합 인덱스로 단순화. Imported는 first-order relevance만 (direct dependency).

## Action Items

- [x] `export_project_context()` collaboration MCP 도구 추가
- [x] `sync.py` 확장 (imported layer + TTL + unified indexing)
- [ ] `setup_project_mem0.py` 업데이트 (새 sync.py 템플릿)
- [ ] SessionStart hook 연동
- [ ] 전체 프로젝트 배포

## Explicitly NOT Doing

- 별도 federated search orchestration layer
- Graph store 활용 (metadata relationship으로 충분)
- LLM-based fact extraction (문서가 이미 구조화됨)
- Cron 기반 주기적 sync (TTL + auto-ensure로 충분)
- 다른 프로젝트의 ADR/diary/backlog import (noise)

## Consequences

- 프로젝트당 corpus: 10-20 → 30-80+ chunks (검색 품질 향상)
- Gateway 불가 시에도 cached imported data로 검색 가능 (resilience)
- Maintenance: sync.py 하나로 local + imported 모두 관리
- 데이터 중복 존재하나 bounded & read-only cache로 관리 가능
