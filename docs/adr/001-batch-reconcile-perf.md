# ADR-001: Batch Reconcile 성능 개선
**Date**: 2026-04-01
**Status**: Accepted
**Participants**: Claude (Opus 4.6) vs Codex (gpt-5.4)
**Debate Style**: constructive
**Confidence**: 7/10

## Context
mem0 sync의 full reconcile이 117 chunks / 239초 소요. 병목은 LiteLLM gateway embedding API 호출 시간 (~40s/batch of 20). 순차 처리로 6 batches x 40s = 240s. 목표: 60초 이내.

## Decision
1. **BATCH_SIZE 20 -> 40**: gateway 오버헤드가 per-request 위주이므로 배치 크기 증가로 호출 횟수 감소 (6회 -> 3회)
2. **ThreadPoolExecutor(max_workers=3)**: embedding 단계만 병렬화, FAISS/history/sync 쓰기는 직렬 유지
3. **Fallback 40 -> 20**: 큰 배치 실패 시 20씩 고정 분할 재시도, 부분 성공 보존
4. **Configurable params**: 모듈 상수 + reconcile() 파라미터 오버라이드 (벤치마크용)
5. **Timing logs**: 배치별 소요시간, embed/write 단계별 총합, 성공/실패 chunk 수

## Debate Summary

### Round 1 (Codex 초기 분석)
- Concurrency + modest batch increase (20->32) 제안
- Concurrency만으로 <30s 달성 어려움 지적 (gateway 40s/req 기준)
- Embedding cache 제안

### Round 2 (Claude 반론)
- Batch size 40으로 더 공격적 제안 (token limit 충분: 40 x 350tok = 14000)
- Gateway 오버헤드가 per-request 위주라는 가설
- Cache는 skip (sync table이 이미 중복 방지)
- ThreadPoolExecutor > AsyncIO (simpler, less refactor)

### Round 3 (합의)
- Codex 동의: 40이 defensible, cache skip OK, ThreadPool OK
- Codex 추가 제안: adaptive fallback (40->20 분할), 벤치마크 매트릭스
- 공유 OpenAI client thread-safety: httpx 기반으로 OK, Memory/FAISS는 메인 스레드만
- Memory warm-up 필수 (lazy-init 레이스 방지)
- workers = min(max_workers, len(batches))

### 핵심 리스크 (합의)
- Gateway 내부 직렬화 시 concurrency 효과 제한적 -> 벤치마크로 확인
- Batch size 증가 시 failure blast radius 증가 -> fallback으로 완화
- Changed-chunk path는 여전히 sequential -> 현재는 rare이므로 후순위

## Action Items
- [x] mem0_sync.py 수정: concurrent embed + batch 40 + fallback
- [ ] 벤치마크 매트릭스: 20x3, 40x3, 40x4
- [ ] 결과에 따라 DEFAULT 값 확정

## Explicitly NOT Doing
- AsyncIO 전면 리팩토링 (ThreadPool로 충분)
- Embedding cache (sync table이 이미 중복 방지)
- Changed-chunk 병렬화 (rare case이므로 후순위)
- Gateway 자체 최적화 (shared infra, 범위 밖)

## Consequences
- **Positive**: 4-8x 성능 향상 예상 (45-90s)
- **Positive**: 벤치마크 인프라로 향후 튜닝 용이
- **Negative**: 코드 복잡도 증가 (ThreadPoolExecutor, fallback 로직)
- **Negative**: Gateway 병렬 처리 여부에 성능이 의존
