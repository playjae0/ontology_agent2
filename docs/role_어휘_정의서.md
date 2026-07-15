# 메타스키마 Role 어휘 정의서 (정본)

> **현재 버전: v1.8** — 파일명 무버전 정본, 갱신은 절 수정으로.
> 지위: **시스템 전체의 기준 계약 문서.** 파서 출력 요구사항, 온톨로지 에이전트 입력 계약,
> doc_type별 스키마 작성 기준이 모두 이 문서를 참조한다.
> 사내에서 새 문서 타입을 등록할 때 이 문서 + mock 스키마를 LLM에 제시하여 스키마 초안을 작성한다.
>
> v1.8: 명세 v1.12 동기화(구현·테스트된 동작의 role 계약 반영) — §3.1 anchor **Tier1 한정**(auto 후보뿐이면
> orphan_anchor)·극성 모호 처리, §3.2 entity에 **canonical 스코프**(Property 등 부모 접두 — 명세 §5.2) 및
> 리스트 값 계약 위반 시 missing_field 큐. (명세 v1.13이 §5.2 canonical 스코프를 명시하므로 role 계약도 동기화.)
> v1.7: role 표기 통일 — "필드 role 5종 + edges 스키마 선언(핸들러 없음)". §2 제목 각주로 6=5+edges 명시.
> v1.6: 정합 감사 — attribute 값에 provenance 필수([{context,value,provenance}], §0 대칭), attribute를 anchor-해소 노드에도 부착 가능 명시.
> v1.5: 맥락형 attribute 일반 규칙(단순형|맥락형, contextual 플래그, context 그룹 내 deep-equal), entity는 맥락형 대상 아님(존재 차이=노드 분화), §5.5 일람에 contextual 추가.
> v1.4: 사내 CP 실물 대조 반영 — attribute 값에 구조체/배열 허용(통째 저장·deep-equal 충돌), 리스트 값 role별 처리(entity=파서 전개/attribute=배열/content=무영향). 구조 정의는 스키마 파일 몫(L1).
> v1.3: table content 필드별 청크 입도 규칙(§3.4) 추가.
> v1.2: 명세 §15 동기화 — PFMEA 예시를 확정 설계(Failure 병합, effect=anchor)로 교체, 스키마 문법 확장(@좌표참조·target_layer·target_category·attr_name·optional), entity 부착 폴백, attribute 충돌 규칙, content table 경로 추가.
> v1.1: entity 처리를 자동 커밋+사후 수정 모델로 정정, 핸들러 3단 구조·연결 메커니즘·파서 자기완결 계약 반영.

---

## 1. 핵심 개념

**role = 그 필드의 값으로 온톨로지 에이전트가 그래프에 수행하는 쓰기 동작.**

메타데이터의 각 필드에 role을 배정하면, 에이전트는 필드 **이름**이 아니라 **role**만 보고 동작한다.
따라서 필드명 변경·추가·삭제, 새 doc_type 등록은 스키마 파일 수정만으로 끝나며 코드는 변경되지 않는다.

한 문장 요약:
> **anchor로 기존 골격에 닻을 내리고, entity로 노드 후보를 데려오고, edge로 그들 사이에 선을 긋고,
> attribute로 노드에 값을 붙이고, content는 LLM에게 넘기고, meta는 출처 장부에 적는다.**

## 2. 완전성(봉쇄)의 근거 — 왜 이 어휘로 전부 커버되는가

> 어휘 = **필드 role 5종**(anchor·entity·attribute·content·meta) + **edges 스키마 선언**(role 아님, 핸들러 없이 필드 해소 후 엣지 생성). "6종"이라 부를 때의 6번째가 edges다. 코드는 5 핸들러 + edges 후처리로 구현.

role 목록은 문서 종류를 예상해서 만든 것이 아니라, **그래프 데이터 모델이 허용하는 쓰기 동작의 전수 열거**에서 도출했다.

```
그래프 = 노드 + 엣지 + 노드필드 + 청크연결 + 이력(provenance)
```

