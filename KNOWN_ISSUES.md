# KNOWN ISSUES

> 인지된 결함 — 지금 고치지 않고 지정 단위에서 구현. 각 항목: 증상 / 원인 / 실측 / 해결 계획 / 검증.

## (나) 재인입 노드 중복 생성 + stale 큐  — ✅ 해결(단위 3.5, 2026-07-15)

> **해결**: `core/ingest.reinject`를 명세 §5.5-3 **회수/보존/재평가 3분류**로 정밀화(v1.13 노드 유일성 불변식).
> ② 보존 — 살아있는 노드의 사전 엔트리·alias는 provenance만 걷고 **삭제하지 않음**(node id가 살아 있으면
> 유지) → 재인입 시 재매칭(중복 0). ③ 재평가 — `queue.remove_doc(doc_id)` + evidence_lost는
> build 말미 `sweep_evidence_lost`(self-heal, provenance 최종 상태로 재평가). 부수: match 경로가
> 노드 provenance를 누적하도록 수정(`_register`) — 다중근거 노드가 재인입 후 근거소멸로 오탐되던 것 해소.
> **실측 전/후**: CP01 재인입 노드 26→26(이전 26→27 중복), 3문서 반복 61→61(이전 61→147), cathode 노칭
> 프레스 1개 유지, mirror_asymmetry 폭증 없음, 동일 재인입 evidence_lost 0(오탐 없음), 재인입 고정점
> (라운드2==라운드3). 검증 `test_reinject`(5케이스)·`test_viz.test_build_without_fresh_is_safe`.
>
> **남은 경계(단위5)**: 대칭↔비대칭 **역방향** 복원(대칭화 노드를 되돌림)은 미성립 — 재인입은 노드를
> 안 지우고 evidence_lost로 남기므로(자동 삭제 금지) 구조가 여전히 대칭. **노드 삭제 도구(단위5)** 가
> 있어야 완성되며, 이는 재인입 결함이 아니라 삭제 미구현. `run.py all`의 `--fresh`는 유지하되(진실
> 초기화 의도), 이제 `--fresh 없이 build 반복`도 안전(중복 0).

**증상**: 같은 doc_id를 재인입하면 (a) 노드가 **중복 생성**되고 (b) 그 문서가 남긴 **수정 큐 항목이 회수되지 않아 stale**로 쌓인다.

**원인**: `core/ingest.reinject()`가 명세 §5.5-3대로 doc_id의 provenance를 회수하면서 **살아있는(삭제 금지·evidence_lost) 노드의 사전(dictionary) 엔트리·alias까지 회수**한다. 그 결과 재인입 시 사전 조회가 미스 → 살아있는 노드를 못 찾고 **신규 생성(중복)**. 또한 `reinject`는 `review_queue`를 건드리지 않아(`queue.remove_doc` 미호출) 옛 항목이 남는다. 현재 재인입 회수 규칙이 "회수 대상"(그 문서 근거)과 "보존 대상"(살아있는 노드의 식별자=사전 엔트리)을 분리하지 못하는 것이 근본.

**실측(2026-07-10)**:
- CP01 1회 인입 후 `cathode 노칭 프레스` 노드 1개 → **CP01 재인입 후 2개**(사전 미스로 신규). `evidence_lost` 큐 28건.
- 이 중복이 극성 mirror 쌍을 데카르트곱으로 만들어, self-heal 도입 전엔 `mirror_asymmetry`가 1→4→6으로 폭증.
- (가) self-heal 도입 후 큐 항목은 (category, 극성제거 canonical) 그룹당 1건으로 dedup되어 **큐 폭증은 해소**(재인입→1 유지). 단, **중복 노드 자체는 그래프에 남는다**(이 이슈의 본체).
- 부작용: 대칭화 후 원본으로 되돌려도 재인입이 stale 노드(추가됐던 자식)를 삭제 안 해 union상 대칭으로 보임 → self-heal 역방향 복원이 (나) 해결 전엔 불성립(테스트 `test_mirror_selfheal` 주석 참조).

**추가 실측(2026-07-13)**: `run.py all`을 data/가 남은 채 두 번 돌리면 이 결함이 그대로 발현한다 —
노드 61 → **147**, 엣지 97 → 259(재인입이 사전 엔트리를 걷어 살아있는 노드를 못 찾고 전부 신규 생성).
→ `run.py all`은 `init --fresh`(data/ 삭제 후 재생성)로 고정하고, **"all 두 번 = 같은 그래프"를
회귀 테스트로 못박음**(test_viz.test_run_py_all_is_reproducible). **이 회피는 재현 경로만 막은 것이고
결함 본체(개정 문서 재인입)는 그대로** — 단위5에서 아래 계획대로 해결해야 한다.

