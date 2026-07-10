# Ontology System 구현용 문서 v1.9 (Claude Code 입력물)

> v1.9: role 표기 통일(필드 role 5종 + edges 선언, edges는 핸들러 없이 루프 후처리) — 명세 v1.10·정의서 v1.7 정합.
> v1.8: §9 실행 준비 신설(Claude Code 자율 실행용) — 환경(Python·패키지·init), 착수 단위 세분(1a~1d/2~5), 자동 검증(완료판정→테스트), 막힘 프로토콜(BLOCKERS.md, 추측 금지), 진행 로그(PROGRESS.md).
> v1.7: 명세 v1.9 동기화 — 기능 감사(다중 occurs_in은 mock R11에 이미 반영됨 확인, flow 단일 스트림). 계약 변경 없음(명세 서술 정합만).
> v1.6: 명세 v1.8 동기화(묶음3) — 층 폴더 무코드(config+스키마만), core에 범용 build/query/skeleton, router 자동발견, skeleton config화(type=tree|flat + data), §3.6 범용성 원리. §1 트리·§4·§5·§7 갱신.
> v1.5: 정합 감사 2차 — attribute provenance([{context,value,provenance}]) §0-5·§2.2·§3·§5, 극성 게이팅(category∈{Unit,Property} AND 행 극성) §2.4·§3, §8-6 노이즈 근거 정정, 단계3에 Q1~8 회귀 판정, mirror_asymmetry 반영분 유지.
> v1.4: 정합 감사 — 계약부에 mirrors/mirror_asymmetry(config·큐·절차), 맥락형/극성 canonical을 그래프 저장 예시·fact_templates·cp.json에 반영, 3문서 참조 최신화.
> v1.3: 명세 v1.6 동기화 — 봉투 context 상속, cp.json spec contextual 플래그, mock에 context 검증(C7)·mirror 검증(C8·C9), 극성 결합 canonical 규칙.
> v1.2: 명세 v1.3 동기화 — severity→effect_category attach, mock severity 1:1 정렬, R13(process_ref orphan) 추가, table content 서브청크 id, 엣지 status(deleted_by_user) 계약.
> v1.1: 명세 §8-R(read측 규약) 동기화 — cli/query.py 라우터, 사전·id 전역화(data/ 트리에 dictionary.json·id_seq.json), quality config에 cross_layer_traverse 기본 포함, §7 단계3 판정 명확화.

> 3문서 체계: **명세**(무엇을·왜 — ontology_system_명세.md, 현행 v1.6) / **정의서**(role 계약 — role_어휘_정의서.md, 현행 v1.5) / **본 문서**(어떻게).
> 본 문서는 구현에 필요한 전부를 담는다: 파일 트리, JSON 계약 실예시, config, mock 데이터 전문, 구현 순서, 완료 판정.
> 충돌 시 우선순위: 명세 > 정의서 > 본 문서. 본 문서에 없는 판단이 필요하면 명세의 원칙(P1~P7)으로 결정한다.

---

## 0. 구현 불변 규칙 (위반 금지)

1. **core/에 층 어휘 금지** — "Process", "part_of", "노칭", "Failure" 등 층의 카테고리·관계·개체 이름이 core 코드에 한 글자도 등장하면 안 된다. core는 목록·스펙을 인자/설정으로 받는다.
2. **단방향 의존**: core는 layers를 모른다(층 폴더엔 코드가 없으므로 자연 성립). core는 config·스키마를 데이터로만 읽는다. 층 어휘를 core에 넣지 않는다(§3.6, §0-1).
3. **미래 층 코드 선작성 금지** — 불량이력층·설비이력층용 처리를 미리 넣지 않는다.
4. **명료함 > 짧음** — 에러 처리, 로깅, provenance 기록, 명시적 변수명을 줄 수를 위해 희생하지 않는다.
5. **모든 자동 생성물에 status와 provenance 기록** — 노드, 엣지, alias, **attribute 값 항목** 전부. 예외 없음.
6. **질의 경로는 읽기 전용** — 질문 표현을 사전에 누적하지 않는다.
7. **모든 단계는 CLI 진입점 + 파일 입출력** — `python <단계>.py <입력> [출력]` 형태. 플랫폼이 subprocess로 호출한다.
8. **USE_MOCK=1**(기본)에서 외부 의존(LLM 게이트웨이, sentence-transformers) 없이 전체가 동작해야 한다.

## 1. 파일 트리

