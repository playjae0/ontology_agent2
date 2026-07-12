# FABLE_REVIEW — 명세-코드 심층 정합 검수 (읽기·분석 전용)

> **반영 라운드 (2026-07-12, 명세 v1.12 마감 지시 기준)** — 처리 현황:
> - ✅ **반영 완료** (`tests/test_fable.py` 10건 + 기존 8개 테스트 전부 통과):
>   F1(골격 극성 alias — skeleton.plant 대칭 등재), F2(현 게이팅=§5.2 ③ **승인** — 코드 무변경, 주석만),
>   F3(mirrors ④ 같은 부모 — 공유 문맥 없는 쌍 보류), F4(Property canonical 부모 접두 —
>   config `canonical_scope` 구동, 부모=attach_to_field→@process_ref 폴백, 표면형 alias 등재),
>   F5-①(anchor Tier1 한정 + auto 후보 payload), F6(missing_field 큐 — §6.5 역방향),
>   F11(극성 이중 접두 방어), F12(링킹 단어 경계 — 왼쪽 글자연속 차단·오른쪽은 조사 허용),
>   F13(invalid_category 큐 + 생성 보류), F15 중 entity 리스트 큐·payload_kind raise,
>   F16 중 embeddings.py 생성(embed() 계약만).
> - ⏸ **이연 유지** (착수 금지 지시): (나)재인입, F7(브리지 청크), F8(flow 링킹0), F9(전역 상한),
>   F10(보강 큐), F14(동시성), F16 후보검색 본체, F15 잔여(chunk_id 중복 감시), F17(배선 체크리스트).
> - ⚠️ **주의**: docs/는 아직 v1.11 — v1.12 교체본이 레포에 없어 **지시문을 정본으로 구현**함.
>   문서 동기화 필요 목록은 PROGRESS.md 반영 라운드 절 참조.
>
> 대상: 명세 v1.11 / 정의서 v1.7 / 구현문서 v1.10, 커밋 `213785e` 기준 전 코드.
> 방법: 3문서·core 전 파일·config·스키마·mock·테스트 통독 + **재현 실험 11건**(스크래치 data_root, 코드·레포 데이터 무수정).
> 범위 규율: P7·§5.6.6·단위5 이연 항목(청크 임베딩·faiss·링킹 2단·성능·재인입 사전보존)은 결함으로 세지 않음.
> 기존 KNOWN_ISSUES (나)(다)(라)(마)·REVIEW_단위3과 겹치는 것은 참조만, **신규 발견만 상세**.
> 표기: 각 발견 = [심각도 / 파일:줄 / 명세 근거 / 재현·영향 / 제안 / 이연 여부].

## 0. 총평

구조 골격(role 5핸들러+edges 후처리, 2-pass, config 무가정 순회, cross-layer 단방향 저장, 채널 분리)은 명세대로 견고하다 — 라운드2 검수 결론을 재확인했다(core 층 어휘 0 재grep 포함). 새로 발견한 문제는 세 무리다:

1. **명세끼리 긴장하는 지점을 코드가 한쪽으로 조용히 해소한 곳** — 극성 게이팅의 판정 주체(F2), Property canonical 유일화(F4), 극성 결합 주체(파서 vs 에이전트, F11). 셋 다 "코드 버그"라기보다 **명세 마감 누락이 코드에 잠복**한 형태이며, 현 mock·테스트가 코드의 선택에 의존하고 있어 나중에 명세대로 "고치면" 테스트가 깨진다.
2. **명세가 시끄럽게 드러나라고 한 것이 조용히 넘어가는 곳** — 필수 필드 부재(F6), 비Tier1 anchor(F5), 닫힌 목록 밖 카테고리(F13). §3.6·§6.5의 "조용한 오염 금지" 철학과 정면 배치.
3. **검수 라운드2가 골격에 극성 공정을 넣으면서 생긴 회귀성 공백** — 극성 골격 노드의 표면형 alias 미공유(F1). **현 빌드에서 "탭용접" 질의·anchor가 이미 실패한다**(가장 사용자 가시적).

LLM 배선(축3)은 ARCHITECTURE.md §1의 감사가 정확했다. 단 하나 승격할 것: **후보검색 단계 부재(F16)는 "판정 함수 채우기"의 선결 조건**이라, 판정 지점은 "함수만 채우면 되는" 상태가 아니다.

## 요약표