**해결 계획**: 명세 §5.5-3 재인입 회수 규칙을 **회수/보존/재평가로 분리**해 정밀화 —
1. **회수**: 그 doc_id의 provenance 항목(노드/엣지/alias/attribute/청크/describes)만 제거.
2. **보존**: provenance-0이 된 노드·그 canonical 사전 엔트리는 **삭제하지 말고 재매칭 가능한 상태로 유지**(evidence_lost 표시는 유지하되 사전에서 지우지 않음) → 재인입이 신규 대신 재매칭·provenance 복원.
3. **재평가**: 재인입은 그 doc_id의 기존 수정 큐 항목도 회수(`queue.remove_doc`) 후 재인입 결과로 재작성. 자동 규칙 큐(mirror_asymmetry)는 (가) self-heal이 이미 재평가.
- 재인입은 실운영(개정 문서)·수정 도구(단위 5) 영역이라 그 단위에서 함께 구현. 단위 1a~3(문서 1회 인입) 산출물·config-only 판정에는 영향 없음.

**검증(단위 5 구현 시)**: CP01 재인입 후 노드 수 불변(중복 0), 사전 재매칭으로 provenance 복원, 옛 큐 항목 회수, 대칭↔비대칭 왕복 self-heal 양방향 성립.

---

## (다) cross-layer 사실 이중 렌더 + raw id 노출  [중] — ✅ 해결(검수 라운드2)

> **해결**: `core/query.graph_facts`에 `skip_relations` 추가, `cli/query.route` per-layer 호출이 그 층의
> `cross_layer_traverse` 관계를 넘겨 제외 → cross-layer 사실은 브리지(`_AllGraphsView` 전역 canonical)가
> 단독 문장화(§8-R1 책임분리). 검증 `test_review2.test_da_crosslayer_render`(Q10 raw id 0, occurs_in 1회씩).


**증상**: 상위층(quality)에 링크되는 cross-layer 질의에서 같은 엣지가 **두 번**, 그중 하나는 dst가 canonical이 아닌 **node id**로 렌더된다. 실측 Q10("단락으로 이어질 불량"): `절연 파괴는 N0002 공정에서 발생한다`(깨짐) + `절연 파괴는 노칭 공정에서 발생한다`(정상)가 함께 출력.

**원인/위치**: `cli/query.py` `route()`의 per-layer 루프 `all_facts += query.graph_facts(scope, g, cfg)` — `graph_facts._canon`이 **단일 층 그래프(g)**만 조회하므로 cross-layer 엣지의 타 층 dst를 못 풀고 id를 그대로 문자열화. 반면 브리지 `_bridge`는 `_AllGraphsView`(전 층 노드 병합)로 전역 해소 → 정상 렌더. 두 경로가 같은 엣지를 각각 렌더 → 이중+불일치.

**영향**: 그래프 데이터는 정상, **라우터 렌더만** 문제. answer_path는 맞음. 단 뷰어가 그래프 사실을 그대로 표시하면 "N0002 공정" 같은 깨진 문자열이 사용자에게 노출.

**조치 방향(사람 결정)**: (a) per-layer `graph_facts` 호출도 전역 canonical 뷰(`_AllGraphsView`)로 렌더, 또는 (b) per-layer 사실에서 `cross_layer_traverse` 관계 엣지는 제외하고 브리지가 단독 소유(중복 제거). **플랫폼(시각화) 착수 전 권장** — 라우터 1곳 수정, core 무관.

**검증**: Q10 그래프 사실에 `N0002/N0003` 등 id 문자열 0건, occurs_in 사실이 canonical로 1회씩만.

## (라) 다중 occurs_in · 극성 잔존 공정(Process급) 미실증  [중·커버리지] — ✅ 해결(검수 라운드2)

> **해결**:
> - **다중 occurs_in**: mock/PFMEA01에 `이물 혼입`을 노칭(R14)·실링(R15) 2행에 failure_mode로 배치 → occurs_in 2건. 질의 Q13("이물 혼입은 어느 공정에서?") 2공정 응답. 검증 `test_review2.test_ra1_multi_occurs_in`.
> - **극성 잔존 공정**: 골격에 `cathode 탭용접`/`anode 탭용접` 순차(precedes) + Process급 mirrors. flow 단일 스트림 유지. 검증 `test_review2.test_ra2_polarity_residual_process`.
> - **⚠️ 이 항목은 config/mock만으로 안 됐음 — core 보강 2건 필요(§3.6 관찰)**: (1) `skeleton.plant`가 극성 접두 골격 노드에 electrode_type 부여(mirrors 전제), (2) `apply_mirrors`가 형제(sibling=precedes) 관계를 자식 대칭 비교에서 제외(순차 precedes가 오탐 비대칭 유발 방지, §5.3 "자식(part_of/has_property) 비교"). 둘 다 config 구동·층 어휘 없음이나, **§5.2 ② Process급 극성은 config-only 표현 밖**이었다는 실측(Rule of Three 관찰 데이터). 명세 §5.2/§5.3 반영 검토 후보.