```
ontology/
├── core/                    A — 층 어휘 없음, config를 개수·이름·유무 무가정 순회(§3.6)
│   ├── graph.py          add_node/add_edge/neighbors(ids, traverse_spec)/save/load, id 발급(전역 N####)
│   ├── dictionary.py     전 층 공유 사전: register/lookup(→후보 id 목록)
│   ├── matcher.py        개체 판정: match(surface, candidates, category)
│   ├── llm.py            게이트웨이 호출 + JSON 파싱 (USE_MOCK 분기)
│   ├── embeddings.py     embed(text) — 노드 판정용, 비저장 (USE_MOCK=해시)
│   ├── ingest.py         role 핸들러 루프 + 검증 + mirrors 자동 규칙
│   ├── build.py          범용 쓰기: config+스키마 로드→재인입→2-pass→mirrors→저장
│   ├── query.py          범용 읽기: 링킹→확장(config.traverse)→수집→답변(config.templates)
│   └── skeleton.py       범용 골격 심기: config.skeleton(type=tree|flat + data) 해석
├── layers/                  **config + 스키마만 (코드 0)**
│   ├── process/config.json
│   └── quality/config.json
├── router.py                층 폴더 자동 발견 (등록 코드 없음)
├── schemas/
│   ├── blocks/common_core.json, process_coord.json
│   ├── pfmea.json
│   └── cp.json
├── mock/                 §6 mock 데이터 전문
│   ├── parsed/PFMEA01.json, CP01.json, PPT01.json
│   └── queries.json
├── cli/
│   ├── build.py          <parsed.json> [--layer] → data/ 갱신
│   ├── query.py          "<질문>" → 답변 stdout — **단일 진입점 라우터(§8-R1)**: 전역 링킹 → layer별로 층 query 로직 호출 → cross-layer 브리지 1홉 → 두 채널 합성
│   └── export.py         --cypher | --mermaid
└── data/
    ├── process/graph.json, quality/graph.json     (진실)
    ├── dictionary.json                             (동의어 사전 — 전 층 공유 단일, §8-R2)
    ├── id_seq.json                                 (id 발급 시퀀스 — 전역 유일 보장, §8-R3)
    ├── chunks.json                                 (청크 저장소, 층 공유)
    └── review_queue.json                           (수정 큐, 층 공유)
```

## 2. 파일 계약 (JSON 실예시)

### 2.1 파서 출력 (계약 #1) — 봉투 + 조각

```json
{
  "doc_id": "PFMEA01", "doc_type": "pfmea", "source_path": "(mock)", "revision": "R1",
  "parsed_at": "2026-01-01T00:00:00", "parser_version": "mock-0.1",
  "context": {"model": "M1"},
  "payload_kind": "table",
  "records": [ { "chunk_id": "PFMEA01-R001", "process_group": "조립", "process_ref": "노칭",
                 "electrode_type": "cathode", "failure_mode": "...", "...": "..." } ]
}
```
- prose 문서는 `"payload_kind": "prose", "chunks": [{"chunk_id","process_group","process_ref","electrode_type","text","section","meta"}]`.
- 공통 조각 필드(chunk_id, doc_type, process_group, process_ref, process_no?, electrode_type)는 모든 record/chunk에 존재. process_no는 optional.

### 2.2 그래프 저장 (계약 #2, 진실)

```json
{
  "nodes": {
    "N0002": { "id": "N0002", "canonical": "노칭", "category": "Process", "layer": "process",
               "status": "confirmed", "attrs": {"process_no": null},
               "aliases": [ {"surface": "notching", "provenance": ["PFMEA01-R003"]} ],
               "provenance": ["seed"] },
    "N0021": { "id": "N0021", "canonical": "cathode 노칭 프레스", "category": "Unit", "layer": "process",
               "status": "confirmed", "electrode_type": "cathode",
               "aliases": [ {"surface": "노칭 프레스", "provenance": ["CP01-C8"]} ],
               "provenance": ["CP01-C8"] },
    "N0031": { "id": "N0031", "canonical": "cathode 노칭 프레스::노칭 정밀도", "category": "Property", "layer": "process",
               "attrs": { "spec": [ {"context": {"model": "M1"}, "value": {"min":-0.1,"center":0,"max":0.1,"unit":"mm"}, "provenance": ["CP01-C8"]} ] },
               "status": "auto", "provenance": ["CP01-C8"] } },
  "edges": [ { "src": "N0002", "rel": "precedes", "dst": "N0003",
               "status": "confirmed", "provenance": ["seed"] },
             { "src": "N0021", "rel": "mirrors", "dst": "N0022",
               "status": "auto", "provenance": ["auto:mirror_rule"] } ]
}
```
- id는 발급 후 불변. cross-layer 엣지는 품질층 graph.json에 저장(src=품질층 노드, dst=공정층 노드 id — 생성 방향 규약 §8-4).
- **극성 노드**: canonical에 극성 결합("cathode 노칭 프레스"), 표면형("노칭 프레스")은 alias 공유(§5.2). Property의 극성별 노드는 canonical 부모 접두로 유일화.
- **맥락형 attribute**(spec 등): `attrs`에 스칼라가 아니라 `[{context, value}]` 리스트로 저장(정의서 §3.3). context 미지정분은 봉투 context 상속.
- **mirrors 엣지**: 자동 규칙(§5.3) 산출물, provenance=auto:mirror_rule.

### 2.3 청크 저장소 / 수정 큐

```json
{ "chunks": { "PPT01-C003": { "doc_id": "PPT01", "text": "...", "section": "슬라이드 5",
              "meta": {}, "linked": false } },
  "describes": [ {"chunk_id": "PPT01-C001", "node_id": "N0011"} ] }
```
```json
[ { "kind": "auto_node|uncertain_match|orphan_anchor|orphan_chunk_link|unknown_field|spec_conflict|evidence_lost|mirror_asymmetry",
    "payload": {"...": "..."}, "reason": "...", "doc_id": "...", "created": "..." } ]
```
- 엣지 status 값: `confirmed` | `auto` | `deleted_by_user`(사람 삭제 툼스톤 — graph.json 영속, add_edge가 건너뜀, 명세 §5.5-3). provenance-0 엣지는 evidence_lost 큐(노드와 대칭). enforcement는 엣지 삭제 도구 시점(단계 5)에 구현, 계약은 지금 준수.

### 2.4 doc_type 스키마 — schemas/pfmea.json (전문)

