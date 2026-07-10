# PROGRESS

> 착수 단위(구현문서 §9.2)를 순서대로 진행. 각 단위: 코드 생성 → 테스트(§9.3) → 통과까지 수정 → 다음.
> 우선순위: 명세 > 정의서 > 구현문서. USE_MOCK=1로 네트워크·API키 없이 전 과정 동작.

## 셋업 ✅
- git init + remote(`https://github.com/playjae0/ontology_agent2.git`), docs/ 이동(명세·정의서·구현문서·착수프롬프트).
- 파일트리 스캐폴딩(core/·layers/·schemas/·cli/·mock/·tests/·data/), `__init__.py`, `.gitignore`, `requirements.txt`.
- `.claude/settings.local.json`: acceptEdits + 안전 명령 허용목록(원격 세션, Shift+Tab 불가 대체).

## 착수 단위
| 단위 | 상태 | 테스트 | 비고 |
|---|---|---|---|
| 1a core/graph·dictionary·id_seq + init | ✅ | test_1a OK | id 전역유일·복원·사전 왕복·neighbors |
| 1b skeleton + process config.skeleton | ✅ | test_1b OK | Process 7·part_of 6·precedes 5, flat 타입 |
| 1c ingest+matcher+build + cp.json | ✅ | test_1c OK | Unit/Property/has_property, C4 conflict·C7 병렬·C8/C9 극성+mirrors+asymmetry |
| 1d content(prose) 경로 + PPT01 | ✅ | test_1d OK | P5 linked=false, P6 주액기 auto+큐, describes, P2 스침 비추출 |
| 2 query + router + cli/query + queries | 대기 | — | |
| 3 quality config+스키마 + PFMEA01 + cross-layer | 대기 | — | git diff core/ 판정 |

## 로그
- (셋업 완료) 1a 착수.
- 1a ✅ — core/graph.py(IdSeq·Graph·init_data_tree), core/dictionary.py. test_1a 통과.
- 1b ✅ — core/skeleton.py(tree|flat 범용), layers/process/config.json. test_1b 통과(Process 7·part_of 6·precedes 5).
- 1c ✅ — core/{llm,matcher,store,ingest,build}.py + router.py + schemas(blocks·cp) + mock/CP01. test_1c 통과.
    - **config 확장 결정(§0-1 준수용)**: 극성 결합 게이팅·mirror 관계명을 core에 박지 않고 layers/process/config.json의 `polarity`(field/values/bind_categories)·`mirrors.relation`으로 내림. §4 config 문면엔 없으나 §0-1(core 층 어휘 금지)+§3.6(범용성 원리)이 상위 규칙이라 config화가 정합적. (추측 아님 — 불변 규칙 준수.)
    - core/store.py(ChunkStore·ReviewQueue) 신설: 파일트리엔 없으나 시스템 인프라(층 어휘 없음), §0-1 무관.
    - mirror 자식 비교를 관계명 무가정 시그니처(rel·방향·극성제거 상대 canonical)로 구현 — part_of/has_property를 코드에 안 박음(§3.6).
- 1d ✅ — prose 경로(llm.extract_mentions·ingest_prose), schemas/ppt.json, mock/PPT01. test_1d 통과.
    - MOCK 추출 = chunk.meta.mock_mentions(파서 mock의 LLM 추출 시뮬레이션, §8·§16.3). 전 청크 원문 보존(P5·§5.6.6).
    - P8 "notching press"(영문 표기 변형)는 MOCK 정규화로 노칭 프레스와 매칭 불가 → 신규 생성. **실물 검증 항목**(§6.3 P8 주석대로 MOCK 한계).
