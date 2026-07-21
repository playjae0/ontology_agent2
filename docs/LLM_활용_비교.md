# LLM 활용 비교 — `ontology_system` vs `ontology_agent2`

> **목적**: 두 온톨로지 구축 에이전트에서 LLM이 **어디에, 어느 수준으로, 어떤 계약으로** 쓰였는지를
> 코드 근거와 함께 정리한다. 명세(`docs/ontology_system_명세20.md`) 재작성 시 "LLM 역할" 절의
> 판단 재료로 사용하는 것을 전제로, 두 프로젝트의 실제 코드를 나란히 확보한다.
>
> **대상 코드**
> - `ontology_system` — 4단계 파일계약 파이프라인 (`1_parsing`/`2_skeleton`/`3_content`/`4_query`).
>   LLM 실물 경로가 **구현**되어 있고 프롬프트가 코드에 하드코딩됨.
> - `ontology_agent2` — config 구동 층형 아키텍처 (`core`/`layers`/`schemas`/`router`).
>   LLM 실물 경로가 **전부 훅(미구현)**이며, mock 규칙 + config로 동작하는 PoC.
>
> **한 줄 결론**: 아키텍처 성숙도는 `ontology_agent2`가 높지만, **실제로 실행되는 LLM 코드의 양은
> `ontology_system`이 압도적으로 많다.** 두 프로젝트는 "LLM을 실제로 돌려 구축·답변까지 해낸다"(system)
> 대 "LLM을 최소 식별 역할로 봉쇄하고 결정성·감사가능성을 코드/config로 확보한 뒤 나중에 훅에 꽂는다"(agent2)로
> 방향이 반대다.

---

## 0. 요약표 — LLM 호출 지점

| LLM 활용 지점 | `ontology_system` | `ontology_agent2` |
|---|---|---|
| **설비/인자 추출 (table)** | ✅ 실물 구현 (`llm_units`·`llm_factors`) | ❌ **불필요** — role 선언이 추출을 대체 |
| **청크 언급 추출 (prose)** | ✅ 실물 구현 (`llm_chunk_mentions`) | ⚠️ **훅만** — `extract_mentions` 실물 = `raise` |
| **개체 판정 (동의어 통합)** | ✅ 실물 구현 (`match_entity`) | ⚠️ **훅만** — `_llm_match` = `raise`, mock=문자열규칙 |
| **질문 링킹 LLM 폴백** | ✅ 실물 구현 (`link_entities` 폴백) | ⚠️ **훅만** — 사전 스캔만 구현 |
| **최종 답변 생성 (RAG Generation)** | ✅ **실물 구현** (`answer`) | ❌ **미구현** — 템플릿 사실 + 청크 원문 조립만 |
| **판정용 임베딩 후보검색** | ✅ 매칭에 배선됨 (`find_candidates`) | ⚠️ `embed()` 계약만, 배선 이연(F16) |
| **프롬프트 소재 위치** | 코드에 하드코딩 | config(`layers/*/config.json`) — 현재 플레이스홀더 |
| **실행 시 실제 LLM 호출** | USE_MOCK=0에서 5지점 호출 | 전 지점 mock/훅 — 실물 미실행 |

---

## PART A — `ontology_system` (LLM 실물 구현형)

### A-1. 공통 LLM 클라이언트

모든 생성형 호출은 단일 함수 `llm_json(system, user)`로 수렴한다.

```python
# common/llm_client.py
def llm_json(system: str, user: str) -> dict:
    resp = _get_client().chat.completions.create(
        model=config.CHAT_MODEL, temperature=0,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}])
    txt = resp.choices[0].message.content.strip()
    txt = txt.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        s, e = txt.find("{"), txt.rfind("}")
        return json.loads(txt[s:e + 1])
```

설정(`common/config.py`): `CHAT_MODEL="claude-opus-4-7"`, `EMBED_MODEL="BAAI/bge-m3"`,
`temperature=0`, `MATCH_THRESHOLD=0.85`, `TOP_K=8`, `USE_MOCK`(기본 1). 출력은 **JSON 강제**.

### A-2. LLM 지점 ① — 설비 추출 (Mode A, `2_skeleton/extract.py`)