```json
{
  "doc_type": "pfmea", "schema_version": 1, "layer": "quality",
  "use_blocks": ["common_core", "process_coord"],
  "fields": {
    "failure_mode":           {"role": "entity",    "category": "Failure"},
    "cause":                  {"role": "entity",    "category": "Failure"},
    "severity":               {"role": "attribute", "attach_to_field": "effect_category", "optional": true},
    "effect_category":        {"role": "anchor",    "target_category": "FailureEffect"},
    "effect_detail":          {"role": "content",   "attach_to_field": "effect_category", "optional": true},
    "control_item_for_fm":    {"role": "entity",    "category": "Property", "target_layer": "process", "optional": true},
    "control_item_for_cause": {"role": "entity",    "category": "Property", "target_layer": "process", "optional": true},
    "prevention_control":     {"role": "content",   "attach_to_field": "cause", "optional": true},
    "detection_control":      {"role": "content",   "attach_to_field": "failure_mode", "optional": true}
  },
  "edges": [
    {"from": "cause",        "relation": "causes",        "to": "failure_mode"},
    {"from": "failure_mode", "relation": "affects",       "to": "effect_category"},
    {"from": "failure_mode", "relation": "occurs_in",     "to": "@process_ref"},
    {"from": "failure_mode", "relation": "controlled_by", "to": "control_item_for_fm",    "optional": true},
    {"from": "cause",        "relation": "controlled_by", "to": "control_item_for_cause", "optional": true}
  ]
}
```
- `@process_ref` = 공통 조각의 좌표 필드 참조. `target_layer` = 걸침 필드(다른 층 그래프에 기록 — 명세 §15.7 규칙 A). entity 미해소 시 부착 폴백은 `@process_ref`(규칙 B).
- blocks: common_core = {chunk_id: meta}, process_coord = {process_group: anchor(대공정), process_ref: anchor(세부공정), process_no: meta(optional)}. electrode_type = {role: attribute, 대상: 행에서 생성/해소된 entity의 노드 필드} + **극성 결합 게이팅**(§5.2 v1.7): category∈{Unit,Property} **AND** 행 electrode_type=cathode/anode → canonical에 극성 결합. Failure 등은 결합 안 함. both/무표기 Unit·Property는 극성 무관 노드(추후 spec_conflict가 극성 분리 신호). context = 봉투/레코드 상속 필드(맥락형 attribute 그룹핑 키).

### 2.5 schemas/cp.json (전문)

```json
{
  "doc_type": "cp", "schema_version": 1, "layer": "process",
  "use_blocks": ["common_core", "process_coord"],
  "fields": {
    "설비":     {"role": "entity",    "category": "Unit"},
    "관리항목": {"role": "entity",    "category": "Property"},
    "규격":     {"role": "attribute", "attach_to_field": "관리항목", "attr_name": "spec", "contextual": true, "optional": true},
    "측정방법": {"role": "attribute", "attach_to_field": "관리항목", "optional": true},
    "대응계획": {"role": "content",   "attach_to_field": "관리항목", "optional": true}
  },
  "edges": [
    {"from": "설비",    "relation": "part_of",      "to": "@process_ref"},
    {"from": "설비",    "relation": "has_property", "to": "관리항목"}
  ]
}
```

## 3. core 기능 명세

- **graph.py**: `add_node(canonical, category, layer, status, attrs, provenance) → id` — **id는 전역 유일**(data/id_seq.json 공유 시퀀스, 층 무관) / `add_edge(src, rel, dst, status, provenance)`(중복 무시. **status="deleted_by_user" 툼스톤인 (src,rel,dst)-by-id는 건너뜀** — 재인입 부활 방지, 명세 §5.5-3. enforcement는 단계5) / `neighbors(ids, traverse_spec)` — traverse_spec은 관계별 {direction: "out|in|both", recursive: bool} dict를 **인자로** 받음(내용은 층 코드가 소유 — 현 C, 명세 §5.6.2) / save/load.
- **dictionary.py**: **전 층 공유 단일 파일**(data/dictionary.json). `lookup(surface) → 후보 노드 id 목록`(층 간 표면형 충돌 허용 — 호출자가 category/layer로 선별). register 시 provenance 필수. canonical과 alias 모두 등재.
- **matcher.py**: 입력 mention+후보들(canonical, aliases, 부착 위치, category). USE_MOCK=문자열 정규화 포함 규칙(공백 제거 후 동일/포함), 실물=판정 프롬프트(정의문·비대칭 기준은 층 config에서 주입). **카테고리 불일치 안전망**: 추출 category ≠ 최상 후보 category → match 금지.
- **ingest.py**: 정의서 §6 핸들러 루프(필드 role 5종 핸들러) + edges 후처리(핸들러 아님, 필드 해소 후 엣지 생성) + 검증. 핸들러 공통 시그니처 `handle(value, spec, ctx) → resolved_id|value|None`. ctx = {graph들(layer별), dic, queue, record, schema}. 처리 순서: Pass1 = 전 record의 anchor/entity 해소(버퍼) → Pass2 = attribute/content/edges 적용. entity 3분기: 매칭(alias 누적)/신규(auto 생성+큐 kind=auto_node)/불확실(신규+큐 kind=uncertain_match). anchor 미스 → 후보검색+판정 → 실패 시 큐 kind=orphan_anchor(레코드 전체를 보류하지 않고 해당 엣지만 생략). 재인입: 동일 doc_id 유입 시 해당 provenance 항목 제거 → provenance 0의 auto 노드는 큐 kind=evidence_lost. **context 상속**: record.context가 없으면 봉투 context 사용. **맥락형 attribute**(contextual:true): [{context, value, provenance}] 리스트에 추가(provenance 필수, §0-5), 충돌은 같은 context 그룹 내 deep-equal만. 단순형도 [{value, provenance}]. 재인입 시 attribute 항목도 doc_id로 회수(같은 문서 개정값은 교체, provenance-0은 evidence_lost). **극성 결합 canonical**: category∈{Unit,Property} AND record.electrode_type=cathode/anode일 때만 entity 생성·조회 canonical에 극성 결합(명세 §5.2 v1.7 — Failure 제외, both/무표기는 극성 무관). mirrors 자동 규칙의 전제. **mirrors 자동 규칙**: build 저장 직전, 같은 부모 아래 (극성 제거 canonical 동일 + electrode_type 반대) 노드 쌍에 mirrors 엣지 생성 + 자식 수·구성 비교 → 불일치 시 mirror_asymmetry 큐(문자열 비교, LLM 불요 — 명세 §5.3). **엣지 provenance**: 재인입 시 엣지 provenance도 doc_id 단위로 회수, provenance-0 엣지는 evidence_lost 큐(노드 대칭).

