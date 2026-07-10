# KNOWN ISSUES

> 인지된 결함 — 지금 고치지 않고 지정 단위에서 구현. 각 항목: 증상 / 원인 / 실측 / 해결 계획 / 검증.

## (나) 재인입 노드 중복 생성 + stale 큐  — 단위 5에서 구현

**증상**: 같은 doc_id를 재인입하면 (a) 노드가 **중복 생성**되고 (b) 그 문서가 남긴 **수정 큐 항목이 회수되지 않아 stale**로 쌓인다.

**원인**: `core/ingest.reinject()`가 명세 §5.5-3대로 doc_id의 provenance를 회수하면서 **살아있는(삭제 금지·evidence_lost) 노드의 사전(dictionary) 엔트리·alias까지 회수**한다. 그 결과 재인입 시 사전 조회가 미스 → 살아있는 노드를 못 찾고 **신규 생성(중복)**. 또한 `reinject`는 `review_queue`를 건드리지 않아(`queue.remove_doc` 미호출) 옛 항목이 남는다. 현재 재인입 회수 규칙이 "회수 대상"(그 문서 근거)과 "보존 대상"(살아있는 노드의 식별자=사전 엔트리)을 분리하지 못하는 것이 근본.

**실측(2026-07-10)**:
- CP01 1회 인입 후 `cathode 노칭 프레스` 노드 1개 → **CP01 재인입 후 2개**(사전 미스로 신규). `evidence_lost` 큐 28건.
- 이 중복이 극성 mirror 쌍을 데카르트곱으로 만들어, self-heal 도입 전엔 `mirror_asymmetry`가 1→4→6으로 폭증.
- (가) self-heal 도입 후 큐 항목은 (category, 극성제거 canonical) 그룹당 1건으로 dedup되어 **큐 폭증은 해소**(재인입→1 유지). 단, **중복 노드 자체는 그래프에 남는다**(이 이슈의 본체).
- 부작용: 대칭화 후 원본으로 되돌려도 재인입이 stale 노드(추가됐던 자식)를 삭제 안 해 union상 대칭으로 보임 → self-heal 역방향 복원이 (나) 해결 전엔 불성립(테스트 `test_mirror_selfheal` 주석 참조).

**해결 계획**: 명세 §5.5-3 재인입 회수 규칙을 **회수/보존/재평가로 분리**해 정밀화 —
1. **회수**: 그 doc_id의 provenance 항목(노드/엣지/alias/attribute/청크/describes)만 제거.
2. **보존**: provenance-0이 된 노드·그 canonical 사전 엔트리는 **삭제하지 말고 재매칭 가능한 상태로 유지**(evidence_lost 표시는 유지하되 사전에서 지우지 않음) → 재인입이 신규 대신 재매칭·provenance 복원.
3. **재평가**: 재인입은 그 doc_id의 기존 수정 큐 항목도 회수(`queue.remove_doc`) 후 재인입 결과로 재작성. 자동 규칙 큐(mirror_asymmetry)는 (가) self-heal이 이미 재평가.
- 재인입은 실운영(개정 문서)·수정 도구(단위 5) 영역이라 그 단위에서 함께 구현. 단위 1a~3(문서 1회 인입) 산출물·config-only 판정에는 영향 없음.

**검증(단위 5 구현 시)**: CP01 재인입 후 노드 수 불변(중복 0), 사전 재매칭으로 provenance 복원, 옛 큐 항목 회수, 대칭↔비대칭 왕복 self-heal 양방향 성립.

---

## (다) cross-layer 사실 이중 렌더 + raw id 노출  [중] — 검수 라운드2 신규

**증상**: 상위층(quality)에 링크되는 cross-layer 질의에서 같은 엣지가 **두 번**, 그중 하나는 dst가 canonical이 아닌 **node id**로 렌더된다. 실측 Q10("단락으로 이어질 불량"): `절연 파괴는 N0002 공정에서 발생한다`(깨짐) + `절연 파괴는 노칭 공정에서 발생한다`(정상)가 함께 출력.

