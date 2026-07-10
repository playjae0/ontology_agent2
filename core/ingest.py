"""core/ingest.py — role 핸들러 루프 + edges 후처리 + 검증 + 재인입 + mirrors 자동 규칙.

정의서 §6 / 명세 §6.6 / 구현문서 §3. 층 어휘 없음(§0-1) — 카테고리·관계·개체·극성값은
전부 schema/config가 준 값. 코드 분기 스위치는 role 5종뿐.

구조:
  - Ctx           : 핸들러 공통 컨텍스트(graphs·dic·queue·chunks·doc·record·schema·config·resolved).
  - ingest_doc    : 2-pass (Pass1 anchor/entity 해소 → Pass2 attribute/content/meta + edges 후처리).
  - HANDLERS      : role 5종 핸들러(anchor/entity/attribute/content/meta). edges는 핸들러 아님(루프 후처리).
  - apply_mirrors : config.mirrors.enabled 시 극성 대칭 노드 자동 연결 + mirror_asymmetry 큐.
  - reinject      : 재인입 — doc_id 단위로 provenance 회수, provenance-0 auto 산출물은 evidence_lost 큐.
"""
from __future__ import annotations

import logging

from core import matcher, llm

log = logging.getLogger(__name__)

# 봉투/공통조각의 구조 필드 — 스키마 fields에 없어도 unknown_field로 보지 않음(§6.5)
STRUCTURAL_FIELDS = {"doc_type", "electrode_type", "context"}


# ======================================================================
# 컨텍스트
# ======================================================================
class Ctx:
    """핸들러 공통 컨텍스트. graphs=층별 Graph dict — id 전역이라 노드 조회는 전 층 스캔.

    layers_cfg = 전 층 config(층 무관 조립용). entity 부착 시 대상 층의 category_pair_map을
    쓰기 위해 필요(걸침 필드는 다른 층에 부착될 수 있음 — 정의서 §3.2, 명세 §15.7).
    """

    def __init__(self, graphs, dic, queue, chunks, doc, config, schema, layers_cfg=None):
        self.graphs = graphs
        self.dic = dic
        self.queue = queue
        self.chunks = chunks
        self.doc = doc
        self.config = config
        self.schema = schema
        self.layers_cfg = layers_cfg or {config.get("layer"): config}
        self.record = None       # 현재 record (pass별로 설정)
        self.resolved = None     # 현재 record의 field->id (pass2)

    def node(self, node_id):
        for g in self.graphs.values():
            if node_id in g.nodes:
                return g.nodes[node_id]
        return None

    def graph_of(self, node_id):
        for g in self.graphs.values():
            if node_id in g.nodes:
                return g
        return None

    def chunk_id(self):
        return self.record.get("chunk_id")

    def prov(self):
        """이 record의 provenance = chunk_id (없으면 doc_id)."""
        return [self.record.get("chunk_id") or self.doc["doc_id"]]

    def record_context(self):
        """맥락형 attribute 그룹핑 키 — record.context가 있으면 그것, 없으면 봉투 context 상속(§6.2)."""
        if self.record.get("context") is not None:
            return self.record["context"]
        return self.doc.get("context", {})

    def enqueue(self, kind, payload, reason):
        self.queue.add(kind, payload, self.doc["doc_id"], reason, self.doc.get("parsed_at", ""))


def _empty(value):
    return value is None or value == "" or value == []


# ======================================================================
# 핸들러 5종 (정의서 §3)
# ======================================================================
def handle_anchor(field, value, spec, ctx):
    """닻 — 이미 존재하는 골격 노드 조회. auto 생성 폴백 금지(골격=Tier1, §3.1). 미스→orphan_anchor."""
    if _empty(value):
        return None
    target_cat = spec.get("target_category")
    cands = [ctx.node(cid) for cid in ctx.dic.lookup(value)]
    cands = [n for n in cands if n and (target_cat is None or n["category"] == target_cat)]
    if len(cands) == 1:
        return cands[0]["id"]
    if len(cands) > 1:
        # 골격은 보통 유일. 표면형 완전일치를 우선 선택, 없으면 첫째(결정적).
        exact = [n for n in cands if n["canonical"] == value]
        return (exact[0] if exact else cands[0])["id"]
    ctx.enqueue("orphan_anchor",
                {"field": field, "surface": value, "target_category": target_cat},
                reason="anchor 미스 — 골격에 없음(auto 생성 금지, orphan)")
    return None