| # | 심각도 | 축 | 제목 | 위치 |
|---|---|---|---|---|
| F1 | 중 | 정합 | 극성 골격 노드의 극성 제거 표면형 alias 미공유 — "탭용접" 질의·anchor 실패 | skeleton.py |
| F2 | 중 | 정합 | 극성 결합 게이팅의 판정 주체 불일치 — 걸침 Property는 절대 극성 결합 안 됨 | ingest.py |
| F3 | 중 | 정합 | mirrors 조건 ④(같은 부모) 미구현 + self-heal 키에 부모 부재 | ingest.py |
| F4 | 중 | 정합 | Property canonical 유일화(부모 접두) 부재 → 교차 설비 동명 인자 오병합 | ingest.py |
| F5 | 중 | 정합 | anchor가 Tier1 여부 미확인 + "후보검색+판정" 2단 생략 | ingest.py |
| F6 | 중 | 정합 | 인입 검증 반쪽 — 비optional 필드 부재가 완전 무음 | ingest.py |
| F7 | 중 | 정합 | 브리지 노드의 청크 미수집 — cross 질의 문서 근거 채널 공백 | cli/query.py |
| F12 | 중 | 엣지 | 링킹 substring 오탐 — 단어 경계 없음 | core/query.py |
| F13 | 중 | 엣지 | 닫힌 카테고리 목록 밖 category 무검증 노드 생성 | ingest.py |
| F16 | 중 | 배선 | 후보검색 부재 = 판정 LLM 배선의 선결 조건 미충족 (embeddings.py 미생성) | ingest/matcher |
| F8 | 하 | 정합 | flow 규칙 — 링킹 0 flow 질문에 골격 미공급 | cli/query.py |
| F9 | 하 | 정합 | 청크 수집 상한(8)이 층별 적용 — 전역 상한 아님 | cli/query.py |
| F10 | 하 | 정합 | 규칙B "보강 큐 기록"(구현문서 §6.2 C2) 미구현 | ingest.py |
| F11 | 하 | 정합 | 극성 이중 접두 무방어 + §5.2/§5.3 결합 주체 긴장 | ingest.py |
| F14 | 하 | 엣지 | id 발급 동시성·저장 원자성 없음 | graph.py/build.py |
| F15 | 하 | 엣지 | 파서 계약 위반 감시 공백 모음 | ingest.py 외 |
| F17 | 하 | 배선 | USE_MOCK 판정 완화·prompts placeholder 등 배선 체크리스트 | llm.py/config |

---

## 축1 — 명세-코드 심층 정합

### F1 [중] 극성 골격 노드가 극성 제거 표면형을 alias로 공유하지 않음 — "탭용접" 질의·anchor 실패