## 4. 층 config (전문)

### layers/process/config.json
```json
{
  "layer": "process",
  "categories": {
    "Process":  "제품을 만들기 위해 수행하는 작업 단계. 기능으로 정의되며 설비 기종이 바뀌어도 존재한다(예: 노칭, 스태킹). 설비 이름이 아니라 '하는 일'의 이름.",
    "Unit":     "공정을 수행하는 물리 장비의 기종/표준 명칭(예: 노칭 프레스). 지그·금형 등 도구류 포함. 호기·특정 공장 개체는 제외.",
    "Property": "공정/설비에서 관리·측정·통제되는 항목의 이름(예: 노칭 정밀도). 관리항목/특성/CTQ 포함. 규격값·측정값·판정결과는 제외(attribute)."
  },
  "skeleton": {"type": "tree", "category": "Process",
               "data": {"조립": ["노칭","스태킹","탭용접","패키징","전해액주입","실링"]},
               "relations": {"child": "part_of", "sibling": "precedes"}},
  "mirrors": {"enabled": true},
  "relations": ["part_of", "precedes", "has_property", "mirrors"],
  "category_pair_map": { "Unit,Process": "part_of", "Process,Property": "has_property", "Unit,Property": "has_property" },
  "match_threshold": 0.85,
  "query_traverse": {
    "part_of":      {"down": {"direction": "in",  "recursive": true},  "up": {"direction": "out", "recursive": false}},
    "has_property": {"both": {"direction": "both", "recursive": false}}
  },
  "fact_templates": {
    "part_of": "{src}는 {dst}의 하위 요소이다",
    "precedes": "{src} 다음 공정은 {dst}이다",
    "has_property": "{src}의 관리인자: {dst}",
    "mirrors": "{src}는 {dst}와(과) 극성 대칭 공정/설비이다",
    "attr:spec": "{node}의 규격: {value} (출처: {prov})"
  },
  "_fact_note": "맥락형 attr(spec 등)은 context 그룹별 한 줄씩 렌더: '[model=M1] 규격: ...'. mirrors는 query_traverse 기본 미포함(비대칭 조회 시에만 명시적 확장 — HOOK).",
  "prompts": { "extract": "(명세 §5.4-1 규칙 — 정의문 3종 삽입, 주제만, 목록 밖 버림, 애매하면 제외)",
               "judge":   "(명세 §5.4-2 규칙 — 의미 판단, 표기 변형 안내, 비대칭: 확신 없으면 uncertain)" }
}
```
- part_of의 src=자식, dst=부모 (Unit part_of Process). precedes는 query_traverse에 없음(의도 — 명세 §5.6.2, 순서 정보는 그래프 사실 채널 담당).

### layers/quality/config.json
```json
{
  "layer": "quality",
  "categories": {
    "Failure":       "공정에서 발생할 수 있는 불량·고장 현상. 고장모드와 고장원인의 병합(열린 집합). 방향은 행 구조가 부여.",
    "FailureEffect": "셀 관점의 결과 분류(단락, 화재 등). 닫힌 Tier1 목록 — anchor 전용, entity 생성 금지."
  },
  "skeleton": {"type": "flat", "category": "FailureEffect",
               "data": ["단락","화재","방전기능상실","충전기능상실"]},
  "mirrors": {"enabled": false},
  "relations": ["causes", "affects", "occurs_in", "controlled_by"],
  "category_pair_map": {},
  "match_threshold": 0.85,
  "query_traverse": {
    "causes":  {"both": {"direction": "both", "recursive": false}},
    "affects": {"both": {"direction": "both", "recursive": false}}
  },
  "cross_layer_traverse": {
    "occurs_in":     {"direction": "both", "recursive": false},
    "controlled_by": {"direction": "both", "recursive": false}
  },
  "fact_templates": {
    "causes": "{src}는 {dst}의 원인이 될 수 있다",
    "affects": "{src}는 {dst}(으)로 이어질 수 있다",
    "occurs_in": "{src}는 {dst} 공정에서 발생한다",
    "controlled_by": "{src}는 {dst}(으)로 관리한다"
  },
  "prompts": { "extract": "(훅만 — PoC 미사용)", "judge": "(공정층과 동일 규칙)" }
}
```
- cross_layer_traverse: **기본 포함, 1홉·비재귀·양방향**(명세 §8-6 해소·§8-R1 브리지). 홉/포함 파라미터는 로그 관찰로 조정. 브리지 엣지의 문장화는 quality fact_templates 사용(§8-R4).

