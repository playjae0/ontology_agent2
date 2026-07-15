"""test_reinject — 재인입 회수 ②(사전 보존) + ③(큐 재평가) (단위 3.5, 명세 §5.5-3 3분류).

KNOWN_ISSUES (나) 핵심 증상 해소 검증:
  (a) 노드 중복 생성 — 사전 엔트리 보존(②)으로 재매칭 → 증가 0.
  (b) stale 큐 — queue.remove_doc(③) + evidence_lost self-heal sweep.
  (c) mirror 데카르트곱 폭증 — 중복 노드가 없으니 apply_mirrors self-heal이 안정.
+ 다중근거 노드는 한 문서 회수에도 생존(match 경로 provenance 누적), 진짜 개정은 evidence_lost로 표면화.

경계(미해결·단위5): 대칭↔비대칭 **역방향** 복원(대칭화 노드를 되돌림)은 노드 삭제 도구가 있어야
성립한다 — 재인입은 노드를 안 지우고 evidence_lost로 남기므로(자동 삭제 금지), 구조상 대칭 유지.
이건 재인입 결함이 아니라 노드 삭제(수정 도구) 미구현. test_mirror_selfheal 주석 참조.
"""
from __future__ import annotations

import json
import os
import tempfile
from collections import Counter
from pathlib import Path

os.environ.setdefault("USE_MOCK", "1")

from core import build

ROOT = Path(__file__).resolve().parent.parent


def _load(name):
    return json.loads((ROOT / f"mock/parsed/{name}.json").read_text(encoding="utf-8"))


def _count(canonical, s):
    return sum(1 for g in s.graphs.values() for n in g.nodes.values() if n["canonical"] == canonical)


def _snap(s):
    """그래프+큐 상태 스냅샷(노드/엣지/큐 kind별 카운트) — 고정점 비교용."""
    nodes = sum(len(g.nodes) for g in s.graphs.values())
    edges = sum(len(g.edges) for g in s.graphs.values())
    qk = tuple(sorted(Counter(i["kind"] for i in s.queue.items).items()))
    return nodes, edges, qk


def test_reinject_uniqueness():
    """(a) CP01 인입 후 노드 N → 재인입 후 N (증가 0). cathode 노칭 프레스 정확히 1개."""
    with tempfile.TemporaryDirectory() as tmp:
        dr = Path(tmp)
        build.plant_skeletons(ROOT, dr)
        s = build.build_doc(_load("CP01"), ROOT, dr)
        n1 = sum(len(g.nodes) for g in s.graphs.values())
        assert _count("cathode 노칭 프레스", s) == 1

        s = build.build_doc(_load("CP01"), ROOT, dr)          # 동일 재인입
        n2 = sum(len(g.nodes) for g in s.graphs.values())
        assert n2 == n1, f"재인입 후 노드 증가(중복 생성): {n1} → {n2}"
        assert _count("cathode 노칭 프레스", s) == 1, "cathode 노칭 프레스 중복"
        assert _count("anode 노칭 프레스", s) == 1

        # 재로드해도 동일(디스크 왕복)
        s2 = build.Stores(ROOT, dr)
        assert sum(len(g.nodes) for g in s2.graphs.values()) == n1


def test_reinject_fixed_point():
    """(b)(c) --fresh 없이 build 반복 → 고정점: 첫 재인입 이후 노드/엣지/큐가 완전 안정."""
    with tempfile.TemporaryDirectory() as tmp:
        dr = Path(tmp)
        build.plant_skeletons(ROOT, dr)
        snaps = []
        for _round in range(3):
            for d in ("CP01", "PPT01", "PFMEA01"):
                s = build.build_doc(_load(d), ROOT, dr)
            snaps.append(_snap(s))
        # 노드·엣지는 1회차부터 불변(중복 0), 큐는 재인입 후 안정
        assert snaps[0][0] == snaps[1][0] == snaps[2][0], f"노드 수 불안정: {[x[0] for x in snaps]}"
        assert snaps[0][1] == snaps[1][1] == snaps[2][1], f"엣지 수 불안정: {[x[1] for x in snaps]}"
        assert snaps[1] == snaps[2], f"재인입 고정점 실패: 라운드2 {snaps[1]} != 라운드3 {snaps[2]}"