```python
def llm_units(doc, sub_names):
    if config.USE_MOCK:
        ...  # 규칙기반 데모 (노칭 프레스/스태커/주액기 문자열 매칭)
    sys = ("제조 문서에서 설비(unit)를 추출한다. 각 설비의 소속 세부공정을 process_tag로 표기하되 "
           "반드시 아래 목록 중 하나(없으면 null). 측정값·인자·문서메타는 제외.")
    usr = json.dumps({"sub_processes": sub_names, "document": doc,
        "instruction": '{"units":[{"surface":"..","process_tag":"..|null"}]}'}, ensure_ascii=False)
    return llm_json(sys, usr).get("units", [])
```

### A-3. LLM 지점 ② — 관리인자 추출 (Mode B, `2_skeleton/extract.py`)

```python
def llm_factors(doc, sub_names, unit_names):
    ...
    sys = ("제조 문서에서 관리인자(Property)를 추출한다. 각 인자가 붙는 attach_to는 세부공정명 또는 "
           "그 아래 설비명 중 하나. 규격값은 spec으로 분리, 실측값·날짜·사건은 제외.")
    usr = json.dumps({"sub_processes": sub_names, "units": unit_names, "document": doc,
        "instruction": '{"factors":[{"surface":"..","attach_to":"..","spec":"..|null"}]}'}, ...)
    return llm_json(sys, usr).get("factors", [])
```

> ★ 여기서 LLM은 **table/문서에서 설비·인자를 직접 추출**한다. (agent2는 이 역할을 role 선언으로 대체 → 아래 B-2.)

### A-4. LLM 지점 ③ — 개체 판정 (`2_skeleton/matching.py`)

```python
def match_entity(surface, candidates, category) -> dict:
    if config.USE_MOCK:                                   # 오프라인: 문자열 규칙
        ...
    sys = ("당신은 개체해소 판정기다. 표면 단어가 아니라 의미·문맥으로 같은 개념인지 판정하라. "
           "애매하면 병합하지 말고 uncertain. confidence 0~1.")
    usr = json.dumps({"mention": surface, "category": category, "candidates": cand,
        "instruction": '{"type":"match|new|uncertain","matched_id":"..|null","confidence":0.0}'}, ...)
    return llm_json(sys, usr)
```

`resolve_or_capture`가 매칭 성공(≥0.85) 시 `sk.add_alias`로 **동의어를 누적**한다 — 사전이 크는 유일 경로.

### A-5. LLM 지점 ④ — 청크 주제 개체 추출 (Mode D, `3_content/extract_content.py`)

```python
def llm_chunk_mentions(chunk_text, section, names_by_cat):
    if config.USE_MOCK: ...
    sys_p = ("당신은 제조 문서 청크의 '주제'를 식별한다. 이 청크가 주제로서 서술하는 "
             "공정/설비/인자 개체만 추출하라. 지나가며 언급만 된 단어는 제외하라. 애매하면 빼는 쪽을 택하라.")
    usr = json.dumps({"section_hint": section, "chunk_text": chunk_text,
        "known_entities": names_by_cat,
        "instruction": '{"mentions":[{"surface":"..","category_hint":"Process|Unit|Property"}]}'}, ...)
    return llm_json(sys_p, usr).get("mentions", [])
```

### A-6. LLM 지점 ⑤ — 최종 답변 생성 (GraphRAG, `4_query/query.py`)

```python
def answer(question, store, cids):
    ...
    if config.USE_MOCK:
        return "[MOCK 답변] ..."
    sys_p = ("당신은 제조 공정 지식 어시스턴트다. 제공된 청크 원문에 근거해서만 답하라. "
             "근거에 없는 내용은 모른다고 말하라. 답변 끝에 사용한 출처([청크ID | 문서 | 섹션])를 표기하라.")
    usr = json.dumps({"question": question, "chunks": context,
                      "instruction": '{"answer":"...","sources":["C0001",".."]}'}, ...)
    r = llm_json(sys_p, usr)
    return f"{r.get('answer','')}\n\n출처: {', '.join(r.get('sources', []))}"
```

또한 링킹 폴백(`link_entities`)에서 사전 미스 시 `"질문에서 공정/설비/관리인자 개체 표현만 추출하라."`로
LLM 언급 추출을 한 번 더 호출한다.

**A 정리**: `ontology_system`은 LLM을 **추출(2종) + 개체판정 + 청크주제추출 + 답변생성 + 링킹폴백**의
5지점에서 **실제로 호출**한다. 프롬프트가 코드에 완비돼 있고, 특히 **RAG 답변 생성**이라는 LLM 노출도가
가장 높은 단계가 구현돼 있다.

---

## PART B — `ontology_agent2` (LLM 봉쇄·훅형)

