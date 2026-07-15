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
| 2 query + router + cli/query + queries | ✅ | test_2 OK | Q1~8·11·12 expected_path, flow 골격 공급, 미스 로그 |
| 3 quality config+스키마 + PFMEA01 + cross-layer | ✅ | test_3 OK | **git diff core/ 비어 있음(config-only 확증)** |

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
- 2 ✅ — core/query.py(link·expand·collect·graph_facts·flow_scope), cli/query.py(라우터+classify+compose), mock/queries.json. test_2 통과 + CLI 스모크(init/build/query) 확인.
    - answer_path 분류(graph_fact/chunk/general_knowledge)는 실물 답변 LLM의 채널 선택 지점(§5.6.4)을 MOCK 대체 — cli(라우터)에 질문 언어 패턴으로 구현(core는 구조적 파이프라인만, 층 어휘 없음).
    - cross_layer_traverse 브리지는 quality 층 추가(단위3) 후 활성 — process 단독 단계에선 무동작.
    - fact_templates의 "{src}는" 조사 오류는 config(B) 문제 — 코드 무관, 필요 시 config만 수정.
- **core 일반화(quality 착수 전)** — `attach_entity`: (카테고리쌍→관계) 매핑으로 entity 부착.
    - 용도: prose 관계 생성(§7-2, 주액기 part_of 전해액주입) + 걸침 필드 규칙B 공정부착(§15.7, PFMEA control_item).
    - 대상 층의 category_pair_map을 양방향('src,dst' 자연방향) 조회 — 관계명 무가정. process config에만 map 존재, quality는 {}.
    - **이 기능은 prose(1d)가 이미 사용** → quality 전용 아님. 그래서 quality 착수 *전에* 넣어 `git diff core/` 기준선을 완성(이후 quality는 config+schema만 추가).
    - 이 커밋이 **단위3 config-only 판정의 core 기준선**.
- 3 ✅ — **config-only 성공**: `git diff core/` 완전히 비어 있음(품질층이 layers/quality/config.json + schemas/pfmea.json + mock/PFMEA01.json만으로 core 범용 파이프라인에서 돎). test_3 통과.
    - 검증된 것: FailureEffect flat 골격, causes 사슬(이물유입→절연파괴→내부단락), 절연파괴 병합(R3 fm=R4 cause), cross-layer occurs_in/affects/controlled_by(quality 그래프 저장, dst=process), R9 orphan_anchor(effect 셀부풀음), R13 orphan_anchor(process 레이저노칭)+occurs_in 드롭+규칙B 부착 드롭, R12 unknown_field(비고), 규칙A(걸침 control_item auto Property), 규칙B(공정 has_property 부착), 노칭정밀도 표기변형 매칭, spec_conflict는 C4에서만(severity effect 정렬 병합), cross 질의 Q9(occurs_in 역방향)·Q10(affects 역방향), Q1~8 회귀 무오염.
    - **core 무변경**. 단위3에서 코드 변경은 `cli/query.py`(라우터)뿐 — cross-layer 브리지를 전역 scope 시딩 + 전 층 노드 병합 뷰(canonical 전역 해소)로 개선. 라우터는 §8-R1이 지정한 cross-layer **합성 지점**이며 층 어휘 없이 config(cross_layer_traverse·fact_templates) 구동이라, Rule-of-Three 관찰상 "2번째 층이 config-only로 붙고, 손댄 코드는 core가 아니라 합성 라우터"라는 실측.

## 국면 1 mock 구현 완료 (단위 1a~3)
- 7개 테스트(test_1a·1b·1c·1d·2·3·mirror_selfheal) 전부 통과, USE_MOCK=1 무의존.
- **config-only 확증 성공** = 핵심 설계 가설(범용성 전략 §3) 실증.
- 남은 로드맵: 단위 4(플랫폼 연동)·5(수정 도구+계기판) — 국면1 후반, 별도 착수.

