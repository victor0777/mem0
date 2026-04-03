# mem0 Findings

## 2026-04-04: Omni-SimpleMem 논문 분석 및 우리 시스템 적용 가능성
**맥락**: knowledge search 성능 개선을 위해 Omni-SimpleMem (arXiv:2604.01007) 논문 및 코드 리뷰
**발견**:

### 논문 핵심
- AutoResearchClaw가 ~50 실험을 72시간 동안 자율적으로 수행하여 Omni-SimpleMem 발견
- LoCoMo F1: 0.117→0.598 (+411%), Mem-Gallery F1: 0.254→0.797 (+214%)
- 가장 큰 개선: bug fix (+175%) > prompt engineering (+188% on specific categories) > architecture (+44%) > hyperparameter tuning

### AutoResearchClaw 파이프라인 (23 stages, 8 phases)
1. Research Scoping → SMART 목표 수립
2. Literature Discovery → OpenAlex/arXiv 탐색
3. Knowledge Synthesis → multi-agent debate로 가설 생성
4. Experiment Design → hardware-aware Python code + AST validation
5. Experiment Execution → sandbox에서 실행, self-healing (10 retries)
6. Analysis & Decision → 통계 분석, PROCEED(≥0.5% 개선)/ITERATE(모호)/PIVOT(2연속 악화)
7. Documentation → 자동 논문 작성
8. Finalization → quality gate + citation verification

### Ablation 결과 (LoCoMo, 4 backbone 평균)
| Component Removed | ΔF1 | Relative |
|---|---|---|
| w/o Pyramid Expansion | -10.2 | -17% |
| w/o BM25 Hybrid | -8.5 | -14% |
| w/o LLM Summarization | -7.3 | -12% |
| Reduced top-k (5 vs 20) | -4.2 | -7% |
| w/o Metadata Context | -1.4 | -2% |

### 우리 시스템에 적용 가능한 개선 (코드 리뷰 기반)

**즉시 적용 (높은 ROI)**:
1. **Chunk dedup** (Jaccard 0.8): 유사 chunk 필터링으로 검색 결과 오염 방지
2. **Rich formatting**: search 결과에 project, date, keywords, full context 포함 (+188% 효과의 핵심)
3. **Set-union hybrid**: FAISS 순서 유지 + BM25 보충 (우리 unified_search 섹션 분리와 유사)
4. **Importance decay**: 0.95^days × access_freq로 최신 정보 우선

**중기 적용**:
5. **Pyramid expansion**: summary→detail→original 3단계 검색
6. **Per-project BM25**: FTS5 인덱스 추가

**적용 불필요**:
- CLIP/VAD 필터링 (텍스트 전용)
- Knowledge Graph (project-registry로 충분)
- Cold storage (chunk 크기 작음)
- Consolidation cycle (문서 기반, 대화 기반 아님)

### AutoResearch 접근법 우리 시스템 적용
- 우리는 이미 eval framework (golden test 8개 + search_logs.db)를 구축함
- AutoResearchClaw의 PROCEED/ITERATE/PIVOT 결정 로직을 적용 가능:
  - PROCEED: golden test pass rate ≥ 0.5% 개선
  - ITERATE: 결과 모호 → 가설 수정
  - PIVOT: 2연속 악화 → revert + 새 방향
**영향**: chunk dedup과 rich formatting은 즉시 구현 가능. AutoResearch 루프는 eval framework 위에 자동화 가능.

## 2026-04-03: TEI bge-m3 pod OOMKilled 근본 원인 확인
**맥락**: reconcile 실행 시 gateway 500 에러 반복 발생, 원인 조사
**발견**:
- TEI pod가 19시간 동안 9회 OOMKilled (Exit Code 137)
- Memory limit 8Gi에서 bge-m3 모델(CPU mode) + batch=32 처리 시 메모리 부족
- 이전에 AAP CPU 경합으로 추정했던 latency spike의 진짜 원인은 OOM → pod restart → cold start 사이클
- phoenix-ktl-01 전체 메모리는 5%만 사용 중 — limit만 늘리면 해결
- agents에 memory limit 8Gi→16Gi 증설 요청 (REQ-20260403-002)
**영향**: reconcile 완료 불가, unified_search cross-project 검색 제한적. memory 증설 전까지 단일 요청은 가능하나 batch 처리 불안정.

## 2026-04-02: AAP 스택 scale down 후 phoenix-ktl-01 리소스 개선
**맥락**: REQ-20260402-002 요청 후 agents에서 AAP scale down 처리
**발견**: CPU limit 79.1 cores (61%) → 14.7 cores (11%), memory limit 75.8Gi → 20.6Gi. TEI bge-m3 경합 리스크 해소됨.
**영향**: embedding endpoint 안정성 대폭 향상. latency spike 재발 가능성 크게 감소