**원인/위치**: `cli/query.py` `route()`의 per-layer 루프 `all_facts += query.graph_facts(scope, g, cfg)` — `graph_facts._canon`이 **단일 층 그래프(g)**만 조회하므로 cross-layer 엣지의 타 층 dst를 못 풀고 id를 그대로 문자열화. 반면 브리지 `_bridge`는 `_AllGraphsView`(전 층 노드 병합)로 전역 해소 → 정상 렌더. 두 경로가 같은 엣지를 각각 렌더 → 이중+불일치.

**영향**: 그래프 데이터는 정상, **라우터 렌더만** 문제. answer_path는 맞음. 단 뷰어가 그래프 사실을 그대로 표시하면 "N0002 공정" 같은 깨진 문자열이 사용자에게 노출.

**조치 방향(사람 결정)**: (a) per-layer `graph_facts` 호출도 전역 canonical 뷰(`_AllGraphsView`)로 렌더, 또는 (b) per-layer 사실에서 `cross_layer_traverse` 관계 엣지는 제외하고 브리지가 단독 소유(중복 제거). **플랫폼(시각화) 착수 전 권장** — 라우터 1곳 수정, core 무관.

**검증**: Q10 그래프 사실에 `N0002/N0003` 등 id 문자열 0건, occurs_in 사실이 canonical로 1회씩만.

## (라) 다중 occurs_in · 극성 잔존 공정(Process급) 미실증  [중·커버리지] — 검수 라운드2 신규

**증상**: 명세 §8-1 핵심 메커니즘 2개가 mock에서 실증되지 않음.
- **다중 occurs_in**("한 불량이 여러 공정에서 발생 → occurs_in 다중, '이 불량 유발 공정들' 질의의 답"): 실측상 **어떤 Failure도 occurs_in 2개+ 없음**. §6.1 R11이 지목한 실증자 `이물 유입`은 R3·R11 모두 *cause*라 occurs_in(=failure_mode 전용) 대상이 아니어서 0건.
- **극성 잔존 공정**(§5.2 ②, Process 레벨 극성 분기: cathode 탭용접/anode 탭용접 precedes 순차 + mirrors): 골격이 단일 `탭용접`이라 flow가 자명하게 단일 스트림 — Process급 극성 분기·mirrors·단일 스트림 규칙 미검증.

**원인**: 코드 능력은 있으나(같은 failure_mode가 2개 process_ref 행에 등장하면 다중 occurs_in 성립; skeleton.data에 극성 Process를 넣으면 분기) **mock 데이터가 두 경우를 안 만듦**.

**조치 방향(사람 결정)**: mock 보강 — (1) 한 failure_mode를 서로 다른 process_ref 2개 행에 배치(다중 occurs_in 실증), (2) 골격에 극성 잔존 공정 한 쌍 추가(예: cathode 탭용접/anode 탭용접). 코드 수정 불요일 가능성 높음(둘 다 config/mock). 단위 4/5 논의 시 함께.

**검증**: 다중 occurs_in Failure ≥1, Q("이 불량 유발 공정들") 응답에 2개 공정, 극성 Process 쌍 mirrors + flow 단일 스트림.

## (마) §3.6 명시적 실패 불완전(query traverse)  [하] — 검수 라운드2 신규

**증상**: config로 표현 안 되는 것이 "시끄럽게" 드러나야 하나(§3.6 탈출구), query traverse의 미지원 방향/패턴은 **silent**(빈 결과)로 넘어간다. skeleton.type은 raise(정상)지만 `graph.neighbors`/`query.expand`는 알 수 없는 direction을 만나면 매칭 0건 반환.

**원인/위치**: `core/graph.py` neighbors — `direction in ("out","both")`/`("in","both")` 미해당 시 아무것도 안 하고 통과. 명시적 실패 없음.

**조치 방향(사람 결정)**: neighbors/expand에서 config가 준 direction·recursive가 지원 집합 밖이면 raise("config 표현 밖 — core 패턴 추가 필요", §3.6). 저위험 소규모.

**검증**: 잘못된 direction config로 질의 시 raise + 메시지.

---

## 참고 — mock 한계(실물 검증 항목, 결함 아님)
- P8 "notching press"(영문): MOCK 문자열 정규화로 "노칭 프레스"와 매칭 불가 → 신규 생성. 실물 LLM 판정에서 해소(§6.3 P8).