## 검수 라운드 1 (사람 지시 반영)
- **Q1 auto_node 42건 감사**: 오분리 0(정규화 canonical 충돌 없음). "노칭정밀도"(R12)는 정상 매칭(신규 아님). 예외 "notching press"(영문)만 신규=문서화된 MOCK 한계.
- **(가) mirror self-heal 수정**: `apply_mirrors`를 매 build 재평가로 전환 — 이 층 mirror_asymmetry 항목 걷어내고 현재 상태로 재작성. (category, 극성제거 canonical) 그룹당 1건, **극성별 자식 시그니처 합집합** 비교(중복 노드에도 강건). 재인입→1 유지(폭증 없음), 대칭 회복→0. `test_mirror_selfheal` 검증. (이전 "첫 감지만" 픽스를 대체 — self-heal 부재 문제 해결.)
- **(나) 재인입 노드 중복+stale 큐**: KNOWN_ISSUES.md 기록, 단위 5(재인입 회수 규칙 정밀화)에서 구현. 단위 1a~3 산출물엔 영향 없음(문서 1회 인입).
- core self-heal 수정은 층 어휘 없음(config 구동) — config-only 성질 유지(quality 격리해도 process 파이프라인 정상).

## 단위 3.5 — 재인입 회수 ②(사전 보존) + 노드 유일성 불변식(P4) (2026-07-15)

