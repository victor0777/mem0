# ADR-002: Hybrid Search 동적 가중치 튜닝
**Date**: 2026-04-01
**Status**: Accepted
**Participants**: Claude (Opus 4.6) vs Codex (gpt-5.4)
**Debate Style**: constructive
**Confidence**: 8/10

## Context
Hybrid search가 semantic 0.6 + keyword 0.4 고정 가중치 사용. 쿼리 타입에 따라 최적 가중치가 다름 (ID 검색 vs 개념적 질문). Keyword 측은 LIKE + flat score 1.0으로 품질 신호 부족.

## Decision
1. **Heuristic query classifier**: exact/keyword/mixed/conceptual 4단계 분류 (regex + token count + 한/영 question markers)
2. **Dynamic weight profiles**: 쿼리 타입별 (semantic, keyword) 가중치 — 보수적 시작 (keyword side가 약하므로)
3. **Tiered keyword scoring**: flat 1.0 대신 5단계 매칭 품질 점수 (file exact 1.0 → partial 0.35)
4. **Mode parameter**: `mode="auto"` default + manual override
5. **Search logging**: knowledge.db에 best-effort 로깅 (query, mode, weights, result_count)

## Debate Summary

### Round 1 (Codex 초기 분석)
- Combination (heuristic + score-based) 추천
- Keyword side의 근본적 약점 지적: LIKE + flat score = 품질 신호 없음
- FTS5 선행 필요 주장
- Weight bands 제안: exact(0.85-0.95 kw) ~ conceptual(0.70-0.85 sem)

### Round 2 (Claude 반론)
- FTS5는 별도 backlog, 지금은 heuristic만으로도 개선 가능
- Concrete classifier 제안 (regex patterns + token count)
- Codex 수정: classifier 순서 버그 (conceptual check을 short-keyword보다 먼저)
- Korean particle 처리: `marker in q_low` (substring match)
- Weight 보수적 조정 합의 (keyword side 약하므로)

### Round 3 (구현 확정)
- Keyword tiered scoring 합의 (5단계, keywords JSON 파싱 필요)
- Search log → knowledge.db (별도 테이블, rebuild와 독립)
- Logging에 실제 weight pair 포함
- 한 PR 범위: classifier + scorer + weights + mode + logging

## Action Items
- [x] _classify_query() 구현
- [x] _score_keyword_result() 구현
- [x] hybrid_search_knowledge() 수정
- [x] search_logs 테이블 + logging
- [ ] 검증 테스트

## Explicitly NOT Doing
- FTS5 migration (별도 backlog)
- Click/interaction tracking
- Knowledge DB schema 재설계
- LLM-based query classification

## Consequences
- **Positive**: ID 검색 시 keyword 우선, 개념 질문 시 semantic 우선
- **Positive**: Keyword 품질 신호 개선 (5단계 scoring)
- **Positive**: Search log로 향후 데이터 기반 튜닝 가능
- **Negative**: Heuristic은 edge case에 취약 (특히 짧은 Korean queries)
- **Negative**: LIKE 기반이므로 keyword 정밀도 한계 존재
