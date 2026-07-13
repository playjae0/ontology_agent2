#!/usr/bin/env python3
"""viz.py — 시각화 실행 (표준 라이브러리만, 외부 패키지 0).

  python viz.py html [--open]     data/ 그래프 → out/ontology.html (vis.js CDN 단일 파일)
  python viz.py cypher            → out/ontology.cypher (명세 §11 파생물)
  python viz.py neo4j             cypher 생성 + Neo4j 적재(드라이버 있으면) + Browser 안내

진실은 data/의 JSON 그래프 — 여기서 만드는 것은 전부 **재생성 가능한 파생물/뷰**(P5).
**읽기 전용** — data/를 수정하지 않는다. deleted_by_user 엣지는 제외(툼스톤은 진실엔 남지만 뷰엔 없음).

층 어휘 무가정(§0-1·§3.6): 카테고리 색·관계 선 스타일·mirrors 관계명·극성 값은 코드에 박지 않고
layers/*/config.json과 그래프 데이터에서 읽어 **발견 순서대로** 팔레트를 배정한다.
층·카테고리·관계가 몇 개든, 이름이 무엇이든 그대로 그린다.
"""
from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

import router  # noqa: E402

DEFAULT_DATA = PROJECT_ROOT / "data"
OUT_DIR = PROJECT_ROOT / "out"
EGO_THRESHOLD = 300          # 노드 수가 이보다 많으면 기본 ego 뷰(전체는 토글) — 대규모 force 멈춤 방지

# 색·선 스타일 팔레트 — 값(층 어휘 아님). 카테고리/관계에 발견 순서대로 배정된다.
PALETTE = ["#4C8BF5", "#F5A623", "#7ED321", "#BD10E0", "#50E3C2",
           "#E36B6B", "#B8A25C", "#9B9B9B", "#417505", "#9013FE"]
DASHES = [False, [8, 4], [2, 3], [12, 4, 2, 4], [4, 2]]


# ----------------------------------------------------------------------
# 로드 (읽기 전용)
# ----------------------------------------------------------------------
def load_graphs(data_root):
    """층별 graph.json + 공유 스토어 로드. 반환: (nodes, edges, chunks, describes, layers_cfg)

    nodes = {id: node(+layer)}, edges = 툼스톤 제외 전 층 엣지(+src_layer).
    """
    data_root = Path(data_root)
    layers_cfg = router.discover_layers(PROJECT_ROOT / "layers")
    nodes, edges = {}, []
    for layer in layers_cfg:
        gp = data_root / layer / "graph.json"
        if not gp.exists():
            continue
        g = json.loads(gp.read_text(encoding="utf-8"))
        for nid, n in g.get("nodes", {}).items():
            n.setdefault("layer", layer)
            nodes[nid] = n
        for e in g.get("edges", []):
            if e.get("status") == "deleted_by_user":     # 툼스톤 제외(뷰 전용 필터)
                continue
            e = dict(e, src_layer=layer)
            edges.append(e)
    cp = data_root / "chunks.json"
    store = json.loads(cp.read_text(encoding="utf-8")) if cp.exists() else {}
    return nodes, edges, store.get("chunks", {}), store.get("describes", []), layers_cfg


def _require(nodes, data_root):
    if not nodes:
        print(f"❌ 그래프가 비었다 — `python run.py all` 먼저 실행 ({data_root})", file=sys.stderr)
        raise SystemExit(1)