def handle_entity(field, value, spec, ctx):
    """개체 — 사전조회→후보검색→판정 3분기(매칭/신규/불확실). 극성 결합 canonical(config.polarity)."""
    if _empty(value):
        return None
    category = spec["category"]
    surface = str(value).strip()
    polarity = _polarity_for(ctx, category)                 # cathode/anode or None (config 구동)
    canonical = f"{polarity} {surface}" if polarity else surface
    target_layer = spec.get("target_layer") or ctx.schema.get("layer") or ctx.doc.get("layer")
    graph = ctx.graphs[target_layer]
    prov = ctx.prov()

    # 후보 = 사전 조회(canonical) 필터(category + target_layer)
    cands = []
    for cid in ctx.dic.lookup(canonical):
        n = ctx.node(cid)
        if n and n["category"] == category and n["layer"] == target_layer:
            cands.append(n)

    result = matcher.match(canonical, cands, category,
                           threshold=ctx.config.get("match_threshold", 0.85))

    if result["type"] == "match":
        nid = result["matched_id"]
        _register(ctx, graph, nid, canonical, surface, polarity, prov)  # alias 누적
        return nid

    # 신규(auto) 또는 불확실 → 되돌리기 쉬운 쪽: 둘 다 신규 생성 + 큐(명세 §7-5)
    extra = {}
    if polarity:
        extra["electrode_type"] = polarity
    nid = graph.add_node(canonical, category, layer=target_layer,
                         status="auto", provenance=prov, **extra)
    _register(ctx, graph, nid, canonical, surface, polarity, prov)
    if result["type"] == "uncertain":
        ctx.enqueue("uncertain_match",
                    {"surface": canonical, "node": nid, "candidates": [c["id"] for c in cands]},
                    reason="판정 불확실 — 신규 생성(되돌리기 쉬운 쪽)")
    else:
        ctx.enqueue("auto_node",
                    {"surface": canonical, "node": nid, "category": category},
                    reason="신규 개체 자동 생성(status=auto)")
    return nid


def _register(ctx, graph, nid, canonical, surface, polarity, prov):
    """사전·노드 alias 등재. 극성 결합 시 표면형(극성 제거)도 alias 공유(명세 §5.2)."""
    ctx.dic.register(canonical, nid, prov)
    graph.add_alias(nid, canonical, prov)
    if polarity and surface != canonical:
        ctx.dic.register(surface, nid, prov)
        graph.add_alias(nid, surface, prov)


def handle_attribute(field, value, spec, ctx):
    """속성 — 부착 대상(entity/anchor 해소 노드)의 필드에 저장. 맥락형/충돌 규칙(정의서 §3.3)."""
    if _empty(value):
        return None
    target_field = spec.get("attach_to_field")
    node_id = ctx.resolved.get(target_field)
    if node_id is None:
        # 부착 대상 미해소 → 저장 보류(폴백 훅 자리 — 명세 §7-6). 조용히 드롭.
        log.info("attribute '%s' 부착 대상 '%s' 미해소 — 저장 보류", field, target_field)
        return None
    node = ctx.node(node_id)
    attr_name = spec.get("attr_name") or field
    contextual = bool(spec.get("contextual", False))
    context = ctx.record_context() if contextual else {}
    _apply_attr(node, attr_name, value, context, contextual, ctx.prov(), ctx, node_id)
    return node_id


def _apply_attr(node, attr_name, value, context, contextual, provenance, ctx, node_id):
    lst = node["attrs"].setdefault(attr_name, [])
    for ex in lst:
        ex_ctx = ex.get("context", {})
        if ex_ctx == context:                       # 같은 context 그룹 내에서만 비교
            if ex["value"] == value:                # 완전 동일(deep-equal) → provenance 병합
                for p in provenance:
                    if p not in ex["provenance"]:
                        ex["provenance"].append(p)
                return
            # 같은 context 다른 값 → spec_conflict(덮어쓰지 않음 — 개정 이력, 명세 §9)
            ctx.enqueue("spec_conflict",
                        {"node": node_id, "attr": attr_name, "context": context,
                         "existing": ex["value"], "incoming": value},
                        reason="같은 context 그룹에서 기존과 다른 값")
            return
    # 없으면 항목 추가 (다른 context = 충돌 아니라 병렬 항목, 정의서 §3.3)
    item = {"value": value, "provenance": list(provenance)}
    if contextual:
        item = {"context": context, "value": value, "provenance": list(provenance)}
    lst.append(item)


