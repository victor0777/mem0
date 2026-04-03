# mem0 Backlog

## improvement

- [ ] Embedding 모델 업그레이드 및 벤치마크 (발견일: 2026-04-02, 보류: 운영 안정화 후 진행)
  - 현재: gateway `bge-m3` (CPU-only TEI), local `bge-small-en-v1.5` (FastEmbed)
  - 후보: `multilingual-e5-large`, `bge-m3` GPU 버전
  - 전제조건: TEI pod 안정성 확보, 충분한 운영 데이터 축적
  - 한국어+영어 기술문서 검색 품질 평가 포함
- [ ] Gateway 안정 시 batch reconcile 벤치마크 재실행 (발견일: 2026-04-01)
  - 20x1 vs 32x1 vs 32x2 비교
  - AAP scale down 후 안정화되었으므로 재측정 가능

## tech-debt

- [ ] TEI pod CPU-only + NFS 서버 동거 리스크 (발견일: 2026-04-02)
  - TEI `cpu-1.6` 이미지가 phoenix-ktl-01(NFS 서버)에서 실행 중
  - AAP scale down으로 경합 완화됨 (61% → 11%), 하지만 구조적 리스크 잔존
  - 대안: GPU 노드로 이전 또는 dedicated CPU 할당(Guaranteed QoS)
- [x] super-ktl-01 SchedulingDisabled (발견일: 2026-04-02, 해결: 2026-04-02)
  - 복구 확인: Ready, GPU 2x RTX 5000 인식, Unschedulable=false
- [ ] 테스트 큐 자동 실행 기능 (발견일: 2026-04-02)
  - 장시간 작업(reconcile 등) 완료 후 대기 중인 테스트를 자동 실행
  - deferred task queue + completion callback 패턴
- [ ] mem0 FAISS 인덱스 백업 전략 (발견일: 2026-04-01)
  - 인덱스 손실 시 full reconcile 필요 (~4분)
  - 주기적 백업 또는 빠른 rebuild 경로 필요

## idea

- [ ] mem0를 collaboration MCP의 memory backend로 활용 (발견일: 2026-04-02)
  - 현재 collaboration은 자체 knowledge DB 사용
  - mem0의 fact extraction + dedup 파이프라인 활용 가능성 검토
- [x] ~~Graph memory 활용~~ (발견일: 2026-04-01, 결론: 불필요)
  - project-registry.yaml + unified_search + get_blockers로 충분
  - 18개 프로젝트 규모에서 Neo4j는 오버엔지니어링
