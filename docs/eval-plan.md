# Knowledge Search 성능 평가 계획

## 1. Verification Criteria

### 1.1 Search Quality Metrics

| Metric | 정의 | 목표 | 측정 방법 |
|--------|------|------|-----------|
| **Pass Rate** | Golden test 통과율 | ≥ 80% | `eval_search.py golden` |
| **Precision@10** | 반환된 top-10 중 관련 문서 비율 | ≥ 0.3 | 수동 annotation + 자동 계산 |
| **Recall** | 기대 문서 중 실제 반환된 비율 | ≥ 0.7 | Golden test expected_docs 매칭 |
| **MRR** | 첫 관련 결과의 역순위 평균 | ≥ 0.5 | Annotation 기반 |
| **Empty Rate** | 결과 0건 비율 | ≤ 10% | 운영 로그 통계 |

### 1.2 Operational Metrics

| Metric | 정의 | 목표 | 측정 방법 |
|--------|------|------|-----------|
| **Latency (P50)** | 검색 응답 시간 중앙값 | ≤ 5초 | 운영 로그 |
| **Latency (P95)** | 검색 응답 시간 95백분위 | ≤ 15초 | 운영 로그 |
| **Degraded Mode Rate** | Gateway 불가로 degraded 비율 | ≤ 20% | 운영 로그 |
| **Error Rate** | 검색 실패 비율 | ≤ 5% | 운영 로그 |

### 1.3 Coverage Metrics

| Metric | 정의 | 목표 | 측정 방법 |
|--------|------|------|-----------|
| **Indexed Projects** | 인덱싱된 프로젝트 수 | 18/18 | chunker stats |
| **Total Chunks** | collaboration-wide chunks | ≥ 2000 | reconcile 후 확인 |
| **Per-Project Chunks** | 프로젝트별 평균 chunks | ≥ 30 | manifest.json 집계 |
| **Freshness (Local)** | 로컬 인덱스 최신성 | ≤ 24h | manifest synced_at |
| **Freshness (Imported)** | imported cache 최신성 | ≤ 6h (TTL) | state.json |

## 2. 평가 인프라

### 2.1 Search Logger (`collab/search_logger.py`)

모든 `unified_search()` 호출을 SQLite에 자동 기록:

```
data/search_logs.db
├── search_queries      # 쿼리, scope, latency, result counts
├── search_results      # 개별 결과 (doc_id, score, snippet)
└── relevance_judgments  # 수동 relevance annotation (0-3)
```

Relevance scale:
- 0 = 무관 (completely irrelevant)
- 1 = 부분적 (partially relevant, tangential)
- 2 = 관련 (relevant, addresses the query)
- 3 = 완벽 (perfect match, directly answers)

### 2.2 Golden Test Set (`scripts/eval_search.py`)

8개 predefined test cases:

| ID | 쿼리 | 프로젝트 | Scope | 검증 포인트 |
|----|------|----------|-------|-------------|
| G001 | embedding latency spike bge-m3 | mem0 | all | TEI findings + ADR-001 매칭 |
| G002 | REQ-20260402-002 AAP scale down | mem0 | all | 특정 request ID 검색 |
| G003 | camera calibration pipeline | mem0 | cross | cross-project 결과 존재 |
| G004 | batch reconcile 성능 개선 | mem0 | local | ADR-001 로컬 검색 |
| G005 | panoptic segmentation inference | mem0 | cross | perception 프로젝트 매칭 |
| G006 | Hybrid search 동적 가중치 | mem0 | local | 한국어 검색 + ADR-002 |
| G007 | vehicle tracker BEV replay | map | cross | vehicle-tracker 결과 |
| G008 | upstream downstream dependency | perception | all | scope auto→all 해석 |

### 2.3 Backtesting

운영 중 수집된 실제 쿼리를 새 설정으로 재실행:
```bash
python scripts/eval_search.py backtest --limit 50
```

비교 항목:
- 결과 변화 (added/removed/unchanged)
- latency 변화
- 새로운 empty results 발생 여부

## 3. 평가 실행 방법

### 3.1 정기 평가 (권장: 주 1회)

```bash
cd ~/projects/collaboration
python scripts/eval_search.py report
```

출력: golden test + operational stats 통합 리포트
저장: `data/eval/golden-{timestamp}.json`

### 3.2 설정 변경 후 평가

Embedding 모델 변경, chunker 수정 등 후:
1. `python scripts/eval_search.py golden` — golden test 재실행
2. `python scripts/eval_search.py backtest` — 기존 쿼리 재실행, diff 확인
3. 이전 결과와 비교: `data/eval/golden-*.json`

### 3.3 수동 Annotation

운영 중 검색 결과의 품질을 수동으로 평가:
```bash
python scripts/eval_search.py annotate <query_id>
```

축적된 annotation으로 precision/recall 정밀 측정 가능.

## 4. Baseline (2026-04-02)

| Metric | 값 | 비고 |
|--------|-----|------|
| Golden Pass Rate | 62.5% (5/8) | Gateway 불안정으로 3건 degraded |
| Avg Latency | 48,282ms | Gateway 500 에러 + reconcile 포함 |
| Total Chunks (collaboration) | 2081 | chunker 확장 후 (reconcile 미완) |
| Per-Project Chunks (mem0) | 76 | 50 local + 26 imported |

**주의**: baseline은 gateway 불안정 상태에서 측정됨. 안정 시 재측정 필요.

## 5. 개선 시 평가 포인트

### Embedding 모델 변경 시
- Golden test 전후 비교 (pass rate, recall)
- 한국어 쿼리 (G006) 특히 주목
- Backtest diff: 기존 쿼리 결과 변화 확인
- Latency 변화 (bge-m3 local은 느릴 수 있음)

### Chunker 변경 시
- Coverage: 새 doc_type 추가 → 관련 golden test 추가
- Chunk 수 변화 확인
- 기존 검색 결과가 사라지지 않는지 backtest

### 인프라 변경 시 (TEI pod, gateway)
- Degraded mode rate 변화
- Latency P50/P95 변화
- Error rate 변화
