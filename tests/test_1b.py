"""test_1b — core/skeleton.py + process config.skeleton (구현문서 §9.2 단위 1b).

통과 조건: seed 심기 후 Process 7노드, part_of 6·precedes 5 엣지.
+ 전부 confirmed·provenance=["seed"], precedes 체인이 seed 나열 순서, 사전 등재, flat 타입.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from core.graph import IdSeq, Graph, init_data_tree
from core.dictionary import Dictionary
from core import skeleton

ROOT = Path(__file__).resolve().parent.parent


def _count(graph, rel):
    return sum(1 for e in graph.edges if e["rel"] == rel)


def test_1b():
    config = json.loads((ROOT / "layers/process/config.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        init_data_tree(root, ["process"])
        ids = IdSeq(root / "id_seq.json")
        g = Graph("process", ids)
        dic = Dictionary(root / "dictionary.json")

        skeleton.plant(g, config["skeleton"], dic)

        procs = [n for n in g.nodes.values() if n["category"] == "Process"]
        assert len(procs) == 7, f"Process 노드 7개 기대, 실제 {len(procs)}"
        assert _count(g, "part_of") == 6, f"part_of 6 기대, 실제 {_count(g,'part_of')}"
        assert _count(g, "precedes") == 5, f"precedes 5 기대, 실제 {_count(g,'precedes')}"

        # 전부 confirmed·seed provenance (Tier1)
        for n in g.nodes.values():
            assert n["status"] == "confirmed", n
            assert n["provenance"] == ["seed"], n

        # canonical -> id 맵
        by_name = {n["canonical"]: nid for nid, n in g.nodes.items()}
        assert set(by_name) == {"조립", "노칭", "스태킹", "탭용접", "패키징", "전해액주입", "실링"}

        # part_of: 각 세부공정 -> 조립 (src=child, dst=parent)
        assembly = by_name["조립"]
        for leaf in ("노칭", "스태킹", "탭용접", "패키징", "전해액주입", "실링"):
            assert any(e["src"] == by_name[leaf] and e["rel"] == "part_of" and e["dst"] == assembly
                       for e in g.edges), f"{leaf} part_of 조립 누락"

        # precedes 체인이 seed 나열 순서: 노칭→스태킹→탭용접→패키징→전해액주입→실링
        order = ["노칭", "스태킹", "탭용접", "패키징", "전해액주입", "실링"]
        for a, b in zip(order, order[1:]):
            assert any(e["src"] == by_name[a] and e["rel"] == "precedes" and e["dst"] == by_name[b]
                       for e in g.edges), f"precedes {a}->{b} 누락"

        # 조립(대공정 단일 root)에는 precedes 없음
        assert not any(e["rel"] == "precedes" and e["src"] == assembly for e in g.edges)

        # 사전 등재 — anchor 조회용
        assert dic.lookup("노칭") == [by_name["노칭"]]
        assert dic.lookup("조립") == [assembly]

        # down 확장(part_of 자식 재귀): 조립 -> 6 세부공정
        down = g.neighbors([assembly], {"part_of": {"direction": "in", "recursive": True}})
        assert down == {by_name[x] for x in order}, f"조립 down 확장: {down}"

    # flat 타입도 심어지는지(품질층 골격 형태) — 엣지 0
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        init_data_tree(root, ["quality"])
        ids = IdSeq(root / "id_seq.json")
        g = Graph("quality", ids)
        skeleton.plant(g, {"type": "flat", "category": "FailureEffect",
                           "data": ["단락", "화재", "방전기능상실", "충전기능상실"]})
        fx = [n for n in g.nodes.values() if n["category"] == "FailureEffect"]
        assert len(fx) == 4 and len(g.edges) == 0, "flat: 4노드·엣지 0"

    print("test_1b OK")


if __name__ == "__main__":
    test_1b()