## 5. core 범용 파이프라인 절차 (층 코드 아님 — config 구동)

층 폴더엔 코드가 없다(§3.6). 아래는 core가 config를 읽어 수행하는 절차이며, 층별 차이는 전부 config 결정점(skeleton/relations/mirrors/query_traverse/fact_templates)으로 표현된다. config로 표현 안 되는 절차를 만나면 **명시적 실패**(오버라이드 코드 금지).

- **core/skeleton.py (범용)**: config.skeleton을 해석. `type=tree`면 data(중첩 dict)를 부모-자식 part_of + 형제 나열순 precedes로 심음. `type=flat`이면 data(목록)를 지정 category의 노드로만 심음(엣지 없음). 노드는 confirmed·provenance=["seed"]. canonical 층 내 유일 검사. 극성 잔존 공정을 극성별로 심는 것도 skeleton.data가 표현(사내 seed).
  - process config.skeleton = {"type":"tree", "category":"Process", "data":{"조립":["노칭","스태킹","탭용접","패키징","전해액주입","실링"]}, "relations":{"child":"part_of","sibling":"precedes"}}
  - quality config.skeleton = {"type":"flat", "category":"FailureEffect", "data":["단락","화재","방전기능상실","충전기능상실"]}  `# [사내 확정] 교체`
- **core/build.py (범용)**: config+스키마 로드 → 재인입 처리(청크·describes·노드/엣지/attribute provenance를 doc_id로 회수, provenance-0 → evidence_lost) → ingest.ingest_doc(2-pass) → mirrors 자동 규칙(config.mirrors.enabled일 때) → 저장. prose는 content 경로(추출→describes, 미해소 orphan_chunk_link), table은 핸들러 루프. **층 무관** — 차이는 스키마 edges·config.mirrors뿐.
- **core/query.py (범용)** + **router.py**: router가 층 폴더 자동 발견, cli/query.py가 단일 진입점(전역 링킹 → layer별 core.query 호출 → cross-layer 브리지 1홉 → 합성, §8-R1). core.query 4단: ①링킹(사전 스캔[긴 표면형 우선] → USE_MOCK=0이면 LLM 폴백; 3단 `# HOOK: hybrid_search`) ②확장(config.query_traverse 스펙으로 core.neighbors — 관계 개수·이름 무가정 순회) ③수집(2-tier 직접>확장, 상한 8, 최신순, 잘림 로그) ④답변(그래프 사실 문장화[config.fact_templates: 엣지+attrs, 맥락형은 context 그룹별 한 줄] + 청크 원문. flow 패턴→골격+precedes 통째. 답변 3단 규칙: 근거 있음→출처 / 없음→"사내 근거 없음"+[일반지식—사내 검증 필요]+등록 개체 안내 / 미스 로그).
- **명시적 실패 지점**: skeleton.type이 tree/flat이 아니거나, config에 없는 traverse 방향/패턴을 만나면 core가 raise하며 "config 표현 밖 — core 패턴 추가 필요"를 알림(§3.6 탈출구).

## 6. mock 데이터 전문

### 6.1 mock/parsed/PFMEA01.json — records 12행 (각 행 주석 = 검증 메커니즘)

공통: doc_type=pfmea, process_group=조립, electrode_type은 cathode/anode/both 순환 배정. 아래 요지 표대로 §2.1 계약의 완전한 record로 작성할 것.

| # | process_ref | failure_mode | cause | effect_category | control_item_for_cause | 검증 메커니즘 |
|---|---|---|---|---|---|---|
| R1 | 노칭 | 전극 치수 불량 | 금형 마모 | 방전기능상실 | 금형 클리어런스 | 기본 경로 + 규칙A(Property auto 생성) + 규칙B(공정 부착) |
| R2 | 노칭 | 전극 치수 불량 | 타발 속도 과다 | 방전기능상실 | 타발 속도 | 모드 1:원인 N 전개 — R1과 동일 fm이 한 노드로 해소 |
| R3 | 노칭 | 절연 파괴 | 이물 유입 | 단락 | 이물 검출 감도 | causes 연쇄 시작점 |
| R4 | 스태킹 | 내부 단락 | 절연 파괴 | 단락 | (없음) | **병합 연쇄**: R3의 fm = R4의 cause → 한 노드, "이물 유입→절연 파괴→내부 단락" 사슬 성립 |
| R5 | 스태킹 | 적층 어긋남 | 정렬 센서 오차 | 충전기능상실 | 적층 정렬도 | 기본 |
| R6 | 스태킹 | 적층 어긋남 | 흡착 불량 | 충전기능상실 | 흡착 압력 | 동일 fm 재등장(매칭 경로) |
| R7 | 탭용접 | 용접 강도 부족 | 가압력 부족 | 방전기능상실 | 용접 가압력 | 기본 |
| R8 | 탭용접 | 용접 강도 부족 | 진폭 이상 | 방전기능상실 | 용접 진폭 | 기본 |
| R9 | 패키징 | 실링 파단 | 실링 온도 저하 | **셀 부풀음** | 실링 온도 | **anchor 미스**: 골격에 없는 effect → orphan_anchor 큐 |
| R10 | 전해액주입 | 주액량 편차 | 주액 노즐 막힘 | 충전기능상실 | 주액량 | 기본 |
| R11 | 실링 | 밀봉 불량 | 이물 유입 | 화재 | 이물 검출 감도 | cause가 R3와 한 노드(교차 공정 매칭 — occurs_in이 노칭·실링 양쪽에 생김 = **다중 occurs_in 정상**, "이 불량 유발 공정들" 질의의 답, 명세 §8-1) |
| R12 | 노칭 | 버 발생 | 금형 마모 | 단락 | **노칭정밀도** | **표기 변형**(CP의 "노칭 정밀도"와 판정→alias) + 이 record에만 "비고" 필드 추가 → **unknown_field 큐** |
| R13 | **레이저노칭** | 슬리팅 버 | 빔 출력 편차 | 단락 | 빔 출력 | **process_ref anchor 미스**(골격에 없는 공정): occurs_in 드롭 + 규칙B 폴백(@process_ref) 미스로 Property 부착도 드롭 → orphan_anchor 큐(§8-1 연쇄 검증) |

