"""test_fable — FABLE_REVIEW 반영 라운드(명세 v1.12) 검증.

즉시 수정분: F1(골격 극성 alias), F6+F15(인입 검증 역방향·계약 위반), F13(닫힌 카테고리),
F5-①(anchor Tier1), F12(링킹 단어 경계).
v1.12 마감분: F4(Property canonical 부모 접두), F11(극성 이중 접두 방어),
F3(mirrors 같은 부모 조건), F16 준비(embeddings.py 계약).
이연 유지(착수 금지 확인 대상 아님): (나)재인입·F7~F10·F14·F16 후보검색 본체.
"""
from __future__ import annotations

import json
import math
import os
import tempfile
from pathlib import Path

os.environ.setdefault("USE_MOCK", "1")

from core import build, embeddings
from cli import query as qcli

ROOT = Path(__file__).resolve().parent.parent


def _load(name):
    return json.loads((ROOT / f"mock/parsed/{name}.json").read_text(encoding="utf-8"))


def _build_all(dr):
    build.plant_skeletons(ROOT, dr)
    for d in ("CP01", "PPT01", "PFMEA01"):
        build.build_doc(_load(d), ROOT, dr)


def _doc(doc_id, doc_type, records=None, chunks=None, payload_kind=None):
    d = {"doc_id": doc_id, "doc_type": doc_type, "source_path": "(test)", "revision": "R1",
         "parsed_at": "2026-07-12T00:00:00", "parser_version": "test",
         "context": {"model": "M1"},
         "payload_kind": payload_kind or ("prose" if chunks is not None else "table")}
    if records is not None:
        d["records"] = records
    if chunks is not None:
        d["chunks"] = chunks
    return d


def _find(g, canonical, category=None):
    for n in g.nodes.values():
        if n["canonical"] == canonical and (category is None or n["category"] == category):
            return n
    return None


def test_f1_polar_skeleton_alias():
    """F1 — 극성 골격 노드의 극성 제거 표면형 alias 공유(§5.2)."""
    with tempfile.TemporaryDirectory() as tmp:
        dr = Path(tmp)
        _build_all(dr)
        s = build.Stores(ROOT, dr)
        # 사전: "탭용접"이 양 극성 골격 노드를 후보로 반환
        cands = s.dic.lookup("탭용접")
        assert len(cands) == 2, f"'탭용접' 후보 2(양 극성) 기대, 실제 {cands}"
        # 질의: general_knowledge로 새지 않고 그래프 사실 경로
        r = qcli.route("탭용접 다음 공정은?", ROOT, dr)
        assert r["answer_path"] == "graph_fact", f"탭용접 질의가 {r['answer_path']}로 샘"
        assert len(r["linked"]) >= 2, "양 극성 골격 노드 링킹"
        # anchor: 극성 제거 표면형 좌표는 극성 모호 → orphan_anchor(후보 id 동반, 사람 판단)
        recs = [{"chunk_id": "FT1-R1", "process_group": "조립", "process_ref": "탭용접",
                 "electrode_type": "both", "failure_mode": "용접 스패터", "cause": "출력 과다",
                 "effect_category": "단락", "severity": 9}]
        s2 = build.build_doc(_doc("FT1", "pfmea", records=recs), ROOT, dr)
        orph = [i for i in s2.queue.by_kind("orphan_anchor")
                if i["doc_id"] == "FT1" and i["payload"].get("surface") == "탭용접"]
        assert len(orph) == 1, "극성 모호 anchor → orphan_anchor"
        assert len(orph[0]["payload"].get("candidates", [])) == 2, "payload에 양 극성 후보 id"


