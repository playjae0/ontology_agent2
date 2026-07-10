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

## 검수 라운드 2 (REVIEW_단위3.md) + 조치
- 감사(읽기): 구조·범용성(core 층 어휘 0, quality 코드 0)·그래프 무결성(극성·병합·맥락형 attr·provenance §0-5) 견고. 질의 12문항 expected_path 일치.
- **조치 3건 (테스트 추가·통과, 8개 테스트 전부 OK)**:
    - **(다)** cross-layer 사실 이중 렌더/raw id → `graph_facts.skip_relations` + 라우터가 per-layer에서 cross_layer 관계 제외, 브리지 단독 문장화. `test_review2` 검증.
    - **(라-1)** 다중 occurs_in → mock에 이물 혼입(노칭·실링 2행) + Q13. **(라-2)** 극성 잔존 공정 → 골격 cathode/anode 탭용접 + Process급 mirrors + flow 단일 스트림.
    - **(마)** §3.6 명시적 실패 → neighbors가 미지원 direction/recursive에 raise.
- **(라-2)가 요구한 core 보강 2건**(§3.6 관찰): skeleton.plant 극성 electrode_type 부여 + apply_mirrors 형제(precedes) 관계 자식비교 제외. **§5.2 ② Process급 극성은 config-only 표현 밖**이었다는 실측 — 둘 다 config 구동·층 어휘 없음. config-only(quality 추가 무수정) 성질은 유지.
- (나) 재인입은 명세 v1.11 §5.5-3(회수/보존/재평가 3분류)대로 **단위 5 유지**.
- 골격 변경(탭용접→극성 2노드) 반영: Process 8·part_of 7·precedes 6. test_1b·2·mirror_selfheal 갱신.
