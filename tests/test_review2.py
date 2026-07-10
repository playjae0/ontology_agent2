"""test_review2 — 검수 라운드2 조치 (다)·(마) 검증.

(다) cross-layer 사실: per-layer graph_facts에서 cross_layer_traverse 관계 제외, 브리지 단독 소유.
    → Q10 그래프 사실에 raw id(N####) 0건, occurs_in/affects 사실이 canonical로 1회씩만.
(마) 명시적 실패: graph.neighbors가 config 표현 밖 direction/recursive에 raise.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

os.environ.setdefault("USE_MOCK", "1")

from core import build
from core.graph import IdSeq, Graph, init_data_tree
from cli import query as qcli

ROOT = Path(__file__).resolve().parent.parent


def _load(name):
    return json.loads((ROOT / f"mock/parsed/{name}.json").read_text(encoding="utf-8"))


def test_da_crosslayer_render():
    with tempfile.TemporaryDirectory() as tmp:
        dr = Path(tmp)
        build.plant_skeletons(ROOT, dr)
        for d in ("CP01", "PPT01", "PFMEA01"):
            build.build_doc(_load(d), ROOT, dr)
        r = qcli.route("단락으로 이어질 수 있는 불량은 뭐가 있어?", ROOT, dr)
        assert r["answer_path"] == "graph_fact"
        # raw node id(N####) 문자열이 사실에 없어야
        raw = [f for f in r["graph_facts"] if "N00" in f]
        assert raw == [], f"cross-layer 사실에 raw id 잔존: {raw}"
        occ = [f for f in r["graph_facts"] if "공정에서 발생" in f]
        assert occ, "occurs_in 사실이 있어야(브리지)"
        assert len(occ) == len(set(occ)), f"occurs_in 사실 중복 렌더: {occ}"
        # 대표 사실이 canonical로
        assert any("절연 파괴는 노칭 공정에서 발생한다" in f for f in occ)


def test_ma_explicit_failure():
    with tempfile.TemporaryDirectory() as tmp:
        dr = Path(tmp)
        init_data_tree(dr, ["process"])
        ids = IdSeq(dr / "id_seq.json")
        g = Graph("process", ids)
        a = g.add_node("A", "Process", provenance=["seed"])
        b = g.add_node("B", "Process", provenance=["seed"])
        g.add_edge(a, "rel", b, provenance=["seed"])
        # 정상 방향은 통과
        assert g.neighbors([a], {"rel": {"direction": "out", "recursive": False}}) == {b}
        # 미지원 direction → raise
        try:
            g.neighbors([a], {"rel": {"direction": "sideways", "recursive": False}})
            assert False, "미지원 direction인데 raise 안 함"
        except ValueError as e:
            assert "config 표현 밖" in str(e)
        # 미지원 recursive → raise
        try:
            g.neighbors([a], {"rel": {"direction": "out", "recursive": "yes"}})
            assert False, "미지원 recursive인데 raise 안 함"
        except ValueError as e:
            assert "config 표현 밖" in str(e)


def _build_all(dr):
    build.plant_skeletons(ROOT, dr)
    for d in ("CP01", "PPT01", "PFMEA01"):
        build.build_doc(_load(d), ROOT, dr)


def test_ra1_multi_occurs_in():
    """(라-1) 한 failure_mode(이물 혼입)가 서로 다른 공정 2개(노칭·실링)에서 발생 → occurs_in 2건."""
    with tempfile.TemporaryDirectory() as tmp:
        dr = Path(tmp)
        _build_all(dr)
        q = json.loads((dr / "quality/graph.json").read_text(encoding="utf-8"))
        p = json.loads((dr / "process/graph.json").read_text(encoding="utf-8"))
        pn = {i: n["canonical"] for i, n in p["nodes"].items()}
        iid = next(i for i, n in q["nodes"].items() if n["canonical"] == "이물 혼입")
        procs = {pn[e["dst"]] for e in q["edges"] if e["rel"] == "occurs_in" and e["src"] == iid}
        assert procs == {"노칭", "실링"}, f"이물 혼입 다중 occurs_in 기대 {{노칭,실링}}, 실제 {procs}"
        # 질의: "이 불량 유발 공정들" → 2개 공정
        r = qcli.route("이물 혼입은 어느 공정에서 발생해?", ROOT, dr)
        assert r["answer_path"] == "graph_fact"
        assert any("이물 혼입는 노칭 공정에서 발생한다" in f for f in r["graph_facts"])
        assert any("이물 혼입는 실링 공정에서 발생한다" in f for f in r["graph_facts"])


def test_ra2_polarity_residual_process():
    """(라-2) 극성 잔존 공정 — Process급 mirrors + flow 단일 스트림 + 자식 비대칭(안전망)."""
    with tempfile.TemporaryDirectory() as tmp:
        dr = Path(tmp)
        _build_all(dr)
        p = json.loads((dr / "process/graph.json").read_text(encoding="utf-8"))
        by = {n["canonical"]: i for i, n in p["nodes"].items()}
        cat, an = by["cathode 탭용접"], by["anode 탭용접"]
        # 극성 결합 골격 노드
        assert p["nodes"][cat]["electrode_type"] == "cathode"
        assert p["nodes"][an]["electrode_type"] == "anode"
        assert p["nodes"][cat]["category"] == "Process"
        # Process급 mirrors 엣지
        assert any(e["rel"] == "mirrors" and {e["src"], e["dst"]} == {cat, an} for e in p["edges"]), \
            "cathode↔anode 탭용접 Process mirrors 누락"
        # flow 단일 스트림 — precedes 선형(분기 없음): 각 노드 out precedes ≤ 1
        for i in p["nodes"]:
            outs = [e for e in p["edges"] if e["rel"] == "precedes" and e["src"] == i]
            assert len(outs) <= 1, f"precedes 분기 발생(단일 스트림 위반): {p['nodes'][i]['canonical']}"
        assert any(e["src"] == by["스태킹"] and e["rel"] == "precedes" and e["dst"] == cat for e in p["edges"])
        assert any(e["src"] == cat and e["rel"] == "precedes" and e["dst"] == an for e in p["edges"])
        assert any(e["src"] == an and e["rel"] == "precedes" and e["dst"] == by["패키징"] for e in p["edges"])
        # 자식 비대칭 큐(안전망) — 탭용접 base, 단 precedes는 비대칭 사유에서 제외됐어야
        qq = json.loads((dr / "review_queue.json").read_text(encoding="utf-8"))
        tap = [i for i in qq if i["kind"] == "mirror_asymmetry" and i["payload"].get("base") == "탭용접"]
        assert len(tap) == 1, f"탭용접 mirror_asymmetry 1건 기대, 실제 {len(tap)}"
        blob = json.dumps(tap[0]["payload"], ensure_ascii=False)
        assert "precedes" not in blob, "precedes가 자식 비대칭 사유에 잘못 포함됨(§5.3 위반)"


if __name__ == "__main__":
    test_da_crosslayer_render()
    test_ma_explicit_failure()
    test_ra1_multi_occurs_in()
    test_ra2_polarity_residual_process()
    print("test_review2 OK")