- **severity ↔ effect_category 1:1 정렬(§15.5)**: severity는 effect_category에 부착되므로 같은 effect면 같은 값이어야 우발 spec_conflict가 없음. 매핑 = {단락:9, 화재:9, 방전기능상실:8, 충전기능상실:7}. 각 행의 severity는 이 표에서 결정(R3·R4·R11·R12=9, R1·R2·R7·R8=8, R5·R6·R10=7). effect orphan(R9 셀 부풀음)·process orphan(R13)은 severity 부착 대상 자체가 미해소 → 저장 보류.
- prevention_control/detection_control: 각 행에 1문장 창작 텍스트. **필드별 별도 청크**로 저장(id={record chunk_id}-{필드명}, 정의서 §3.4) → prevention은 행의 cause에, detection은 행의 failure_mode에 describes.

### 6.2 mock/parsed/CP01.json — records 6행

| # | process_ref | 설비 | 관리항목 | 규격 | 검증 메커니즘 |
|---|---|---|---|---|---|
| C1 | 노칭 | 노칭 프레스 | 노칭 정밀도 | ±0.1mm | Unit 생성+has_property, R12 "노칭정밀도"와 매칭→alias 누적 |
| C2 | 노칭 | 노칭 프레스 | 금형 클리어런스 | 20±2㎛ | **규칙B 보강**: R1이 공정에 부착한 auto Property가 설비 소속으로 정밀화(has_property 추가+큐 기록) |
| C3 | 스태킹 | 스태커 | 적층 정렬도 | ±0.2mm | R5와 매칭 |
| C4 | 스태킹 | 스태커 | 적층 정렬도 | **±0.3mm** | **spec 충돌**: C3와 다른 값 → spec_conflict 큐, 덮어쓰지 않음 |
| C5 | 탭용접 | 초음파 융착기 | 용접 가압력 | 0.3MPa | R7과 매칭 |
| C6 | 실링 | 실러 | 실링 온도 | 180±5℃ | R9의 auto Property와 매칭 |
| C7 | 스태킹 | 스태커 | 적층 정렬도 | ±0.25mm (record context: {model:"M2"}) | **맥락형 검증**: 봉투 M1을 record가 M2로 덮어씀 → C3(M1)과 context가 다르므로 **충돌 아님**, 병렬 항목 추가 |
| C8 | 노칭 | 노칭 프레스 (electrode_type: cathode) | 노칭 정밀도 | ±0.1mm | **극성 결합 canonical**: "cathode 노칭 프레스" 노드 생성 |
| C9 | 노칭 | 노칭 프레스 (electrode_type: anode) | 노칭 정밀도 | ±0.12mm | C8과 **mirrors 자동 연결** 검증(극성 제거 canonical 동일+극성 반대+같은 부모). C9에만 관리항목 "버 높이" 1건 추가 → **mirror_asymmetry 큐** 검증 |

※ C1~C7의 electrode_type=both(극성 무관), C8·C9만 극성 지정 — 극성 메커니즘 검증을 이 쌍에 국한하여 mock 단순성 유지. C1과 C8의 관리항목이 같은 표면형("노칭 정밀도")이나 canonical이 갈리는 것(무극성 vs cathode 결합)도 관찰 대상.

### 6.3 mock/parsed/PPT01.json — prose 청크 8개

| # | process_ref | 내용 요지 | 검증 메커니즘 |
|---|---|---|---|
| P1 | 노칭 | 노칭 프레스 상세 서술(금형·타발 방식) | 주제 추출 → describes |
| P2 | 노칭 | 본문 중 "…스태커로 이송된다" 지나가는 언급 포함 | 스침 언급 비추출 |
| P3 | 스태킹 | 적층 정렬도 관리 방법 서술 | Property describes |
| P4 | 탭용접 | 수치·날짜 다수 포함 서술 | 수치/날짜 비추출 |
| P5 | 패키징 | 일반 안전 수칙(개체 없음) | linked=false 보존 |
| P6 | 전해액주입 | "주액기" — 골격·기존에 없는 신규 설비 서술 | prose 신규 entity 경로(auto+큐) |
| P7 | 실링 | meta.image_summary=true, 이미지 요약 텍스트 | 이미지 청크 동일 처리 |
| P8 | 노칭 | "notching press" 영문 표기 서술 | 표기 변형 판정 (USE_MOCK 규칙 한계 시 `# 실물 검증 항목` 주석) |

### 6.4 mock/queries.json — 12문항 (스모크 테스트, ③ 골든셋과 별개)

각 문항에 expected_path(graph_fact | chunk | both | general_knowledge) 명기.

