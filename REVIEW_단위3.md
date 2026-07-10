# REVIEW — 단위 1a~3 완료 후 검수 (플랫폼 착수 전)

> 읽기·보고 전용 검수. 근거는 실제 grep·그래프 덤프·질의 출력. 대상 문서: 명세 v1.11 / 정의서 v1.7 / 구현문서 v1.10.
> 결론 요약: **구조·범용성·그래프 무결성은 견고**(우연이 아니라 설계대로 동작). 질의 답 내용도 대체로 정확하나
> **cross-layer 사실 렌더 버그 1건(중간)** 발견. mock 커버리지 공백 2건. 플랫폼 붙이기 전 (다) 렌더 버그만 고치면 시각화 가도 됨.

---

## A. 프로젝트 구조

### A1. 레포 트리 (핵심)
```
core/                    A층 — 층 어휘 0. config 순회 파이프라인
  graph.py               IdSeq(전역 id)·Graph(add_node/edge/neighbors/save/load)·init_data_tree
  dictionary.py          전 층 공유 동의어 사전(register/lookup/normalize)
  matcher.py             개체 판정(MOCK 정규화 규칙 + 카테고리 안전망)
  llm.py                 게이트웨이/추출 USE_MOCK 분기(실물 경로는 raise)
  store.py               ChunkStore·ReviewQueue(수정 큐, remove/by_kind)
  ingest.py              role 5핸들러+edges 후처리+검증+attach_entity+apply_mirrors(self-heal)+reinject
  build.py               스키마 블록조립·범용 쓰기 파이프라인(plant_skeletons /build_doc/Stores)
  skeleton.py            범용 골격(tree|flat), 미지원 type→raise
  query.py               읽기 파이프라인(link·expand·collect·graph_facts·flow_scope)
router.py                층 폴더 자동 발견(등록 코드 없음)
layers/<층>/config.json  B — 층별 값만(코드 0). process·quality
schemas/                 doc_type 스키마 + blocks(common_core·process_coord), cp·pfmea·ppt
cli/                     build.py(--init/인입)·query.py(단일 라우터+classify+compose+bridge)
mock/parsed/             CP01·PPT01·PFMEA01, queries.json
tests/                   test_1a·1b·1c·1d·2·3·mirror_selfheal (7개 전부 통과)
data/                    산출물(gitignore) — 진실 그래프·사전·청크·큐
docs/                    명세 v1.11·정의서 v1.7·구현문서 v1.10·착수프롬프트
PROGRESS.md BLOCKERS.md KNOWN_ISSUES.md
```

### A2. 관리 문서 요지
- **PROGRESS.md**: 셋업→단위 1a~3 완료(각 테스트 결과·비자명 결정 기록)·검수 라운드1(mirror self-heal) 반영. config-only 확증 성공(`git diff core/` 빈 것).
- **BLOCKERS.md**: 단위 4(플랫폼 — 기존 platform 구조/개조 범위 미상)·5(수정 도구 — 명세 ② 미마감) 착수 보류. §9.4 추측 금지로 정지, 사람 결정 대기.
- **KNOWN_ISSUES.md**: (나) 재인입 노드 중복+stale 큐 — 명세 v1.11 §5.5-3에 3분류(회수/보존/재평가)로 정식 반영, 단위5 구현. (+본 검수 신규 항목은 아래 E·KNOWN_ISSUES 추가.)

### A3. 세 문서 반영 대조 (요지)
| 스펙 | 반영 | 근거 |
|---|---|---|
| §3 범용성(A/B/C, config-only) | ✅ | `git diff core/` 빈 것, layers/quality=config만 |
| §3.6 명시적 실패 | ⚠️ 부분 | skeleton.type raise만, query traverse 방향은 silent (E-마) |
| §5.2 골격(가변깊이·극성 결합) | ✅ leaf / ⚠️ 극성 잔존 공정 미실증 | C8/C9 극성 Unit/Property ✓, Process급 극성분기(탭용접) mock 없음 |
| §5.3 관계·mirrors self-heal(v1.11) | ✅ | apply_mirrors 매 build 재평가·쌍 dedup·해소 시 제거(test_mirror_selfheal) |
| §5.5 쓰기(2-pass·임계 0.85·재인입) | ✅ / ⚠️ 재인입은 (나) | ingest 2-pass, reinject 존재하나 사전보존 미구현(단위5) |
| §5.6 읽기 4단·이원 채널 | ✅ / ⚠️ cross-layer 렌더 | link·expand·collect·graph_facts, but E-다 |
| §6 role 5종+edges | ✅ | HANDLERS 5 + _make_edges 후처리 |
| §8 층간 연결·cross-layer 브리지 | ✅ / ⚠️ 다중 occurs_in 미실증 | occurs_in/affects/controlled_by 저장·질의 O, §8-1 다중 occurs_in 없음(E-라) |
| §15 품질층 여섯 칸 | ✅ | quality config+pfmea 스키마, causes 사슬·규칙A/B |
| 단위 4 플랫폼 / 5 수정도구 | ❌ 미착수 | BLOCKERS 기록, 별도 논의 |