| # | 그래프 쓰기 동작 | 대응 |
|---|---|---|
| 1 | 기존 노드를 찾아 부착점으로 쓴다 | `anchor` |
| 2 | 노드를 만든다(제안한다) | `entity` |
| 3 | 노드의 필드에 값을 쓴다 | `attribute` |
| 4 | 두 대상 사이에 엣지를 만든다 | `edges` 선언 (스키마 레벨) |
| 5 | 청크를 노드에 연결한다(describes) | `content` |
| 6 | 그래프에 쓰지 않고 이력만 남긴다 | `meta` |

어떤 필드가 오든 그 값은 이 여섯 동작 중 하나를 하거나 하지 않을 뿐, 제7의 동작은 그래프 모델상 존재하지 않는다.
→ **커버리지가 경험이 아니라 구조로 보장된다.** 이 보장이 깨지는 경우는 그래프 모델 자체(property graph 표준)가
담을 수 없는 정보가 등장할 때뿐이며, 이는 role의 문제가 아니라 별도 설계 재검토 대상(§7 L4)이다.

## 3. Role 정의 (필드 단위 5종)

### 3.1 `anchor` — 닻
- **뜻**: 배가 닻을 내려 이미 있는 바닥에 고정하듯, 이 필드의 값은 **이미 존재하는 골격 노드**를 가리켜 이 행의 정보를 그곳에 붙들어 맨다. 새로 만들지 않는다. 대상 골격은 트리(공정 트리)일 수도, 평평한 분류 목록(FailureEffect)일 수도 있다 — 형태 무관, "사람이 보증한 Tier1 노드"면 anchor 대상.
- **spec 속성**: `target_category` — 조회 대상 카테고리 지정(예: "FailureEffect"). 생략 시 좌표 블록의 기본(공정 골격).
- **에이전트 처리**: 동의어 사전 조회 → 골격 노드에 부착. 미스 시 후보검색+판정 → 그래도 미해소면 orphan_anchor 큐(사람). anchor는 entity 생성으로 폴백하지 않는다 — 골격은 유형이므로(P2) auto 생성 금지.
- **Tier1 한정 (v1.12)**: 조회 결과가 **auto 노드(발견형)뿐이면 anchor로 쓰지 않고** orphan_anchor 큐에 그 후보 id를 실어 사람 판단으로 보낸다. 근거: prose가 스친 이름으로 만든 auto 노드(예: "레이저노칭" Unit/Process)가 사전에 등재되면, 후속 문서의 좌표가 **조용히 그 위에 앉아 골격 행세**를 한다 — P2("골격·유형은 사람이 고정")의 우회로가 열린다. anchor 대상은 **사람이 보증한 것**(seed provenance 또는 승격된 confirmed)뿐이다.
- **극성 모호 (v1.12)**: 극성 제거 표면형이 양 극성 골격 노드를 함께 가리키면(§5.2 — "탭용접" → cathode/anode 탭용접) 임의 선택하지 않고 orphan_anchor(후보 id 동반). 쓰기는 좁게, 읽기(질의 링킹)는 양쪽 다.
- **예**: `process_ref: "노칭"` — 노칭 노드를 만들라는 게 아니라 "이 행 정보를 전부 노칭에 걸어라".
- **효과**: 부착이 LLM 추측이 아니라 **결정적 조회**가 된다. 파서가 골격의 좌표계로 말하게 하는 장치.
- **용어 출신**: HTML anchor, UI anchor point 등 "기존 위치에 고정"의 표준 용법. 온톨로지 문헌의 grounding/linking에 해당.