def handle_content(field, value, spec, ctx):
    """서술 — 청크 보존 + describes. table 경로는 attach_to_field로 대상 직접 지정(LLM 추출 없음).

    prose 경로(LLM 언급 추출)는 build에서 별도 처리(단위 1d). 여기서는 table content(§3.4)를 처리.
    한 record에 content 필드가 여럿이면 필드별 별도 청크(id={chunk_id}-{field}, 정의서 §3.4).
    """
    if _empty(value):
        return None
    sub_chunk_id = f"{ctx.chunk_id()}-{field}"
    target_field = spec.get("attach_to_field")
    node_id = ctx.resolved.get(target_field) if target_field else None
    ctx.chunks.add_chunk(sub_chunk_id, doc_id=ctx.doc["doc_id"], text=str(value),
                         section=None, meta={"field": field}, linked=node_id is not None)
    if node_id is not None:
        ctx.chunks.add_describes(sub_chunk_id, node_id)
    else:
        ctx.enqueue("orphan_chunk_link",
                    {"chunk_id": sub_chunk_id, "attach_to_field": target_field},
                    reason="content 부착 대상 미해소")
    return None


def handle_meta(field, value, spec, ctx):
    """관리 정보 — 그래프 무기록(출처 장부용). 저장만(정의서 §3.5)."""
    return None


def attach_entity(nid, category, spec, ctx, target_layer):
    """(카테고리쌍→관계) 매핑으로 entity를 부착 대상에 연결 (명세 §5.3·§7-2, 정의서 §3.2).

    부착 대상 = attach_to_field(명시) → 없으면 @process_ref(규칙B 폴백 — 공정좌표, 명세 §15.7).
    관계 = 대상 층의 category_pair_map에서 양방향 조회('src,dst' 자연 방향). 매핑 없으면 부착 안 함.
    부착 대상 미해소면 부착 드롭(레코드 보류 아님 — R13 연쇄: process_ref orphan → 부착 드롭).
    """
    attach_field = spec.get("attach_to_field")
    target_id = ctx.resolved.get(attach_field) if attach_field else None
    if target_id is None:
        target_id = ctx.resolved.get("process_ref")          # 규칙B 폴백(공정좌표)
    if target_id is None:
        log.info("entity 부착 대상 미해소 — 부착 드롭(nid=%s)", nid)
        return None
    target_node = ctx.node(target_id)
    if target_node is None:
        return None
    cpm = ctx.layers_cfg.get(target_layer, {}).get("category_pair_map", {})
    tcat = target_node["category"]
    if f"{category},{tcat}" in cpm:                           # 자연 방향 entity→대상
        rel, src, dst = cpm[f"{category},{tcat}"], nid, target_id
    elif f"{tcat},{category}" in cpm:                         # 자연 방향 대상→entity
        rel, src, dst = cpm[f"{tcat},{category}"], target_id, nid
    else:
        return None                                          # 매핑 없음 — 부착 안 함(유무 무가정)
    ctx.graphs[target_layer].add_edge(src, rel, dst, status="confirmed", provenance=ctx.prov())
    return (src, rel, dst)


HANDLERS = {
    "anchor": handle_anchor,
    "entity": handle_entity,
    "attribute": handle_attribute,
    "content": handle_content,
    "meta": handle_meta,
}

PASS1_ROLES = ("anchor", "entity")           # 해소 (버퍼)
PASS2_ROLES = ("attribute", "content", "meta")  # 부착


def _polarity_for(ctx, category):
    """config.polarity로 이 record가 극성 결합 대상인지 판정. config 없으면 항상 None(유무 무가정)."""
    pol = ctx.config.get("polarity")
    if not pol:
        return None
    if category not in pol.get("bind_categories", []):
        return None
    val = ctx.record.get(pol.get("field", "electrode_type"))
    return val if val in pol.get("values", []) else None