---

## B. core §3.6 범용성 (구조 검증 — grep 근거)

- **B1 층 어휘 0**: `grep -rnE "['\"](Process|Unit|Property|Failure|part_of|has_property|causes|occurs_in|cathode|anode|노칭…)['\"]" core/` → **그래프 어휘 리터럴 0건**. 유일 히트 `mirrors`는 `config.get("mirrors")` 접근·로그·함수명뿐(관계명은 `config.mirrors.relation`에서 읽음). §0-1 준수.
- **B2 하드코딩 분기 0**: `== "Process"`류 0건, `len(relations)==3`·특정 카테고리 분기 0건. build/query/skeleton은 config 리스트/딕셔너리를 순회만.
- **B3 layers/quality/ 코드 0**: `find layers/quality -type f` → `config.json` 하나뿐.
- **B4 명시적 실패**: skeleton.py:34 `type` 미지원 raise(§3.6 탈출구 ✓), skeleton canonical 중복(§5.2), dictionary provenance 필수, build.py:88 layer 미발견, llm 실물경로. **단, query traverse의 미지원 방향/패턴은 raise 없이 silent**(neighbors가 매칭 0건 반환) → §3.6 탈출구 불완전(E-마).

**판정**: core는 "가정을 안 하는 순회기"로 실제 구현됨. config-only는 우연이 아니라 구조적.

---

## C. 그래프 무결성 (결과 검증 — 덤프)

- **C1-a 노칭 이웃**: part_of→조립, precedes→스태킹, part_of← {노칭 프레스, cathode/anode 노칭 프레스, notching press}, has_property→ {노칭 정밀도, 금형 클리어런스, 타발 속도, 이물 검출 감도}. (금형클리어런스·타발속도·이물검출감도는 PFMEA 규칙B 공정부착, 노칭정밀도는 R12 규칙B.) 정상.
- **C1-b 극성**: `cathode 노칭 프레스`(N0021, et=cathode)·`anode 노칭 프레스`(N0023, et=anode) 별도 노드, mirrors 2건(Unit 쌍 + Property 쌍), status=auto prov=auto:mirror_rule. 극성 결합 canonical·표면형 alias 공유 정상.
- **C1-c 이물 유입** ⚠️: causes→{절연 파괴, 밀봉 불량}, controlled_by→이물 검출 감도. **occurs_in 0건**. causes 사슬 `이물 유입→절연 파괴→내부 단락` 성립(절연 파괴=R3 fm=R4 cause 병합 확인). **그러나 명세 §8-1·§6.1 R11이 주장하는 "이물 유입 노칭·실링 양쪽 occurs_in"은 실현 안 됨** — 이물 유입은 두 행 모두 *cause*라 schema상 occurs_in(=failure_mode 전용) 대상 아님. **어떤 Failure도 다중 occurs_in 없음**(E-라).
- **C2 맥락형 attribute** ✅: `적층 정렬도.attrs.spec = [{context:{model:M1}, value:{…max:0.2}, prov:[CP01-C3]}, {context:{model:M2}, value:{…max:0.25}, prov:[CP01-C7]}]`. C7(M2)이 C3(M1)와 **충돌 없이 병렬**, C4(M1 다른 값)만 spec_conflict. 정의서 §3.3 정확 구현.
- **C3 큐 47건**: auto_node 42 / mirror_asymmetry 1 / orphan_anchor 2(셀 부풀음·레이저노칭) / spec_conflict 1(C4=N0016 적층정렬도) / unknown_field 1(비고). 비-auto 전수 확인 정상. (mirror_asymmetry doc_id가 PFMEA01=마지막 build로 표기 — 발원 CP01 아님, self-heal 재작성 특성. payload.base로 추적 가능, 경미.)
- **C4 provenance(§0-5)** ✅: 노드·엣지·attribute·alias·사전 **누락 0건**. status: process 7 confirmed(seed)+22 auto, quality 4 confirmed(FailureEffect)+20 auto.

**판정**: 그래프는 설계대로 구축됨. 극성·병합·맥락·규칙A/B·provenance 전부 실측 확인.

---

## E. 종합 판정

### E1. 어긋나거나 의심스러운 지점 (심각도 순)