### 3.2 `entity` — 개체
- **뜻**: 세상에 존재하는 식별 가능한 하나의 것. 이름을 갖고 다른 것과 구별되어 **노드가 될 자격이 있는 것**.
- **에이전트 처리**: 개체 판정 경로 — 사전 조회 → 후보 검색 → LLM 동일성 판정 → 매칭(동의어 누적) / 신규(**자동 생성**, status=auto + provenance, 수정 큐 기록) / 불확실(**신규로 생성 + 수정 큐** — 오병합은 복구가 어려우므로 "되돌리기 쉬운 쪽으로 틀어라").
- **필수 속성**: `category` — 해당 층의 닫힌 카테고리 목록에서 지정. 선택 속성: `attach_to_field`(어느 필드의 개체에 붙는지), `target_layer`(**걸침 필드** — 이 필드는 다른 층의 그래프에 기록됨. 예: PFMEA의 관리항목 → 공정층 Property. 한 인입이 필드별로 여러 층에 쓸 수 있음).
- **맥락형 대상 아님 (v1.5)**: "모델 A에만 있는 설비"처럼 **존재 자체가 맥락별로 다른 것**은 context 태그로 표현하지 않는다 — 그것은 노드 분화 문제이며 실물 관찰 후 별도 판단(극성의 노드 분화와 같은 계열). 맥락형은 attribute 전용, content는 청크 provenance로 자동 보유.
- **부착 폴백 (규칙 B)**: attach 대상이 없거나 미해소이면 행의 공정좌표(@process_ref)에 부착한다 — 오류가 아니라 저해상도 부착이며, 후속 문서(예: CP의 설비 소속 정보)가 수정 큐/재해소로 보강한다.
- **canonical 스코프 (v1.12)**: 층 config가 `canonical_scope.bind_categories`로 지정한 카테고리(공정층: Property)의 canonical은 **`{부착 부모 canonical}::{표면형}`**으로 유일화한다(부모 = attach_to_field 해소 노드, 폴백 = @process_ref — 규칙 B와 같은 좌표). 표면형은 alias로 등재되어 질의 링킹은 그대로 동작. 근거·대가는 명세 §5.2. 어느 카테고리가 대상인지는 **값(config)**이며 코드는 모른다.
- **리스트 값은 계약 위반 (v1.12)**: entity 필드에 리스트/구조 값이 오면(파서가 전개하지 않음 — §3.4·§12-3) 값을 문자열로 뭉개 노드를 만들지 않고 **드롭 + `missing_field` 큐**. 핸들러는 단일 값만 본다는 전제를 코드가 방어한다.
- **anchor와의 차이**: anchor는 "이미 있는 것을 가리킴", entity는 "노드 후보를 데려옴". 같은 글자라도 role에 따라 동작이 다르다.
- **용어 출신**: ER 모델, entity extraction/resolution — 업계 표준 그대로.

### 3.3 `attribute` — 속성
- **뜻**: 어떤 것 자체가 아니라 어떤 것**에 붙어 있는** 성질/값. 노드를 만들지 않고 노드의 필드에 저장된다.
- **값 타입 (v1.4)**: 스칼라뿐 아니라 **구조체(JSON object)·배열**도 허용하며, 통째로 하나의 값으로 저장·비교한다. 예: CP 파라미터 `spec: {min, center, max, unit, type, is_cc}`는 6개로 흩뿌리지 않고 한 필드에 통째 저장 — 사람이 스펙을 세트로 파악하는 단위와 일치하고, 개정 시 충돌이 실체대로 1건으로 집계됨. **구조체 내부 필드는 정의서가 고정하지 않는다**(문서마다 세트가 다름 — 구조 정의는 doc_type 스키마 파일 몫, L1). is_cc 등 구조체 내 값은 현재 **저장 전용**(질의 승격은 명세 확정 후 별도 — [질의 이연 목록] 참조).
- **provenance 필수 (v1.6)**: attribute 값 항목은 provenance를 보유한다 — 노드·엣지·alias와 대칭(§0 불변식). 단순형도 `{value, provenance}`, 맥락형은 `{context, value, provenance}`. 재인입이 doc_id로 회수·교체하는 근거이며, 같은 문서 개정값 변경(교체)과 교차출처 충돌(spec_conflict)을 구별.
- **맥락형 값 (v1.5 — 일반 규칙)**: attribute 값은 두 형태 중 하나. ①단순형 `[{value, provenance}]` ②맥락형 `[{context:{축:값}, value:V, provenance}, ...]` — 값이 모델/사이트/라인 등 맥락별로 다를 때. 어느 attribute든 스키마의 `"contextual": true` 플래그로 선언(L1, 코드 무변경). context는 임의 딕셔너리(축 미리 발명 금지), 값은 스칼라/리스트. 출처는 봉투/레코드의 context 필드(상속 — 명세 §6.2).
- **부착 대상 (v1.6)**: attribute는 entity뿐 아니라 **anchor로 해소된 골격 노드에도 부착 가능**(예: severity → effect_category=FailureEffect). "개체의 필드"를 "해소된 노드의 필드"로 일반화.
- **에이전트 처리**: `attach_to_field`가 가리키는 (entity 또는 anchor-해소) 노드의 필드로 저장(저장 키는 `attr_name`, 생략 시 필드명). **충돌 규칙**: **같은 context 그룹 내에서만** 통째 동등성(deep equal) 비교 — 다르면 spec_conflict 큐, 완전 동일이면 무시, **context가 다르면 충돌이 아니라 병렬 항목 추가**(모델 A와 B의 spec 차이는 충돌이 아님). 단순형은 빈 context 그룹 하나로 취급(기존 동작과 동일). 구조체는 한 필드라도 다르면 1건 — 흩뿌리기 대비 실체대로 집계. 개정 이력 관리의 자연 획득.
- **판별 테스트**: "이것에 대해 더 말할 게 생기는가?" — 노칭 프레스는 금형·마모주기 등 더 말할 게 있음(→entity). 규격 ±0.1mm는 더 말할 게 없음(→attribute).
- **원칙 대응**: "측정값·spec은 노드가 아니라 필드" 원칙의 role 형태.
- **용어 출신**: 그래프 DB의 node property/attribute. Neo4j 용어는 property이나, 본 시스템의 카테고리 Property(관리인자)와의 충돌을 피해 attribute를 채택.

