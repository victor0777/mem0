# mem0 Roadmap

## Phase 1: Collaboration MCP 통합
- [x] mem0 프로젝트 collaboration MCP 등록
- [x] Semantic search 통합 (collaboration MCP knowledge base)
- [x] 프로젝트 문서 체계 정비
- [x] 인프라 리스크 대응 (TEI pod 안정성, AAP scale down, agents escalation)
- [x] Per-project 데이터 소스 확장 (ADR-005: Option A+, Codex debate 합의)
- [x] Cross-project 통합 검색 (ADR-006: unified_search, Codex debate 합의)
  - [x] Collaboration chunker 확장 (495→2081 chunks)
  - [x] sync.py --json 출력 + 18개 프로젝트 배포
  - [x] unified_search() MCP 도구 구현
- [ ] Embedding 모델 업그레이드 (운영 안정화 후 진행, backlog로 이관)

## Phase 2: 전체 프로젝트 배포
- [x] setup_project_mem0.py 업데이트 (새 sync.py 템플릿)
- [x] SessionStart hook 연동 (ensure-imported + ensure)
- [x] 18개 프로젝트 일괄 배포 (par02 서버)

## Phase 3: 운영 안정화 ← **current**
- [ ] Collaboration reconcile 실행 (2081 chunks 인덱싱) ← **current**
- [ ] 다른 서버(dgx01, ktl01) 배포 (테스트 후)
- [ ] Embedding 벤치마크: multilingual-e5-large vs bge-m3 (Phase 2 of embedding debate)
- [ ] 운영 모니터링 (imported TTL, chunk count 추적)

## Phase 4: Self-hosted mem0 활용
- [ ] Local mem0 서버 배포 (Docker)
- [ ] 프로젝트별 memory store 구성
- [ ] Cross-project knowledge sharing via mem0