> **조치 완료(검수 라운드2)**: 1(다)·2·3(라)·4(마)는 코드+mock+테스트로 **해결**(8개 테스트 통과, KNOWN_ISSUES 해결 표시). (나) 재인입만 단위 5 유지. 5·6은 설계/문서화된 MOCK 한계라 조치 불요. (라-2 극성 잔존 공정은 config-only 표현 밖이라 core 보강 2건 수반 — KNOWN_ISSUES (라) 참조.)

1. **[중] ✅해결 cross-layer 사실 이중 렌더 + raw id** — `cli/query.py` route()의 per-layer `all_facts += query.graph_facts(scope, g, cfg)`가 단일 층 그래프만 봐서, cross-layer 엣지(occurs_in 등)의 타 층 dst를 canonical이 아닌 **node id로 렌더**. 브리지(`_bridge`)는 `_AllGraphsView`로 전역 해소 → 같은 엣지가 **id버전+canonical버전 이중** 출력. 실측 Q10: "절연 파괴는 **N0002** 공정에서 발생한다" + "절연 파괴는 **노칭** 공정에서 발생한다". 상위층에 링크되는 질의(Q10형)에서 사용자에게 깨진 사실 노출. **그래프 데이터는 정상 — 라우터 렌더만 문제.** → KNOWN_ISSUES (다).
2. **[중·커버리지] 다중 occurs_in 미실증** — §8-1 핵심 메커니즘("이 불량 유발 공정들" 질의)이 mock에서 0. 코드엔 다중 occurs_in 능력 있으나(같은 failure_mode가 2개 공정에 등장하면 성립) 어떤 mock 행도 안 만듦. 지목된 실증자 이물 유입은 cause라 불가. → KNOWN_ISSUES (라).
3. **[하·커버리지] 극성 잔존 공정(Process급) 미실증** — §5.2 ②(cathode 탭용접/anode 탭용접 precedes 순차 + mirrors)가 골격에 없음(단일 탭용접). flow는 자명하게 단일 스트림. Process급 극성 분기·합류 검증 안 됨. → KNOWN_ISSUES (라).
4. **[하] §3.6 명시적 실패 불완전** — skeleton.type만 raise, query traverse 미지원 방향/패턴은 silent(빈 결과). config 표현 밖이 "시끄럽게" 드러나지 않음. → KNOWN_ISSUES (마).
5. **[하·설계] MOCK 그래프 사실 채널 무필터 + 브리지 상시 발화** — Q1(청크 답)도 그래프 사실 35건(cross-layer Failure 포함). §8-6 관련성 필터는 답변 LLM 몫이라 MOCK엔 없음. answer_path는 정상, 채널만 시끄러움. 실물 LLM에서 통제. 결함 아님(문서화된 MOCK 한계).
6. **[하·mock데이터] 규칙B 저해상도 부착** — R9(패키징 행)의 control_item 실링 온도 → `패키징 has_property 실링 온도`(실링온도의 자연 소속은 실링). 규칙B는 행 process_ref에 무조건 부착(저해상도, CP가 정밀화)이므로 메커니즘은 정상, mock 데이터 의미상 어색.

### E2. 플랫폼(뷰어) 붙이기 전 조치
- **(다)(라)(마) 모두 조치 완료** — cross-layer 렌더 버그 해소(뷰어에 깨진 "N0002 공정" 안 나옴), mock 커버리지 보강(다중 occurs_in·극성 잔존 공정), 명시적 실패 완성.
- 그래프 데이터·질의 경로 믿을 만함 + 렌더 정상화 → **바로 시각화(단위 4)로 가도 됨**. 남은 잠재 이슈는 (나) 재인입(단위5)·E1-5·6(문서화된 MOCK 한계).

### E3. 실물 규모에서 문제 될 것 (성능·확장)
- **선형 스캔 다발**: `graph.neighbors`·`edges_incident`·`graph_facts`가 매 호출 전 엣지 순회. 질의 1회에 관계×엣지 스캔. 10만+ 엣지에서 질의 지연. (인덱스 없음 — 현재 mock은 무해.)
- **브리지 `_AllGraphsView`가 매 질의 전 층 노드·엣지 병합** — O(전체 그래프)/질의. 대규모에서 비쌈.
- **링킹 `dictionary.surfaces()` 전수 + 질문 substring 스캔** — O(표면형 수). 10만 표면형에서 느림(명세 §5.6.6 임베딩/faiss 사다리가 이 지점 — 도입 이연 상태).
- **저장이 매 인입마다 graph.json 전체 재기록** — O(그래프)/문서. 대량 인입 시 IO 병목. (Neo4j 승격·증분 저장은 이연.)
- 전부 명세가 "측정 후 도입"(P7)으로 이연한 지점과 일치 — 지금 구조 결함은 아니나 실데이터 파일럿(국면2-5) 전 재검토 대상.

---

_생성: 검수 라운드 2 (읽기 전용). 코드 미수정. 조치 여부는 사람 결정._
