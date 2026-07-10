"""core/query.py — 범용 읽기 파이프라인 (구현문서 §5, 명세 §5.6). 층 어휘 없음(§0-1).

읽기 전용(P6) — 질문 표현을 사전에 누적하지 않는다. config 구동(query_traverse·fact_templates).
제공 함수(라우터 cli/query.py가 조립):
  - link          : 링킹 1단 — 사전 표면형 스캔(긴 표면형 우선, 무LLM). 2단 LLM·3단 임베딩은 HOOK.
  - expand        : 확장 — config.query_traverse 스펙으로 core.neighbors(관계 개수·이름 무가정 순회).
  - collect_chunks: 수집 — 2-tier(직접>확장), 상한, 최신순, 잘림 로그.
  - graph_facts   : 그래프 사실 문장화 — 엣지(fact_templates) + 노드 attrs(attr:템플릿, 맥락형 한 줄씩).
  - flow_scope    : flow 질의용 골격 전체 범위(골격 category 노드 통째).
"""
from __future__ import annotations

import logging

from core.dictionary import normalize

log = logging.getLogger(__name__)

CHUNK_CAP = 8  # 수집 상한(명세 §5.6.3, 측정 후 조정)


# ----------------------------------------------------------------------
# 1) 링킹 — 사전 표면형 스캔 (긴 표면형 우선, 무LLM)
# ----------------------------------------------------------------------
def link(question, dic):
    """질문 문자열에서 사전 표면형을 긴 것 우선으로 스캔 → 후보 노드 id 목록(중복 제거, 전역).

    소비: 구축 때 쌓인 동의어가 질의 히트율로 회수되는 지점. 읽기 전용(P6) — 사전 미갱신.
    2단(사전 미스 시 LLM 언급 추출) / 3단(임베딩 청크 검색)은 HOOK(명세 §5.6.1·§5.6.6).
    """
    surfaces = sorted({s for s in dic.surfaces() if s}, key=len, reverse=True)
    remaining = question
    linked = []
    for surf in surfaces:
        if surf in remaining:
            for nid in dic.lookup(surf):
                if nid not in linked:
                    linked.append(nid)
            remaining = remaining.replace(surf, " " * len(surf))  # 긴 표면형 소거(부분 재매칭 방지)
    return linked


# ----------------------------------------------------------------------
# 2) 확장 — config.query_traverse 스펙 순회 (관계 개수·이름 무가정)
# ----------------------------------------------------------------------
def expand(linked, config, graph):
    """query_traverse의 각 관계·하위스펙(down/up/both …)마다 neighbors 호출, 합집합(seed 제외)."""
    traverse = config.get("query_traverse", {})
    expanded = set()
    for rel, sub_specs in traverse.items():
        for _name, spec in sub_specs.items():
            expanded |= graph.neighbors(linked, {rel: spec})
    expanded -= set(linked)
    return expanded


def flow_scope(config, graph):
    """flow 질의 — 골격 category 노드 통째(트리+precedes 체인 공급, 명세 §5.6.4)."""
    cat = config.get("skeleton", {}).get("category")
    return {nid for nid, n in graph.nodes.items() if n["category"] == cat}


# ----------------------------------------------------------------------
# 3) 수집 — 2-tier(직접>확장), 상한, 잘림 로그
# ----------------------------------------------------------------------
def collect_chunks(linked, expanded, chunks, cap=CHUNK_CAP):
    def gather(ids):
        out = []
        for nid in ids:
            for cid in chunks.chunks_for_node(nid):
                if cid not in out:
                    out.append(cid)
        return out

    tier1 = gather(linked)
    tier2 = [c for c in gather(expanded) if c not in tier1]
    ordered = _by_recent(tier1, chunks) + _by_recent(tier2, chunks)
    truncated = len(ordered) > cap
    if truncated:
        log.info("청크 잘림(tier2부터): %d → %d (잘림률 계기판)", len(ordered), cap)
    return ordered[:cap], truncated


def _by_recent(chunk_ids, chunks):
    # 최신순(문서 최신) 근사 — doc_id 역순 안정 정렬(mock: 나중 인입=최신)
    return sorted(chunk_ids, key=lambda c: chunks.chunks.get(c, {}).get("doc_id", ""), reverse=True)


# ----------------------------------------------------------------------
# 4) 그래프 사실 문장화 — 엣지 + 노드 attrs (config.fact_templates)
# ----------------------------------------------------------------------
def graph_facts(scope, graph, config):
    """scope(노드 id 집합)에 걸린 엣지·필드를 fact_templates로 문장화. 맥락형 attr은 context별 한 줄."""
    templates = config.get("fact_templates", {})
    facts = []
    seen = set()
    for e in graph.edges_incident(scope):
        tmpl = templates.get(e["rel"])
        if not tmpl:
            continue
        src = _canon(graph, e["src"])
        dst = _canon(graph, e["dst"])
        line = tmpl.format(src=src, dst=dst)
        if line not in seen:
            seen.add(line)
            facts.append(line)
    for nid in scope:
        node = graph.nodes.get(nid)
        if not node:
            continue
        for attr_name, items in node.get("attrs", {}).items():
            tmpl = templates.get(f"attr:{attr_name}")
            if not tmpl:
                continue
            for item in items:
                line = _render_attr(tmpl, node["canonical"], item)
                if line not in seen:
                    seen.add(line)
                    facts.append(line)
    return facts


def _render_attr(tmpl, node_canonical, item):
    value = item["value"]
    prov = ", ".join(item.get("provenance", []))
    prefix = ""
    ctx = item.get("context")
    if ctx:
        prefix = "[" + ", ".join(f"{k}={v}" for k, v in ctx.items()) + "] "
    return prefix + tmpl.format(node=node_canonical, value=value, prov=prov)


def _canon(graph, node_id):
    n = graph.nodes.get(node_id)
    return n["canonical"] if n else node_id
