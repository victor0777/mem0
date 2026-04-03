# ADR-004: 운영 모니터링 MVP
**Date**: 2026-04-01
**Status**: Accepted
**Participants**: Claude (Opus 4.6) vs Codex (gpt-5.4)
**Debate Style**: constructive
**Confidence**: 8/10

## Context
Batch reconcile, hybrid search 동적 가중치 등 구현 후 운영 상태를 모니터링할 수단이 없음.

## Decision
SQLite-first 관측성 레이어:
1. **reconcile_logs**: 실행별 1 row (trigger, timing, batch config, errors)
2. **search_logs 확장**: latency, count, top1_source, keyword/semantic errors, requested_mode
3. **check_system_health() MCP 도구**: reconcile/search/system 건강 JSON 출력
4. Markdown report는 기존 reports 프레임워크에 통합

## Explicitly NOT Doing (MVP)
- monitor_alerts 테이블 / 자동 create_request
- Search quality evaluator (replay queries)
- External monitoring (Prometheus/Grafana)
- Live dashboard UI

## Consequences
- **Positive**: 에이전트가 `check_system_health()`로 상태 자가 진단 가능
- **Positive**: search_logs로 가중치 효과, zero-result rate 추적 가능
- **Positive**: reconcile_logs로 gateway 안정성 추적 가능
- **Negative**: 수동 확인 필요 (자동 알림 없음)
