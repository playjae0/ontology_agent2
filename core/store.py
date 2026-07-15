"""core/store.py — 층 공유 저장소: 청크 스토어 + 수정 큐 (구현문서 §2.3).

시스템 인프라(층 어휘 없음, §0-1 무관) — 전 층이 공유하는 청크 원문과 수정 작업목록.
- ChunkStore: 청크 원문 보존(전 청크 — 링킹 0건도, 명세 §5.6.6) + describes 링크.
- ReviewQueue: 자동 커밋 후 사후 수정 재료(차단 대기열 아님 — 명세 §9). 표준 kind 목록은 §2.3.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

# 수정 큐 표준 kind (구현문서 §2.3 + v1.12: missing_field·invalid_category) — 시스템 어휘(층 무관)
QUEUE_KINDS = {
    "auto_node", "uncertain_match", "orphan_anchor", "orphan_chunk_link",
    "unknown_field", "spec_conflict", "evidence_lost", "mirror_asymmetry",
    "missing_field",      # 비optional 필드 부재/빈 값·미전개 리스트(§6.5 역방향, F6·F15)
    "invalid_category",   # 닫힌 카테고리 목록 밖(§7-1 구조적 차단, F13)
}


def _read_json(path, default):
    p = Path(path)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return default


def _write_json(path, obj):
    """원자적 저장(F14): tmp에 쓰고 os.replace로 교체 — 중단 시 유실 방지(graph._write_json과 대칭)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, p)


class ChunkStore:
    """청크 원문 저장소(층 공유). 링킹 0건 청크도 원문 보존(전 청크 — 명세 §5.6.6)."""

    def __init__(self, path):
        self.path = Path(path)
        data = _read_json(self.path, {"chunks": {}, "describes": []})
        self.chunks = data.get("chunks", {})
        self.describes = data.get("describes", [])

    def add_chunk(self, chunk_id, doc_id, text, section=None, meta=None, linked=False):
        self.chunks[chunk_id] = {
            "doc_id": doc_id, "text": text, "section": section,
            "meta": dict(meta or {}), "linked": bool(linked),
        }

    def add_describes(self, chunk_id, node_id):
        if chunk_id in self.chunks:
            self.chunks[chunk_id]["linked"] = True
        link = {"chunk_id": chunk_id, "node_id": node_id}
        if link not in self.describes:
            self.describes.append(link)

    def nodes_for_chunk(self, chunk_id):
        return [d["node_id"] for d in self.describes if d["chunk_id"] == chunk_id]

    def chunks_for_node(self, node_id):
        return [d["chunk_id"] for d in self.describes if d["node_id"] == node_id]

    def remove_doc(self, doc_id):
        """재인입 — 해당 doc_id의 청크·describes 회수(명세 §5.5-3)."""
        removed = {cid for cid, c in self.chunks.items() if c.get("doc_id") == doc_id}
        for cid in removed:
            del self.chunks[cid]
        self.describes = [d for d in self.describes if d["chunk_id"] not in removed]
        return removed

    def save(self):
        _write_json(self.path, {"chunks": self.chunks, "describes": self.describes})


class ReviewQueue:
    """수정 작업목록(층 공유). add로 적재, 사람이 자기 리듬으로 소화(비차단 — 명세 §9)."""

    def __init__(self, path):
        self.path = Path(path)
        self.items = _read_json(self.path, [])

    def add(self, kind, payload, doc_id, reason, created=""):
        if kind not in QUEUE_KINDS:
            log.warning("알 수 없는 큐 kind: %s (§2.3 표준 목록 밖)", kind)
        self.items.append({
            "kind": kind, "payload": payload, "reason": reason,
            "doc_id": doc_id, "created": created,
        })

    def by_kind(self, kind):
        return [i for i in self.items if i["kind"] == kind]

    def remove(self, predicate):
        """predicate(item)==True인 항목 제거. 제거 개수 반환(self-heal 재작성 등)."""
        before = len(self.items)
        self.items = [i for i in self.items if not predicate(i)]
        return before - len(self.items)

    def remove_doc(self, doc_id):
        self.items = [i for i in self.items if i.get("doc_id") != doc_id]

    def save(self):
        _write_json(self.path, self.items)