### B-1. LLM 역할 3분할 — 명세 §7에 명문화

`ontology_agent2`는 LLM의 자유도를 코드가 아니라 **설계 계약으로 봉쇄**한다.

> **"사람이 구조를, 규칙이 관계를, LLM이 식별을."** (명세 §7)

| 주체 | 결정하는 것 |
|---|---|
| 사람 | 골격(seed)·카테고리 정의문·관계 유형·스키마(role·edges)·프롬프트 — 전부 config 값(B) |
| 규칙(코드) | 관계 선택·사전 조회·후보 검색·임계 비교·**처리 순서** |
| LLM | **식별만** — 추출(무엇이 언급됐나+닫힌 목록 분류) · 개체 판정(같은 개념인가) |

명세 §7이 못박은 제약(= 명세 재작성 시 유지/재검토 대상):
- **"LLM 판정 지점은 두 곳뿐"** — 추출·개체판정. 그 외 금지.
- **"관계는 LLM이 결정하지 않는다"** → 관계 오류가 **구조적으로 불가능**("LLM이 실수할 자유 자체가 없음").
- **"제어 흐름은 코드 소유"** — 구축 파이프라인의 **에이전트화 금지**(재현·감사 보존). 에이전트화 허용은
  개체 판정 한 지점뿐이며 그것도 도입 보류(P7, 측정 후).
- **"정형=규칙+매칭, 산문=판단+추출"** → **table 문서는 추출 LLM 불필요**, LLM은 개체 판정에만 남음.

### B-2. LLM 게이트웨이 — 실물 경로가 훅

```python
# core/llm.py
def extract_mentions(chunk, config):
    """prose 청크 언급 추출 → [{surface, category}] (명세 §5.4-1, §7)."""
    if use_mock():
        meta = chunk.get("meta") or {}
        return list(meta.get("mock_mentions", []))            # ← 파서 mock이 넣은 추출 시뮬레이션
    raise RuntimeError("실물 추출 경로 미구현 — USE_MOCK=1로 실행하거나 게이트웨이 연결 필요")

def call_gateway(prompt, *, system=None, json_out=True):
    if use_mock():
        raise RuntimeError("call_gateway는 USE_MOCK=1에서 호출되면 안 된다 — 규칙 폴백 경로 누락")
    ...  # urllib 구현은 있으나 mock에서 호출 금지, 실물 프롬프트 조립 로직 없음
```

`ontology_system`의 추출 LLM에 대응하는 자리이지만, **mock에서는 파서가 청크 `meta.mock_mentions`에
넣어준 값**을 그대로 반환한다. 즉 "무엇이 언급됐나"의 정답을 **파서 mock이 공급**하고, 코드는 그것을
개체 판정 경로로 흘려보낼 뿐이다.

**mock 언급 주입 예** (`mock/parsed/PPT01.json`):
```json
{ "chunk_id": "PPT01-P1", "process_ref": "노칭",
  "text": "노칭 프레스는 전극 원단을 정밀 타발한다. 금형 관리가 품질의 핵심이며...",
  "meta": {"mock_mentions": [{"surface": "노칭 프레스", "category": "Unit"}]} }
```

### B-3. 개체 판정 — mock은 문자열 규칙, 실물 LLM은 훅

```python
# core/matcher.py
def match(surface, candidates, category, threshold=0.85):
    if llm.use_mock():
        return _mock_match(surface, candidates, category, threshold)
    return _llm_match(surface, candidates, category, threshold)  # HOOK: 실물

def _mock_match(surface, candidates, category, threshold):
    nsurf = normalize(surface)
    for c in candidates:
        if category is not None and c.get("category") != category:
            continue                                  # 카테고리 불일치 안전망 — 조용한 오병합 차단
        ...  # 정규화 후 동일=0.95, 포함=0.90
    ...

def _llm_match(surface, candidates, category, threshold):
    raise RuntimeError("실물 판정 경로 미구현 — USE_MOCK=1로 실행하거나 게이트웨이 연결 필요")
```

판정 프롬프트의 **설계 지침**은 명세 §5.4에 서술돼 있으나 코드/`config.json`에는 플레이스홀더뿐이다:

```json
// layers/quality/config.json
"prompts": {
  "extract": "(훅만 — PoC 미사용, prose 추출 경로는 품질층 미도입)",
  "judge":   "(공정층과 동일 규칙)"
}
```

