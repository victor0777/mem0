# mem0 활용 가이드

mem0ai 라이브러리의 전체 역량과 우리 프로젝트 생태계에서의 활용 현황 및 확장 방안.

---

## 1. 현재 활용 중인 기능

### 1.1 Collaboration-Wide Semantic Search
- **용도**: reports, requests, insights 문서에 대한 의미 기반 cross-project 검색
- **구성**: FAISS + text-embedding-3-large (LiteLLM Gateway) + infer=False
- **도구**: `semantic_search_knowledge()`, `hybrid_search_knowledge()`
- **동기화**: dual-write hook + startup reconcile + 6h 자동화 cycle
- **데이터**: ~495 chunks (reports, requests, insights, diaries, ADR, CHANGELOG, findings, lessons), 단일 namespace `user_id="collaboration-kb"`

### 1.2 Hybrid Search (동적 가중치)
- **용도**: 쿼리 타입에 따라 semantic/keyword 가중치 자동 조정
- **분류**: exact (ID) / keyword (짧은) / mixed / conceptual (질문)
- **keyword 품질**: 5단계 tiered scoring (file exact 1.0 → partial 0.35)
- **ADR**: 002-hybrid-search-weights

### 1.3 Agent Memory (remember/recall)
- **용도**: 에이전트의 선호, 결정, 패턴, 맥락을 세션 간 저장
- **구성**: 별도 namespace `user_id="agent-memory"`, metadata로 category/project/tags
- **가이드**: shared-conventions.md §12

### 1.4 Per-Project Local Search
- **용도**: 개별 프로젝트의 findings, lessons, diaries 로컬 검색
- **구성**: FastEmbed (BAAI/bge-small-en-v1.5) + FAISS, 외부 API 의존 없음
- **자동화**: manifest 기반 ensure, search 시 auto-rebuild
- **설정**: `setup_project_mem0.py` → `.mem0/sync.py`

### 1.5 운영 모니터링
- **reconcile_logs**: 실행별 timing, batch config, gateway errors
- **search_logs**: latency, mode, count, errors, top1_source
- **check_system_health()**: 24h 윈도우 건강 상태 JSON

---

## 2. 활용 가능하나 아직 미사용인 기능

### 2.1 Graph Memory (높은 활용 가치)
- **기능**: 텍스트에서 엔티티(entity)와 관계(relation)를 자동 추출하여 지식 그래프 구축
- **지원 DB**: Neo4j, Memgraph, Kuzu (경량 임베디드), Apache AGE (PostgreSQL 확장), Neptune
- **활용 시나리오**:
  - 프로젝트 간 의존 관계 자동 추출 (perception → vehicle-tracker → map)
  - "perception과 관련된 모든 프로젝트는?" 같은 그래프 쿼리
  - 데이터 파이프라인 계보(lineage) 추적
- **현재 대안**: metadata의 upstream/downstream 필드로 수동 관리
- **도입 시점**: 프로젝트 10개 이상, 관계가 복잡해질 때

### 2.2 Reranker (중간 활용 가치)
- **기능**: 초기 검색 결과를 cross-encoder로 재정렬하여 정밀도 향상
- **옵션**: Cohere, HuggingFace cross-encoder, Sentence Transformer, LLM 기반
- **활용 시나리오**:
  - semantic search 결과 top-10에서 실제 관련성 높은 상위 3개 추출
  - 한국어+영어 혼용 쿼리에서 정밀도 향상
- **현재 대안**: tiered keyword scoring + dynamic weights
- **도입 시점**: search_logs 분석 후 precision이 문제일 때

### 2.3 Vector Store 교체/업그레이드 (상황별)
- **현재**: FAISS (로컬, 경량, zero-infra)
- **업그레이드 옵션**:
  | 후보 | 장점 | 도입 시점 |
  |------|------|-----------|
  | **Qdrant** | 고성능, 메타데이터 필터링 우수, self-hosted | chunk 1000+ |
  | **PGVector** | PostgreSQL 통합, SQL 조인 가능 | DB 이미 사용 시 |
  | **Pinecone** | 하이브리드 검색 네이티브 (BM25+vector) | FTS5 대안으로 |
  | **Elasticsearch** | 전문 검색 + 벡터 검색 통합 | 대규모 문서 |
- **현재 FAISS가 적합한 이유**: ~200 chunks, 단일 서버, 관리 부담 없음

### 2.4 다국어/고급 Embedding 모델 (중간 가치)
- **현재**: text-embedding-3-large (1024d) — 한국어+영어 혼용
- **비교 대상**:
  - multilingual-e5-large: 다국어 특화
  - bge-m3: 다국어 + 희소 벡터 지원
  - Gemini embedding: Google 다국어
- **활용**: 한국어 기술 문서 검색 품질이 떨어질 때 A/B 비교
- **backlog에 이미 등록됨**

### 2.5 Custom Prompt (낮은 난이도, 높은 효과)
- **기능**: mem0의 fact extraction / memory update 시스템 프롬프트를 커스터마이즈
- **현재**: `infer=False`로 LLM 호출 자체를 건너뜀
- **활용 시나리오**:
  - `infer=True`로 전환 시 — 기술 문서 특화 fact extraction prompt
  - 예: "프로젝트 간 의존 관계를 추출하라", "성능 지표를 구조화하라"
- **도입 시점**: 비구조화 문서 (회의록, 자유형 메모) 인덱싱 필요 시