1. Q1 "노칭 프레스 금형 관리 어떻게 해?" → chunk
2. Q1 "적층 정렬도 관리 방법은?" → chunk
3. Q2 "노칭 다음 공정은?" → graph_fact
4. Q2 "스태킹에 어떤 설비가 있어?" → graph_fact
5. Q3 "조립 전체 공정 흐름 설명해줘" → graph_fact (flow 규칙)
6. Q4 "노칭 정밀도 규격이 뭐야?" → graph_fact (attr)
7. Q4 "실링 온도 규격은?" → graph_fact (attr)
8. Q5 "금형 클리어런스를 관리하는 설비는?" → graph_fact (역방향)
9. Q5-cross "노칭에서 발생할 수 있는 불량은?" → graph_fact (occurs_in 역방향)
10. cross "단락으로 이어질 수 있는 불량은 뭐가 있어?" → graph_fact (affects 역방향 + causes 연쇄)
11. Q8 "노칭이 영어로 뭐야?" → general_knowledge ([일반지식] 표시 확인)
12. Q8 "리튬이온 배터리 동작 원리 설명해줘" → general_knowledge

## 7. 구현 순서와 완료 판정 (국면 1)

| 단계 | 작업 | 완료 판정 |
|---|---|---|
| 1 | core(graph·dict·matcher·llm·embeddings·ingest·build·query·skeleton) + router + process config·스키마 + CP01·PPT01 인입 | seed 7노드. CP 인입 후 Unit·Property·has_property 엣지 존재, C4가 spec_conflict 큐(같은 context 그룹), **C7은 충돌 없이 병렬 항목**(context 그룹 상이), **C8·C9 극성 결합 canonical 2노드 + mirrors 엣지 + mirror_asymmetry 큐**. PPT 인입 후 P5 linked=false 보존, P6 auto+큐. USE_MOCK=1 전 과정 무에러 |
| 2 | 질의 4단 + 이원 근거 채널 | queries.json 1~8·11·12가 expected_path대로 응답. flow 질의(5번)가 골격 전체 공급. 링킹 미스 로그 기록 확인 |
| 3 | 품질지식층 = **config+스키마만 추가**(층 코드 0) + PFMEA01 인입 + cross-layer | **`git diff core/` 가 비어 있음** = **품질층이 config만으로 core 범용 파이프라인에서 도는 것**이 성공 판정(§3.6 config-only 확증). 도중 core 수정이 필요했다면 그 지점이 "config 표현 부족→core 패턴 추가"의 첫 실측(기록 남길 것). "이물 유입→절연 파괴→내부 단락" causes 사슬 존재. R9 orphan_anchor(effect)·R13 orphan_anchor(process_ref, occurs_in+Property 동반 드롭)·R12 unknown_field 큐. 규칙A(auto Property)·규칙B(공정 부착 → C2로 보강) 동작. effect_category↔severity 정렬로 spec_conflict는 C4에서만 발생. add_edge가 deleted_by_user status를 건너뛰는 계약 준수(enforcement는 단계5). cross 질의 응답: 9번=occurs_in 역방향으로 노칭의 Failure들, 10번=affects 역방향 **직접 결과**(수집 노드 간 causes 엣지는 그래프 사실로 문장화 — 2홉 연쇄 전체는 스모크 요구 아님). **Q1~8 회귀**: cross-layer on 상태에서 1~8이 단계2 baseline과 동일 응답(브리지로 딸려온 Failure 청크·노드에 오염 안 됨) — §8-6 채널분리(그래프 사실 관련성 필터 + 청크 tier2 잘림)의 실증 지점 |
| 4 | 플랫폼 연동 (명세 §16.2 개조 1·2) | 플랫폼이 subprocess로 build/query 호출, 2층+cross-layer 그래프 표시, 수정 큐 열람 |
| 5 | 수정 도구 + 계기판 최소 (② 명세 마감 후 착수) | 병합/alias 이관/개명/엣지 삭제가 CLI(+플랫폼)에서 동작, 큐 소화 왕복 확인 |

- 각 단계 종료 시 사람 검수(그래프 JSON·큐 눈검사) 후 진행 — 병목은 코드 생성이 아니라 검수 시간.
- 단계 3에서 품질층 추가가 **core를 한 줄도 안 건드렸는지**를 기록 — config-only 확증(§3.6). core 수정이 있었다면 어느 결정점이 config로 표현 안 됐는지가 3층 대비 관찰 데이터.

## 8. USE_MOCK 동작 정의

- **llm.py**: 추출=키워드 규칙(config categories의 예시 표면형 + mock 데이터의 개체명 매칭), 판정=문자열 정규화 규칙(공백 제거 후 동일/포함 → match 0.95), 답변=두 채널을 정형 텍스트로 나열(문장 생성 없음).
- **embeddings.py**: sha256 해시 → 정규화 벡터. 로그에 "MOCK 임베딩 — 수치 무의미" 경고 출력.
- 환경 변수: `USE_MOCK`(기본 1), `LLM_GATEWAY_URL`, `LLM_API_KEY`, `CHAT_MODEL`. 설정 접근은 core/llm.py 한 곳으로 수렴.

## 9. 실행 준비 (Claude Code 자율 실행용)

> 이 섹션은 Claude Code가 **문서만 보고 추측 없이 자율 실행**하기 위한 것. 자율 루프 중 문서로 판단 안 되는 지점을 만나면 §9.4 막힘 프로토콜을 따른다.