def test_f6_missing_field():
    """F6 — 비optional 필드 부재/빈 값이 무음이 아니라 missing_field 큐(§6.5 역방향)."""
    with tempfile.TemporaryDirectory() as tmp:
        dr = Path(tmp)
        _build_all(dr)
        recs = [
            {"chunk_id": "FT2-R1", "process_group": "조립", "process_ref": "노칭",
             "electrode_type": "both", "cause": "미지 원인", "effect_category": "단락",
             "severity": 9},                                    # failure_mode 부재
            {"chunk_id": "FT2-R2", "process_group": "조립", "electrode_type": "both",
             "failure_mode": "좌표 없는 불량", "cause": "원인X", "effect_category": "화재",
             "severity": 9},                                    # process_ref 부재
        ]
        s = build.build_doc(_doc("FT2", "pfmea", records=recs), ROOT, dr)
        missing = {(i["payload"]["chunk_id"], i["payload"]["field"])
                   for i in s.queue.by_kind("missing_field") if i["doc_id"] == "FT2"}
        assert ("FT2-R1", "failure_mode") in missing, f"failure_mode 부재 감지: {missing}"
        assert ("FT2-R2", "process_ref") in missing, f"process_ref 부재 감지(occurs_in 드롭 무음 아님): {missing}"


def test_f15_contract_violations():
    """F15 — entity 리스트 값 큐, payload_kind 미지원 raise(§3.6·§12-3)."""
    with tempfile.TemporaryDirectory() as tmp:
        dr = Path(tmp)
        _build_all(dr)
        # entity 리스트 값 → missing_field(전개 필요) + 쓰레기 노드 미생성
        recs = [{"chunk_id": "FT3-C1", "process_group": "조립", "process_ref": "노칭",
                 "electrode_type": "both", "설비": ["프레스A", "프레스B"], "관리항목": "정밀도X",
                 "규격": {"max": 1, "unit": "mm"}}]
        s = build.build_doc(_doc("FT3", "cp", records=recs), ROOT, dr)
        lst = [i for i in s.queue.by_kind("missing_field")
               if i["doc_id"] == "FT3" and i["payload"].get("value_type") == "list"]
        assert len(lst) == 1, "entity 리스트 값 → 파서 계약 위반 큐"
        g = s.graphs["process"]
        assert not any("[" in n["canonical"] for n in g.nodes.values()), "str(list) 쓰레기 노드 없음"
        # payload_kind 미지원 → 명시적 실패
        try:
            build.build_doc(_doc("FT3X", "cp", records=[], payload_kind="xml"), ROOT, dr)
            assert False, "payload_kind 미지원인데 raise 안 함"
        except ValueError as e:
            assert "payload_kind" in str(e)


def test_f13_invalid_category():
    """F13 — 닫힌 카테고리 목록 밖 category는 노드 생성 보류 + invalid_category 큐(§7-1)."""
    with tempfile.TemporaryDirectory() as tmp:
        dr = Path(tmp)
        _build_all(dr)
        chunks = [{"chunk_id": "FT4-P1", "process_group": "조립", "process_ref": "노칭",
                   "electrode_type": "both", "section": "s", "text": "신규 장비 소개.",
                   "meta": {"mock_mentions": [{"surface": "만능 검사기", "category": "Equipment"}]}}]
        s = build.build_doc(_doc("FT4", "ppt", chunks=chunks), ROOT, dr)
        for g in s.graphs.values():
            assert _find(g, "만능 검사기") is None, "목록 밖 카테고리 노드 미생성"
        inv = [i for i in s.queue.by_kind("invalid_category") if i["doc_id"] == "FT4"]
        assert len(inv) == 1 and inv[0]["payload"]["category"] == "Equipment"