- **파일**: [core/skeleton.py:87-106](core/skeleton.py#L87-L106) `_ensure_node` — `dictionary.register(canonical, ...)`만 수행. [core/ingest.py:147-153](core/ingest.py#L147-L153) `_register`는 entity 경로에서 극성 제거 표면형을 alias 공유하지만, skeleton 경로에는 대응 코드가 없다.
- **명세 근거**: §5.2 "극성별 노드의 canonical은 극성 포함(사내 관행), **표면형(극성 제거)은 alias 공유**" — entity/골격 구분 없는 일반 규칙. §5.2 ② 극성 잔존 공정이 바로 골격(seed) 사례다.
- **재현** (현 골격 그대로, 3문서 인입 후):
  - `dic.lookup("탭용접")` → `[]`. `dic.lookup("cathode 탭용접")` → 정상.
  - 질의 `"탭용접 다음 공정은?"` → linked 0 → **general_knowledge**(근거 없음 처리). 골격에 있는 공정인데 못 찾는다.
  - `process_ref: "탭용접"`인 PFMEA 행 인입 → **orphan_anchor**. 실물 문서가 극성 무표기 공정명으로 좌표를 달면(극성은 electrode_type 열에 있는 것이 보통) 전부 orphan.
- **영향**: 검수 라운드2 (라-2) 조치로 골격이 `탭용접`→`cathode/anode 탭용접` 2노드가 되면서 생긴 회귀. queries.json에 탭용접 질의가 없어 테스트가 못 잡았다. 실물에서 극성 잔존 공정 관련 질의·좌표 태깅이 통째로 빠진다.
- **제안**: `skeleton.plant`가 극성 접두 노드에 대해 극성 제거 표면형을 사전·alias에 등재(entity 경로 `_register`와 대칭). alias 공유 시 lookup("탭용접")이 2노드를 반환하므로 anchor 다중 후보 처리(현재 exact→첫째)와 함께 검토 — 명세상 "탭용접" 단독 좌표가 어느 극성인지는 사람이 정할 문제라 orphan이 맞는지 양쪽 부착이 맞는지 §5.2에 한 줄 필요.
- **이연 여부**: 아님(P7 무관, 지금 범위).

### F2 [중] 극성 결합 게이팅의 판정 주체 — 명세(행 극성+카테고리) vs 코드(문서 층 config 보유 여부)

- **파일**: [core/ingest.py:265-273](core/ingest.py#L265-L273) `_polarity_for`가 **`ctx.config`(=인입 문서의 층 config)** 의 polarity 선언을 읽음. PFMEA는 quality 층이고 quality config에 polarity가 없으므로, 걸침 필드(control_item, target_layer=process)는 **행 극성이 cathode여도 절대 극성 결합되지 않는다**.
- **명세 근거**: §5.2 v1.7 "극성 결합 canonical은 ①category∈{Unit,Property} AND ②행의 electrode_type이 cathode/anode 확정일 때만 적용" — 문서 층 조건이 없다. 구현문서 §2.4(=pfmea.json 절)의 blocks 주석도 같은 게이팅을 **pfmea 문맥에서** 서술한다. 즉 문면대로면 PFMEA cathode 행의 Property는 결합 대상.
- **재현**: CP01 인입 후(무극성 `노칭 정밀도`=C1, `cathode 노칭 정밀도`=C8 공존 상태) PFMEA 행 `{electrode_type: cathode, control_item_for_cause: "노칭 정밀도"}` 인입 → controlled_by 대상 = **무극성 `노칭 정밀도`**. 행이 cathode라고 명시했고 cathode 전용 노드가 있는데도 극성 정보가 버려진다.
- **영향·맥락**: 이것은 단순 버그가 아니라 **명세 내부 긴장**이다 — 문면대로 구현하면 mock의 두 검증(C2 규칙B 보강: R1 cathode행 `금형 클리어런스`가 CP의 무극성 노드와 매칭 / R12 `노칭정밀도` 표기변형 매칭)이 깨진다. 즉 mock 설계 자체가 "PFMEA 걸침 필드는 비극성"을 전제하고, 코드는 그 전제가 성립하는 쪽(문서 층 게이팅)을 골랐다(PROGRESS 1c "config 확장 결정"에 기록됐으나 이 **의미론적 함의**는 미기록). 반대로 §5.2의 [사내 확인] 항목("control_item류가 실물에서 극성을 항상 명시하는지")은 이 긴장을 명세도 인지하고 있음을 보여준다.
- **제안**: 코드 수정이 아니라 **명세 §5.2 마감** — 게이팅 주체를 "행 극성 + **기록 대상 층**(target_layer) config의 polarity 선언"으로 할지 "행 극성 + 문서 층 config"로 할지 명문화. 전자를 택하면 mock C2/R12를 both 행으로 조정해야 함. 후자를 택하면 §5.2에 "걸침 필드는 문서 층이 극성 층이 아니면 비극성" 한 줄 추가 + 구현문서 §2.4 주석 위치 정정.
- **이연 여부**: 아님(명세 정합 사안). 단 결정은 사내 확인 항목과 묶는 것이 자연스러움.

### F3 [중] mirrors 자동 규칙 조건 ④(같은 부모/같은 precedes 위치) 미구현 — self-heal 키에도 부모 없음

- **파일**: [core/ingest.py:409-436](core/ingest.py#L409-L436) `apply_mirrors` — 그룹 키가 `(category, 극성제거 canonical)`뿐. 부모/precedes 위치 확인 없이 cathode×anode 데카르트로 mirrors 엣지 생성.
- **명세 근거**: §5.3 mirrors 자동 연결 규칙 "④ [Process면] 같은 precedes 위치 / [Unit·Property면] **같은 부모 부착**". §5.3 v1.11 self-heal "큐 항목은 (극성 제거 canonical, **부모**) 쌍 키로 dedup" — 코드 키는 부모 미포함.
- **재현**: `실링`의 `cathode 히터`와 `패키징`의 `anode 히터`(서로 다른 부모, CP 2행) 인입 → `cathode 히터 ↔ anode 히터` mirrors 엣지 생성 + mirror_asymmetry 큐(`only_a=[part_of→실링], only_b=[part_of→패키징]`) 오적재. `cathode 히터 온도 ↔ anode 히터 온도`(Property)도 동일.
- **영향**: 히터·컨베이어·센서류 범용 설비명이 여러 공정에 등장하는 실물에서 가짜 대칭 선언 + asymmetry 큐 오염. 현 mock은 이름이 전부 유일해서 잠복. F4(Property 동명 병합)와 결합하면 오염이 증폭된다.
- **제안**: 그룹 키에 부모 시그니처(part_of/attach 대상 id) 추가, Process는 precedes 위치 비교. 관계명은 이미 config에서 읽고 있어 §0-1 유지 가능.
- **이연 여부**: 아님(§5.3 확정 규칙의 미구현 부분).

### F4 [중] Property canonical 유일화(부모 접두) 부재 — 교차 설비 동명 인자 오병합·가짜 spec_conflict

- **파일**: [core/ingest.py:109](core/ingest.py#L109) `canonical = f"{polarity} {surface}" if polarity else surface` — 부모 접두 없음.
- **명세 근거**: 구현문서 §2.2 그래프 예시 N0031 canonical = `"cathode 노칭 프레스::노칭 정밀도"`(**부모 접두**). 명세 §5.2도 극성 Property에 "canonical 부모 접두"를 명시(v1.5 항목). 코드는 극성 접두만 구현.
- **재현**: `실러/온도(175~185C)`와 `파우치 성형기/온도(100~120C)` 2행 인입 → **`온도` Property 1노드**에 has_property 2개(실러·파우치 성형기), 두 번째 spec은 **spec_conflict 큐로 버려짐**(그래프에는 실러 값만 저장; incoming 값은 큐 payload에만 잔존).
- **영향**: 온도·압력·속도 같은 흔한 인자명에서 물리적으로 다른 항목이 병합 — §9 "오병합이 잘못된 신규보다 해롭다"의 정반대 방향으로 틀리는 구조. 또한 spec_conflict가 "극성 분리 신호"(§5.2)로 쓰이는 설계인데, 이런 가짜 충돌이 섞이면 신호가 오염된다.
- **제안**: 명세 결정 필요 — Property canonical 규칙(항상 부모 접두? 극성 시만? 충돌 시만?)이 명세 §5.2(극성 케이스만)·구현문서 §2.2(예시상 항상)·코드(안 함) 셋이 다르다. mock에 동명 교차 인자 케이스 추가 권장.
- **이연 여부**: 아님(구현문서 자기 예시와 불일치). 단, "부모 접두 없이 병합 → spec_conflict → node split" 흐름을 **의도된 자동커밋+사후수정**으로 재해석해 명세에 못박는 선택지도 있음(그 경우 구현문서 §2.2 예시를 수정).

### F5 [중] anchor 해소가 Tier1을 확인하지 않고, "후보검색+판정" 2단이 없음

- **파일**: [core/ingest.py:83-99](core/ingest.py#L83-L99) `handle_anchor` — `dic.lookup` 정확(정규화) 일치 → category 필터 → 끝. status/provenance(seed) 무확인, matcher 폴백 없음.
- **명세 근거**: 정의서 §3.1 "이미 존재하는 **골격 노드**… 사람이 보증한 Tier1 노드면 anchor 대상 / 미스 시 **후보검색+판정** → 그래도 미해소면 orphan_anchor". 구현문서 §3 ingest 항목도 "anchor 미스 → 후보검색+판정 → 실패 시 큐".
- **재현**: prose가 `레이저노칭`을 Process로 언급(추출 시뮬) → auto Process 노드 생성·사전 등재. 이후 `process_ref: "레이저노칭"` PFMEA 인입 → **auto 노드에 anchor 성립, occurs_in 생성, orphan_anchor 0건**. (본 mock R13에서는 orphan이었던 것이, 아무 prose가 그 이름을 스치면 조용히 "골격"이 된다.)
- **영향**: P2(골격=사람 고정)의 우회로. auto Process가 좌표가 되면 이후 문서들이 그 위에 쌓여, 사람이 나중에 그 노드를 정리할 때 부착물이 연쇄로 걸린다. 2단 생략은 실물에서 표기 변형 anchor("노칭 공정" vs "노칭")를 전부 orphan으로 보냄 — MOCK 정규화가 잡는 범위 밖은 전멸.
- **제안**: ①anchor 후보를 status=confirmed(또는 provenance에 seed)로 제한 — auto 후보만 있으면 orphan_anchor로 (payload에 auto 후보 id를 실어 사람 판단 재료 제공). ②2단(판정 폴백)은 F16(후보검색)·축3 배선과 함께.
- **이연 여부**: ①은 아님. ②는 판정 LLM 배선(국면2-5)과 동시 착수가 자연스러움.

### F6 [중] 인입 검증 반쪽 — 스키마에 있는데 레코드에 없는 비optional 필드가 완전 무음

- **파일**: [core/ingest.py:343-349](core/ingest.py#L343-L349) `_validate_record` — unknown_field 방향만 구현. 역방향(부재 필드의 optional 검사) 없음. 빈 process_ref도 [handle_anchor:85](core/ingest.py#L85)가 조용히 None.
- **명세 근거**: §6.5 "레코드에 스키마에 없는 필드 등장 → unknown_field … **스키마에 있는데 레코드에 없음 → optional 검사**. 어긋남이 조용한 오염 대신 큐에 시끄럽게 나타난다."
- **재현**: ①failure_mode 없는 PFMEA 행 → 큐 0건(auto_node 외), causes/affects/occurs_in 전부 무음 생략. ②process_ref 없는 행 → Failure 노드는 생기고 occurs_in만 조용히 드롭, orphan_anchor 0건 — §8-1 "앵커 미스=orphan 큐 보유"가 **빈 값 미스에는 작동 안 함**(값이 있으나 골격에 없을 때만 orphan).
- **영향**: 파서 결함(병합 셀 전개 실패, 빈 셀)이 조용한 지식 누락으로. §12 파서 계약의 감시 체계가 절반만 있는 셈.
- **제안**: `_validate_record`에 "필드가 스키마에 있고 optional이 아닌데 부재/빈 값 → 큐" 추가. 큐 kind는 §2.3 표준 목록에 없으므로(예: `missing_field`) **명세 §2.3/§6.5 갱신 동반** — QUEUE_KINDS(store.py:16)는 경고만 하므로 코드는 돌지만 계약을 어기게 됨.
- **이연 여부**: 아님(§6.5 확정 문면).

### F7 [중] cross-layer 브리지가 사실만 가져오고 청크는 안 가져옴 — 문서 근거 채널 공백

- **파일**: [cli/query.py:130-145](cli/query.py#L130-L145) `_bridge` — graph_facts만 합류. bridged 노드는 `collect_chunks` 어디에도 안 들어감.
- **명세 근거**: §8-6 "노이즈는 채널 분리 + **청크 tier2 잘림**(§5.6.3)으로 통제" — 브리지로 딸려온 노드의 청크가 tier2로 수집됨을 전제한 문장. §8-R1 "그래프 사실+**문서 근거** 합성". 구현문서 단계3 "Q1~8 회귀: **브리지로 딸려온 Failure 청크**·노드에 오염 안 됨" — 실제로는 청크가 아예 안 딸려오므로 이 회귀는 자명하게 통과(검증력 없음).
- **재현**: Q9 "노칭에서 발생할 수 있는 불량은?" → chunk_ids = PPT01·CP01 것만, **PFMEA 청크 0건**. 절연 파괴의 detection_control("절연 저항을 측정한다") 등 서술 근거가 답변 재료에 없다.
- **영향**: cross 질의가 그래프 사실 단채널 — §5.6.4가 경계한 "단채널이면 못 답하는" 문제의 거울상(서술 질문 쪽이 빈다). "노칭 불량은 어떻게 검출해?" 류 Q1×cross 질문에서 근거 부족.
- **제안**: `_bridge`가 bridged id 집합을 반환하고 라우터가 tier2로 `collect_chunks`에 합류(상한·잘림은 기존 규칙 재사용). §8-6의 노이즈 통제 문면과 정확히 일치하게 됨.
- **이연 여부**: 아님(§8-6은 v1.2에서 이연 해소된 확정 사항).

### F8 [하] flow 규칙 — "특정 노드에 안 걸리는" flow 질문이 골격을 못 받음

- **파일**: [cli/query.py:38-42](cli/query.py#L38-L42) `classify` — `linked_count == 0`이면 flow 검사 전에 general_knowledge로 확정.
- **명세 근거**: §5.6.4 flow 질의 규칙 "**특정 노드에 안 걸리고** 공정 전반을 묻는 패턴 → 골격 트리+precedes 체인 통째 공급".
- **재현**: `"전체 공정 흐름 설명해줘"` → linked 0 → general_knowledge, 사실 0건. `"조립 전체 공정 흐름 설명해줘"` → flow, 사실 71건. mock #5는 "조립"이 링킹돼 통과할 뿐.
- **영향**: 명세가 정의한 flow의 대표 케이스(무링킹 전역 질문)가 미지원. MOCK 분류기 한계이기도 하나, 실물 답변 LLM 채널 선택으로 넘어가도 "링킹 0 → 즉시 일반지식" 구조는 라우터에 남는다.
- **제안**: flow 패턴 감지를 linked 검사보다 먼저. 실물 배선 시 채널 선택을 LLM에 넘기더라도 flow 스코프 공급 훅은 라우터가 소유해야 함(§5.6.4).
- **이연 여부**: 아님.

### F9 [하] 청크 수집 상한(8)이 층별 적용

- **파일**: [cli/query.py:67-78](cli/query.py#L67-L78) — per-layer 루프 안에서 `collect_chunks(cap=8)` 후 `all_chunks +=`.
- **명세 근거**: §5.6.3 "상한 8(측정 후 조정)" — 전역 상한으로 읽힘.
- **영향**: 2층 링킹 질의에서 최대 16. 현 mock 무해. 잘림률 계기판(§10-4)도 층별로 측정돼 왜곡 소지.
- **제안**: 합성 후 전역 cap 적용, 또는 명세에 "층별 상한"으로 명문화(한 줄).
- **이연 여부**: 아님(경미 정합).

### F10 [하] 규칙B "보강 큐 기록"(구현문서 §6.2 C2) 미구현

- **파일**: [core/ingest.py:224-250](core/ingest.py#L224-L250) `attach_entity` / `_make_edges` — 저해상도(공정) 부착과 정밀(설비) 부착이 공존하게 될 때 어떤 큐도 안 남김.
- **명세 근거**: 구현문서 §6.2 C2 "R1이 공정에 부착한 auto Property가 설비 소속으로 정밀화(has_property 추가+**큐 기록**)". 명세 §15.7 규칙B "CP가 더 정밀한 소속을 주면 **수정 큐**/재해소로 보강".
- **영향**: `노칭 has_property 금형 클리어런스`(저해상도)와 `노칭 프레스 has_property 금형 클리어런스`(정밀)가 영구 공존하는데 사람이 큐에서 볼 수 없음 — 단위5 수정 도구가 저해상도 엣지를 정리할 단서 부재. test_3은 공존만 확인.
- **제안**: 정밀 부착 발생 시(같은 Property에 Unit has_property가 새로 생기고 Process has_property가 이미 있음) 큐 기록. 단위5와 묶어도 됨 — 그 경우 KNOWN_ISSUES에 이관 명시.
- **이연 여부**: 경계선 — 구현문서 단계1c 판정엔 없고 §6.2 문면에만 있어, 단위5 이관이 합리적. 다만 "미구현" 사실은 기록돼야 함.

### F11 [하] 극성 이중 접두 무방어 — §5.2(에이전트 결합) vs §5.3(파서가 canonical에 담음) 긴장

- **파일**: [core/ingest.py:109](core/ingest.py#L109) — 게이팅 통과 시 무조건 `f"{polarity} {surface}"`.
- **명세 근거**: §5.2 entity 해소 규칙은 에이전트가 결합. §5.3 mirrors ③ 주석은 "**파서가 극성을 canonical에 담아주므로** 결정적" — 결합 주체가 두 절에서 다르게 읽힘.
- **재현**: `설비: "cathode 노칭 프레스"` + `electrode_type: cathode` 행 → canonical `"cathode cathode 노칭 프레스"` 노드 생성(별도 노드로 분화, mirrors도 오작동 대상).
- **제안**: 파서 계약 §12에 "표면형에 극성 미결합(극성은 electrode_type로만)"을 명시하거나, handle_entity에 `surface.startswith(polarity+" ")` 방어 1줄. 명세 §5.3 주석 문구 정정.
- **이연 여부**: 아님(계약 명문화 사안).

---

## 축2 — 엣지 케이스

### F12 [중] 링킹 substring 오탐 — 단어 경계 없음

- **파일**: [core/query.py:31-40](core/query.py#L31-L40) `link` — `surf in remaining` 원문 부분문자열 매칭.
- **명세 근거**: §5.6.1 1단(표면형 스캔, 긴 것 우선)은 준수. 오탐 가능성은 명세가 상정 안 한 입력.
- **재현**: `"레이저노칭 공정에서 발생할 수 있는 불량은?"` → **`노칭`에 오링킹** → answer_path=graph_fact로 **노칭의 불량들을 자신 있게 답함**(레이저노칭은 그래프에 없는데). 등록 안 된 개체명이 등록된 것을 부분문자열로 포함하기만 하면 재현.
- **영향**: 3단 규칙 ⑵(모른다고 말하기)가 작동해야 할 질문이 ⑴(확신 답변)로 새는 오답 경로 — 일반지식 오염보다 나쁨(시스템 보증 채널로 나감).
- **제안**: 이연 항목 아님(임베딩 불요) — 최소 방어로 (a) 매칭 표면형 좌우가 한글·영숫자와 연속이면 제외(단어 경계 근사), 또는 (b) 미링킹 잔여 토큰이 등록 표면형을 포함-초과하면 링킹 신뢰 하향 + 답변 3단 ⑵ 폴백. 실물 2단(LLM 언급 추출)이 생겨도 1단이 먼저 발화하므로 남는 문제.

### F13 [중] 닫힌 카테고리 목록 밖 category — 무검증 노드 생성

- **파일**: [core/ingest.py:324-339](core/ingest.py#L324-L339) `ingest_prose` — `m["category"]`를 검증 없이 spec으로 사용. table 경로도 schema의 category를 config.categories와 대조하지 않음.
- **명세 근거**: §7-1 "카테고리는 config의 닫힌 목록+정의문에서 선택, **목록 밖 발명은 구조적으로 차단**" — 현재 차단이 프롬프트(값)에만 위임되고 코드 안전망이 없음. §5.4의 "추출-판정 카테고리 안전망"은 matcher에 있으나(§0-1 카테고리 불일치 match 금지), 목록 밖 카테고리는 후보 0 → 그냥 신규 생성으로 흐른다.
- **재현**: mock_mentions에 `{"surface": "만능 검사기", "category": "Equipment"}` → **category="Equipment" 노드가 process 층에 생성**, 큐는 auto_node뿐(카테고리 이상 신호 없음).
- **영향**: 실물 추출 LLM은 목록 밖 문자열을 낼 수 있다(프롬프트는 확률적 방어). 목록 밖 카테고리 노드는 query_traverse·category_pair_map 어디에도 안 걸려 유령이 됨. 스키마 오타(table)도 동일 경로.
- **제안**: handle_entity(또는 ingest_prose/스키마 로드 시점)에서 category ∉ config.categories → 큐 + 생성 보류(또는 생성하되 별도 kind). 축3 배선 전 필수 안전망.

### F14 [하] id 발급 동시성·저장 원자성 없음

- **파일**: [core/graph.py:32-48](core/graph.py#L32-L48) IdSeq(파일 읽고 메모리 증가, save는 마지막) / [core/build.py:55-61](core/build.py#L55-L61) Stores.save(graphs→ids→dic→queue→chunks 순 전체 재기록).
- **명세 근거**: §8-R3 id 전역 유일. 단일 프로세스 직렬 실행 전제는 어느 문서에도 명문화 안 됨. 단위4(플랫폼 subprocess 호출)에서 병렬 build가 자연 발생 가능.
- **재현**: 같은 data_root에 Stores 2개 생성 → 양쪽 `allocate()` → **동일 id(N0013) 발급**. 또한 save 도중 중단 시 graph에는 새 id가 있는데 id_seq.json은 옛값 → 다음 빌드가 같은 id 재발급(P4 위반).
- **제안**: 지금은 "build는 직렬" 계약을 BLOCKERS/구현문서에 명문화(한 줄). 파일 락·원자적 쓰기(tmp+rename)는 단위4 전 결정. 성능 이연(P7)과 별개로 **계약 명시는 무비용**.
- **이연 여부**: 락 구현은 단위4 성격. 계약 명문화는 지금.

### F15 [하] 파서 계약 위반 감시 공백 모음 (§12 자기완결 계약)

코드 근거 기반(개별 재현 생략), 전부 무음 처리:
- **entity 리스트 값**: 파서가 전개 안 하고 `["A","B"]`를 주면 [ingest.py:107](core/ingest.py#L107) `str(value)` → canonical `"['A', 'B']"` 노드 생성. 정의서 §3.4 "핸들러는 단일 값만 본다"의 전제 위반이 감지 안 됨 → isinstance(list) 시 큐 권장.
- **chunk_id 전역 중복**: [store.py:44](core/store.py#L44) dict 키 덮어쓰기 — 문서 간 chunk_id 충돌 시 선행 문서 청크가 조용히 소실(remove_doc은 doc_id로 걸러 부분 방어). 계약상 chunk_id 유일성 검사 없음.
- **payload_kind 부재/오타**: [build.py:97](core/build.py#L97) prose가 아니면 전부 table 경로 → records 없으면 0건 인입 "성공". 미지원 payload_kind는 §3.6 명시적 실패 대상이 되는 게 정합.
- **제안**: 인입 검증(F6)과 한 묶음으로 — "계약 위반은 큐에 시끄럽게"의 잔여 구멍들.

### 기존과 동일 (신규 아님, 참조만)

- **재인입 중복 노드·stale 큐** — 기존 **(나)** 와 동일(단위5, 명세 §5.5-3 ②③). 본 검수에서 재확인만.
- **선형 스캔·전량 재기록·_AllGraphsView 병합 비용** — REVIEW_단위3 E3와 동일, **P7 이연** 성격 유지.
- **P8 영문 표기 MOCK 한계** — 기존 참고 항목과 동일. 단 실물 전환 시에도 후보검색 부재(F16) 때문에 해소 안 됨 — F16 참조.

---

## 축3 — LLM 배선 가능성

ARCHITECTURE.md §1의 감사 결과를 코드로 재검증했고 **표의 판정(추출=함수만/판정=config 주입 필요/답변=소규모 신설, call_gateway payload 사내 스펙 맞춤)은 정확하다**. 아래는 그 위에 얹는 신규·승격 사항만.

### F16 [중] "후보검색" 단계 부재 — 판정 LLM 배선의 선결 조건 미충족

- **파일**: [core/ingest.py:113-119](core/ingest.py#L113-L119) — 판정 후보 = `dic.lookup(canonical)` 즉 **정규화(공백 제거·소문자) 완전 일치**뿐. [core/matcher.py:37](core/matcher.py#L37)의 포함 관계(0.90) 분기는 후보가 이미 완전 일치라서 **도달 불가능한 코드**다. anchor(F5)도 동일 구조.
- **명세 근거**: §7-1 "①사전 조회 → ②**후보 검색** → ③LLM 동일성 판정" 3단 — ②가 없다. §5.6.6(a) "판정용 노드 임베딩 — **core에 판정용으로 존재**"라고 명세가 이연 안전성의 전제로 명시했으나, `core/embeddings.py`는 **구현문서 §1 파일트리·§8 USE_MOCK 정의(sha256 해시)에 있는데 파일 자체가 없다**. §5.6.6이 이연한 것은 (b) 청크 인덱스(하이브리드 서치)뿐 — (a)는 이연 항목이 아니다.
- **영향**: 이 상태에서 `_llm_match`만 채우면 판정 LLM은 **자명한 후보만 받는다** — 정규화로 못 잡는 모든 표기 변형("노칭 정밀"·오탈자·한영 혼용)은 후보 0 → 판정 없이 신규 생성. §5.4-2의 비대칭 판정(match/uncertain)·동의어 사전 성장(§7-5) 메커니즘이 실물에서 공회전한다. P8(notching press)이 "실물 LLM 판정에서 해소"(BLOCKERS 참고 항목)라는 기대도 **후보검색 없이는 성립하지 않는다** — lookup("notchingpress")은 "노칭 프레스"를 반환하지 못하므로 판정 LLM에게 갈 후보가 없다.
- **판정**: 추출·답변과 달리 판정 지점은 "함수만 채우면 되는" 상태가 **아니다**. 필요한 것: ①embeddings.py 생성(구현문서 §8 정의대로 MOCK=해시), ②handle_entity/handle_anchor의 후보 수집을 사전 정확 일치 + 임베딩 top-k(전 노드 canonical+정의문, §5.6.6(a) 비저장·재생성)로 확장, ③matcher에 config 주입(ARCHITECTURE 1.2 기존 지적). ②는 core 수정이지만 층 어휘 없는 범용 확장이라 §0-1·config-only 성질은 유지된다.
- **이연 여부**: **아님** — 구현문서 파일트리 명시물의 부재이자 명세 3단 구조의 미구현. (청크 임베딩·faiss와 혼동 주의: 그쪽은 이연 맞음.)

### F17 [하] 배선 체크리스트 잔여 (ARCHITECTURE 미기재분)

- **USE_MOCK 판정**: [llm.py:16](core/llm.py#L16) `!= "0"` — `USE_MOCK=false`·`no`도 mock으로 돎. 사내 배선 시 "실물로 바꿨는데 mock이 도는" footgun. 파싱 엄격화 또는 README 명시.
- **prompts가 placeholder**: 양 층 config의 `prompts.extract/judge`가 실제 프롬프트가 아니라 `"(명세 §5.4-1 규칙 — …)"` 요약 문자열. 배선 시 **정의문 3종 삽입·비대칭 기준을 포함한 실프롬프트로 교체**해야 하며, 이는 B(config 값)라 코드 0 — 단 "프롬프트 조립"(categories dict → 정의문 블록 렌더) 코드는 extract_mentions/_llm_match 함수 몸통에 들어가야 함(현재 조립 코드 0줄).
- **추출 응답 검증**: 실물 추출이 돌기 시작하면 F13(목록 밖 category)이 즉시 유효한 공격면 — 파싱 직후 `category in config.categories` 검증이 계약상 필요(§7-1 "구조적 차단"의 코드 반쪽).
- **general_knowledge 경로의 등록 개체 안내**: [cli/query.py:150-156](cli/query.py#L150-L156) — linked가 비면 안내도 빔. 명세 ⑵의 안내("혹시 노칭·스태킹 중…")는 **미링킹** 상황용이므로, 실물 배선 시 근사 후보(F16의 후보검색 재사용) 공급 훅이 여기 필요.
- **재확인**: 링킹 2단 미배선·`classify` 휴리스틱의 실물 대체 지점은 ARCHITECTURE 1.3 기재와 동일 — 중복 생략.

---

## 정합 확인됨 (문제 없음을 확인한 항목)

- **§0-1 core 층 어휘 0**: 재grep — 기능 코드에 층 카테고리·관계·개체명 리터럴 0건(주석·docstring 제외). polarity·mirrors.relation의 config 하강도 §0-1·§3.6 정합.
- **2-pass·Failure 병합·causes 사슬·다중 occurs_in·R13 연쇄 드롭**: test_3·test_review2 그대로 재확인.
- **맥락형 attribute**: context 상속(record>봉투)·그룹 내 deep-equal·병렬 항목·provenance 전수(§0-5) — 코드·명세 일치.
- **재인입 회수 ①(청크·describes·엣지 prov·attr 항목)·evidence_lost 대칭·툼스톤 skip**: §5.5-3 문면대로(②③은 기존 (나) 계획대로 단위5).
- **채널 분리 (다)·명시적 실패 (마)·극성 잔존 공정 (라-2)**: 라운드2 조치 유지 확인(단 (라-2)의 잔여 공백이 F1).
- **neighbors 재귀의 순환 안전성**: visited 집합으로 part_of/causes 순환 데이터에도 무한루프 없음(확인).
- **cross-layer 저장 방향**: `_make_edges`가 src 소유 그래프에 저장 — §8-4(상위층 저장) 정합.

## 권고 우선순위 (사람 결정용)

1. **지금 (코드 소규모·명세 무변경)**: F1(골격 극성 alias), F6(+F15 인입 검증), F13(카테고리 검증), F5-①(anchor Tier1), F12(링킹 경계 방어).
2. **명세 마감 후 (문면 결정이 선행)**: F2(게이팅 주체), F4(Property canonical 규칙), F3(mirrors ④ — 규칙은 확정이므로 사실상 1군에 가까움), F11(극성 결합 주체·파서 계약).
3. **배선 착수 시**: F16(embeddings.py+후보검색) → matcher config 주입 → 프롬프트 실채움(F17) → F5-②(anchor 판정 폴백).
4. **단위4/5로**: F14(동시성 계약), F10(보강 큐), F7·F8·F9(질의 합성 — 단위4 뷰어 전이 자연스러움), 기존 (나).

---
_생성: Fable 검수 (읽기·분석 전용, 코드 무수정). 재현 실험은 스크래치 data_root에서 수행 — 레포 data/·코드 무영향. 모든 발견은 코드 근거·재현 절차 포함, "미확인" 항목 없음._
