# ADR-003: 프로젝트별 mem0 Setup 자동화
**Date**: 2026-04-01
**Status**: Accepted
**Participants**: Claude (Opus 4.6) vs Codex (gpt-5.4)
**Debate Style**: constructive
**Confidence**: 8/10

## Context
`setup_project_mem0.py`로 per-project mem0를 수동 설정 가능하나, `sync.py rebuild`를 매번 수동 실행해야 함. 자동화 필요.

## Decision
**MVP: manifest 기반 ensure + search auto-ensure**
1. `.mem0/manifest.json`에 파일 상태(mtime_ns, size) 기록
2. `sync.py ensure`: manifest vs 현재 docs 비교, 변경 시만 rebuild
3. `sync.py search`: 검색 전 자동 ensure (self-healing)
4. SessionStart에서 `.mem0/config.json` 존재 시 ensure 실행 (향후)

## Debate Summary
- Option A~F 비교: hooks, CLAUDE.md 지시, Makefile, inotify, git hook, hybrid
- Codex 추천: collaboration-wide startup reconcile 패턴 재사용
- 합의: manifest 기반 staleness > FAISS dir mtime (더 신뢰)
- search에서 auto-ensure → PostToolUse hook 불필요
- Per-project opt-in (.mem0/ 존재 여부로 판단)

## Explicitly NOT Doing
- Per-file incremental sync (chunk 수 적어서 full rebuild 충분)
- inotify/watchdog daemon
- PostToolUse hooks for doc edits
- SessionStart hook 연동 (향후 과제)

## Consequences
- **Positive**: rebuild 수동 실행 불필요, search가 항상 최신 데이터 반환
- **Positive**: 변경 없으면 ensure 즉시 완료 (stat() 비교만)
- **Negative**: 첫 search에서 rebuild 발생 시 지연 (~3-5초)