### 3.4 `content` — 서술
- **뜻**: 구조화되지 않은 자유 서술 텍스트. 필드 단위 규칙 처리가 불가능한 산문.
- **에이전트 처리**: (prose) 청크로 보존, LLM 언급 추출 → 해소된 노드에 describes 연결. 미해소 언급은 orphan_chunk_link 큐. (table) 행 문맥이 명확하므로 **LLM 추출 없이 `attach_to_field`로 describes 대상을 직접 지정** — 예: prevention_control은 행의 cause에, detection_control은 행의 failure_mode에.
- 링킹 0건 청크도 원문 그대로 보존한다(전 청크 보존 — 하이브리드 서치 전제조건, 명세 §5.6.6).
- **table content 청크 입도(v1.3)**: 한 record에 content 필드가 여럿이면 **필드별 별도 청크**를 생성하고 id = `{record chunk_id}-{필드명}`(예: PFMEA01-R001-prevention_control). 한 청크로 합치면 cause 검색에 detection 텍스트가 노이즈로 딸려오므로 분리.
- **리스트 값 처리(v1.4)**: 한 필드에 값이 여럿일 때 role별로 처리가 다르다 — **entity 리스트**("설비: A, B, C")는 값이 아니라 여러 개체이므로 **파서가 개별 값으로 전개**(자기완결 레코드, §12-3) → 핸들러는 단일 값만 본다. **attribute 리스트**는 배열로 통째 저장(§3.3 값 타입). **content 리스트**는 텍스트로 보존되어 무영향. 별도 cardinality 규칙은 두지 않는다.

### 3.5 `meta` — 관리 정보
- **뜻**: 내용물이 아니라 내용물의 신상정보("데이터에 대한 데이터"). 지식(그래프)에는 들어가지 않으나 출처 추적(provenance)을 위해 보관.
- **에이전트 처리**: 저장만. 그래프 무기록.
- **예**: chunk_id, 개정번호, 작성일. (주의: raw(가공 전 원료)가 아니라 "내용 바깥의 관리 정보"라는 뜻)

## 4. `edges` 선언 (스키마 레벨)

관계는 필드 하나의 성질이 아니라 필드 **사이**의 성질이므로, 필드 role이 아닌 스키마 레벨에 선언한다.

```json
"edges": [
  {"from": "cause",        "relation": "causes",    "to": "failure_mode"},
  {"from": "failure_mode", "relation": "occurs_in", "to": "@process_ref"},
  {"from": "failure_mode", "relation": "controlled_by", "to": "control_item_for_fm", "optional": true}
]
```

- **처리 순서**: ① 필드들을 role대로 해소(entity들이 노드 id 획득) → ② edges 선언대로 해소된 id 사이에 엣지 생성.
- **`@필드명` 문법**: 공통 조각의 좌표 필드(anchor로 해소된 노드)를 참조 — cross-layer 기본 닻(occurs_in)의 표현 수단.
- **`optional: true`**: from/to 필드가 빈 행에서는 해당 엣지만 조용히 생략(레코드 전체 보류 아님).
- **원칙 유지**: 관계 종류는 LLM이 아니라 스키마(사람이 쓴 값)가 결정. LLM은 식별(판정)만 담당. cross-layer 엣지의 생성 방향은 상위층→하위층 단방향(명세 §8-4).

