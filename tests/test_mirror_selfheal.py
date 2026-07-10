"""test_mirror_selfheal — mirror_asymmetry self-heal (검수 지적 (가) 수정 검증).

apply_mirrors가 매 build 재평가·큐 재작성 → 재인입/후속문서 모두에서 self-heal.
- 최초 빌드: asymmetry 1
- CP01 동일 재인입: asymmetry 1 유지(폭증 없음 — 중복 노드에도 강건)
- 대칭으로 고쳐 재인입: asymmetry 0 (해소 시 큐에서 빠짐)
(재인입 노드 중복 자체는 KNOWN_ISSUES (나) — 단위5. 여기선 큐 self-heal만 검증.)
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

os.environ.setdefault("USE_MOCK", "1")

from core import build

ROOT = Path(__file__).resolve().parent.parent


def _load(name):
    return json.loads((ROOT / f"mock/parsed/{name}.json").read_text(encoding="utf-8"))


def _n_asym(s):
    return len(s.queue.by_kind("mirror_asymmetry"))


def test_mirror_selfheal():
    with tempfile.TemporaryDirectory() as tmp:
        dr = Path(tmp)
        build.plant_skeletons(ROOT, dr)
        build.build_doc(_load("CP01"), ROOT, dr)
        build.build_doc(_load("PPT01"), ROOT, dr)
        s = build.build_doc(_load("PFMEA01"), ROOT, dr)
        assert _n_asym(s) == 1, f"최초 빌드 asymmetry 1 기대, 실제 {_n_asym(s)}"

        # CP01 동일 재인입 — 폭증 없이 1 유지
        s = build.build_doc(_load("CP01"), ROOT, dr)
        assert _n_asym(s) == 1, f"CP01 재인입 후 asymmetry 1 유지 기대, 실제 {_n_asym(s)}"

        # 대칭으로 고쳐 재인입 — cathode에도 '버 높이' 추가 → 대칭 → asymmetry 0
        cp = _load("CP01")
        cp["records"].append({
            "chunk_id": "CP01-C8b", "process_group": "조립", "process_ref": "노칭",
            "electrode_type": "cathode", "설비": "노칭 프레스", "관리항목": "버 높이",
            "규격": {"max": 5, "unit": "um"}, "측정방법": "현미경 샘플", "대응계획": "버 발생 시 금형 연마",
        })
        s = build.build_doc(cp, ROOT, dr)
        assert _n_asym(s) == 0, f"대칭 회복 후 asymmetry 0 기대, 실제 {_n_asym(s)}: {s.queue.by_kind('mirror_asymmetry')}"

        # [경계] 원본으로 되돌려 다시 비대칭이 되는 검증은 여기 두지 않는다:
        # 재인입이 살아있는 노드(대칭화로 추가된 cathode '버 높이')를 삭제하지 않고 evidence_lost로
        # 남기므로(KNOWN_ISSUES (나)), union 비교상 여전히 대칭으로 보인다. self-heal의 정방향
        # (비대칭→대칭 감지)은 여기서 확증됐고, 역방향 복원은 (나) 재인입 회수 정밀화(단위5) 후 성립.

    print("test_mirror_selfheal OK")


if __name__ == "__main__":
    test_mirror_selfheal()