> 명세 §5.4 판정 지침(요지): "글자 유사성 아닌 의미·문맥으로 판단" + 표기 변형 안내 +
> **비대칭 기준**("확신 없으면 match가 아니라 uncertain — 잘못된 병합이 잘못된 신규보다 해롭다").
> 출력 `{"type":"match|new|uncertain","matched_id","confidence"}`.

### B-4. 추출을 role 선언이 대체 — table 경로 (핵심 설계)

`ontology_system`이 LLM으로 하던 "문서에서 무엇을 뽑을까"를 `agent2`는 **스키마 role 배정**으로 치환한다.
table(Excel) 문서는 열마다 role(anchor/entity/attribute/content/meta)이 선언돼 있어, ingest가 그 선언대로
해소·부착한다 — **추출 LLM 없이**.

```python
# core/ingest.py — role 5종 핸들러 루프. LLM은 handle_entity 내부의 matcher.match 한 곳만 잠재 소비.
HANDLERS = {"anchor": handle_anchor, "entity": handle_entity,
            "attribute": handle_attribute, "content": handle_content, "meta": handle_meta}

def handle_entity(field, value, spec, ctx):
    ...
    category = spec["category"]                       # ← 카테고리를 스키마가 선언(LLM 분류 불필요)
    # F13 닫힌 카테고리 검증: 목록 밖이면 invalid_category 큐(생성 보류)
    if category not in target_cfg.get("categories", {}):
        ctx.enqueue("invalid_category", ...); return None
    ...
    result = matcher.match(canonical, cands, category, threshold=...)  # ← 유일한 LLM 잠재 지점
    if result["type"] == "match":
        _register(...); return nid                    # 매칭 → alias 누적
    # 신규/불확실 → 둘 다 신규 생성(status=auto), 검토 큐로 표면화(§7-5 "되돌리기 쉬운 쪽")
```

관계도 LLM이 아니라 `(카테고리쌍→관계)` 매핑·스키마 `edges` 선언이 결정한다:

```python
def attach_entity(nid, category, spec, ctx, target_layer):
    cpm = ctx.layers_cfg.get(target_layer, {}).get("category_pair_map", {})
    if f"{category},{tcat}" in cpm:      rel, src, dst = cpm[f"{category},{tcat}"], nid, target_id
    elif f"{tcat},{category}" in cpm:    rel, src, dst = cpm[f"{tcat},{category}"], target_id, nid
    else:                                 return None      # 매핑 없으면 부착 안 함
    ctx.graphs[target_layer].add_edge(src, rel, dst, status="confirmed", ...)
```

prose 경로(`ingest_prose`)만이 `llm.extract_mentions`를 소비하지만, 위에서 봤듯 mock에서는 파서가
언급을 공급하고 실물은 훅이다.

### B-5. 질의(답변)에서의 LLM — 미구현, 조립만

`ontology_system`은 질의 마지막에 LLM이 답변을 **생성**했다. `agent2`의 현 코드는 **그래프 사실(템플릿
문장) + 문서 근거(청크 원문)를 조립**만 한다. 답변 채널 선택조차 LLM이 아니라 **키워드 분류(mock)**다.

```python
# cli/query.py
_EXTERNAL = ["영어로", "무슨 뜻", "동작 원리", ...]
_VALUE    = ["규격", "공차", "스펙", "얼마"]
_STRUCTURE= ["다음", "이전", "설비", "흐름", "관리하는", ...]

def classify(question, linked_count):
    """실물에선 답변 LLM이 채널을 고르는 지점(§5.6.4)의 MOCK 대체."""
    if any(p in question for p in _EXTERNAL):  return "general_knowledge", False
    if linked_count == 0:                      return "general_knowledge", False
    ...

def _compose(question, path, facts, chunk_ids, s, linked):
    ...
    if path == "general_knowledge":
        lines.append("[일반지식 — 사내 검증 필요] (LLM 일반지식 답변 위치 — 실물 경로)")  # ← 훅 자리
    if facts:      lines += ["[그래프 사실]"] + [f"  - {f}" for f in facts]      # 템플릿 문장
    if chunk_ids:  lines += ["[문서 근거]"] + [청크 원문 나열]                    # LLM 생성 아님
```

그래프 사실은 `fact_templates`로 문자열 포맷된다 (LLM 불요):

```json
// layers/quality/config.json
"fact_templates": {
  "occurs_in":     "{src}는 {dst} 공정에서 발생한다",
  "controlled_by": "{src}는 {dst}(으)로 관리한다",
  "attr:severity": "{node}의 심각도(S): {value}"
}
```