## 5. 스키마 파일 구조

### 5.1 3층 구조

```
문서 봉투 (doc 단위)     doc_id, doc_type, source_path, revision, parsed_at, parser_version
  └ 조각 공통 (전 문서)   chunk_id, doc_type, process_group, process_ref, process_no(선택), electrode_type
      └ 조각 payload      doc_type별 스키마가 정의 (prose | table)
```

- 봉투는 문서 개정 시 **해당 문서 조각 전체 교체(재인입)** 의 단위.
- 공통 조각 필드 중 process_group/ref/no는 **공정 좌표**(anchor), electrode_type은 **속성 차원**(attribute, 질의 필터용).

### 5.2 doc_type 스키마 예시 (PFMEA — 표준 양식 기준 초안, 사내 실물로 교정)

```json
{
  "doc_type": "pfmea",
  "schema_version": 1,
  "layer": "quality",
  "use_blocks": ["common_core", "process_coord"],
  "fields": {
    "failure_mode":           {"role": "entity",    "category": "Failure"},
    "cause":                  {"role": "entity",    "category": "Failure"},
    "severity":               {"role": "attribute", "attach_to_field": "failure_mode", "optional": true},
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
- **설계 요점**: 고장모드와 고장원인은 같은 카테고리 **Failure**로 병합(같은 현상이 행에 따라 원인/모드로 등장 — 한 노드 해소로 causes 연쇄 성립. 방향은 카테고리가 아니라 행의 열 구분+edges가 부여). effect_category는 entity가 아니라 **anchor**(셀 관점 고장영향은 닫힌 Tier1 골격 — auto 생성 금지, 미스는 orphan_anchor). nested(모드 1:원인 N)는 파서가 모드×원인 쌍으로 전개(자기완결 레코드).

### 5.3 Control Plan 배정 예시 (초안)

| 열 | 배정 |
|---|---|
| 공정번호/공정명 | anchor |
| 설비/지그 | entity(Unit) |
| 관리항목(제품·공정특성) | entity(Property) + edges: 설비 has_property 관리항목 |
| 규격/공차 | attribute → 관리항목 (attr_name: spec) |
| 측정방법/주기/샘플 | attribute → 관리항목 |
| 대응계획 | content |

※ 카테고리 배정은 층의 카테고리 목록에 종속된다. **걸침 문서**(PFMEA처럼 여러 층의 카테고리를 담는 문서)는
필드의 `target_layer`가 층을 지정하므로 한 번의 인입이 여러 층 그래프에 기록된다 — 소비 주체 라우팅 불요(명세 §15.7 규칙 A).

### 5.4 블록(fragment) 조립

- 여러 doc_type에서 반복되는 필드 묶음은 블록으로 승격하여 `use_blocks`로 조립.
- **승격 규칙**: 블록을 미리 발명하지 않는다. 2~3개 스키마에서 같은 묶음이 관찰되면 승격 (공통 코어·공정좌표는 이미 전 문서 공통으로 확정 → 첫날부터 블록).
- 블록도 값(B)이므로 코드 리스크 0 — 로더가 dict를 합칠 뿐.

### 5.5 필드 spec 속성 일람 (스키마 작성 시 사용 가능한 전체 문법)

| 속성 | 적용 role | 의미 |
|---|---|---|
| `role` | 전체(필수) | anchor / entity / attribute / content / meta |
| `category` | entity(필수) | 층의 닫힌 카테고리 목록에서 지정 |
| `target_category` | anchor | 조회 대상 골격 카테고리 (생략 시 공정 골격) |
| `attach_to_field` | entity·attribute·content | 부착/저장/describes 대상 필드 |
| `attr_name` | attribute | 저장 키 이름 (생략 시 필드명) |
| `target_layer` | entity | 걸침 필드 — 기록될 층 지정 (생략 시 스키마 헤더의 layer) |
| `contextual` | attribute | true면 맥락형 — 값을 [{context, value}] 리스트로 저장, 충돌은 context 그룹 내 비교 (§3.3) |
| `optional` | 전체 | true면 빈 값 허용(검증 통과), 관련 edges도 조용히 생략 |
| — 스키마 헤더 | — | `doc_type`, `schema_version`, `layer`(기본 소속 층), `use_blocks` |
| — edges | — | `from`/`to`(필드명 또는 `@좌표필드`), `relation`, `optional` |

## 6. 처리 메커니즘 (참고 — 코드 형태)

```python
HANDLERS = {
    "anchor": handle_anchor, "entity": handle_entity,
    "attribute": handle_attribute, "content": handle_content, "meta": handle_meta,
}