# ======================================================================
# 2-pass 인입
# ======================================================================
def ingest_doc(doc, schema, ctx):
    """문서 내 2-pass 인입(명세 §5.5-1). records(table) 또는 chunks(prose 좌표부)를 처리."""
    fields = schema["fields"]
    records = doc.get("records") or []
    layer = schema.get("layer") or doc.get("layer")
    graph = ctx.graphs[layer]

    # Pass1: 전 record의 anchor/entity 해소 → 버퍼
    resolved_all = []
    for rec in records:
        ctx.record = rec
        _validate_record(rec, fields, ctx)
        resolved = {}
        for f, spec in fields.items():
            if spec["role"] in PASS1_ROLES:
                resolved[f] = HANDLERS[spec["role"]](f, rec.get(f), spec, ctx)
        resolved_all.append(resolved)

    # Pass2: attribute/content/meta 적용 + 걸침 entity 부착 + edges 후처리 (문서 내 개체 모두 존재)
    for rec, resolved in zip(records, resolved_all):
        ctx.record = rec
        ctx.resolved = resolved
        for f, spec in fields.items():
            if spec["role"] in PASS2_ROLES:
                HANDLERS[spec["role"]](f, rec.get(f), spec, ctx)
        # 걸침 entity(target_layer ≠ 문서 층)는 (카테고리쌍→관계)로 대상 층에 부착(규칙B, §15.7)
        for f, spec in fields.items():
            if spec["role"] == "entity" and resolved.get(f) is not None:
                tl = spec.get("target_layer") or layer
                if tl != layer:
                    attach_entity(resolved[f], spec["category"], spec, ctx, tl)
        _make_edges(schema.get("edges", []), resolved, ctx, graph)


def ingest_prose(doc, ctx):
    """prose 문서 인입(명세 §5.5·§5.6.1, 정의서 §3.4).

    전 청크 원문 보존(링킹 0건도 — 하이브리드 서치 전제, §5.6.6). 언급 추출(LLM/MOCK)
    → 개체 판정 경로로 해소(신규는 auto 생성 + 큐) → describes 연결. 미해소 언급은 orphan_chunk_link.
    """
    layer = ctx.schema.get("layer") or doc.get("layer")
    skel_cat = ctx.config.get("skeleton", {}).get("category")
    for chunk in doc.get("chunks", []):
        ctx.record = chunk
        cid = chunk["chunk_id"]
        mentions = llm.extract_mentions(chunk, ctx.config)          # MOCK: meta.mock_mentions
        # 청크 공정좌표 해소 — prose 관계(카테고리쌍→관계)의 부착 앵커(§7-2)
        ctx.resolved = {"process_ref": handle_anchor(
            "process_ref", chunk.get("process_ref"), {"target_category": skel_cat}, ctx)}
        meta = {k: v for k, v in (chunk.get("meta") or {}).items() if k != "mock_mentions"}
        ctx.chunks.add_chunk(cid, doc["doc_id"], chunk.get("text", ""),
                             section=chunk.get("section"), meta=meta, linked=False)
        for m in mentions:
            spec = {"role": "entity", "category": m["category"]}
            nid = handle_entity("(prose)", m.get("surface"), spec, ctx)
            if nid is not None:
                ctx.chunks.add_describes(cid, nid)                  # 해소된 노드에 연결
                attach_entity(nid, m["category"], spec, ctx, layer)  # 카테고리쌍→관계로 공정좌표 부착
            else:
                ctx.enqueue("orphan_chunk_link", {"chunk_id": cid, "surface": m.get("surface")},
                            reason="prose 언급 미해소")
    # 링킹 0건 청크는 linked=False로 보존(전 청크 보존 — P5·§5.6.6)


def _validate_record(rec, fields, ctx):
    """인입 검증(§6.5) — 스키마에 없는 필드 → unknown_field. 봉투 구조 필드는 제외."""
    known = set(fields) | STRUCTURAL_FIELDS
    for k in rec:
        if k not in known:
            ctx.enqueue("unknown_field", {"field": k, "chunk_id": rec.get("chunk_id")},
                        reason="스키마에 없는 필드 — 파서-스키마 어긋남 신호")