- **docs v1.13/v1.12 정본 반영**: 사용자가 명세 v1.13·구현문서 v1.12 교체본 투입(파일명 " (14)/(7)" →
  정본명으로 정리, git 트리 M으로 정돈). v1.13 P4 = **노드 유일성 불변식**("같은 개념=언제나 한 노드,
  중복 생성 금지"), §5.5-3 ②를 "단위5 이연"에서 **플랫폼 전(단위 3.5)**으로 전진. **내 구현이 이 정본과 일치**.
- **구현(명세 §5.5-3 3분류)** — `core/ingest.reinject` 정밀화:
    - **② 보존**: provenance만 doc_id로 걷고 **살아있는 노드의 사전 엔트리·alias·노드·엣지 자체는 삭제 금지**
      (node id가 그래프에 있으면 유지 — `item["id"] in live_ids`). 재인입 시 사전 재조회로 재매칭(중복 0).
    - **③ 재평가**: `queue.remove_doc(doc_id)`로 그 문서 큐 항목 회수 → 재인입 결과로 재작성.
      evidence_lost는 build 말미 `sweep_evidence_lost`(신설)가 provenance **최종** 상태로 self-heal
      (재인입 중 판정하면 같은 문서 재매칭 시 stale로 남음 — mirror_asymmetry와 같은 매-build 재평가 패턴).
    - **부수(match provenance 누적)**: `_register`가 매칭 경로에서도 노드 provenance를 누적 —
      없으면 재인입이 provenance를 걷은 뒤 재매칭돼도 노드가 근거 0으로 보여 evidence_lost 오탐(§5.5-3
      "provenance가 여럿인 노드는 다른 문서가 여전히 근거"의 실제 구현. 다중근거 노드 실증: 노칭::노칭 정밀도
      = CP01-C1 + PFMEA01-R12 양쪽).
- **실측 전/후**(viz html 노드/엣지 카운트 + status):
    - CP01 단독 재인입: 노드 26 → **26**(이전 26→27 중복), cathode 노칭 프레스 **1개**(이전 2개).
    - 3문서 반복(--fresh 없이): 61 → **61**(이전 **61→147**), 엣지 97 → **97**, mirrors 3 유지(데카르트곱 없음).
    - 큐: 첫 빌드 55건 → 재인입 후 **6건**(auto_node는 재매칭이라 재적재 안 됨 — 정상), evidence_lost **0**(오탐 없음).
    - 재인입 **고정점**: 라운드2 == 라운드3(노드/엣지/큐 완전 일치). status 표에서 중복 노드·가짜 mirror 없음 확인.
- **테스트 파일 10→11개**: `tests/test_reinject.py` 신설(유일성·고정점·큐 비폭증·다중근거 생존·개정
  evidence_lost 5케이스), `test_viz.test_build_without_fresh_is_safe` 추가(--fresh 없이 재빌드 안전),
  `test_run_py_all_is_reproducible`에 큐 수 일치 추가. **전체 11/11 파일 통과**.
- **KNOWN_ISSUES (나) → ✅ 해소**. 남은 경계: 대칭↔비대칭 **역방향** 복원은 노드 삭제 도구(단위5) 필요
  (재인입은 노드를 안 지우고 evidence_lost로 남김 — 자동 삭제 금지, 재인입 결함 아님).

## 실행 진입점 + 시각화 (2026-07-13)

- **run.py** — 파이프라인 단일 진입점(표준 라이브러리만): `init [--fresh]` · `build [파일…]`(기본 mock 전량)
  · `query "<질문>"` [-v] · `test`(tests/test_*.py 전량) · `status`(층·카테고리·관계·큐·청크·사전 요약표)
  · `all`(= init --fresh → build → test, **깨끗한 재현**). 명령별 exit code, USE_MOCK 기본 1.
  기존 CLI(§0-7 계약)를 대체하지 않고 감싼다 — 플랫폼은 여전히 `cli.build`/`cli.query`를 subprocess 호출.
    - **`--fresh`가 필요한 이유(이번에 실측)**: `init_data_tree`는 기존 파일을 덮어쓰지 않으므로(재실행 안전),
      data/가 남은 채 `all`을 다시 돌리면 build가 **재인입 경로**를 타 노드가 61→147로 불어난다
      (KNOWN_ISSUES (나) 그 자체가 사용자 눈앞에 발현). `all`은 fresh init으로 고정하고,
      **"all 두 번 = 같은 그래프"를 회귀 테스트로 못박음**(test_viz.test_run_py_all_is_reproducible).
- **viz.py** — 시각화(표준 라이브러리만, 파생물 전용·읽기 전용 P5): `html [--open] [--threshold N]`
  (vis.js CDN 단일 HTML) · `cypher`(out/ontology.cypher) · `neo4j`(cypher 생성 + bolt 적재, 드라이버·서버
  없으면 친절 안내 + html 경로 제안 — 실측: 드라이버는 있고 서버 인증 실패 시 안내 경로 정상 동작).
    - **뷰 규칙**: 카테고리 색·관계 선 스타일·극성 모양·mirrors 관계명을 **config·데이터에서 발견 순서대로**
      배정(§0-1 하드코딩 금지 — 층 어휘 0). cross-layer 엣지 강조(굵은 적색), mirrors는 무방향 파선,
      극성은 노드 모양(▲cathode/▼anode/●무극성), confirmed는 굵은 테두리.
      노드 클릭 → 속성 패널(canonical/id/층/카테고리/status/극성/aliases/provenance/attrs/엣지/근거 청크).
    - **규모 대비**: 노드 > 임계(기본 300)면 기본 ego 뷰(선택 노드+1홉), 전체는 토글 — 기존 platform M8
      교훈(1000노드 force 멈춤). `--threshold 30`으로 ego 동작 확인.
    - **판정**: HTML·cypher의 노드/엣지 수 == graph.json 집계(파생물 무결성), 툼스톤만 제외
      (test_viz). 생성 HTML의 인라인 JS는 `node --check` 문법 통과.
- **테스트 10/10 통과**(test_viz 신설 — 4케이스). out/은 gitignore(파생물).

## FABLE 반영 라운드 (2026-07-12, 명세 v1.12 마감 지시)

- **✅ docs/ 동기화 완료(2026-07-13)**: 지시 시점엔 docs/ 교체본이 레포에 없어 지시문을 정본으로 구현했고,
  이번에 **명세 v1.12 / 정의서 v1.8 / 구현문서 v1.11**로 문면을 반영(전문 재작성 없이 해당 절 수정 — 문서 자체 규칙).
  반영 지점: 명세 §5.2(canonical 스코프·게이팅 ③·이중 접두 금지·골격 극성 alias)·§5.3(mirrors ④ 공유 문맥)
  ·§5.6.1(링킹 단어 경계)·§5.6.6((a) 판정용 임베딩은 이연 아님)·§6.5(missing_field·payload_kind raise)
  ·§7-1(invalid_category)·§11(뷰어 계약·규모 대비) / 정의서 §3.1(anchor Tier1·극성 모호)·§3.2(스코프·리스트 계약)
  / 구현문서 §1(파일트리 — store·embeddings·run·viz·out)·§2.2(canonical 예시)·§2.3(큐 kind 2종)·§4(config
  polarity·canonical_scope)·§6.2(C6 v1.12 정정)·§9.1(실행 진입점).
- **즉시 수정분(명세 무변경)**: F1 골격 극성 표면형 alias(skeleton.plant — "탭용접" 질의·anchor 정상화,
  극성 모호 anchor는 orphan+후보 id) / F6+F15 인입 검증 역방향(missing_field kind 신설, entity 리스트 큐,
  payload_kind 미지원 raise §3.6) / F13 닫힌 카테고리 검증(invalid_category kind, 생성 보류) /
  F5-① anchor Tier1(seed) 한정(auto 후보는 orphan+payload) / F12 링킹 단어 경계(왼쪽 글자연속·오른쪽
  라틴연속 차단 — **오른쪽 한글은 조사라 허용**: 문면 그대로면 "노칭에서"가 깨져 기존 판정 하향이 되므로 조정).
- **v1.12 마감분**: F4 Property canonical 부모 접두 — config `canonical_scope`(bind_categories/separator)
  구동, 부모=attach_to_field 해소 노드→@process_ref 폴백, 표면형 alias 등재. R12↔C1 표기변형 매칭·
  C2/R1 규칙B 보강은 좌표 접두가 같아 유지, 교차 좌표 동명 인자(실링::온도 vs 패키징::온도)는 분리 /
  F2 현 게이팅(문서 층 config)이 §5.2 ③으로 승인 — 코드 무변경, 주석만 / F11 이중 접두 방어
  (표면형이 극성 토큰으로 시작하면 재결합 금지, electrode_type은 표면형 우선) / F3 mirrors ④ —
  극성별 자식 시그니처의 **공유 문맥 존재**를 쌍 성립 조건으로(없으면 mirrors·asymmetry 보류),
  strip을 스코프 구획별 극성 제거로 일반화 / F16 준비 — core/embeddings.py 생성(embed() 계약,
  MOCK=sha256 32차원 정규화+경고, 실물=sentence-transformers 지연 import. 후보검색 확장은 이연).
- **이연 유지(착수 안 함)**: (나)재인입·F7~F10·F14·F16 후보검색 본체 — KNOWN_ISSUES (바) 표 참조.
- **테스트**: tests/test_fable.py 신설(10건). 기존 테스트는 v1.12 canonical 스코프만 기대값 갱신
  (test_1c·1d·3 — 판정 하향 없음). **9개 파일 전부 통과**, CLI 스모크(탭용접 질의 graph_fact·
  레이저노칭 미링킹·규격 3극성 렌더) 확인. core 층 어휘 0 재grep 통과 — core 수정은 §3.6 "core 패턴
  추가"에 해당(전부 config 구동·층 어휘 없음).

## 검수 라운드 2 (REVIEW_단위3.md) + 조치
- 감사(읽기): 구조·범용성(core 층 어휘 0, quality 코드 0)·그래프 무결성(극성·병합·맥락형 attr·provenance §0-5) 견고. 질의 12문항 expected_path 일치.
- **조치 3건 (테스트 추가·통과, 8개 테스트 전부 OK)**:
    - **(다)** cross-layer 사실 이중 렌더/raw id → `graph_facts.skip_relations` + 라우터가 per-layer에서 cross_layer 관계 제외, 브리지 단독 문장화. `test_review2` 검증.
    - **(라-1)** 다중 occurs_in → mock에 이물 혼입(노칭·실링 2행) + Q13. **(라-2)** 극성 잔존 공정 → 골격 cathode/anode 탭용접 + Process급 mirrors + flow 단일 스트림.
    - **(마)** §3.6 명시적 실패 → neighbors가 미지원 direction/recursive에 raise.
- **(라-2)가 요구한 core 보강 2건**(§3.6 관찰): skeleton.plant 극성 electrode_type 부여 + apply_mirrors 형제(precedes) 관계 자식비교 제외. **§5.2 ② Process급 극성은 config-only 표현 밖**이었다는 실측 — 둘 다 config 구동·층 어휘 없음. config-only(quality 추가 무수정) 성질은 유지.
- (나) 재인입은 명세 v1.11 §5.5-3(회수/보존/재평가 3분류)대로 **단위 5 유지**.
- 골격 변경(탭용접→극성 2노드) 반영: Process 8·part_of 7·precedes 6. test_1b·2·mirror_selfheal 갱신.