**증상**: 명세 §8-1 핵심 메커니즘 2개가 mock에서 실증되지 않음.
- **다중 occurs_in**("한 불량이 여러 공정에서 발생 → occurs_in 다중, '이 불량 유발 공정들' 질의의 답"): 실측상 **어떤 Failure도 occurs_in 2개+ 없음**. §6.1 R11이 지목한 실증자 `이물 유입`은 R3·R11 모두 *cause*라 occurs_in(=failure_mode 전용) 대상이 아니어서 0건.
- **극성 잔존 공정**(§5.2 ②, Process 레벨 극성 분기: cathode 탭용접/anode 탭용접 precedes 순차 + mirrors): 골격이 단일 `탭용접`이라 flow가 자명하게 단일 스트림 — Process급 극성 분기·mirrors·단일 스트림 규칙 미검증.

**원인**: 코드 능력은 있으나(같은 failure_mode가 2개 process_ref 행에 등장하면 다중 occurs_in 성립; skeleton.data에 극성 Process를 넣으면 분기) **mock 데이터가 두 경우를 안 만듦**.

**조치 방향(사람 결정)**: mock 보강 — (1) 한 failure_mode를 서로 다른 process_ref 2개 행에 배치(다중 occurs_in 실증), (2) 골격에 극성 잔존 공정 한 쌍 추가(예: cathode 탭용접/anode 탭용접). 코드 수정 불요일 가능성 높음(둘 다 config/mock). 단위 4/5 논의 시 함께.

**검증**: 다중 occurs_in Failure ≥1, Q("이 불량 유발 공정들") 응답에 2개 공정, 극성 Process 쌍 mirrors + flow 단일 스트림.

## (마) §3.6 명시적 실패 불완전(query traverse)  [하] — ✅ 해결(검수 라운드2)

> **해결**: `core/graph.neighbors`가 config가 준 `direction`이 {out,in,both} 밖이거나 `recursive`가 {True,False} 밖이면 raise("config 표현 밖 — core 패턴 추가 필요", §3.6). `query.expand`는 neighbors 호출이라 전파. 검증 `test_review2.test_ma_explicit_failure`.


**증상**: config로 표현 안 되는 것이 "시끄럽게" 드러나야 하나(§3.6 탈출구), query traverse의 미지원 방향/패턴은 **silent**(빈 결과)로 넘어간다. skeleton.type은 raise(정상)지만 `graph.neighbors`/`query.expand`는 알 수 없는 direction을 만나면 매칭 0건 반환.

**원인/위치**: `core/graph.py` neighbors — `direction in ("out","both")`/`("in","both")` 미해당 시 아무것도 안 하고 통과. 명시적 실패 없음.

**조치 방향(사람 결정)**: neighbors/expand에서 config가 준 direction·recursive가 지원 집합 밖이면 raise("config 표현 밖 — core 패턴 추가 필요", §3.6). 저위험 소규모.

**검증**: 잘못된 direction config로 질의 시 raise + 메시지.

---

## (바) FABLE_REVIEW 이연 항목 — 지정 단위에서 구현 (v1.12 반영 라운드에서 착수 금지로 유지)

> 상세·재현·제안은 FABLE_REVIEW.md 각 항목 참조. 여기는 소재 추적용 목록.

| # | 항목 | 예정 시점 |
|---|---|---|
| F7 | cross 브리지 노드의 청크 tier2 수집(문서 근거 채널 공백) | 단위 4(질의 합성/뷰어) |
| F8 | flow 규칙 — 링킹 0 flow 질문에 골격 공급 | 단위 4 |
| F9 | 청크 수집 상한 전역화(현재 층별 8) | 단위 4 |
| F10 | 규칙B "보강 큐 기록" | 단위 5(수정 도구) |
| ~~F14~~ | ~~id 발급 동시성·저장 원자성·"build 직렬" 계약~~ | ✅ **부분 해결(v1.14)** — 직렬 계약 명문화(build.py·README)·원자적 저장(tmp+os.replace). 프로세스 간 파일 락만 단위4 |
| F16 | 후보검색 본체(handle_entity/anchor에 임베딩 top-k) — embeddings.py 계약은 생성됨 | LLM 배선(국면2-5) |
| F15 잔여 | chunk_id 전역 중복 감시 | F6 계열 후속 |
| F17 | 배선 체크리스트(USE_MOCK 엄격화·프롬프트 실채움·추출 응답 검증 등) | LLM 배선 |

