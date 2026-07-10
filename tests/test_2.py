"""test_2 — query 4단 + 이원 근거 채널 (구현문서 §9.2 단위 2).

통과 조건: queries.json 1~8·11·12가 expected_path대로 응답. flow 질의(5)가 골격 전체 공급.
링킹 미스 로그(12) 기록. (9·10은 cross-layer — 단위 3에서 검증.)
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

os.environ.setdefault("USE_MOCK", "1")

from core import build
from cli import query as qcli

ROOT = Path(__file__).resolve().parent.parent
UNIT2_IDS = {1, 2, 3, 4, 5, 6, 7, 8, 11, 12}  # 9·10은 cross-layer(단위3)


def test_2():
    cp = json.loads((ROOT / "mock/parsed/CP01.json").read_text(encoding="utf-8"))
    ppt = json.loads((ROOT / "mock/parsed/PPT01.json").read_text(encoding="utf-8"))
    queries = json.loads((ROOT / "mock/queries.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        data_root = Path(tmp)
        build.plant_skeletons(ROOT, data_root)
        build.build_doc(cp, ROOT, data_root)
        build.build_doc(ppt, ROOT, data_root)

        by_id = {q["id"]: q for q in queries}
        for qid in sorted(UNIT2_IDS):
            q = by_id[qid]
            r = qcli.route(q["question"], ROOT, data_root)
            assert r["answer_path"] == q["expected_path"], \
                f"Q{qid} '{q['question']}': expected {q['expected_path']}, got {r['answer_path']}"

        # --- flow(5) 골격 전체 공급: precedes 체인 전부 그래프 사실로 ---
        r5 = qcli.route(by_id[5]["question"], ROOT, data_root)
        assert r5["is_flow"] is True
        facts = "\n".join(r5["graph_facts"])
        # 극성 잔존 공정(탭용접)도 단일 스트림 — cathode→anode 순차(§5.2 ②)
        for a, b in [("노칭", "스태킹"), ("스태킹", "cathode 탭용접"), ("cathode 탭용접", "anode 탭용접"),
                     ("anode 탭용접", "패키징"), ("패키징", "전해액주입"), ("전해액주입", "실링")]:
            assert f"{a} 다음 공정은 {b}" in facts, f"flow precedes {a}->{b} 누락"

        # --- Q2(3) 구조: precedes 사실 ---
        r3 = qcli.route(by_id[3]["question"], ROOT, data_root)
        assert any("노칭 다음 공정은 스태킹" in f for f in r3["graph_facts"])

        # --- Q4(6) 값: 규격 attr 사실(맥락형 [model=...] 렌더) ---
        r6 = qcli.route(by_id[6]["question"], ROOT, data_root)
        assert any("규격" in f and "model=" in f for f in r6["graph_facts"]), r6["graph_facts"]

        # --- Q5(8) 역방향: 금형 클리어런스 관리 설비 = 노칭 프레스 ---
        r8 = qcli.route(by_id[8]["question"], ROOT, data_root)
        assert any("노칭 프레스" in f and "금형 클리어런스" in f for f in r8["graph_facts"]), r8["graph_facts"]

        # --- Q1(1) 서술: 청크 채널 ---
        r1 = qcli.route(by_id[1]["question"], ROOT, data_root)
        assert r1["chunk_ids"], "Q1 청크 근거 있어야"

        # --- Q8(12) 링킹 미스 + 일반지식 마커 ---
        r12 = qcli.route(by_id[12]["question"], ROOT, data_root)
        assert r12["linking_miss"] is True, "배터리 원리 질문 링킹 미스"
        assert "[일반지식 — 사내 검증 필요]" in r12["answer_text"]

        # --- Q8(11) 노칭은 링크되나 답은 일반지식(그래프 밖) ---
        r11 = qcli.route(by_id[11]["question"], ROOT, data_root)
        assert r11["answer_path"] == "general_knowledge"
        assert r11["linking_miss"] is False, "노칭은 링킹됨(미스 아님)"

    print("test_2 OK")


if __name__ == "__main__":
    test_2()