> 명세 §5.6.4는 GraphRAG(그래프로 Retrieval, LLM이 Generation)로 **설계**돼 있으나,
> **현 코드는 Generation 단계가 미구현**(조립·나열까지만). "LLM은 마지막에만 등장"이 설계 의도지만
> PoC에서는 그 마지막 등장 자체가 아직 훅이다.

### B-6. 임베딩 — 계약만, 배선 이연

```python
# core/embeddings.py
def embed(text) -> list:
    if llm.use_mock():
        log.warning("MOCK 임베딩 — 수치 무의미. 유사도 판단에 쓰지 말 것.")
        ... # sha256 → 32차원 L2정규화
    return _real_embed(str(text))   # sentence-transformers 지연 import (실물)
```

`embed()` 계약은 제공되나 **후보검색(사전 정확일치 + 임베딩 top-k)에 배선되지 않음**(F16, 이연).
현재 `handle_entity`의 후보는 **사전 정확 조회만** 사용한다. (system은 `find_candidates`가 임베딩 코사인
top-k를 매칭에 실제로 먹인다 — 이 점이 배선 여부의 실질 차이.)

**B 정리**: `agent2`에서 LLM이 잠재적으로 개입하는 지점은 명세상 딱 두 곳(추출·개체판정)이며, **현 코드는
그 두 곳이 모두 훅/mock**이다. 지능은 (a) 파서(구조화 레코드 + 좌표 태깅 + mock 언급), (b) 스키마 role 선언,
(c) config(카테고리 정의문·관계 매핑·문장화 템플릿), (d) 결정적 규칙(사전 조회·임계·2-pass·mirror self-heal·
재인입)으로 이동했다.

---

## PART C — 나란히 비교 & 명세 시사점

### C-1. 항목별 대조

| 관점 | `ontology_system` | `ontology_agent2` |
|---|---|---|
| LLM 실동작 지점 | 5곳 (추출2·판정·청크추출·답변) | 0곳 실행 (2곳 훅 + 나머지 규칙/이연) |
| 추출("무엇을 뽑나") | LLM이 문서에서 직접 | **role 선언(table)** / prose는 훅 |
| 카테고리 분류 | LLM (추출과 함께) | **스키마 `category` 선언** + 닫힌목록 검증 |
| 개체 판정("같은 개념?") | LLM 실물 (프롬프트 있음) | 훅 (mock=문자열 정규화 규칙) |
| 관계 결정 | 코드(모드별 부착 규칙) | 코드(`category_pair_map`·`edges`) — LLM 원천 배제 |
| 답변 생성 | **LLM RAG 실물** | 템플릿 사실 + 청크 조립 (LLM 미구현) |
| 프롬프트 관리 | 코드 하드코딩 | config 값(현재 플레이스홀더) |
| 임베딩 | 매칭에 배선 | 계약만, 배선 이연(F16) |
| 결정성/재현성 | temperature=0로 확보 | **제어흐름 코드 고정 + 에이전트화 금지**로 원천 확보 |
| 감사(provenance) | provenance 필드 존재 | 재인입 회수/보존/재평가 3분류 + self-heal 큐 |
| 층 확장 비용 | 코드 수정 | **config.json + schema만, 코드 0** |

### C-2. 사상 차이 (명세 재작성 시 핵심 축)

1. **LLM 신뢰 범위**: system은 LLM에게 추출·분류·판정·생성을 맡긴다. agent2는 "**LLM이 실수할 자유
   자체를 구조로 제거**"하는 방향 — 관계·제어흐름·카테고리 발명을 전부 코드/config가 잠근다.
2. **추출의 소멸**: agent2의 "정형=규칙+매칭" 원칙은 table에서 추출 LLM을 아예 없앤다. 이는
   system 대비 **LLM 호출 횟수·비용·오류표면을 크게 줄이는** 대신, **파서·스키마 품질에 의존**을 옮긴다.
3. **답변 채널**: system은 답변을 LLM이 만든다. agent2는 그래프 사실(구조·값)과 청크 원문(서술)을
   **두 채널로 분리**해 조립하고, LLM 생성은 그 위에 얹는 마지막 훅으로 남긴다(현재 미구현).
   → 명세 §5.6.4의 "답변 3단 규칙"(근거 있음/없음/미스로그)과 "일반지식 경계표시 계약"이 이 조립층에
   대응한다.