### 9.1 실행 환경
- **Python 3.10+**. 표준 라이브러리 우선(json, hashlib, dataclasses, pathlib, argparse, logging).
- **패키지**: PoC 코어는 **외부 패키지 0** 목표(USE_MOCK=1 경로). 실물 경로용 선택 의존은 지연 import로 격리 — `sentence-transformers`(임베딩), LLM 게이트웨이 호출용 `requests`(또는 표준 urllib). requirements.txt에 선택 의존 명시하되 USE_MOCK=1에서는 import되지 않아야 함(§0-8).
- **가상환경**: `python3 -m venv .venv && source .venv/bin/activate`. requirements는 실물 전환 시에만 설치.
- **디렉토리 초기화**: 첫 실행 시 data/ 하위(process/·quality/·dictionary.json·id_seq.json·chunks.json·review_queue.json)를 빈 상태로 생성하는 `init` 동작. 각 파일 초기값: graph.json={"nodes":{},"edges":[]}, dictionary.json={}, id_seq.json={"next":1}, chunks.json={"chunks":{},"describes":[]}, review_queue.json=[].
- **패키지 구조**: core/·layers/·cli/에 `__init__.py`. import는 절대경로(`from core.graph import ...`), 실행은 프로젝트 루트에서 `python -m cli.build ...`.
- **로깅**: logging 표준 모듈, 레벨 INFO. MOCK 경고·큐 적재·명시적 실패(§3.6)는 명확히 로그.

### 9.2 착수 단위 (§7 5단계를 자율 실행 가능한 크기로 세분)
큰 단계를 한 번에 만들면 검수·디버깅이 어렵다. 아래 순서로 하나씩, 각 단위는 자기 완결 테스트(§9.3)를 통과해야 다음으로.

| 단위 | 산출 | 통과 조건(테스트) |
|---|---|---|
| 1a | core/graph.py·dictionary.py·id_seq + init | 노드 2개 add→저장→로드 시 id 전역 유일·복원 동일 |
| 1b | core/skeleton.py + process config.skeleton | seed 심기 후 Process 7노드, part_of 6·precedes 5 엣지 |
| 1c | core/ingest.py(핸들러)+matcher(MOCK)+build + cp.json | CP01 인입 후 Unit·Property·has_property, C4 spec_conflict·C7 병렬·C8/C9 극성+mirrors+mirror_asymmetry 큐 |
| 1d | content 경로 + PPT01 | P5 linked=false 보존, P6 auto+큐, describes 연결 |
| 2 | core/query.py + router + cli/query + queries.json | Q1~8·11·12 expected_path 일치, flow(5) 골격 공급, 미스 로그 |
| 3 | quality config+스키마만 추가 + PFMEA01 + cross-layer | git diff core/ 빈 것(config-only 확증), causes 사슬, R9/R13 orphan·R12 unknown_field, cross Q9·10, Q1~8 회귀 무오염 |
| 4 | 플랫폼 연동(§16.2 개조1·2) | subprocess build/query, 2층+cross 그래프·큐 열람 |
| 5 | 수정 도구 + 계기판 최소 | 병합/이관/개명/엣지삭제(deleted_by_user enforcement) CLI 동작 |

### 9.3 자동 검증 (완료판정 → 실행 가능한 테스트)
- 각 단위의 통과 조건을 **tests/test_<단위>.py**(assert 기반, 표준 unittest 또는 단순 assert 스크립트)로 구현. mock 데이터 인입 후 그래프 JSON·큐를 로드해 상태를 assert.
- 예: `test_1b`: skeleton 심기 → `len([n for n in nodes if n.category=="Process"])==7` and `count_edges("part_of")==6`.
- 자율 루프 지시: **"해당 단위 코드 생성 → 그 테스트 실행 → 실패 시 수정 → 통과까지 반복 → 통과하면 다음 단위."** USE_MOCK=1이라 네트워크·키 없이 전 루프 자율 가능.
- 테스트는 완료판정의 기계 번역일 뿐, 완료판정(§7·9.2)이 진실. 테스트가 통과해도 판정 문구와 어긋나면 판정 우선.

### 9.4 막힘 프로토콜 (자율 실행 중 불명확 지점)
- 문서(명세>정의서>구현문서)로 결정 안 되는 지점을 만나면 **추측해서 진행하지 않는다.** 대신:
  1. `BLOCKERS.md`에 [단위/파일/줄, 무엇이 불명확한지, 어떤 결정이 필요한지] 기록.
  2. 그 지점을 건너뛰고 **의존 없는 다음 독립 작업**으로 이동(막힌 것 위에 추측을 쌓지 않는다).
  3. 명시적 실패가 정당한 곳(§3.6: config 표현 밖)은 raise로 드러내고 BLOCKERS.md에도 기록.
- **금지**: 명세와 다른 임의 결정으로 빈틈 메우기, §0 불변 규칙 위반으로 우회, 테스트를 판정에 맞추는 대신 판정을 낮추기.

### 9.5 진행 로그 (5시간 창 후 사람 확인용)
- `PROGRESS.md`: 완료 단위, 각 단위 테스트 결과, 생성 파일 목록, git diff core/ 상태(단위3 config-only 확증), 소요.
- `BLOCKERS.md`: §9.4 누적 — 사람이 돌아왔을 때 "어디서 추측을 피하고 멈췄나"를 이걸로 확인.
- 한 창 종료 시: PROGRESS·BLOCKERS 갱신 후 마지막 통과 단위에서 정지. 다음 창은 여기서 재개.