# ----------------------------------------------------------------------
# 뷰 모델 — 색·스타일 배정은 데이터/config에서(하드코딩 금지)
# ----------------------------------------------------------------------
def build_view(nodes, edges, chunks, describes, layers_cfg):
    # 카테고리: config 선언 순서 우선 + 데이터에서 발견된 것 뒤에 추가(유무 무가정)
    categories = []
    for cfg in layers_cfg.values():
        for cat in cfg.get("categories", {}):
            if cat not in categories:
                categories.append(cat)
    for n in nodes.values():
        if n["category"] not in categories:
            categories.append(n["category"])
    cat_color = {c: PALETTE[i % len(PALETTE)] for i, c in enumerate(categories)}

    # 관계: config.relations 선언 순서 + 데이터 발견분
    relations = []
    for cfg in layers_cfg.values():
        for rel in cfg.get("relations", []):
            if rel not in relations:
                relations.append(rel)
        for rel in cfg.get("cross_layer_traverse", {}):
            if rel not in relations:
                relations.append(rel)
    for e in edges:
        if e["rel"] not in relations:
            relations.append(e["rel"])
    rel_dash = {r: DASHES[i % len(DASHES)] for i, r in enumerate(relations)}

    # mirrors 관계명·극성 값 — config에서(코드에 박지 않음)
    mirror_rels = {cfg["mirrors"]["relation"] for cfg in layers_cfg.values()
                   if cfg.get("mirrors", {}).get("enabled") and cfg["mirrors"].get("relation")}
    polarity_values = sorted({v for cfg in layers_cfg.values()
                              for v in (cfg.get("polarity") or {}).get("values", [])})

    # 청크 역인덱스(노드 → 청크 원문) — 속성 패널 재료
    by_node = {}
    for d in describes:
        ch = chunks.get(d["chunk_id"], {})
        by_node.setdefault(d["node_id"], []).append(
            {"id": d["chunk_id"], "text": ch.get("text", ""), "doc": ch.get("doc_id", "")})

    vnodes = []
    for nid, n in nodes.items():
        et = n.get("electrode_type")
        vnodes.append({
            "id": nid,
            "label": n["canonical"],
            "group": n["category"],
            "layer": n["layer"],
            "category": n["category"],
            "status": n.get("status", ""),
            "electrode_type": et,
            "attrs": n.get("attrs", {}),
            "aliases": [a.get("surface") for a in n.get("aliases", [])],
            "provenance": n.get("provenance", []),
            "chunks": by_node.get(nid, []),
            "color": {"background": cat_color[n["category"]], "border": "#2b2b2b"},
            # 극성 노드는 모양으로 구별(cathode=삼각, anode=역삼각, 무극성=원) — 값은 config 유래
            "shape": ("triangle" if et and polarity_values and et == polarity_values[0]
                      else "triangleDown" if et else "dot"),
            "borderWidth": 3 if n.get("status") == "confirmed" else 1,
        })

    vedges = []
    for e in edges:
        dst_layer = nodes.get(e["dst"], {}).get("layer")
        src_layer = nodes.get(e["src"], {}).get("layer", e["src_layer"])
        cross = dst_layer is not None and dst_layer != src_layer
        is_mirror = e["rel"] in mirror_rels
        vedges.append({
            "from": e["src"], "to": e["dst"], "rel": e["rel"],
            "label": e["rel"],
            "cross": cross,
            "mirror": is_mirror,
            "status": e.get("status", ""),
            "provenance": e.get("provenance", []),
            "dashes": [6, 3] if is_mirror else rel_dash.get(e["rel"], False),
            "color": {"color": "#E0245E" if cross else ("#8E44AD" if is_mirror else "#9aa0a6"),
                      "opacity": 1.0 if cross else 0.7},
            "width": 3 if cross else (2 if is_mirror else 1),
            "arrows": {"to": {"enabled": not is_mirror}},   # mirrors는 대칭(무방향 표시)
        })

    return {
        "nodes": vnodes, "edges": vedges,
        "legend": {
            "categories": [{"name": c, "color": cat_color[c]} for c in categories
                           if any(n["category"] == c for n in nodes.values())],
            "relations": [{"name": r, "mirror": r in mirror_rels} for r in relations
                          if any(e["rel"] == r for e in edges)],
            "layers": sorted({n["layer"] for n in nodes.values()}),
            "polarity": polarity_values,
        },
        "stats": {
            "nodes": len(vnodes), "edges": len(vedges),
            "cross": sum(1 for e in vedges if e["cross"]),
            "mirrors": sum(1 for e in vedges if e["mirror"]),
        },
        "ego_threshold": EGO_THRESHOLD,
    }