4. **성숙도의 역설**: agent2가 엔지니어링(범용성·감사·재인입·self-heal)은 앞서지만, **지금 실행되는
   LLM 지능은 거의 없다**. 명세는 "LLM 훅을 언제·어떻게 실물로 채우는가"(P7 측정 기준: 수정 큐 건수
   감소)를 구체화하는 것이 다음 과제.

### C-3. 명세 반영 체크리스트 (제안)

- [ ] LLM 지점을 명세에서 **"실물 구현 / 훅 / 규칙 대체"**로 3분류해 표로 고정 (지금은 §7 서술형).
- [ ] 추출 훅(prose `extract_mentions`)과 판정 훅(`_llm_match`)의 **프롬프트 문안을 config로 승격** —
      §5.4 지침 → `layers/*/config.json` `prompts`의 실제 값. (system의 프롬프트 5종이 참고 초안.)
- [ ] 답변 생성(§5.6.4)의 실물 경로 정의: LLM 입력 = 그래프 사실 + 청크 두 채널, 출력 = 답+출처,
      경계표시 계약. (system `query.answer` 프롬프트가 참고 초안.)
- [ ] 임베딩 후보검색 배선(F16) 완료 조건 명시: 사전 정확일치 + 임베딩 top-k 폴백을 `handle_entity`/
      링킹 2·3단에 연결. (system `find_candidates`가 참고 구현.)
- [ ] 카테고리 분류 정책 확정: agent2는 스키마 선언(table)·추출 LLM(prose 훅). system은 추출과 동시 분류.
      두 경로의 **카테고리 불일치 안전망**(match 금지) 동작을 명세에 통일 기술.

---

## PART D — 개체 해소 능력 분석 (이름 변형 대응)

> 검토 질문: "role/스키마 기반이면 **동의어·오타·대소문자·한↔영·어순** 등 **이름이 다른** 개체를
> 연결할 방법이 없는 것 아닌가? 이건 원래 LLM이 해야 하는 일인데, agent2는 규칙으로 된다고 보는 것인가,
> 아니면 보완 장치가 있는가?"

### D-1. 개념 분리 — role이 푸는 문제 ≠ 이름 매칭 문제

role/스키마가 결정하는 것은 **"어디에 붙고(anchor/attach) 무슨 관계인가(edges/category_pair_map)"**뿐이다.
"이름이 달라도 같은 개념인가"(개체 해소, entity resolution)는 role의 영역이 **아니며**, `agent2`에서도
오직 `matcher.match` 한 지점이 담당한다. 따라서 검토 질문의 전제("role 기반이면 이름 변형 대응 불가")는 옳다 —
이름 변형 흡수는 role이 아니라 매칭기의 몫이다.

### D-2. 규칙(normalize)이 실제로 흡수하는 변형 — 딱 2가지

```python
# core/dictionary.py
def normalize(surface) -> str:
    """표면형 정규화 키 — 공백 제거 + 소문자화."""
    return "".join(str(surface).split()).lower()

def lookup(self, surface):
    return [item["id"] for item in self.entries.get(normalize(surface), [])]  # 정규화 키 완전일치
```

후보 생성은 이 **정규화 키의 완전일치 조회**뿐이다(`handle_entity`의 `cands = ctx.dic.lookup(canonical)`).
따라서 규칙이 자동으로 흡수하는 이름 변형은:

- ✅ **띄어쓰기** 차이 ("노칭 프레스" = "노칭프레스")
- ✅ **영문 대소문자** ("Notching" = "notching")

### D-3. 규칙이 대응 못 하는 변형 — 검토 질문의 거의 전부

| 변형 유형 | 규칙(normalize)으로? | 결과 |
|---|---|---|
| 오타 ("노칭프레스" vs "노징프레스") | ❌ 다른 키 | 후보 0 → **신규 노드** |
| 동의어 ("노칭 프레스" vs "래미네이터"/"적층기") | ❌ 공유 키 없음 | **신규 노드** |
| 한↔영 ("노칭 프레스" vs "notching press") | ❌ `노칭프레스`≠`notchingpress` | **신규 노드** |
| 어순 ("노칭 프레스" vs "프레스 노칭") | ❌ 포함관계도 아님 | **신규 노드** |
| 축약 ("초음파 융착기" vs "USW") | ❌ (부분포함만 0.90) | 대부분 **신규 노드** |

**자기네 mock 데이터가 이를 증명한다** (`mock/parsed/PPT01.json`): P1 청크는 `{"surface":"노칭 프레스",
"category":"Unit"}`, P8 청크는 `{"surface":"notching press","category":"Unit"}`(같은 노칭 공정, 영어).
규칙만으로는 `노칭프레스`≠`notchingpress`라 **서로 다른 Unit 노드 2개**가 생긴다 — 같은 설비인데 연결 안 됨.

