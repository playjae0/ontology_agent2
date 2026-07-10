"""core/graph.py — 노드/엣지 저장 + 전역 id 발급 (구현문서 §1·§3).

구현 불변 규칙(§0-1): 이 파일에는 층의 카테고리·관계·개체 이름이 한 글자도 없다.
canonical·category·layer·relation은 전부 호출자가 넘기는 값(문자열)일 뿐, core는 의미를 모른다.

- IdSeq        : data/id_seq.json 을 읽어 전역 유일 id(N####)를 발급 (전 층 공유 — 명세 §8-R3).
- Graph        : 한 층의 nodes(dict) + edges(list). add_node/add_edge/neighbors/save/load.
- init_data_tree: data/ 하위(층별 graph.json + 공유 스토어)를 초기값으로 생성 (§9.1 init).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)


def _write_json(path, obj):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path, default):
    p = Path(path)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return default


class IdSeq:
    """전역 유일 id 발급기. data/id_seq.json = {"next": N}. 전 층 공유(명세 §8-R3).

    발급 후 불변(P4). 여러 Graph 인스턴스가 같은 IdSeq를 공유해 층을 넘어 유일성 보장.
    """

    def __init__(self, path):
        self.path = Path(path)
        self._next = _read_json(self.path, {"next": 1})["next"]

    def allocate(self) -> str:
        nid = f"N{self._next:04d}"
        self._next += 1
        return nid

    def save(self):
        _write_json(self.path, {"next": self._next})


class Graph:
    """한 층의 그래프(노드+엣지). 진실 = data/<layer>/graph.json (계약 #2)."""

    def __init__(self, layer, ids: IdSeq):
        self.layer = layer          # config가 준 층 이름 (core는 값으로만 취급)
        self.ids = ids              # 공유 IdSeq
        self.nodes = {}             # id -> node dict
        self.edges = []             # list of edge dict

    # --- 노드 ---------------------------------------------------------------
    def add_node(self, canonical, category, layer=None, status="auto",
                 attrs=None, provenance=None, **extra):
        """노드 생성 후 발급 id 반환. 모든 자동 생성물에 status·provenance 기록(§0-5)."""
        nid = self.ids.allocate()
        node = {
            "id": nid,
            "canonical": canonical,
            "category": category,
            "layer": layer or self.layer,
            "status": status,
            "attrs": dict(attrs or {}),
            "aliases": [],                       # [{surface, provenance:[...]}]
            "provenance": list(provenance or []),
        }
        # electrode_type 등 선택 필드는 층 어휘가 아니라 값으로 그대로 실림
        for k, v in extra.items():
            if v is not None:
                node[k] = v
        self.nodes[nid] = node
        return nid

    def get(self, node_id):
        return self.nodes.get(node_id)

    def add_alias(self, node_id, surface, provenance):
        """노드에 표면형 별칭 누적(provenance 필수 — §0-5). 중복 표면형은 provenance만 병합."""
        node = self.nodes[node_id]
        for a in node["aliases"]:
            if a["surface"] == surface:
                for p in provenance or []:
                    if p not in a["provenance"]:
                        a["provenance"].append(p)
                return
        node["aliases"].append({"surface": surface, "provenance": list(provenance or [])})

    # --- 엣지 ---------------------------------------------------------------
    def add_edge(self, src, rel, dst, status="auto", provenance=None):
        """(src,rel,dst) 엣지 생성. 중복은 provenance 병합, 툼스톤은 건너뜀.

        status="deleted_by_user" 툼스톤인 (src,rel,dst)-by-id는 재생성하지 않는다
        (재인입 부활 방지 — 명세 §5.5-3). enforcement 강화는 단계5, 계약은 지금 준수.
        from/to 어느 한쪽이 미해소(None)이면 조용히 생략(부분 실패 — 레코드 전체 보류 아님).
        """
        if src is None or dst is None:
            return None
        for e in self.edges:
            if e["src"] == src and e["rel"] == rel and e["dst"] == dst:
                if e.get("status") == "deleted_by_user":
                    log.info("add_edge 건너뜀(툼스톤): %s -%s-> %s", src, rel, dst)
                    return None
                for p in provenance or []:                # 중복 엣지 = provenance 병합
                    if p not in e["provenance"]:
                        e["provenance"].append(p)
                return e
        edge = {"src": src, "rel": rel, "dst": dst,
                "status": status, "provenance": list(provenance or [])}
        self.edges.append(edge)
        return edge

    def neighbors(self, ids, traverse_spec):
        """ids로부터 traverse_spec에 명시된 관계를 따라간 이웃 id 집합(seed 제외).

        traverse_spec: {relation: {"direction": "out|in|both", "recursive": bool}}
        core는 관계 개수·이름을 가정하지 않고 config가 준 relation 키만 순회한다(§3.6).
        존재하지 않는 relation은 그냥 매칭 0건(유무 무가정).
        """
        result = set()
        for rel, spec in traverse_spec.items():
            direction = spec.get("direction", "both")
            recursive = spec.get("recursive", False)
            # 명시적 실패(§3.6 탈출구) — config가 준 방향/재귀가 지원 집합 밖이면 조용히 넘기지 않고 raise
            if direction not in ("out", "in", "both"):
                raise ValueError(
                    f"neighbors: 미지원 traverse direction '{direction}' (rel={rel}) — "
                    f"config 표현 밖, core 패턴 추가 필요 (§3.6)")
            if recursive not in (True, False):
                raise ValueError(
                    f"neighbors: 미지원 traverse recursive '{recursive}' (rel={rel}) — "
                    f"config 표현 밖, core 패턴 추가 필요 (§3.6)")
            visited = set(ids)
            frontier = set(ids)
            while frontier:
                step = set()
                for e in self.edges:
                    if e.get("status") == "deleted_by_user" or e["rel"] != rel:
                        continue
                    if direction in ("out", "both") and e["src"] in frontier:
                        step.add(e["dst"])
                    if direction in ("in", "both") and e["dst"] in frontier:
                        step.add(e["src"])
                step -= visited
                if not step:
                    break
                result |= step
                visited |= step
                if not recursive:
                    break
                frontier = step
        return result

    def edges_incident(self, ids):
        """주어진 id 집합에 걸린(양끝 중 하나가 포함) 엣지 목록 — 그래프 사실 문장화 재료."""
        idset = set(ids)
        return [e for e in self.edges
                if e.get("status") != "deleted_by_user"
                and (e["src"] in idset or e["dst"] in idset)]

    # --- 영속 ---------------------------------------------------------------
    def save(self, path):
        _write_json(path, {"nodes": self.nodes, "edges": self.edges})

    @classmethod
    def load(cls, path, layer, ids: IdSeq):
        g = cls(layer, ids)
        data = _read_json(path, {"nodes": {}, "edges": []})
        g.nodes = data.get("nodes", {})
        g.edges = data.get("edges", [])
        return g


def init_data_tree(root, layers):
    """data/ 하위를 초기값으로 생성(§9.1). layers는 값(층 이름 목록)으로 주입 — core 무가정.

    각 파일 초기값: graph.json={"nodes":{},"edges":[]}, id_seq.json={"next":1},
    dictionary.json={}, chunks.json={"chunks":{},"describes":[]}, review_queue.json=[].
    이미 있으면 덮어쓰지 않는다(재실행 안전).
    """
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    for layer in layers:
        gp = root / layer / "graph.json"
        if not gp.exists():
            _write_json(gp, {"nodes": {}, "edges": []})
    shared = {
        "id_seq.json": {"next": 1},
        "dictionary.json": {},
        "chunks.json": {"chunks": {}, "describes": []},
        "review_queue.json": [],
    }
    for name, val in shared.items():
        fp = root / name
        if not fp.exists():
            _write_json(fp, val)
    log.info("init_data_tree: %s (layers=%s)", root, layers)