## (사) 좌표 불명 오병합 (2차 검수 G4) — 실데이터 파일럿 전 구현 (명세 v1.14 마감안 확정)

**증상**: `process_ref`(부모 좌표)가 미해소(anchor 미스)여서 **무접두 canonical**로 생성되는 스코프 Property가,
같은 표면형을 가진 **기존 스코프 노드의 alias에 히트해 오병합**된다(예: `노칭::타발 속도` 존재 상태에서
좌표 불명 행의 "타발 속도"가 그 노드에 병합). 동명 존재 여부에 따라 병합/분리가 갈리는 비결정성.

**원인**: F4(표면형 alias 등재) × anchor 미스의 교차 — `handle_entity`가 부모 미해소 시 무접두 canonical로
`dic.lookup` → 스코프 노드의 표면형 alias(0.95)에 match. 1차 F4 검증(실링/패키징 온도)은 양쪽 다 좌표가
있을 때만 봐서 이 교차를 놓침.

**마감안(명세 §5.2 v1.14, G4)**: 부모 미해소로 무접두 생성되는 Property는 후보 조회에서 **스코프 canonical
보유 노드를 제외**(무접두끼리만 병합) — 또는 이 경우 match를 uncertain으로 강등("되돌리기 쉬운 쪽", §9).

**현 상태**: mock에 좌표 불명 스코프 Property 케이스가 없어 **미발현**. 명세가 마감안을 확정했고,
실데이터 파일럿(국면2-5) 전 구현. 상세·재현은 FABLE_REVIEW2.md G4.

## (아) 경미 이연 (2차 검수 G5·G7·G8)

- **G5**: 근거 소멸(prov-0) 잔존 노드/엣지가 mirror 대칭 비교(`_incident_sig`)에 계속 참여 — 자동 삭제
  금지의 귀결. 단위5 노드 삭제 도구와 함께 자연 해소(삭제하면 sig에서 빠짐). 명세 §5.3에 "prov-0 항목
  포함 여부" 한 줄 마감 권고.
- **G7**: match 재등재로 "::" 스코프 문자열이 alias·사전 표면형에 유입(질의 무해, 뷰 노이즈). 뷰에서
  "::" 포함 alias 숨김 또는 _register 표면형 계열만 등재 — 저위험.
- **G8 [미확인]**: cypher 한글 카테고리 라벨의 Neo4j 문법 호환(백틱 필요 여부) — 로컬 서버 인증 불가로
  미검증. 현 카테고리 전부 영문이라 실해 없음. 라벨 백틱 처리 1줄이면 논점 소멸.

## v1.12 반영 라운드의 의도된 동작 변화 (결함 아님 — 기록)

- **Property canonical 스코프(F4)**: `좌표(또는 attach 부모)::표면형`. 이로써 mock의 C6("실링::실링 온도")과
  R9(패키징 행의 실링 온도 → "패키징::실링 온도")가 **별도 노드**가 됨 — 이전엔 병합.
  R9의 좌표 어긋난 control_item(REVIEW_단위3 E1-6에서 "mock 의미상 어색"으로 지적)이 데이터로 드러난 것.
  구현문서 §6.2 C6 서술("R9의 auto Property와 매칭")은 v1.12 기준으로 갱신 필요(문서 몫).
- **mirrors ④(F3)**: 공유 문맥(극성 제거 기준 같은 이웃 — 같은 부모 포함) 없는 극성쌍은 mirrors·asymmetry
  모두 보류(로그만). 완전 고립 극성쌍도 보류됨 — 부모 정보가 생기면 다음 build 재평가에서 자동 연결(self-heal).
- **링킹 경계(F12)**: 지시문 "좌우 글자 연속 제외"를 문면대로 하면 조사 부착("노칭에서")까지 차단되어
  기존 판정(Q9·Q13)이 깨지므로, **오른쪽 한글(조사)은 허용**으로 조정 — 왼쪽 글자 연속(복합어)과
  오른쪽 라틴 연속만 차단. 판정 하향 없음.

## 참고 — mock 한계(실물 검증 항목, 결함 아님)
- P8 "notching press"(영문): MOCK 문자열 정규화로 "노칭 프레스"와 매칭 불가 → 신규 생성. 실물 LLM 판정에서 해소(§6.3 P8) — 단 해소의 전제는 F16 후보검색 배선(FABLE_REVIEW F16).