### D-4. 보완 장치 — 설계엔 3중, 코드엔 1개만 실동작

| 보완 장치 | 상태 | 설명 |
|---|---|---|
| ① LLM 개체 판정 (`_llm_match`) | ⚠️ **훅** (`raise`) | "의미·문맥으로 같은 개념" — 의미 기반 매칭이 있어야 할 자리 |
| ② 임베딩 후보검색 | ⚠️ **이연(F16)** | 의미 근접 후보를 뽑아 판정기에 공급. 현재 후보는 사전 완전일치뿐 |
| ③ 매칭 실패 → 신규 노드 + 검토 큐 | ✅ **실동작** | `auto_node`/`uncertain_match`로 사람 검토에 위임 |

즉 **"이름 변형을 자동 흡수하는 지능(LLM·임베딩)은 현재 코드에 안 꽂혀 있다."** 살아있는 동작은
"못 붙이면 **중복 노드 생성 + 검토 큐**"뿐 — 자동 연결이 아니라 **사람에게 위임**하는 형태의 보완만 있다.
(한 번 어떤 수단으로든 매칭되면 그 표면형이 alias로 등재돼 다음부터는 사전 완전일치로 잡힌다. 문제는
"처음 보는 변형"이고, 그 첫 등장을 잡을 수단이 ①②인데 지금 없으므로 첫 등장은 사실상 반드시 신규가 된다.)

대조: `system`은 실물 모드에서 `find_candidates`가 **임베딩 코사인 top-k**로 후보를 만들고
`match_entity`가 **LLM 판정**을 실제 호출한다 → 이름 변형 흡수를 실제로 시도한다. 이 능력만 놓고 보면
현재는 `system`이 앞서고 `agent2`는 설계도만 있는 상태.

### D-5. "훅만 채우면 system과 동일한가?" — 개체 판정 지점 한정으로만 그렇다

- **맞는 부분**: 개체 판정이라는 역할 배정의 **의도는 동일**하고, 훅을 채우면 그 지점은 수렴한다.
- **조건**: 판정 훅(①)만 채우면 부족하다. 후보가 사전 완전일치뿐이면 처음 보는 동의어는 **후보 목록이 비어**
  LLM에게 줄 게 없다 → 여전히 신규로 샌다. 따라서 **임베딩 후보검색(②) 배선이 판정의 전제조건**이며,
  ①②를 **한 세트**로 채워야 `system`과 같아진다. (명세 반영 시 이 의존관계를 강제할 것 — C-3 참조.)
- **구현으로도 안 메워지는 차이**: 훅을 다 채워도 `agent2`의 LLM 역할 범위는 설계상 더 좁다 —
  **table 추출을 LLM에서 제거(role 대체)**, 답변 생성은 두 채널 조립 위의 얇은 훅, 관계 결정은 영원히 배제.
  즉 "동일 역할"은 **개체 판정 지점에 한정**해서만 성립한다.

---

## PART E — 관계(relation) 소유권 비교

> 검토 질문: "매칭 말고, **관계를 규정하고 이어주는 기능**에서도 차이가 있지 않나?"
> → 있다. 오히려 매칭보다 더 본질적인 설계 분기다.

### E-1. 공통점 — 둘 다 관계는 LLM이 결정하지 않는다

`system`·`agent2` 모두 관계 유형은 사람/코드가 정하고 LLM은 관여하지 않는다. 이 철학은 동일하다.
차이는 **관계 로직이 "코드"에 있느냐 "데이터(config)"에 있느냐**이다.

### E-2. `system` — 관계가 코드에 하드코딩

```python
# 2_skeleton/modes.py
def mode_build_units(...):       # Mode A는 항상 part_of (unit→process)
    sk.add_edge(Edge(uid, "part_of", it.attach_to, "approved", status="confirmed"))
def mode_extract_factors(...):   # Mode B는 항상 has_property
    sk.add_edge(Edge(it.attach_to, "has_property", pid, "approved", status="confirmed"))
```

- 관계 종류가 `part_of / precedes / has_property / describes` 넷으로 **고정**.
- 새 관계 추가 = **새 모드 함수(코드) 작성**. 단일 그래프 내부로 한정 — 층 개념 없음.

### E-3. `agent2` — 관계가 config 데이터, core엔 관계 어휘 0