# ----------------------------------------------------------------------
# HTML
# ----------------------------------------------------------------------
def cmd_html(args):
    nodes, edges, chunks, describes, cfg = load_graphs(args.data)
    _require(nodes, args.data)
    view = build_view(nodes, edges, chunks, describes, cfg)
    view["ego_threshold"] = args.threshold

    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / "ontology.html"
    out.write_text(HTML_TEMPLATE.replace("__DATA__", json.dumps(view, ensure_ascii=False)),
                   encoding="utf-8")

    st = view["stats"]
    mode = "ego(이웃)" if st["nodes"] > args.threshold else "전체"
    print(f"✅ {out}")
    print(f"   노드 {st['nodes']} · 엣지 {st['edges']} "
          f"(cross-layer {st['cross']} · mirrors {st['mirrors']}) — 기본 뷰: {mode}")
    if args.open:
        webbrowser.open(out.as_uri())
        print("   브라우저에서 열었다")
    return 0


# ----------------------------------------------------------------------
# Cypher (명세 §11 파생물)
# ----------------------------------------------------------------------
def _cy_str(v):
    return json.dumps(v, ensure_ascii=False)


def build_cypher(nodes, edges):
    """노드=라벨(category)+:Node, 엣지=관계 타입(rel). attrs·provenance는 JSON 문자열로 보존."""
    lines = [
        "// ontology_agent2 — data/ 그래프에서 재생성된 파생물(P5). 진실 아님.",
        "// 적재: cat out/ontology.cypher | cypher-shell -u neo4j -p <pw>",
        "// 재적재 전 초기화가 필요하면: MATCH (n:Node) DETACH DELETE n;",
        "CREATE CONSTRAINT node_id IF NOT EXISTS FOR (n:Node) REQUIRE n.id IS UNIQUE;",
        "",
    ]
    for nid, n in nodes.items():
        label = "".join(ch for ch in n["category"] if ch.isalnum()) or "Unknown"
        props = {
            "id": nid, "canonical": n["canonical"], "category": n["category"],
            "layer": n["layer"], "status": n.get("status", ""),
            "provenance": ", ".join(n.get("provenance", [])),
            "aliases": ", ".join(a.get("surface", "") for a in n.get("aliases", [])),
        }
        if n.get("electrode_type"):
            props["electrode_type"] = n["electrode_type"]
        if n.get("attrs"):
            props["attrs_json"] = json.dumps(n["attrs"], ensure_ascii=False)
        body = ", ".join(f"{k}: {_cy_str(v)}" for k, v in props.items())
        lines.append(f"MERGE (n:Node:{label} {{id: {_cy_str(nid)}}}) SET n += {{{body}}};")
    lines.append("")
    for e in edges:
        if e["src"] not in nodes or e["dst"] not in nodes:
            continue
        rel = "".join(ch if ch.isalnum() else "_" for ch in e["rel"]).upper()
        cross = nodes[e["src"]]["layer"] != nodes[e["dst"]]["layer"]
        props = {"status": e.get("status", ""),
                 "provenance": ", ".join(e.get("provenance", [])),
                 "cross_layer": cross}
        body = ", ".join(f"{k}: {_cy_str(v)}" for k, v in props.items())
        lines.append(
            f"MATCH (a:Node {{id: {_cy_str(e['src'])}}}), (b:Node {{id: {_cy_str(e['dst'])}}}) "
            f"MERGE (a)-[r:{rel}]->(b) SET r += {{{body}}};")
    return "\n".join(lines) + "\n"


def cmd_cypher(args):
    nodes, edges, _c, _d, _cfg = load_graphs(args.data)
    _require(nodes, args.data)
    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / "ontology.cypher"
    out.write_text(build_cypher(nodes, edges), encoding="utf-8")
    print(f"✅ {out}  (노드 {len(nodes)} · 엣지 {len(edges)})")
    print("   적재: cypher-shell -u neo4j -p <pw> -f out/ontology.cypher")
    print("   또는: python viz.py neo4j  (드라이버 있으면 자동 적재)")
    return 0