def test_f5_anchor_tier1_only():
    """F5-① — anchor는 Tier1(seed)만. prose가 만든 auto Process에 좌표가 걸리지 않는다(P2)."""
    with tempfile.TemporaryDirectory() as tmp:
        dr = Path(tmp)
        _build_all(dr)
        # prose가 '레이저노칭'을 Process로 언급 → auto Process 생성(사전 등재)
        chunks = [{"chunk_id": "FT5-P1", "process_group": "조립", "process_ref": "노칭",
                   "electrode_type": "both", "section": "s", "text": "레이저노칭 공정 도입 검토.",
                   "meta": {"mock_mentions": [{"surface": "레이저노칭", "category": "Process"}]}}]
        build.build_doc(_doc("FT5A", "ppt", chunks=chunks), ROOT, dr)
        # 후속 PFMEA의 process_ref=레이저노칭 → auto뿐이므로 orphan_anchor(+auto 후보 id)
        recs = [{"chunk_id": "FT5-R1", "process_group": "조립", "process_ref": "레이저노칭",
                 "electrode_type": "both", "failure_mode": "슬리팅 버2", "cause": "빔 편차2",
                 "effect_category": "단락", "severity": 9}]
        s = build.build_doc(_doc("FT5B", "pfmea", records=recs), ROOT, dr)
        q = s.graphs["quality"]
        fm = _find(q, "슬리팅 버2", "Failure")
        assert fm is not None
        assert not any(e["src"] == fm["id"] and e["rel"] == "occurs_in" for e in q.edges), \
            "auto Process에 occurs_in이 걸리면 안 됨"
        orph = [i for i in s.queue.by_kind("orphan_anchor")
                if i["doc_id"] == "FT5B" and i["payload"].get("surface") == "레이저노칭"]
        assert orph and orph[0]["payload"].get("auto_candidates"), \
            "orphan_anchor + auto 후보 id(사람 판단 재료)"


def test_f12_link_word_boundary():
    """F12 — 복합어 내부 substring 오링킹 차단('레이저노칭'→'노칭' 금지), 조사 부착은 허용."""
    with tempfile.TemporaryDirectory() as tmp:
        dr = Path(tmp)
        _build_all(dr)
        r = qcli.route("레이저노칭 공정 불량은?", ROOT, dr)
        assert r["linked"] == [], f"복합어 내부 오링킹: {r['linked']}"
        assert r["answer_path"] == "general_knowledge", "미링킹 경로(답변 3단 ⑵)"
        # 조사 부착("노칭에서")은 여전히 링킹
        r2 = qcli.route("노칭에서 발생할 수 있는 불량은?", ROOT, dr)
        assert r2["linked"], "조사 부착 표면형은 링킹 유지"


def test_f4_property_canonical_scope():
    """F4 — Property canonical 부모(좌표) 접두: 교차 설비 동명 인자 오병합·가짜 spec_conflict 방지."""
    with tempfile.TemporaryDirectory() as tmp:
        dr = Path(tmp)
        _build_all(dr)
        recs = [
            {"chunk_id": "FT6-C1", "process_group": "조립", "process_ref": "실링",
             "electrode_type": "both", "설비": "실러", "관리항목": "온도",
             "규격": {"min": 175, "max": 185, "unit": "C"}},
            {"chunk_id": "FT6-C2", "process_group": "조립", "process_ref": "패키징",
             "electrode_type": "both", "설비": "파우치 성형기", "관리항목": "온도",
             "규격": {"min": 100, "max": 120, "unit": "C"}},
        ]
        s = build.build_doc(_doc("FT6", "cp", records=recs), ROOT, dr)
        g = s.graphs["process"]
        t1 = _find(g, "실링::온도", "Property")
        t2 = _find(g, "패키징::온도", "Property")
        assert t1 and t2 and t1["id"] != t2["id"], "동명 인자가 좌표별 별도 노드"
        assert len(t1["attrs"]["spec"]) == 1 and len(t2["attrs"]["spec"]) == 1, "spec 각자 저장"
        confl = [i for i in s.queue.by_kind("spec_conflict") if i["doc_id"] == "FT6"]
        assert confl == [], f"가짜 spec_conflict 0 기대: {confl}"
        # 표면형 alias 등재 — "온도"로 두 노드 모두 조회 가능
        assert set(s.dic.lookup("온도")) >= {t1["id"], t2["id"]}, "표면형 alias 공유"