def _make_edges(edges, resolved, ctx, default_graph):
    """edges 선언대로 해소된 id 사이에 엣지 생성(핸들러 아님, 루프 후처리 — 정의서 §4).

    cross-layer 엣지는 상위층(src) 그래프에 저장(명세 §8-4) — src 노드가 있는 그래프에 add.
    문서 근거 엣지는 confirmed(P5). from/to 미해소(optional) 시 해당 엣지만 조용히 생략.
    """
    for e in edges:
        src = _resolve_ref(e["from"], resolved)
        dst = _resolve_ref(e["to"], resolved)
        if src is None or dst is None:
            continue  # optional 여부와 무관 — 미해소 엣지는 생략(레코드 전체 보류 아님)
        graph = ctx.graph_of(src) or default_graph
        graph.add_edge(src, e["relation"], dst, status="confirmed", provenance=ctx.prov())


def _resolve_ref(ref, resolved):
    """edges의 from/to 참조 해소. '@필드' = 공통 좌표 필드(anchor 해소 노드) 참조(정의서 §4)."""
    key = ref[1:] if isinstance(ref, str) and ref.startswith("@") else ref
    return resolved.get(key)


# ======================================================================
# mirrors 자동 규칙 (명세 §5.3) — config.mirrors.enabled·config.polarity 구동
# ======================================================================
def apply_mirrors(graph, config, queue, doc_id, parsed_at=""):
    """극성 대칭 노드 자동 연결 + 자식 대칭 검사 (self-heal). config.mirrors.enabled·polarity 구동.

    **self-heal (매 build 재평가)**: 이 층의 기존 mirror_asymmetry 항목을 먼저 걷어내고 현재 그래프
    상태로 재작성한다. (category, 극성제거 canonical) 그룹당 항목 1건(부모 맥락은 payload.shared).
    → 재인입·후속문서로 대칭이 회복되면 항목이 사라지고, 비대칭이 지속되면 1건만 유지(폭증 없음).
    극성별 자식 시그니처의 **합집합** 비교라 중복 노드(재인입 부작용, KNOWN_ISSUES)에도 강건.
    문자열 비교(LLM 불요 — 명세 §5.3).
    """
    mcfg = config.get("mirrors", {})
    layer = config.get("layer")
    if not mcfg.get("enabled"):
        return
    relation = mcfg["relation"]
    values = config.get("polarity", {}).get("values", [])
    if len(values) != 2:
        log.warning("mirrors enabled이나 polarity.values 2종 아님 — 건너뜀")
        return
    a_val, b_val = values[0], values[1]
    # 형제(순서) 관계는 자식 대칭 비교에서 제외 — precedes 순차가 극성 Process 쌍의 오탐 비대칭을
    # 만들지 않게(명세 §5.3은 "자식(part_of/has_property) 수·구성" 비교). 관계명은 config에서.
    sibling_rel = config.get("skeleton", {}).get("relations", {}).get("sibling")
    skip_rels = {relation} | ({sibling_rel} if sibling_rel else set())

    def strip(canon):
        for v in values:
            if canon.startswith(v + " "):
                return canon[len(v) + 1:]
        return canon

    # self-heal ①: 이 층의 기존 mirror_asymmetry 항목 전부 제거 → 현재 상태로 재작성
    queue.remove(lambda i: i["kind"] == "mirror_asymmetry" and i.get("payload", {}).get("layer") == layer)

    # (category, 극성제거 canonical)로 그룹 → 극성별 노드 목록(중복 노드도 각 측에 모임)
    groups = {}
    for nid, n in graph.nodes.items():
        et = n.get("electrode_type")
        if et not in values:
            continue
        groups.setdefault((n["category"], strip(n["canonical"])), {}).setdefault(et, []).append(nid)

    for (cat, base), by_pol in groups.items():
        cath = by_pol.get(a_val, [])
        anod = by_pol.get(b_val, [])
        if not cath or not anod:
            continue
        # mirror 엣지 생성(중복 엣지는 add_edge가 provenance 병합만) — 재평가라 idempotent
        for x in cath:
            for y in anod:
                graph.add_edge(x, relation, y, status="auto", provenance=["auto:mirror_rule"])
        # self-heal ②: 극성별 자식 시그니처 합집합 비교(짝 측 노드·형제관계 제외) → 대칭이면 항목 없음
        cath_sig = set().union(*(_incident_sig(graph, x, set(anod), strip, skip_rels) for x in cath))
        anod_sig = set().union(*(_incident_sig(graph, y, set(cath), strip, skip_rels) for y in anod))
        only_a, only_b = cath_sig - anod_sig, anod_sig - cath_sig
        if only_a or only_b:
            queue.add("mirror_asymmetry",
                      {"layer": layer, "category": cat, "base": base,
                       "shared": sorted(str(s) for s in (cath_sig & anod_sig)),
                       "only_a": sorted(str(s) for s in only_a),
                       "only_b": sorted(str(s) for s in only_b)},
                      doc_id, "극성 대칭 선언 후 자식 수·구성 불일치(문서 누락 vs 진짜 차이)", parsed_at)