# ----------------------------------------------------------------------
# Neo4j 적재
# ----------------------------------------------------------------------
def cmd_neo4j(args):
    cmd_cypher(args)                                   # 파생물 먼저 생성(적재 실패해도 남는다)
    try:
        from neo4j import GraphDatabase             # 지연 import — 선택 의존(§0-8)
    except ImportError:
        print("\n⚠️  neo4j 드라이버 없음 — 적재 건너뜀.")
        print("   설치:  pip install neo4j")
        print("   서버:  docker run -d -p7474:7474 -p7687:7687 "
              "-e NEO4J_AUTH=neo4j/password neo4j:5")
        print("   수동 적재: cypher-shell -u neo4j -p password -f out/ontology.cypher")
        print("\n👉 지금 바로 보려면 드라이버·서버 없이:  python viz.py html --open")
        return 0                                        # 안내는 실패가 아니다

    uri, user, pw = args.uri, args.user, args.password
    statements = [s.strip() for s in (OUT_DIR / "ontology.cypher").read_text(encoding="utf-8")
                  .split(";\n") if s.strip() and not s.strip().startswith("//")]
    try:
        driver = GraphDatabase.driver(uri, auth=(user, pw))
        with driver.session() as session:
            if args.wipe:
                session.run("MATCH (n:Node) DETACH DELETE n")
                print("   기존 :Node 삭제(--wipe)")
            for st in statements:
                session.run(st)
        driver.close()
    except Exception as exc:
        print(f"\n⚠️  Neo4j 적재 실패({uri}): {type(exc).__name__}: {exc}")
        print("   서버가 떠 있는지 확인:  docker run -d -p7474:7474 -p7687:7687 "
              "-e NEO4J_AUTH=neo4j/password neo4j:5")
        print(f"   자격 증명: --user/--password (현재 {user}/***)")
        print("\n👉 대안:  python viz.py html --open")
        return 1
    print(f"\n✅ Neo4j 적재 완료 — {uri}")
    print("   Browser: http://localhost:7474  →  MATCH (n)-[r]->(m) RETURN n,r,m LIMIT 100")
    print("   cross-layer만: MATCH (n)-[r {cross_layer: true}]->(m) RETURN n,r,m")
    return 0