## 2026-04-02: phoenix-ktl-01 CPU limit 61%의 원인
**맥락**: TEI embedding latency spike 근본 원인 추적
**발견**:
- phoenix-ktl-01에서 CPU limit 합계 79.1 cores (61%) — 대부분 AAP 서비스 스택이 차지
- Top 소비자: `aap-db-postgresql` 단독 16 cores limit (20%), PostgreSQL DB 3개 합계 24 cores
- AAP 웹 UI/API pod ~20개가 limit 합계 ~70 cores 점유
- TEI bge-m3는 4 cores limit (5%)으로 소규모이나, AAP DB burst 시 CPU 경합 발생 가능
- phoenix-ktl-01은 NFS 스토리지 서버 역할도 겸하고 있어 I/O + CPU 이중 부하
**영향**: 이전 embedding latency spike(5-40초)의 근본 원인은 AAP DB burst와의 CPU 경합일 가능성이 높음. 장기 대책으로 TEI를 전용 노드로 이전하거나 AAP 스택과 분리 필요

## 2026-04-02: TEI bge-m3 인프라 현황 점검
**맥락**: embedding 모델 업그레이드 전 인프라 안정성 검토
**발견**:
- TEI pod는 **CPU-only** 이미지(`cpu-1.6`)로 phoenix-ktl-01(NFS 서버)에서 실행 중
- phoenix-ktl-01 CPU limit 61% 할당 — TEI(2-4 CPU)가 다른 pod burst와 경합 가능
- 부하 테스트: sequential 0.42-0.48s, concurrent 5 batch=10에서 최대 1.55s, 500 에러 없음
- 이전 보고된 5-40초 spike 및 500 에러는 현시점 재현 불가
- super-ktl-01: 13일간 SchedulingDisabled → 현재 Ready, GPU 2x RTX 5000 복구됨
**영향**: embedding endpoint 현재 안정. 단 NFS I/O burst 시 재발 가능성 존재하므로 장기적으로 TEI GPU 이전 또는 Guaranteed QoS 적용 권장

## 2026-04-02: mem0 아키텍처 분석
**맥락**: 프로젝트 초기 분석 및 collaboration 통합 검토
**발견**: mem0의 core memory flow는 LLM 기반 fact extraction → embedding → vector store 검색 → LLM 기반 dedup 판단 (ADD/UPDATE/DELETE/NOOP) 파이프라인. EmbedderFactory에서 14+ embedding provider 지원 (openai, huggingface, ollama, fastembed, gemini 등).
**영향**: collaboration MCP semantic search의 embedding 품질 개선에 mem0의 다양한 embedding provider를 활용할 수 있음

## 2026-04-01: LiteLLM Gateway 배치 및 동시성 제한 발견
**맥락**: Batch reconcile 성능 개선 작업 중 batch_size/concurrency 벤치마크
**발견**:
- LiteLLM gateway(192.168.0.199)의 embedding API 배치 제한: **최대 32 inputs**
- 32 초과 시 413 에러: `batch size N > maximum allowed batch size 32`
- 동시 2-3개 embedding 요청 시 500 Connection error 빈발 (gateway 과부하)
- 동시 1개(순차)에서도 간헐적 500 에러 발생 — gateway 자체 불안정성
- Fallback 로직 (32→16 분할)이 정상 작동하여 데이터 손실 방지 확인
- Write phase (FAISS insert + history)는 무시할 수준 (0.1s / 117 chunks)
**영향**: DEFAULT_BATCH_SIZE=32, DEFAULT_MAX_WORKERS=1(보수적). Gateway 안정화 후 workers=2 재시도 필요.

## 2026-04-01: Hybrid Search Runtime 검증에서 LIKE 한계 발견
**맥락**: 동적 가중치 구현 후 end-to-end 검증
**발견**:
- multi-word LIKE 쿼리는 연속 문자열만 매칭 (`%perception pipeline%` → 실패)
- 해결: 토큰별 AND LIKE 분할로 multi-word 검색 가능하게 개선
- `requests` 테이블의 `request_id` 컬럼, `documents` 테이블의 `frontmatter` JSON도 검색 대상에 추가
- 실존하는 REQ ID (`REQ-2026-0313-002`)가 exact mode로 1위에 정확히 매칭됨 확인
**영향**: keyword 검색 커버리지 대폭 개선. FTS5는 여전히 장기 과제.

## 2026-04-01: LiteLLM Gateway 지연 근본 원인 발견
**맥락**: gateway 느린 원인 진단 (단일 embed 15-54초)
**발견**:
- `text-embedding-3-large` 요청은 실제로 **bge-m3** 모델로 라우팅됨 (OpenAI가 아님)
- Backend: `tei-bge-m3.llm-serving.svc.cluster.local:8080` (K8s TEI 서비스)
- Warm 상태에서 **0.1-0.3초** (매우 빠름), 하지만 **간헐적 5-40초 지연** 발생
- Cold start가 아님 (5초 pause 후에도 0.08초). 연속 호출 중에도 갑자기 느려짐
- 원인 추정: K8s TEI pod 리소스 경합, GPU 메모리 pressure, 또는 pod rescheduling
- LiteLLM gateway의 max batch size 32 제한은 gateway config, 모델 자체 제한 아님
**영향**: reconcile 성능은 gateway 안정성에 100% 의존. 코드 최적화보다 인프라 안정화가 우선.
