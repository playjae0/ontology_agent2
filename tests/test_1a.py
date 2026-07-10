"""test_1a — core/graph·dictionary·id_seq + init (구현문서 §9.2 단위 1a).

통과 조건: 노드 2개 add→저장→로드 시 id 전역 유일·복원 동일.
+ 전역 id 시퀀스가 복원 후 이어져 겹치지 않음, 동의어 사전 register/lookup 왕복.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from core.graph import IdSeq, Graph, init_data_tree
from core.dictionary import Dictionary


def test_1a():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        init_data_tree(root, ["process"])

        # 초기 파일 생성 확인 (§9.1)
        for name in ("id_seq.json", "dictionary.json", "chunks.json", "review_queue.json"):
            assert (root / name).exists(), f"init 누락: {name}"
        assert (root / "process" / "graph.json").exists()

        # 노드 2개 add
        ids = IdSeq(root / "id_seq.json")
        g = Graph("process", ids)
        a = g.add_node("노칭", "Process", status="confirmed", provenance=["seed"])
        b = g.add_node("스태킹", "Process", status="confirmed", provenance=["seed"])
        assert a != b, "id 전역 유일해야 함"
        assert a == "N0001" and b == "N0002", f"id 발급 형식/순서: {a},{b}"
        g.add_edge(a, "precedes", b, status="confirmed", provenance=["seed"])
        g.add_alias(a, "notching", ["PPT01-C001"])
        g.save(root / "process" / "graph.json")
        ids.save()

        # 사전 register/save
        dic = Dictionary(root / "dictionary.json")
        dic.register("노칭", a, ["seed"])
        dic.register("notching", a, ["PPT01-C001"])
        dic.register("스태킹", b, ["seed"])
        dic.save()

        # --- 재로드: 복원 동일 ---
        ids2 = IdSeq(root / "id_seq.json")
        g2 = Graph.load(root / "process" / "graph.json", "process", ids2)
        assert g2.nodes[a]["canonical"] == "노칭"
        assert g2.nodes[b]["canonical"] == "스태킹"
        assert g2.nodes[a]["status"] == "confirmed"
        assert g2.nodes[a]["aliases"][0]["surface"] == "notching"
        assert len(g2.edges) == 1 and g2.edges[0]["rel"] == "precedes"

        # 복원 후 발급 id가 이어져 겹치지 않음(전역 유일 유지)
        c = g2.add_node("탭용접", "Process", provenance=["seed"])
        assert c == "N0003", f"복원 후 id 이어짐: {c}"
        assert c not in (a, b), "복원 후 id 겹치면 안 됨"

        # 사전 왕복 — 정규화(대소문자·공백) 흡수
        dic2 = Dictionary(root / "dictionary.json")
        assert set(dic2.lookup("notching")) == {a}
        assert set(dic2.lookup("Notching")) == {a}, "대소문자 정규화"
        assert set(dic2.lookup(" 노칭 ")) == {a}, "공백 정규화"
        assert set(dic2.lookup("스태킹")) == {b}
        assert dic2.lookup("없는표면형") == []

        # neighbors: precedes out 1홉
        nb = g2.neighbors([a], {"precedes": {"direction": "out", "recursive": False}})
        assert nb == {b}, f"neighbors precedes out: {nb}"

    print("test_1a OK")


if __name__ == "__main__":
    test_1a()