# ----------------------------------------------------------------------
HTML_TEMPLATE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<title>Ontology — 그래프 뷰</title>
<script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
<style>
  :root { color-scheme: light dark; }
  * { box-sizing: border-box; }
  body { margin:0; font: 14px/1.5 -apple-system, "Apple SD Gothic Neo", sans-serif;
         display:flex; height:100vh; background:#fbfbfd; color:#1d1d1f; }
  @media (prefers-color-scheme: dark) { body { background:#161618; color:#f0f0f2; } }
  #graph { flex:1; min-width:0; }
  #side { width: 340px; border-left:1px solid rgba(128,128,128,.3); padding:14px 16px;
          overflow-y:auto; }
  h1 { font-size:15px; margin:0 0 4px; }
  h2 { font-size:12px; text-transform:uppercase; letter-spacing:.05em; opacity:.6;
       margin:16px 0 6px; }
  .stat { font-size:12px; opacity:.75; }
  .row { display:flex; align-items:center; gap:6px; font-size:12px; padding:1px 0; }
  .sw { width:12px; height:12px; border-radius:3px; flex:none; border:1px solid rgba(0,0,0,.2); }
  .ln { width:22px; height:0; border-top:2px solid #9aa0a6; flex:none; }
  .ln.cross { border-color:#E0245E; border-top-width:3px; }
  .ln.mirror { border-top:2px dashed #8E44AD; }
  button { font:inherit; font-size:12px; padding:5px 10px; border-radius:6px; cursor:pointer;
           border:1px solid rgba(128,128,128,.4); background:transparent; color:inherit; }
  button.on { background:#4C8BF5; color:#fff; border-color:#4C8BF5; }
  #panel { margin-top:8px; font-size:12px; }
  #panel .k { opacity:.55; }
  #panel pre { background:rgba(128,128,128,.12); padding:8px; border-radius:6px;
               white-space:pre-wrap; word-break:break-all; font-size:11px; margin:4px 0; }
  .chunk { background:rgba(128,128,128,.1); padding:6px 8px; border-radius:6px; margin:4px 0; }
  .cid { font-size:10px; opacity:.6; }
  .hint { font-size:11px; opacity:.55; margin-top:6px; }
</style></head><body>
<div id="graph"></div>
<div id="side">
  <h1>Ontology 그래프</h1>
  <div class="stat" id="stats"></div>
  <div style="margin-top:10px; display:flex; gap:6px; flex-wrap:wrap;">
    <button id="btnMode"></button>
    <button id="btnFit">전체 맞춤</button>
    <button id="btnPhys" class="on">물리 on</button>
  </div>
  <div class="hint" id="modeHint"></div>
  <h2>카테고리</h2><div id="legendCat"></div>
  <h2>관계</h2><div id="legendRel"></div>
  <h2 id="selTitle">선택</h2>
  <div id="panel">노드를 클릭하면 속성·근거 청크가 여기 표시된다.</div>
</div>
<script>
const DATA = __DATA__;
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[<>&]/g, c => ({'<':'&lt;','>':'&gt;','&':'&amp;'}[c]));
const S = DATA.stats;
$('stats').textContent = `노드 ${S.nodes} · 엣지 ${S.edges} (cross-layer ${S.cross} · mirrors ${S.mirrors}) · 층 ${DATA.legend.layers.join(', ')}`;

// 범례 — 데이터에서 생성(하드코딩 없음)
$('legendCat').innerHTML = DATA.legend.categories.map(c =>
  `<div class="row"><span class="sw" style="background:${c.color}"></span>${esc(c.name)}</div>`).join('');
$('legendRel').innerHTML = DATA.legend.relations.map(r => {
  const cross = DATA.edges.some(e => e.rel === r.name && e.cross);
  const cls = cross ? 'ln cross' : (r.mirror ? 'ln mirror' : 'ln');
  const tag = cross ? ' <span style="color:#E0245E">cross-layer</span>' : (r.mirror ? ' (대칭)' : '');
  return `<div class="row"><span class="${cls}"></span>${esc(r.name)}${tag}</div>`;
}).join('') + (DATA.legend.polarity.length ?
  `<div class="row" style="margin-top:6px">▲ ${esc(DATA.legend.polarity[0])} · ▼ ${esc(DATA.legend.polarity[1] || '')} · ● 극성 무관</div>` : '');

// 규모 대비: 임계 초과면 ego 뷰가 기본(전체 force는 대규모에서 멈춤)
const BIG = DATA.stats.nodes > DATA.ego_threshold;
let egoMode = BIG, focus = null, physics = true;
const allNodes = new vis.DataSet(DATA.nodes);
const allEdges = new vis.DataSet(DATA.edges.map((e, i) => ({...e, id: 'e' + i})));
const nodesView = new vis.DataSet(DATA.nodes);
const edgesView = new vis.DataSet(DATA.edges.map((e, i) => ({...e, id: 'e' + i})));

const options = {
  physics: { stabilization: { iterations: 200 },
             barnesHut: { gravitationalConstant: -6000, springLength: 140, avoidOverlap: 0.3 } },
  nodes: { font: { size: 13, color: getComputedStyle(document.body).color },
           scaling: { min: 8, max: 24 }, size: 14 },
  edges: { font: { size: 9, align: 'middle', strokeWidth: 3 }, smooth: { type: 'dynamic' } },
  interaction: { hover: true, tooltipDelay: 150 },
};
const net = new vis.Network($('graph'), { nodes: nodesView, edges: edgesView }, options);

function applyMode() {
  $('btnMode').textContent = egoMode ? 'ego 뷰 (이웃만)' : '전체 뷰';
  $('btnMode').className = egoMode ? 'on' : '';
  $('modeHint').textContent = egoMode
    ? (focus ? 'ego: 선택 노드 + 1홉 이웃만 표시. 다른 노드를 클릭해 이동.'
             : `노드 ${DATA.stats.nodes}개 — 노드를 클릭하면 그 이웃만 표시(전체는 토글).`)
    : '전체 표시 — 규모가 크면 느릴 수 있다.';
  if (!egoMode) {
    nodesView.update(DATA.nodes); edgesView.update(allEdges.get());
    const keepN = new Set(DATA.nodes.map(n => n.id));
    nodesView.getIds().forEach(id => { if (!keepN.has(id)) nodesView.remove(id); });
    return;
  }
  const seed = focus;
  if (!seed) { // ego인데 선택 없음 → 골격(confirmed)만 미리보기
    const keep = DATA.nodes.filter(n => n.status === 'confirmed');
    const ids = new Set(keep.map(n => n.id));
    nodesView.clear(); nodesView.add(keep);
    edgesView.clear();
    edgesView.add(allEdges.get().filter(e => ids.has(e.from) && ids.has(e.to)));
    return;
  }
  const inc = allEdges.get().filter(e => e.from === seed || e.to === seed);
  const ids = new Set([seed, ...inc.map(e => e.from), ...inc.map(e => e.to)]);
  nodesView.clear(); nodesView.add(DATA.nodes.filter(n => ids.has(n.id)));
  edgesView.clear(); edgesView.add(inc);
}

net.on('click', p => {
  if (!p.nodes.length) return;
  focus = p.nodes[0];
  showPanel(allNodes.get(focus));
  if (egoMode) applyMode();
});
$('btnMode').onclick = () => { egoMode = !egoMode; applyMode(); };
$('btnFit').onclick = () => net.fit({ animation: true });
$('btnPhys').onclick = () => {
  physics = !physics;
  net.setOptions({ physics: { enabled: physics } });
  $('btnPhys').className = physics ? 'on' : '';
  $('btnPhys').textContent = physics ? '물리 on' : '물리 off';
};

function showPanel(n) {
  const inc = allEdges.get().filter(e => e.from === n.id || e.to === n.id);
  const rel = inc.map(e => {
    const other = allNodes.get(e.from === n.id ? e.to : e.from);
    const dir = e.from === n.id ? '→' : '←';
    const mark = e.cross ? ' <span style="color:#E0245E">[cross-layer]</span>' : '';
    return `<div class="row">${esc(e.rel)} ${dir} ${esc(other ? other.label : '?')}${mark}</div>`;
  }).join('') || '<div class="row" style="opacity:.5">(없음)</div>';
  const chunks = (n.chunks || []).map(c =>
    `<div class="chunk"><div class="cid">${esc(c.id)} · ${esc(c.doc)}</div>${esc(c.text)}</div>`
  ).join('') || '<div style="opacity:.5">(연결된 청크 없음)</div>';
  $('selTitle').textContent = '선택 — ' + n.label;
  $('panel').innerHTML = `
    <div><span class="k">canonical</span> <b>${esc(n.label)}</b></div>
    <div><span class="k">id</span> ${esc(n.id)} · <span class="k">층</span> ${esc(n.layer)}
         · <span class="k">카테고리</span> ${esc(n.category)}</div>
    <div><span class="k">status</span> ${esc(n.status)}${
      n.electrode_type ? ` · <span class="k">극성</span> ${esc(n.electrode_type)}` : ''}</div>
    <div><span class="k">aliases</span> ${esc((n.aliases || []).join(', ') || '—')}</div>
    <div><span class="k">provenance</span> ${esc((n.provenance || []).join(', ') || '—')}</div>
    ${Object.keys(n.attrs || {}).length
      ? `<h2>attrs</h2><pre>${esc(JSON.stringify(n.attrs, null, 2))}</pre>` : ''}
    <h2>엣지 (${inc.length})</h2>${rel}
    <h2>근거 청크 (${(n.chunks || []).length})</h2>${chunks}`;
}
applyMode();
</script></body></html>
"""


# ----------------------------------------------------------------------
def main(argv=None):
    parser = argparse.ArgumentParser(prog="viz.py", description="그래프 시각화(파생물 — P5, 읽기 전용)")
    parser.add_argument("--data", default=str(DEFAULT_DATA), help="데이터 루트(기본 data/)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_html = sub.add_parser("html", help="out/ontology.html 생성(vis.js)")
    p_html.add_argument("--open", action="store_true", help="생성 후 브라우저로 열기")
    p_html.add_argument("--threshold", type=int, default=EGO_THRESHOLD,
                        help=f"이 노드 수를 넘으면 ego 뷰가 기본(기본 {EGO_THRESHOLD})")
    sub.add_parser("cypher", help="out/ontology.cypher 생성(§11 파생물)")

    p_neo = sub.add_parser("neo4j", help="cypher 생성 + Neo4j 적재")
    p_neo.add_argument("--uri", default="bolt://localhost:7687")
    p_neo.add_argument("--user", default="neo4j")
    p_neo.add_argument("--password", default="password")
    p_neo.add_argument("--wipe", action="store_true", help="적재 전 기존 :Node 삭제")

    args = parser.parse_args(argv)
    return {"html": cmd_html, "cypher": cmd_cypher, "neo4j": cmd_neo4j}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
