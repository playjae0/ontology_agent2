"""test_3 — 품질지식층(config+스키마만) + PFMEA01 + cross-layer (구현문서 §9.2 단위 3).

핵심 판정: **git diff core/ 가 비어 있음**(품질층이 config만으로 core 범용 파이프라인에서 도는 것,
§3.6 config-only 확증 — git 검사는 별도 스크립트). + causes 사슬, R9/R13 orphan_anchor,
R12 unknown_field, 규칙A(auto Property)·규칙B(공정 부착), spec_conflict는 C4에서만, cross Q9·Q10, Q1~8 회귀.
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


def _find(g, canonical, category=None):
    for n in g.nodes.values():
        if n["canonical"] == canonical and (category is None or n["category"] == category):
            return n
    return None


def _has_edge(g, s, rel, d):
    return any(e["src"] == s and e["rel"] == rel and e["dst"] == d for e in g.edges)


def _load(name):
    return json.loads((ROOT / f"mock/parsed/{name}.json").read_text(encoding="utf-8"))


def test_3():
    with tempfile.TemporaryDirectory() as tmp:
        data_root = Path(tmp)
        build.plant_skeletons(ROOT, data_root)               # process 트리 + quality flat(FailureEffect)
        build.build_doc(_load("CP01"), ROOT, data_root)
        build.build_doc(_load("PPT01"), ROOT, data_root)
        s = build.build_doc(_load("PFMEA01"), ROOT, data_root)
        q = s.graphs["quality"]
        p = s.graphs["process"]

        # --- FailureEffect 골격(flat, config만) ---
        for fx in ("단락", "화재", "방전기능상실", "충전기능상실"):
            assert _find(q, fx, "FailureEffect"), f"FailureEffect {fx} 골격"

        # --- causes 사슬: 이물 유입 → 절연 파괴 → 내부 단락 ---
        ii = _find(q, "이물 유입", "Failure")
        jp = _find(q, "절연 파괴", "Failure")
        ns = _find(q, "내부 단락", "Failure")
        assert ii and jp and ns
        assert _has_edge(q, ii["id"], "causes", jp["id"]), "이물 유입 causes 절연 파괴"
        assert _has_edge(q, jp["id"], "causes", ns["id"]), "절연 파괴 causes 내부 단락"

        # --- 병합: 절연 파괴는 R3 fm이자 R4 cause = 한 노드(위 사슬이 성립함이 곧 병합 증거) ---
        assert sum(1 for n in q.nodes.values() if n["canonical"] == "절연 파괴") == 1

        # --- cross-layer occurs_in (quality 그래프에 저장, dst=process 노드) ---
        nochi = _find(p, "노칭", "Process")
        assert _has_edge(q, jp["id"], "occurs_in", nochi["id"]), "절연 파괴 occurs_in 노칭(cross-layer)"

        # --- affects (Failure → FailureEffect) ---
        danlak = _find(q, "단락", "FailureEffect")
        assert _has_edge(q, jp["id"], "affects", danlak["id"]), "절연 파괴 affects 단락"

        # --- R9 orphan_anchor(effect '셀 부풀음') + R13 orphan_anchor(process '레이저노칭') ---
        orphans = [o["payload"].get("surface") for o in s.queue.by_kind("orphan_anchor")]
        assert "셀 부풀음" in orphans, "R9 effect orphan_anchor"
        assert "레이저노칭" in orphans, "R13 process_ref orphan_anchor"

        # --- R13 연쇄: occurs_in 드롭 + 규칙B Property 부착 드롭 ---
        slit = _find(q, "슬리팅 버", "Failure")
        assert slit is not None
        assert not any(e["src"] == slit["id"] and e["rel"] == "occurs_in" for e in q.edges), \
            "R13 process orphan → occurs_in 드롭"
        beam = _find(p, "빔 출력", "Property")
        assert beam is not None, "빔 출력 Property는 생성됨(auto)"
        assert not any(e["rel"] == "has_property" and e["dst"] == beam["id"] for e in p.edges), \
            "R13 규칙B 폴백 미스 → 공정 부착 드롭"

        # --- R12 unknown_field('비고') ---
        uf = [u["payload"].get("field") for u in s.queue.by_kind("unknown_field")]
        assert "비고" in uf, "R12 비고 unknown_field"

        # --- 규칙A: 걸침 control_item이 process 층 Property auto 생성 ---
        tabal = _find(p, "노칭::타발 속도", "Property")   # v1.12 F4: 좌표 접두
        assert tabal and tabal["status"] == "auto" and tabal["layer"] == "process", "규칙A auto Property"

        # --- 규칙B: auto Property가 공정좌표에 has_property로 부착(카테고리쌍 매핑) ---
        assert _has_edge(p, nochi["id"], "has_property", tabal["id"]), "규칙B 공정 부착(노칭 has_property 타발 속도)"
        # 금형 클리어런스: CP(설비 부착) + PFMEA 규칙B(공정 부착) 공존 = C2 보강
        gm = _find(p, "노칭::금형 클리어런스", "Property")
        press = _find(p, "노칭 프레스", "Unit")
        assert _has_edge(p, press["id"], "has_property", gm["id"]), "C2: 노칭프레스 has_property 금형클리어런스"
        assert _has_edge(p, nochi["id"], "has_property", gm["id"]), "규칙B: 노칭 has_property 금형클리어런스"

        # --- R12 노칭정밀도 → CP '노칭 정밀도'와 매칭(표기 변형, alias) : 신규 노드 아님 ---
        # v1.12 F4: 양쪽 다 좌표(노칭) 접두라 정규화 키가 같아 매칭 유지 — 스코프 노드 1개뿐
        assert sum(1 for n in p.nodes.values() if n["canonical"] == "노칭::노칭 정밀도") == 1
        assert sum(1 for n in p.nodes.values() if n["canonical"] == "노칭::노칭정밀도") == 0

        # --- effect↔severity 정렬로 spec_conflict는 C4(CP)에서만 (severity 병합, 충돌 없음) ---
        conflicts = s.queue.by_kind("spec_conflict")
        assert len(conflicts) == 1 and conflicts[0]["doc_id"] == "CP01", f"spec_conflict C4에서만: {conflicts}"
        # severity가 FailureEffect에 부착·병합(같은 값)
        assert danlak["attrs"].get("severity", [{}])[0].get("value") == 9, "단락 severity=9"

        # --- cross 질의 Q9(occurs_in 역방향) ---
        r9 = qcli.route("노칭에서 발생할 수 있는 불량은?", ROOT, data_root)
        assert r9["answer_path"] == "graph_fact"
        joined = "\n".join(r9["graph_facts"])
        assert "절연 파괴는 노칭 공정에서 발생한다" in joined, "Q9 occurs_in 역방향"

        # --- cross 질의 Q10(affects 역방향) ---
        r10 = qcli.route("단락으로 이어질 수 있는 불량은 뭐가 있어?", ROOT, data_root)
        assert r10["answer_path"] == "graph_fact"
        joined10 = "\n".join(r10["graph_facts"])
        assert "절연 파괴는 단락(으)로 이어질 수 있다" in joined10, "Q10 affects 역방향"

        # --- Q1~8 회귀: cross-layer on 상태에서도 answer_path 동일(단계2 baseline) ---
        queries = json.loads((ROOT / "mock/queries.json").read_text(encoding="utf-8"))
        by_id = {qq["id"]: qq for qq in queries}
        for qid in (1, 2, 3, 4, 5, 6, 7, 8):
            r = qcli.route(by_id[qid]["question"], ROOT, data_root)
            assert r["answer_path"] == by_id[qid]["expected_path"], \
                f"Q{qid} 회귀 실패: {r['answer_path']} != {by_id[qid]['expected_path']}"

    print("test_3 OK")


if __name__ == "__main__":
    test_3()
