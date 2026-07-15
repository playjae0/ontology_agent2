# ontology_agent2 — 제조 온톨로지/GraphDB PoC

문서(Excel/PPT/Word/PDF)를 파서가 뽑은 JSON으로 받아 **층별 그래프(노드+엣지) + 청크 원문**을 진실로
구축하고 질의하는 에이전트. 진실은 `data/`의 JSON이며 Neo4j·Cypher·시각화는 재생성 가능한 파생물(P5).

- **정본 문서**: `docs/` — 명세(무엇을·왜) > 정의서(role 계약) > 구현문서(어떻게). 이 README는 실행 안내만.
- **범용성 원리**: `core/`에 층 어휘(카테고리·관계·개체명) 없음(§0-1). 층 추가 = `layers/<층>/config.json` +
  `schemas/*.json`, 코드 0. core는 config를 개수·이름·유무 무가정 순회(§3.6).

## 실행 (표준 라이브러리만, USE_MOCK=1 기본 — 네트워크·API 키 불요)

```
python run.py all            # init(--fresh) → build(mock 전부) → test — 깨끗한 재현
python run.py init [--fresh] # data/ 초기화 + 골격 심기(--fresh면 기존 data/ 삭제)
python run.py build [파일…]   # mock/parsed/* 전부(기본) 또는 지정 파일 인입
python run.py query "<질문>"   # 질의 — 그래프 사실 + 문서 근거 두 채널
python run.py status         # 층·카테고리·관계·큐·사전 요약표
python run.py test           # tests/test_*.py 전체

python viz.py html [--open]  # data/ → out/ontology.html (vis.js 단일 파일)
python viz.py cypher         # out/ontology.cypher (Neo4j 적재용 파생물)
python viz.py neo4j          # cypher 생성 + Neo4j 적재(드라이버·서버 있으면)
```

## 운영 계약

- **build 직렬 실행 (F14, 명세 §16.1)**: `build`는 **한 번에 하나**만 돌린다. id 발급(전역 시퀀스)과
  저장(그래프 전체 재기록)이 프로세스 간 원자적이지 않아, 같은 `data/`에 동시 build를 돌리면 id 충돌
  (P4 노드 유일성 위반)·저장 유실이 난다. 플랫폼이 subprocess로 호출할 때 **호출부가 직렬화를 보장**할 것.
  개별 파일 쓰기는 원자적(tmp+`os.replace` — 쓰다 만 파일 방지)이나, 프로세스 간 파일 락은 단위 4에서 구현.
- **읽기 전용**: `query`·`status`·`viz`는 진실(`data/`)을 수정하지 않는다(P6).
- **재인입 안전**: 같은 문서를 다시 build해도 노드 중복 0(노드 유일성 불변식 P4, §5.5-3). `all`은 깨끗한
  재현을 위해 `--fresh`(진실 초기화)로 시작한다.

## 구조

```
core/     A — 층 어휘 없음. graph·dictionary·matcher·llm·embeddings·store·ingest·build·query·skeleton
layers/   B — 층별 config.json만(코드 0). process·quality
schemas/  doc_type 스키마 + blocks
router.py 층 폴더 자동 발견(등록 코드 없음)
mock/     파서 출력 mock + 질의 스모크
tests/    test_1a~3·fable·reinject·mirror_selfheal·review2·viz
data/     산출물(gitignore) — 진실 그래프·사전·청크·큐
out/      시각화 파생물(gitignore)
```
