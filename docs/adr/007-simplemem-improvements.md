# ADR-007: Omni-SimpleMem 기반 Knowledge Search 개선
**Date**: 2026-04-04
**Status**: Accepted
**Source**: arXiv:2604.01007 (Omni-SimpleMem) 코드 리뷰 + 논문 분석
**Confidence**: 7/10

## Context

현재 knowledge search의 성능을 정량적으로 평가할 수 있는 eval framework가 구축됨 (golden test 8개, search_logs.db).
Omni-SimpleMem 논문의 아이디어를 검토하여 높은 ROI의 개선을 적용하고, AutoResearchClaw의 자동 실험 루프를
우리 eval framework 위에 적용하여 체계적 개선을 시도.

## Decision

### Phase 1: 높은 ROI 개선 (즉시 적용)

#### 1. Chunk Dedup (Jaccard Similarity)
- **방법**: 같은 파일 내 chunk 간 Jaccard similarity > 0.8이면 중복으로 판단, 하나만 인덱싱
- **적용 위치**: `sync.py collect_chunks()` + `collab/chunker.py chunk_file()`
- **기대 효과**: 검색 결과에서 같은 문서의 유사 chunk가 여러 개 나오는 문제 해결
- **SimpleMem 참고**: `text_processor.py` Jaccard threshold 0.8

#### 2. Rich Result Formatting
- **방법**: search 결과에 project, date, keywords, doc_type을 구조화하여 포함
- **적용 위치**: `unified_search()` output format, `sync.py --json` output
- **기대 효과**: SimpleMem에서 format_for_llm 개선만으로 +188% 향상 사례
- **핵심**: snippet만 반환하지 않고, 메타데이터를 함께 반환하여 LLM이 컨텍스트를 더 잘 이해

#### 3. Importance Decay
- **방법**: score에 recency 가중치 적용: `adjusted_score = score * 0.95^(days_since_update)`
- **적용 위치**: `unified_search()` result 정렬 시
- **기대 효과**: 오래된 문서보다 최신 문서 우선 노출

### Phase 2: AutoResearch-style 자동 개선 루프

AutoResearchClaw의 핵심 패턴을 우리 eval framework에 적용:

```
diagnose (golden test 분석)
  → hypothesize (개선 가설 생성)
  → implement (코드 변경)
  → evaluate (golden test 재실행)
  → decide (PROCEED ≥0.5% / ITERATE / PIVOT)
```

**구현**: `scripts/auto_improve.py`
- Golden test 결과에서 실패 패턴 분석
- 개선 가설 자동 생성 (chunking 전략, formatting, scoring 등)
- 변경 적용 → golden test 재실행 → 결과 비교
- PROCEED/ITERATE/PIVOT 결정 + 로깅

## Ablation Reference (SimpleMem)

| Component | Impact | 우리 적용 여부 |
|-----------|--------|--------------|
| Pyramid Expansion (-17%) | 높음 | Phase 2 (중기) |
| BM25 Hybrid (-14%) | 높음 | 이미 collaboration에 FTS5 있음 |
| LLM Summarization (-12%) | 중간 | 불필요 (문서가 이미 구조화) |
| Top-k 20 vs 5 (-7%) | 중간 | 현재 top-k=10, 적절 |
| Metadata Context (-2%) | 낮음 | Rich formatting으로 대응 |

## Explicitly NOT Doing
- CLIP/VAD 멀티모달 필터링 (텍스트 전용)
- Knowledge Graph (project-registry로 충분, ADR-007 이전 결론)
- Hot/Cold storage 분리 (chunk 크기 작음)
- LLM-based fact extraction (infer=False 유지)
- Score normalization across embedding spaces (섹션 분리 유지)

## Verification
- Golden test pass rate 변화 추적
- 변경 전후 backtest diff
- search_logs.db에서 운영 지표 모니터링