### 2.6 Procedural Memory (잠재적 가치)
- **기능**: 절차적 지식 (step-by-step 프로세스) 전용 메모리 타입
- **활용 시나리오**:
  - 배포 절차, 트러블슈팅 가이드, 온보딩 체크리스트
  - "perception 배포하는 방법은?" → 단계별 절차 반환
- **도입 시점**: 운영 매뉴얼이 축적될 때

### 2.7 OpenAI-Compatible Proxy (높은 잠재 가치)
- **기능**: OpenAI chat completion API 호환 프록시로, 자동으로 memory context 주입
- **동작**: 에이전트 → proxy → LLM 호출 시 관련 메모리가 자동으로 context에 추가
- **활용 시나리오**:
  - 모든 에이전트 LLM 호출에 투명하게 메모리 컨텍스트 추가
  - 기존 OpenAI SDK 코드 변경 없이 메모리 기능 추가
- **도입 시점**: 에이전트 프레임워크에서 일관된 메모리 접근이 필요할 때

### 2.8 Self-Hosted Server (확장 시)
- **기능**: FastAPI 기반 REST API 서버, Docker 배포
- **구성**: PGVector + Neo4j + OpenAI
- **활용 시나리오**:
  - 여러 서버의 에이전트가 중앙 메모리에 접근
  - API key 기반 인증, 멀티테넌시
- **현재 대안**: MCP 서버 내장 (단일 서버에 충분)
- **도입 시점**: 멀티서버 환경에서 공유 메모리 필요 시

### 2.9 History/Audit Trail (낮은 난이도)
- **기능**: 메모리별 변경 이력 (ADD/UPDATE/DELETE) 추적
- **현재**: batch add 시 history 기록은 하지만 조회 도구 없음
- **활용 시나리오**:
  - "이 메모리가 언제, 왜 변경되었는가?" 추적
  - knowledge base 변경 감사
- **도입 시점**: 규정 준수/감사 요구 시

### 2.10 TypeScript SDK (특수 상황)
- **기능**: Node.js/TypeScript에서 mem0 사용
- **활용 시나리오**: 웹 프론트엔드, Node.js 에이전트, VS Code 확장에서 메모리 접근
- **도입 시점**: JavaScript 기반 도구 개발 시

---

## 3. 도입 우선순위 추천

| 우선순위 | 기능 | 효과 | 난이도 | 시점 |
|----------|------|------|--------|------|
| 1 | Reranker (HuggingFace) | 검색 정밀도 향상 | 낮음 | search 품질 이슈 발견 시 |
| 2 | Custom Prompt | fact extraction 품질 | 낮음 | 비구조화 문서 추가 시 |
| 3 | Graph Memory (Kuzu) | 프로젝트 관계 자동 추출 | 중간 | 프로젝트 10+ |
| 4 | 다국어 Embedding 비교 | 한국어 검색 품질 | 중간 | 검색 품질 불만 시 |
| 5 | OpenAI Proxy | 투명한 메모리 주입 | 중간 | 에이전트 프레임워크 고도화 시 |
| 6 | Vector Store 교체 | 성능/필터링 | 높음 | chunk 1000+ |
| 7 | Self-Hosted Server | 멀티서버 공유 | 높음 | 서버 3+ |

---

## 4. 아키텍처 전체 그림

```
┌─────────────────────────────────────────────────────────┐
│                  Collaboration MCP Server                │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐ │
│  │ hybrid_search│  │   remember   │  │ check_system  │ │
│  │  _knowledge  │  │   / recall   │  │   _health     │ │
│  └──────┬───────┘  └──────┬───────┘  └───────┬───────┘ │
│         │                 │                   │         │
│  ┌──────▼───────┐  ┌──────▼───────┐  ┌───────▼───────┐ │
│  │  Mem0Sync    │  │   Memory     │  │  SQLite       │ │
│  │ (collab-kb)  │  │ (agent-mem)  │  │ (logs/health) │ │
│  └──────┬───────┘  └──────┬───────┘  └───────────────┘ │
│         │                 │                             │
│  ┌──────▼─────────────────▼───────┐                     │
│  │         FAISS Vector Store      │                    │
│  │   text-embedding-3-large (1024d)│                    │
│  │   via LiteLLM Gateway           │                    │
│  └─────────────────────────────────┘                    │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│              Per-Project (.mem0/)                        │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐                     │
│  │  sync.py     │  │  FAISS       │                     │
│  │  ensure      │  │  (local)     │                     │
│  │  search      │  │  FastEmbed   │                     │
│  │  rebuild     │  │  bge-small   │                     │
│  └──────────────┘  └──────────────┘                     │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│              미래 확장 가능                               │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐│
│  │ Graph    │  │ Reranker │  │ Proxy    │  │ Server  ││
│  │ Memory   │  │ (HF/     │  │ (OpenAI  │  │ (REST   ││
│  │ (Kuzu)   │  │  Cohere) │  │  compat) │  │  API)   ││
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘│
└─────────────────────────────────────────────────────────┘
```

---

## 5. 참고 문서

| 문서 | 위치 |
|------|------|
| mem0 초기 설계 | `collaboration/docs/adr/012-mem0-semantic-search.md` |
| Batch reconcile 최적화 | `.omx/docs/adr/001-batch-reconcile-perf.md` |
| Hybrid search 동적 가중치 | `.omx/docs/adr/002-hybrid-search-weights.md` |
| Per-project 자동화 | `.omx/docs/adr/003-per-project-mem0-automation.md` |
| 운영 모니터링 | `.omx/docs/adr/004-operational-monitoring.md` |
| remember/recall 가이드 | `collaboration/docs/shared-conventions.md §12` |
| Gateway 제한 발견 | `.omx/docs/findings.md` |
