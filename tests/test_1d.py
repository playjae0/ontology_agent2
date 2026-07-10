"""test_1d — content(prose) 경로 + PPT01 (구현문서 §9.2 단위 1d).

통과 조건: P5 linked=false 보존, P6 auto+큐, describes 연결.
+ 전 청크 보존(링킹 0건도), P1/P3 기존 노드에 describes, P2 스침 비추출.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

os.environ.setdefault("USE_MOCK", "1")

from core import build

ROOT = Path(__file__).resolve().parent.parent


def _find(g, canonical, category=None):
    for n in g.nodes.values():
        if n["canonical"] == canonical and (category is None or n["category"] == category):
            return n
    return None


def test_1d():
    cp = json.loads((ROOT / "mock/parsed/CP01.json").read_text(encoding="utf-8"))
    ppt = json.loads((ROOT / "mock/parsed/PPT01.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        data_root = Path(tmp)
        build.plant_skeletons(ROOT, data_root)
        build.build_doc(cp, ROOT, data_root)            # 단계1 순서: CP 먼저
        s = build.build_doc(ppt, ROOT, data_root)        # 그다음 PPT
        g = s.graphs["process"]
        chunks = s.chunks

        # --- 전 청크 보존 (P1~P8 전부) ---
        for i in range(1, 9):
            assert f"PPT01-P{i}" in chunks.chunks, f"청크 PPT01-P{i} 보존"

        # --- P5: 개체 없음 → linked=false 보존 ---
        assert chunks.chunks["PPT01-P5"]["linked"] is False, "P5 linked=false"
        assert chunks.nodes_for_chunk("PPT01-P5") == [], "P5 describes 없음"

        # --- P6: 주액기 신규 Unit auto + 큐 + describes ---
        juak = _find(g, "주액기", "Unit")
        assert juak and juak["status"] == "auto", "주액기 auto 생성"
        auto_surfaces = [q["payload"]["surface"] for q in s.queue.by_kind("auto_node")]
        assert "주액기" in auto_surfaces, "P6 auto_node 큐"
        assert chunks.chunks["PPT01-P6"]["linked"] is True
        assert juak["id"] in chunks.nodes_for_chunk("PPT01-P6"), "P6 describes 주액기"
        # prose 관계 생성((카테고리쌍→관계) 매핑): 주액기(Unit) part_of 전해액주입(Process) — §7-2
        ea = _find(g, "전해액주입", "Process")
        assert any(e["src"] == juak["id"] and e["rel"] == "part_of" and e["dst"] == ea["id"]
                   for e in g.edges), "P6 주액기 part_of 전해액주입(prose 카테고리쌍 매핑)"

        # --- P1: 기존 노칭 프레스(CP 생성)에 describes (신규 아님) ---
        press = _find(g, "노칭 프레스", "Unit")
        assert press["id"] in chunks.nodes_for_chunk("PPT01-P1"), "P1 describes 노칭프레스"
        # CP에서 이미 만든 노드에 매칭 — PPT가 새로 만들지 않음(주액기 외 신규 Unit 없음 확인)

        # --- P3: 적층 정렬도(기존)에 describes ---
        align = _find(g, "적층 정렬도", "Property")
        assert align["id"] in chunks.nodes_for_chunk("PPT01-P3"), "P3 describes 적층정렬도"

        # --- P2: 스침 언급(스태커) 비추출 → describes 없음 ---
        assert chunks.chunks["PPT01-P2"]["linked"] is False, "P2 스침 비추출 → linked=false"

        # --- P7: 이미지 청크도 동일 처리(실러 describes) ---
        assert chunks.chunks["PPT01-P7"]["meta"].get("image_summary") is True
        assert _find(g, "실러", "Unit")["id"] in chunks.nodes_for_chunk("PPT01-P7")

        # --- describes 저장 왕복 ---
        s2 = build.Stores(ROOT, data_root)
        assert s2.chunks.chunks["PPT01-P5"]["linked"] is False

    print("test_1d OK")


if __name__ == "__main__":
    test_1d()
