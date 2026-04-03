# mem0 Knowledge System 운영 가이드

## 시스템 구조

```
unified_search() ─────────────────────────────────
    │                                             │
    ▼                                             ▼
Per-Project .mem0/                    Collaboration-wide
(FAISS + bge-small 384d)             (FAISS + bge-m3 1024d)
├── docs/**/*.md (로컬)               ├── reports/
├── .mem0/imported/ (캐시)            ├── requests/
│   ├── requests/                     ├── insights/
│   ├── reports/{self,up,down}/       └── 18개 프로젝트 docs/**/*.md
│   └── insights/
└── state.json (TTL 6h)
```

## 일상 운영

### 세션 시작 시 (자동)
SessionStart hook이 자동 실행:
1. `ensure-imported`: imported cache TTL(6h) 만료 시 refresh
2. `ensure`: 로컬 docs 변경 시 인덱스 rebuild

수동 실행이 필요한 경우:
```bash
python .mem0/sync.py ensure-imported
python .mem0/sync.py ensure
```

### 검색
```bash
# 로컬 검색 (CLI)
python .mem0/sync.py search "쿼리" --top_k 5

# JSON 출력 (프로그래밍 연동)
python .mem0/sync.py search "쿼리" --json

# 통합 검색 (MCP 도구 — Claude 세션 내에서)
# unified_search(query="쿼리", scope="all", project="mem0")
```

### 인덱스 재구축
docs/ 변경 후 즉시 반영하려면:
```bash
python .mem0/sync.py rebuild
```

### Imported context 수동 refresh
collaboration에서 새 request/report가 온 경우:
```bash
python .mem0/sync.py refresh-imported
```

## 모니터링

### 인덱스 상태 확인
```bash
# manifest 확인
cat .mem0/manifest.json | python3 -m json.tool

# imported state 확인
cat .mem0/imported/state.json | python3 -m json.tool

# FAISS 인덱스 크기
ls -lh .mem0/faiss_index/
```

### 검색 품질 평가
```bash
cd ~/projects/collaboration

# Golden test (8개 predefined 쿼리)
python scripts/eval_search.py golden

# 운영 통계
python scripts/eval_search.py stats

# 전체 리포트
python scripts/eval_search.py report

# Backtest (설정 변경 전후 비교)
python scripts/eval_search.py backtest --limit 20
```

### 핵심 지표

| 지표 | 목표 | 확인 명령 |
|------|------|-----------|
| Golden Pass Rate | ≥ 80% | `eval_search.py golden` |
| Latency P50 | ≤ 5초 | `eval_search.py stats` |
| Degraded Rate | ≤ 20% | `eval_search.py stats` |
| Empty Result Rate | ≤ 10% | `eval_search.py stats` |
| Local Chunks | ≥ 30/project | `cat .mem0/manifest.json` |

## 트러블슈팅

### 검색 결과가 비어있을 때
1. 인덱스 확인: `cat .mem0/manifest.json` → chunk_count 확인
2. chunk_count=0이면: `python .mem0/sync.py rebuild`
3. docs/ 디렉토리에 .md 파일이 있는지 확인

### Imported context가 갱신 안 될 때
1. state.json 확인: `cat .mem0/imported/state.json`
2. TTL 만료 확인: `ttl_expires_at` 시간 비교
3. 수동 refresh: `python .mem0/sync.py refresh-imported`
4. collaboration 프로젝트 접근 가능 확인: `ls ~/projects/collaboration/`

### Gateway 에러 (500, Connection Error)
- 원인: TEI bge-m3 pod 불안정 또는 LiteLLM gateway 문제
- 영향: collaboration-wide 검색 불가 → degraded mode
- 대응: 로컬 검색은 정상 동작, imported cache 사용
- 확인: `curl -s http://192.168.0.199/v1/models -H "Authorization: Bearer sk-1234"`

### 인덱스가 느리게 rebuild될 때
- FastEmbed 모델 첫 로드 시 ~8초 (이후 캐시됨)
- 400 chunks 기준 rebuild ~15초
- FAISS 인덱스 크기: 384d × 400 chunks ≈ 600KB

## 배포 & 설정 변경

### 새 프로젝트에 mem0 추가
```bash
python ~/projects/collaboration/scripts/setup_project_mem0.py /path/to/project
cd /path/to/project
python .mem0/sync.py refresh-imported
python .mem0/sync.py rebuild
```

### sync.py 업데이트 (전체 프로젝트)
```bash
# setup script가 sync.py 템플릿을 포함
# 모든 프로젝트에 재실행하면 sync.py가 업데이트됨
for proj in ~/projects/*/; do
  if [ -d "$proj/.mem0" ]; then
    python ~/projects/collaboration/scripts/setup_project_mem0.py "$proj"
  fi
done
```

### Embedding 모델 변경 시
1. `.mem0/config.json` 수정
2. `python .mem0/sync.py rebuild` (전체 재인덱싱 필요)
3. `python ~/projects/collaboration/scripts/eval_search.py golden` (품질 비교)
4. `python ~/projects/collaboration/scripts/eval_search.py backtest` (결과 변화 확인)

## 파일 구조

```
project/
├── docs/                          # 로컬 knowledge (인덱싱 대상)
│   ├── roadmap.md
│   ├── backlog.md
│   ├── findings.md
│   ├── lessons.md
│   ├── adr/
│   ├── diaries/
│   └── ...
├── .mem0/
│   ├── config.json                # embedder/vector store 설정
│   ├── sync.py                    # 동기화/검색 스크립트
│   ├── manifest.json              # 인덱스 상태 (gitignore)
│   ├── faiss_index/               # FAISS 벡터 인덱스 (gitignore)
│   └── imported/                  # cross-project cache (gitignore)
│       ├── state.json             # TTL, dependency 정보
│       ├── requests/              # from/to this project
│       ├── reports/               # self + upstream/downstream
│       └── insights/              # tagged to this project
```

## 관련 문서

- ADR-005: Per-project 데이터 소스 범위 (`docs/adr/005-per-project-data-scope.md`)
- ADR-006: Cross-project 통합 검색 (`docs/adr/006-unified-knowledge-search.md`)
- 평가 계획: `docs/eval-plan.md`
- Utilization guide: `docs/mem0-utilization-guide.md`
