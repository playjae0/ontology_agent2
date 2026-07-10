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
| 1c ingest+matcher+build + cp.json | 대기 | — | |
| 1d content 경로 + PPT01 | 대기 | — | |
| 2 query + router + cli/query + queries | 대기 | — | |
| 3 quality config+스키마 + PFMEA01 + cross-layer | 대기 | — | git diff core/ 판정 |

## 로그
- (셋업 완료) 1a 착수.
- 1a ✅ — core/graph.py(IdSeq·Graph·init_data_tree), core/dictionary.py. test_1a 통과.
- 1b ✅ — core/skeleton.py(tree|flat 범용), layers/process/config.json. test_1b 통과(Process 7·part_of 6·precedes 5).