def test_f11_double_prefix_guard():
    """F11 — 표면형이 이미 극성 토큰으로 시작하면 재결합 금지(이중 접두 0)."""
    with tempfile.TemporaryDirectory() as tmp:
        dr = Path(tmp)
        _build_all(dr)   # C8이 'cathode 노칭 프레스' 생성해 둠
        recs = [{"chunk_id": "FT7-C1", "process_group": "조립", "process_ref": "노칭",
                 "electrode_type": "cathode", "설비": "cathode 노칭 프레스",
                 "관리항목": "노칭 정밀도", "규격": {"max": 0.1, "unit": "mm"}}]
        s = build.build_doc(_doc("FT7", "cp", records=recs), ROOT, dr)
        g = s.graphs["process"]
        assert not any("cathode cathode" in n["canonical"] for n in g.nodes.values()), "이중 접두 0"
        assert sum(1 for n in g.nodes.values()
                   if n["canonical"] == "cathode 노칭 프레스") == 1, "기존 극성 노드와 병합(신규 아님)"


def test_f3_mirrors_same_parent():
    """F3 — §5.3 조건 ④: 부모(공유 문맥)가 다른 동명 극성쌍은 mirrors로 묶지 않는다."""
    with tempfile.TemporaryDirectory() as tmp:
        dr = Path(tmp)
        _build_all(dr)
        recs = [
            {"chunk_id": "FT8-C1", "process_group": "조립", "process_ref": "실링",
             "electrode_type": "cathode", "설비": "히터", "관리항목": "히터 온도",
             "규격": {"max": 200, "unit": "C"}},
            {"chunk_id": "FT8-C2", "process_group": "조립", "process_ref": "패키징",
             "electrode_type": "anode", "설비": "히터", "관리항목": "히터 온도",
             "규격": {"max": 150, "unit": "C"}},
        ]
        s = build.build_doc(_doc("FT8", "cp", records=recs), ROOT, dr)
        g = s.graphs["process"]
        ch = _find(g, "cathode 히터", "Unit")
        ah = _find(g, "anode 히터", "Unit")
        assert ch and ah
        assert not any(e["rel"] == "mirrors" and {e["src"], e["dst"]} == {ch["id"], ah["id"]}
                       for e in g.edges), "부모 다른 극성쌍에 mirrors 생성 금지(④)"
        asym = [i for i in s.queue.by_kind("mirror_asymmetry")
                if "히터" in str(i["payload"].get("base", ""))]
        assert asym == [], f"부모 다른 쌍의 asymmetry 노이즈 0: {asym}"
        # 정당한 쌍(같은 부모: 노칭 프레스)의 mirrors는 유지
        uc = _find(g, "cathode 노칭 프레스", "Unit")
        ua = _find(g, "anode 노칭 프레스", "Unit")
        assert any(e["rel"] == "mirrors" and {e["src"], e["dst"]} == {uc["id"], ua["id"]}
                   for e in g.edges), "같은 부모 극성쌍 mirrors 유지"


def test_f16_embeddings_contract():
    """F16 준비 — core/embeddings.py embed() 계약: L2 정규화·결정적·MOCK 무의존."""
    v1 = embeddings.embed("노칭 정밀도")
    v2 = embeddings.embed("노칭 정밀도")
    v3 = embeddings.embed("적층 정렬도")
    assert v1 == v2, "같은 입력 → 같은 벡터(결정적)"
    assert v1 != v3, "다른 입력 → 다른 벡터"
    assert abs(math.sqrt(sum(x * x for x in v1)) - 1.0) < 1e-9, "L2 정규화"
    assert len(v1) == 32, "MOCK 32차원(sha256)"


if __name__ == "__main__":
    test_f1_polar_skeleton_alias()
    test_f6_missing_field()
    test_f15_contract_violations()
    test_f13_invalid_category()
    test_f5_anchor_tier1_only()
    test_f12_link_word_boundary()
    test_f4_property_canonical_scope()
    test_f11_double_prefix_guard()
    test_f3_mirrors_same_parent()
    test_f16_embeddings_contract()
    print("test_fable OK")
