"""test_1c — ingest 핸들러 + matcher(MOCK) + build + cp.json (구현문서 §9.2 단위 1c).

통과 조건: CP01 인입 후 Unit·Property·has_property, C4 spec_conflict(같은 context)·
C7 병렬(context 상이)·C8/C9 극성 결합 canonical 2노드 + mirrors + mirror_asymmetry 큐.
USE_MOCK=1 전 과정 무에러.
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


def _has_edge(g, src, rel, dst):
    return any(e["src"] == src and e["rel"] == rel and e["dst"] == dst for e in g.edges)


def test_1c():
    doc = json.loads((ROOT / "mock/parsed/CP01.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        data_root = Path(tmp)
        build.plant_skeletons(ROOT, data_root)          # seed(process 7노드)
        s = build.build_doc(doc, ROOT, data_root)       # CP01 인입
        g = s.graphs["process"]

        # --- Unit·Property 생성 ---
        u_both = _find(g, "노칭 프레스", "Unit")
        assert u_both and u_both["status"] == "auto", "노칭 프레스(both) Unit auto 생성"
        p_prec = _find(g, "노칭 정밀도", "Property")
        assert p_prec, "노칭 정밀도 Property 생성"
        assert _find(g, "스태커", "Unit") and _find(g, "적층 정렬도", "Property")
        assert _find(g, "초음파 융착기", "Unit") and _find(g, "실러", "Unit")

        # --- has_property + part_of (설비 part_of 공정, 설비 has_property 관리항목) ---
        assert _has_edge(g, u_both["id"], "has_property", p_prec["id"]), "노칭프레스 has_property 노칭정밀도"
        nochi = _find(g, "노칭", "Process")
        assert _has_edge(g, u_both["id"], "part_of", nochi["id"]), "노칭프레스 part_of 노칭"

        # --- C4 spec_conflict (같은 context M1, 다른 값) : 정확히 1건 ---
        conflicts = s.queue.by_kind("spec_conflict")
        assert len(conflicts) == 1, f"spec_conflict 1건 기대(C4), 실제 {len(conflicts)}: {conflicts}"

        # --- C7 병렬 (context 상이 M2) : 적층 정렬도 spec에 M1·M2 두 항목 ---
        align = _find(g, "적층 정렬도", "Property")
        specs = align["attrs"]["spec"]
        ctxs = sorted(json.dumps(x["context"], ensure_ascii=False, sort_keys=True) for x in specs)
        assert len(specs) == 2, f"적층 정렬도 spec 2항목(M1·M2) 기대, 실제 {specs}"
        assert ctxs == ['{"model": "M1"}', '{"model": "M2"}'], f"context 그룹: {ctxs}"

        # --- C8/C9 극성 결합 canonical : cathode/anode 노칭 프레스 2노드 ---
        u_cat = _find(g, "cathode 노칭 프레스", "Unit")
        u_an = _find(g, "anode 노칭 프레스", "Unit")
        assert u_cat and u_cat["electrode_type"] == "cathode"
        assert u_an and u_an["electrode_type"] == "anode"
        assert u_cat["id"] != u_both["id"] != u_an["id"], "무극성/cathode/anode 별도 노드"

        # 극성 Property도 갈림 + 표면형 alias 공유
        pc = _find(g, "cathode 노칭 정밀도", "Property")
        pa = _find(g, "anode 노칭 정밀도", "Property")
        assert pc and pa
        assert any(a["surface"] == "노칭 프레스" for a in u_cat["aliases"]), "표면형 alias 공유(§5.2)"

        # --- mirrors 자동 연결 : Unit 쌍 + Property 쌍 ---
        assert _has_edge(g, u_cat["id"], "mirrors", u_an["id"]), "cathode↔anode 노칭프레스 mirrors"
        assert _has_edge(g, pc["id"], "mirrors", pa["id"]), "cathode↔anode 노칭정밀도 mirrors"
        for e in g.edges:
            if e["rel"] == "mirrors":
                assert e["status"] == "auto" and e["provenance"] == ["auto:mirror_rule"]

        # --- mirror_asymmetry : anode에만 '버 높이' → 비대칭 큐 ---
        asym = s.queue.by_kind("mirror_asymmetry")
        assert len(asym) >= 1, "mirror_asymmetry 큐(anode 버 높이 추가)"
        assert _find(g, "anode 버 높이", "Property"), "anode 버 높이 Property"
        assert _has_edge(g, u_an["id"], "has_property", _find(g, "anode 버 높이", "Property")["id"])

        # --- content(대응계획) describes ---
        assert "CP01-C1-대응계획" in s.chunks.chunks, "필드별 별도 청크 id(§3.4)"
        assert p_prec["id"] in s.chunks.nodes_for_chunk("CP01-C1-대응계획"), "대응계획 describes 관리항목"

        # --- 무에러 부수 확인: auto_node 큐 다수(Unit·Property 생성분) ---
        assert len(s.queue.by_kind("auto_node")) >= 6

        # --- 재로드 복원 동일 ---
        s2 = build.Stores(ROOT, data_root)
        assert _find(s2.graphs["process"], "cathode 노칭 프레스", "Unit"), "디스크 복원"

    print("test_1c OK")


if __name__ == "__main__":
    test_1c()
