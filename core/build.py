"""core/build.py — 범용 쓰기 파이프라인 (구현문서 §3·§5). 층 무관 — config+스키마 구동.

절차: config/스키마 로드 → 재인입(doc_id 발자국 회수) → ingest 2-pass →
      mirrors 자동 규칙(config.mirrors.enabled) → 저장.
config로 표현 안 되는 절차를 만나면 명시적 실패(§3.6 탈출구, 오버라이드 코드 금지) — ingest/skeleton가 raise.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import router
from core.graph import IdSeq, Graph, init_data_tree
from core.dictionary import Dictionary
from core.store import ChunkStore, ReviewQueue
from core import ingest, skeleton

log = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# 스키마 로드 (블록 조립)
# ----------------------------------------------------------------------
def load_schema(schemas_dir, doc_type):
    """doc_type 스키마 로드 + use_blocks 조립(로더가 dict 합칠 뿐 — 값, 코드 리스크 0, 정의서 §5.4)."""
    schemas_dir = Path(schemas_dir)
    schema = json.loads((schemas_dir / f"{doc_type}.json").read_text(encoding="utf-8"))
    fields = {}
    for block in schema.get("use_blocks", []):
        blk = json.loads((schemas_dir / "blocks" / f"{block}.json").read_text(encoding="utf-8"))
        fields.update(blk.get("fields", {}))
    fields.update(schema.get("fields", {}))     # doc_type 고유 필드가 블록을 덮어씀
    schema["fields"] = fields
    return schema


# ----------------------------------------------------------------------
# 저장소 로드/세이브 묶음
# ----------------------------------------------------------------------
class Stores:
    def __init__(self, project_root, data_root):
        self.project_root = Path(project_root)
        self.data_root = Path(data_root)
        self.layers_cfg = router.discover_layers(self.project_root / "layers")
        self.ids = IdSeq(self.data_root / "id_seq.json")
        self.graphs = {
            layer: Graph.load(self.data_root / layer / "graph.json", layer, self.ids)
            for layer in self.layers_cfg
        }
        self.dic = Dictionary(self.data_root / "dictionary.json")
        self.queue = ReviewQueue(self.data_root / "review_queue.json")
        self.chunks = ChunkStore(self.data_root / "chunks.json")

    def save(self):
        for layer, g in self.graphs.items():
            g.save(self.data_root / layer / "graph.json")
        self.ids.save()
        self.dic.save()
        self.queue.save()
        self.chunks.save()


# ----------------------------------------------------------------------
# 골격 심기 (init 시 1회)
# ----------------------------------------------------------------------
def plant_skeletons(project_root, data_root):
    """발견된 전 층의 config.skeleton을 심는다(§9.1 init의 seed 단계)."""
    init_data_tree(data_root, list(router.discover_layers(Path(project_root) / "layers")))
    s = Stores(project_root, data_root)
    for layer, cfg in s.layers_cfg.items():
        if "skeleton" in cfg:
            skeleton.plant(s.graphs[layer], cfg["skeleton"], s.dic)
    s.save()
    log.info("plant_skeletons 완료: %s", list(s.layers_cfg))
    return s


# ----------------------------------------------------------------------
# 문서 인입
# ----------------------------------------------------------------------
def build_doc(doc, project_root, data_root):
    """파서 출력 doc(계약 #1)을 인입해 data/ 갱신."""
    s = Stores(project_root, data_root)
    schema = load_schema(Path(project_root) / "schemas", doc["doc_type"])
    layer = schema.get("layer") or doc.get("layer")
    if layer not in s.layers_cfg:
        raise ValueError(f"스키마 layer '{layer}'에 해당하는 layers/{layer}/config.json 없음")
    config = s.layers_cfg[layer]

    # 재인입 — 같은 doc_id 발자국 회수(개정 문서 교체, 명세 §5.5-3)
    ingest.reinject(doc["doc_id"], s.graphs, s.dic, s.chunks, s.queue,
                    parsed_at=doc.get("parsed_at", ""))

    # 인입 — payload_kind로 table(핸들러 루프) vs prose(추출→describes) 분기
    ctx = ingest.Ctx(s.graphs, s.dic, s.queue, s.chunks, doc, config, schema)
    if doc.get("payload_kind") == "prose":
        ingest.ingest_prose(doc, ctx)
    else:
        ingest.ingest_doc(doc, schema, ctx)

    # mirrors 자동 규칙 — 발견된 각 층에 대해(enabled 층만 동작, config 구동)
    for lyr, cfg in s.layers_cfg.items():
        ingest.apply_mirrors(
            s.graphs[lyr], cfg,
            lambda kind, payload, reason, _lyr=lyr: s.queue.add(
                kind, payload, doc["doc_id"], reason, doc.get("parsed_at", "")),
        )

    s.save()
    log.info("build_doc 완료: doc=%s layer=%s", doc["doc_id"], layer)
    return s