def _incident_sig(graph, nid, exclude, strip, skip_rels):
    """노드에 걸린 엣지 시그니처 = {(rel, 방향, 극성제거 상대 canonical)}. skip_rels·짝 노드·툼스톤 제외."""
    sig = set()
    for e in graph.edges:
        if e["rel"] in skip_rels or e.get("status") == "deleted_by_user":
            continue
        if e["src"] == nid and e["dst"] not in exclude:
            other = graph.nodes.get(e["dst"])
            sig.add((e["rel"], "out", strip(other["canonical"]) if other else e["dst"]))
        elif e["dst"] == nid and e["src"] not in exclude:
            other = graph.nodes.get(e["src"])
            sig.add((e["rel"], "in", strip(other["canonical"]) if other else e["src"]))
    return sig


# ======================================================================
# 재인입 (명세 §5.5-3) — doc_id 단위 provenance 회수
# ======================================================================
def reinject(doc_id, graphs, dic, chunks, queue, parsed_at=""):
    """개정 문서 재인입 전 해당 doc_id의 발자국 회수.

    노드/엣지/alias/attribute 값 항목의 provenance에서 doc_id 소속 항목 제거.
    노드·엣지 자체는 삭제하지 않음(다른 문서가 근거일 수 있음). provenance-0이 된 auto
    산출물은 evidence_lost 큐(자동 삭제 금지 — 되돌리기 쉬운 쪽). 청크·describes는 회수.
    """
    def belongs(p):
        return p == doc_id or (isinstance(p, str) and p.startswith(doc_id + "-"))

    def filt(prov):
        return [p for p in prov if not belongs(p)]

    for g in graphs.values():
        # 노드 provenance + alias + attribute 항목
        for nid, n in n_items(g):
            before = len(n["provenance"])
            n["provenance"] = filt(n["provenance"])
            n["aliases"] = _filt_aliases(n["aliases"], belongs)
            _filt_attrs(n["attrs"], belongs)
            if n["status"] == "auto" and before and not n["provenance"]:
                queue.add("evidence_lost", {"node": nid, "canonical": n["canonical"]},
                          doc_id, "근거 소멸 — provenance 0(자동 삭제 금지)", parsed_at)
        # 엣지 provenance
        kept = []
        for e in g.edges:
            if e.get("status") == "deleted_by_user":
                kept.append(e)
                continue
            had = len(e["provenance"])
            e["provenance"] = filt(e["provenance"])
            if had and not e["provenance"]:
                queue.add("evidence_lost", {"edge": [e["src"], e["rel"], e["dst"]]},
                          doc_id, "엣지 근거 소멸 — provenance 0", parsed_at)
                # 자동 삭제 금지 — 엣지도 남기되 근거 0 표시(큐로 표면화)
            kept.append(e)
        g.edges = kept

    # 사전 provenance 회수 (빈 항목 제거)
    for key in list(dic.entries):
        bucket = []
        for item in dic.entries[key]:
            item["provenance"] = filt(item["provenance"])
            if item["provenance"]:
                bucket.append(item)
        if bucket:
            dic.entries[key] = bucket
        else:
            del dic.entries[key]

    chunks.remove_doc(doc_id)


def n_items(graph):
    return list(graph.nodes.items())


def _filt_aliases(aliases, belongs):
    out = []
    for a in aliases:
        a["provenance"] = [p for p in a["provenance"] if not belongs(p)]
        if a["provenance"]:
            out.append(a)
    return out


def _filt_attrs(attrs, belongs):
    for name in list(attrs):
        kept = []
        for item in attrs[name]:
            item["provenance"] = [p for p in item["provenance"] if not belongs(p)]
            if item["provenance"]:
                kept.append(item)
        if kept:
            attrs[name] = kept
        else:
            del attrs[name]