def ingest_record(record, schema, graph, dic):
    resolved = {}
    for field, spec in schema["fields"].items():
        resolved[field] = HANDLERS[spec["role"]](record.get(field), spec, graph, dic)
    for e in schema.get("edges", []):
        graph.add_edge(resolved[e["from"]], e["relation"], resolved[e["to"]])
```

- 코드에는 필드명이 등장하지 않는다. **role만이 코드로 가는 분기 스위치.**
- table 문서는 추출 LLM이 불필요 — role 선언이 추출을 대체하고, LLM은 개체 판정에만 남는다.
  (기존 원칙 "정형=규칙+매칭, 산문=판단+추출"의 자동 구현)
- **핸들러 3단 구조 (표준)**: 모든 핸들러는 `규칙 → LLM 폴백(훅) → 수정 큐` 순으로 처리한다.
  anchor/entity는 본래 이 구조이며, attribute/edges에는 폴백 훅 자리만 확보(실채움은 사내 갭 관찰 후 —
  빈 셀 부착·상동/병합 셀·복수값 셀·혼입 산문. 단 상동/병합/복수값의 1차 방어선은 파서의 자기완결 레코드 계약).
- **인입 검증**: 스키마에 없는 필드 → `unknown_field` 리뷰(파서-스키마 어긋남 신호). 스키마에 있는데 부재 → optional 검사.

## 7. 변경 등급 (무엇이 바뀌면 무엇을 고치나)

| 등급 | 사건 | 고치는 것 | 코드 변경 |
|---|---|---|---|
| L1 | 필드명 변경, 필드 추가/삭제 | 스키마 파일 한 줄 | **0** |
| L2 | 새 doc_type (기존 role로 표현 가능) | 스키마 파일 1개 추가 | **0** |
| L3 | 기존 role로 표현 불가한 필드 성격 | role 1종 + 핸들러 함수 1개 추가 | 함수 1개 (기존 무수정) |
| L4 | 그래프 모델 자체가 못 담는 정보 | 설계 재검토 | 구조 변경 |

- 범용성의 정의: L1~L2가 사건의 대부분이 되게 하고, **L3 비용을 함수 1개로 봉쇄**하는 것.
- L4는 어떤 설계로도 예방 불가한 영역 — 정직하게 명세에 기록.

## 8. 사내 작업 절차

### 8.1 첫 작업 = 검증 실험 (코딩 아님)
실물 문서 2~3종(PFMEA, Control Plan 우선)의 열 이름 전체에 role 배정을 시도한다.
- 배정 가능성 자체는 §2에 의해 보장 — 검증 대상은 **배정의 정확성**(이 열이 entity인가 content인가 등의 판단).
- 막히는 필드 발견 시 L3(role 추가)인지 L4(모델 문제)인지 판정 — 어느 쪽이든 근거를 갖고 진행.

### 8.2 새 doc_type 등록 워크플로우
```
1. 본 정의서 + mock 스키마를 사내 LLM에 제시
2. 실물 문서의 열 이름을 보여주고 "이 형식으로 작성" 요청
3. LLM이 스키마 초안 작성 (role 배정 판단 포함)
4. 사람 검토 — 필드당 5지선다 검수 (role 오배정만 잡으면 됨)
5. 스키마 파일 저장 → 완료. 코드 배포·수정 없음
```
- 3에서 LLM이 "어느 role에도 안 맞는다"고 답하면 그것이 §8.1의 검증 신호.
- 이 워크플로우는 향후 플랫폼의 "문서 타입 등록" 기능의 원형.