def test_reinject_no_queue_explosion():
    """(b)(c) 재인입해도 mirror_asymmetry 데카르트곱 폭증 없음 + evidence_lost 오탐 없음."""
    with tempfile.TemporaryDirectory() as tmp:
        dr = Path(tmp)
        build.plant_skeletons(ROOT, dr)
        for d in ("CP01", "PPT01", "PFMEA01"):
            s = build.build_doc(_load(d), ROOT, dr)
        asym1 = len(s.queue.by_kind("mirror_asymmetry"))
        for _ in range(3):                                    # CP01 3회 재인입
            s = build.build_doc(_load("CP01"), ROOT, dr)
        asym2 = len(s.queue.by_kind("mirror_asymmetry"))
        assert asym2 == asym1, f"mirror_asymmetry 폭증: {asym1} → {asym2}"
        # 동일 재인입은 노드를 재매칭하므로 근거 소멸이 아님 → evidence_lost 0
        el = s.queue.by_kind("evidence_lost")
        assert el == [], f"동일 재인입인데 evidence_lost 오탐: {[i['payload'] for i in el]}"
        # cathode 노칭 프레스 여전히 1개(데카르트곱의 원인이었던 중복 없음)
        assert _count("cathode 노칭 프레스", s) == 1


def test_reinject_preserves_multi_provenance_node():
    """② 다중근거 노드는 한 문서만 회수돼도 생존 — match 경로 provenance 누적(§5.5-3)."""
    with tempfile.TemporaryDirectory() as tmp:
        dr = Path(tmp)
        build.plant_skeletons(ROOT, dr)
        for d in ("CP01", "PPT01", "PFMEA01"):
            s = build.build_doc(_load(d), ROOT, dr)
        # 노칭::노칭 정밀도 = CP01-C1(생성) + PFMEA01-R12(노칭정밀도 표기변형 매칭) 양쪽 근거
        node = next(n for g in s.graphs.values() for n in g.nodes.values()
                    if n["canonical"] == "노칭::노칭 정밀도")
        provs = node["provenance"]
        assert any(p.startswith("CP01") for p in provs) and any(p.startswith("PFMEA") for p in provs), \
            f"다중근거 누적 실패: {provs}"
        # CP01만 재인입(동일) → 노칭 정밀도는 여전히 존재·근거 유지, evidence_lost 아님
        s = build.build_doc(_load("CP01"), ROOT, dr)
        assert _count("노칭::노칭 정밀도", s) == 1
        el_canons = [i["payload"].get("canonical") for i in s.queue.by_kind("evidence_lost")]
        assert "노칭::노칭 정밀도" not in el_canons, "다중근거 노드가 근거소멸로 오표시"


def test_reinject_genuine_revision_surfaces_evidence_lost():
    """개정으로 정말 사라진 개체는 노드는 남기되(자동 삭제 금지) evidence_lost로 표면화(§5.5-3 ①)."""
    with tempfile.TemporaryDirectory() as tmp:
        dr = Path(tmp)
        build.plant_skeletons(ROOT, dr)
        s = build.build_doc(_load("CP01"), ROOT, dr)
        assert _count("스태커", s) == 1
        # 스태커 행을 뺀 개정 CP01 재인입
        rev = _load("CP01")
        rev["records"] = [r for r in rev["records"] if r.get("설비") != "스태커"]
        s = build.build_doc(rev, ROOT, dr)
        assert _count("스태커", s) == 1, "노드는 자동 삭제하지 않는다(되돌리기 쉬운 쪽)"
        el_canons = [i["payload"].get("canonical") for i in s.queue.by_kind("evidence_lost")]
        assert "스태커" in el_canons, f"근거 소멸이 evidence_lost로 표면화돼야: {el_canons}"


if __name__ == "__main__":
    test_reinject_uniqueness()
    test_reinject_fixed_point()
    test_reinject_no_queue_explosion()
    test_reinject_preserves_multi_provenance_node()
    test_reinject_genuine_revision_surfaces_evidence_lost()
    print("test_reinject OK")