```python
# core/ingest.py  attach_entity — 카테고리 쌍으로 관계를 "조회"(무가정 순회)
cpm = ctx.layers_cfg[target_layer].get("category_pair_map", {})
if f"{category},{tcat}" in cpm:   rel, src, dst = cpm[f"{category},{tcat}"], nid, target_id
elif f"{tcat},{category}" in cpm: rel, src, dst = cpm[f"{tcat},{category}"], target_id, nid
else:                              return None       # 매핑 없으면 부착 안 함
```
```json
// layers/quality/config.json — 관계·문장화 전부 값
"relations": ["causes", "affects", "occurs_in", "controlled_by"],
"category_pair_map": {...},
"fact_templates": {"occurs_in": "{src}는 {dst} 공정에서 발생한다", ...}
```

- **core에 관계 어휘가 없다.** 새 관계 추가 = `category_pair_map`+`fact_template`에 한 줄, **코드 0**.
- **cross-layer 관계**(`occurs_in`·`controlled_by`) 지원 — 층을 넘어 잇는다. `system`엔 없는 개념.

### E-4. `agent2`만 가진 관계-연결 장치 3가지

1. **결정적 좌표 부착(anchor)** — `process_ref` 공정좌표를 **사전 완전일치로** 붙인다(LLM 추측 아님).
   미스 시 `orphan_anchor` 큐. `system`은 부착 대상도 fuzzy 매칭(`resolve_anchor`)을 태운다.
   ```python
   # core/ingest.py  handle_anchor — Tier1(seed) 노드로 후보 제한, 미스→orphan
   cands = [n for n in found if "seed" in (n.get("provenance") or [])]
   if not cands: ctx.enqueue("orphan_anchor", ...); return None
   ```
2. **2-pass 인입** — Pass1에서 문서 내 개체를 모두 해소한 뒤 Pass2에서 관계 생성 → 부착 실패가
   "순서 문제"인지 "진짜 미해소"인지 구분(orphan 노이즈 감소). `system`은 인라인이라 순서 의존이 남는다.
3. **mirrors 자동 관계 규칙** — 극성 대칭(cathode↔anode) 노드를 **문자열 비교로 자동 연결**하고
   자식 구성 비대칭이면 `mirror_asymmetry` 큐로 표면화하는 self-heal(`apply_mirrors`). `system`에 없는,
   관계를 **자동 생성+감사**하는 기능. (LLM 불요 — 규칙.)

### E-5. 정리

| 관계 관점 | `system` | `agent2` |
|---|---|---|
| 관계를 누가 정하나 | 코드/사람 (LLM 아님) | 코드/사람 (LLM 아님) — **동일** |
| 관계 로직 위치 | **코드 하드코딩**(modes.py) | **config 데이터**(category_pair_map·edges) |
| 관계 집합 | 고정 4종 | config로 임의 확장 |
| 층 간 관계 | ❌ 없음 | ✅ cross-layer |
| 부착 앵커 | fuzzy 매칭 | **결정적 사전 조회**(anchor) |
| 관계 생성 순서 | 인라인 | **2-pass** |
| 자동 관계 규칙 | ❌ | ✅ mirrors + self-heal |

**→ 관계 역할은 "누가 정하나"는 같지만(둘 다 LLM 배제), 코드 vs config·단층 vs 다층·고정 vs 임의·
수동 vs 자동규칙에서 갈린다. 이는 구현으로 메울 격차가 아니라 아키텍처 분기다.**

---

## 부록 — LLM 관점 파이프라인 대조

```
[ontology_system]  (LLM 5지점 실동작)
 parsed → Mode A(llm_units)·B(llm_factors) → match_entity → 승인 → 뼈대
                                              └ embed(후보랭킹)
        → Mode D(llm_chunk_mentions) → match_entity → describes
        → query: link(LLM폴백) → 그래프탐색 → 청크수집 → answer(LLM 생성+출처)

[ontology_agent2]  (LLM 0지점 실행 — 훅/규칙)
 parser(구조화+좌표+mock_mentions)
   → build: reinject → ingest 2-pass
        · table: role 핸들러(추출 LLM 없음) → handle_entity → matcher.match(훅/mock규칙)
        · prose: extract_mentions(훅/mock) → handle_entity → describes
      → mirrors(문자열, LLM불요) → sweep(evidence_lost·review 큐) → save
   → query: link(사전스캔) → expand(config) → collect → _compose(템플릿+청크, LLM생성 훅)
```
