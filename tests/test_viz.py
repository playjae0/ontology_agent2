"""test_viz — 실행 진입점(run.py) + 시각화(viz.py) 검증.

핵심 판정: **viz가 만든 뷰의 노드/엣지 수가 data/의 graph.json과 일치**(파생물이 진실을 빠짐없이·
더함없이 반영 — P5). deleted_by_user 툼스톤만 예외(뷰에서 제외).
+ run.py init/build/query/status가 exit 0. (run.py all은 여기서 부르지 않는다 — test를 포함하므로 재귀.)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from argparse import Namespace
from pathlib import Path

os.environ.setdefault("USE_MOCK", "1")

import viz
from core import build

ROOT = Path(__file__).resolve().parent.parent


def _seed(dr):
    """init + mock 전량 인입 — 진실 그래프 생성."""
    build.plant_skeletons(ROOT, dr)
    for name in ("CP01", "PPT01", "PFMEA01"):
        doc = json.loads((ROOT / f"mock/parsed/{name}.json").read_text(encoding="utf-8"))
        build.build_doc(doc, ROOT, dr)


def _truth(dr):
    """graph.json 직접 집계(진실). 툼스톤 제외 엣지 수."""
    n, e = 0, 0
    for gp in sorted(dr.glob("*/graph.json")):
        g = json.loads(gp.read_text(encoding="utf-8"))
        n += len(g["nodes"])
        e += sum(1 for x in g["edges"] if x.get("status") != "deleted_by_user")
    return n, e


def test_viz_matches_truth():
    """viz 뷰·HTML·cypher의 노드/엣지 수 = graph.json 집계(파생물 무결성)."""
    with tempfile.TemporaryDirectory() as tmp:
        dr = Path(tmp)
        _seed(dr)
        t_nodes, t_edges = _truth(dr)
        assert t_nodes > 0 and t_edges > 0

        nodes, edges, chunks, describes, cfg = viz.load_graphs(dr)
        assert len(nodes) == t_nodes, f"load 노드 {len(nodes)} != 진실 {t_nodes}"
        assert len(edges) == t_edges, f"load 엣지 {len(edges)} != 진실 {t_edges}"

        view = viz.build_view(nodes, edges, chunks, describes, cfg)
        assert view["stats"]["nodes"] == t_nodes and view["stats"]["edges"] == t_edges
        assert len(view["nodes"]) == t_nodes and len(view["edges"]) == t_edges

        # cross-layer 엣지가 실제로 잡히는가(층 넘는 게 핵심 볼거리 — §8)
        assert view["stats"]["cross"] > 0, "cross-layer 엣지 0 — 브리지 표시 불가"
        assert view["stats"]["mirrors"] > 0, "mirrors 엣지 0 — 극성 대칭 표시 불가"
        # 극성 노드가 모양으로 구별되는가(config polarity 유래)
        assert any(n.get("electrode_type") for n in view["nodes"]), "극성 노드 없음"

        # --- HTML: 파일에 박힌 DATA의 노드/엣지 수가 graph.json과 일치 ---
        viz.cmd_html(Namespace(data=str(dr), open=False, threshold=viz.EGO_THRESHOLD))
        html = (ROOT / "out/ontology.html").read_text(encoding="utf-8")
        m = re.search(r"^const DATA = (.*);$", html, re.M)   # DATA는 한 줄(json.dumps)
        assert m, "HTML에 DATA 임베드 실패"
        data = json.loads(m.group(1))
        assert len(data["nodes"]) == t_nodes, f"HTML 노드 {len(data['nodes'])} != 진실 {t_nodes}"
        assert len(data["edges"]) == t_edges, f"HTML 엣지 {len(data['edges'])} != 진실 {t_edges}"
        assert "vis-network" in html, "vis.js 로드 누락"
        # 카테고리 색·관계 스타일이 데이터에서 배정됐는가(하드코딩 금지 §0-1)
        cats = {c["name"] for c in data["legend"]["categories"]}
        assert cats == {n["category"] for n in nodes.values()}, "범례 카테고리가 데이터와 불일치"

        # --- cypher: MERGE 문 수 = 노드 + 엣지 ---
        viz.cmd_cypher(Namespace(data=str(dr)))
        cy = (ROOT / "out/ontology.cypher").read_text(encoding="utf-8")
        n_stmt = len(re.findall(r"^MERGE \(n:Node:", cy, re.M))
        e_stmt = len(re.findall(r"^MATCH \(a:Node", cy, re.M))
        assert n_stmt == t_nodes, f"cypher 노드문 {n_stmt} != {t_nodes}"
        assert e_stmt == t_edges, f"cypher 엣지문 {e_stmt} != {t_edges}"


def test_viz_excludes_tombstone():
    """deleted_by_user 엣지는 뷰에서 제외(진실엔 남고 파생물엔 없음 — §5.5-3)."""
    with tempfile.TemporaryDirectory() as tmp:
        dr = Path(tmp)
        _seed(dr)
        _, before = _truth(dr)

        gp = dr / "process/graph.json"
        g = json.loads(gp.read_text(encoding="utf-8"))
        g["edges"][0]["status"] = "deleted_by_user"          # 툼스톤 1건 심기
        gp.write_text(json.dumps(g, ensure_ascii=False, indent=2), encoding="utf-8")

        _nodes, edges, _c, _d, _cfg = viz.load_graphs(dr)
        assert len(edges) == before - 1, "툼스톤 엣지가 뷰에 남음"
        assert not any(e.get("status") == "deleted_by_user" for e in edges)


def test_run_py_all_is_reproducible():
    """`all`(=init --fresh → build)이 **깨끗한 재현**인가 — 두 번 돌려도 그래프가 동일.

    회귀 방지: init이 기존 data/를 보존하면(재실행 안전) 두 번째 build가 재인입 경로를 타
    노드가 중복 생성된다(KNOWN_ISSUES (나) — 단위5까지 미해결). 그래서 all은 fresh여야 한다.
    (여기선 test 단계를 뺀 init --fresh + build만 재현 — all을 그대로 부르면 테스트가 재귀한다.)
    """
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ, USE_MOCK="1", PYTHONPATH=str(ROOT))

        def cycle():
            for argv in (["init", "--fresh"], ["build"]):
                r = subprocess.run([sys.executable, str(ROOT / "run.py"), "--data", tmp, "-q", *argv],
                                   cwd=ROOT, env=env, capture_output=True, text=True)
                assert r.returncode == 0, r.stdout + r.stderr
            return _truth(Path(tmp))

        first = cycle()
        second = cycle()
        assert first == second, f"all 재현 불가(재인입 중복): 1회차 {first} != 2회차 {second}"


def test_run_py_commands():
    """run.py init/build/query/status가 exit 0 (표준 라이브러리만·USE_MOCK=1)."""
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ, USE_MOCK="1", PYTHONPATH=str(ROOT))

        def run(*argv):
            return subprocess.run([sys.executable, str(ROOT / "run.py"), "--data", tmp, "-q", *argv],
                                  cwd=ROOT, env=env, capture_output=True, text=True)

        # build 전 status/build는 미초기화 안내로 실패(exit 1) — 조용한 오작동 아님
        assert run("status").returncode == 1, "미초기화 status가 실패해야"

        assert run("init").returncode == 0
        r = run("build")
        assert r.returncode == 0 and "인입 3건" in r.stdout, r.stdout + r.stderr

        r = run("query", "노칭 다음 공정은?")
        assert r.returncode == 0 and "스태킹" in r.stdout, r.stdout + r.stderr

        r = run("status")
        assert r.returncode == 0
        for word in ("노드", "카테고리 분포", "수정 큐", "청크·사전"):
            assert word in r.stdout, f"status 표에 '{word}' 없음"


if __name__ == "__main__":
    test_viz_matches_truth()
    test_viz_excludes_tombstone()
    test_run_py_all_is_reproducible()
    test_run_py_commands()
    print("test_viz OK")
