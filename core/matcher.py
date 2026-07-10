"""core/matcher.py — 개체 판정 (구현문서 §1·§3, 명세 §5.4-2·§7).

match(surface, candidates, category) -> {"type": match|new|uncertain, "matched_id", "confidence"}.
- USE_MOCK: 문자열 정규화 규칙(공백 제거 후 동일/포함 → 높은 점수). 실물: 판정 프롬프트(HOOK).
- 카테고리 불일치 안전망: 추출 category ≠ 후보 category → match 금지(조용한 오병합 차단, 명세 §5.4).
- 비대칭 기준: 확신 없으면 match가 아니라 uncertain(잘못된 병합이 잘못된 신규보다 해롭다 — §9).

candidates = 노드 dict 목록({id, canonical, category, aliases:[{surface}]}).
"""
from __future__ import annotations

import logging

from core.dictionary import normalize
from core import llm

log = logging.getLogger(__name__)


def match(surface, candidates, category, threshold=0.85):
    if llm.use_mock():
        return _mock_match(surface, candidates, category, threshold)
    return _llm_match(surface, candidates, category, threshold)  # HOOK: 실물


def _mock_match(surface, candidates, category, threshold):
    nsurf = normalize(surface)
    best_id, best_score = None, 0.0
    for c in candidates:
        # 카테고리 불일치 안전망 — 이름이 비슷해도 다른 카테고리면 match 금지
        if category is not None and c.get("category") != category:
            continue
        names = [c.get("canonical", "")] + [a.get("surface", "") for a in c.get("aliases", [])]
        nnames = [normalize(x) for x in names if x]
        if nsurf in nnames:
            score = 0.95                       # 정규화 후 완전 동일
        elif any(nsurf and (nsurf in nn or nn in nsurf) for nn in nnames):
            score = 0.90                       # 정규화 후 포함 관계(부분 일치)
        else:
            continue
        if score > best_score:
            best_id, best_score = c["id"], score
    if best_id is not None and best_score >= threshold:
        return {"type": "match", "matched_id": best_id, "confidence": best_score}
    return {"type": "new", "matched_id": None, "confidence": 0.0}


def _llm_match(surface, candidates, category, threshold):
    """실물 판정 — 정의문·비대칭 기준을 config에서 주입한 프롬프트로 게이트웨이 호출(HOOK)."""
    raise RuntimeError("실물 판정 경로 미구현 — USE_MOCK=1로 실행하거나 게이트웨이 연결 필요")
