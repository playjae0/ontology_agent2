"""core/dictionary.py — 전 층 공유 동의어 사전 (구현문서 §1·§3, 명세 §8-R2).

계약: lookup(surface) -> 후보 노드 id 목록. 층 간 표면형 충돌 허용 —
호출자가 category/layer로 선별한다(사전은 층을 모른다 = 층 어휘 없음, §0-1).
canonical과 alias 모두 등재하며 register 시 provenance 필수(§0-5, 명세 §9).

동의어 사전은 영속 지식(P4). 질의 경로는 읽기 전용이라 사전에 누적하지 않는다(P6).
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)


def normalize(surface) -> str:
    """표면형 정규화 키 — 공백 제거 + 소문자화(띄어쓰기·영문 대소문자 변형 흡수)."""
    return "".join(str(surface).split()).lower()


class Dictionary:
    """surface(정규화) -> [{id, surface, provenance:[...]}]. 전 층 단일 저장."""

    def __init__(self, path=None):
        self.path = Path(path) if path else None
        self.entries = {}
        if self.path and self.path.exists():
            self.entries = json.loads(self.path.read_text(encoding="utf-8"))

    def register(self, surface, node_id, provenance):
        """표면형→노드 등재. provenance 필수. 같은 (surface,id)는 provenance만 병합."""
        if not provenance:
            raise ValueError("dictionary.register: provenance 필수 (§0-5)")
        key = normalize(surface)
        bucket = self.entries.setdefault(key, [])
        for item in bucket:
            if item["id"] == node_id:
                for p in provenance:
                    if p not in item["provenance"]:
                        item["provenance"].append(p)
                return
        bucket.append({"id": node_id, "surface": surface, "provenance": list(provenance)})

    def lookup(self, surface):
        """정규화 일치하는 후보 노드 id 목록(층 무관). 호출자가 category/layer로 선별."""
        return [item["id"] for item in self.entries.get(normalize(surface), [])]

    def surfaces(self):
        """등재된 원본 표면형 전체 — 질의 링킹 1단(문자열 스캔, 긴 표면형 우선)의 재료."""
        out = []
        for bucket in self.entries.values():
            for item in bucket:
                out.append(item["surface"])
        return out

    def save(self, path=None):
        p = Path(path) if path else self.path
        if p is None:
            raise ValueError("dictionary.save: 경로 없음")
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".tmp")               # 원자적 저장(F14) — tmp+os.replace
        tmp.write_text(json.dumps(self.entries, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, p)
