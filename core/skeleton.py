"""core/skeleton.py — 범용 골격 심기 (구현문서 §5, 명세 §5.2·§15.2).

config.skeleton(값)만 해석한다. 층 어휘 없음(§0-1) — category·relation 이름은 config가 준다.
  - type="tree" : data(중첩 dict/list)를 부모-자식 child_rel + 형제 나열순 sibling_rel로 심음.
  - type="flat" : data(목록)를 지정 category 노드로만 심음(엣지 없음).
노드는 status="confirmed", provenance=["seed"] (Tier1 — 사람이 고정, P2).
canonical은 층 내 유일(§5.2) — 같은 plant 호출에서 중복 canonical은 작성 오류로 raise.
config로 표현 안 되는 type을 만나면 명시적 실패(§3.6 탈출구, 오버라이드 코드 금지).
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def plant(graph, skeleton, dictionary=None, polarity=None):
    """config.skeleton을 graph에 심는다. dictionary가 주어지면 canonical을 등재(anchor 조회용).

    polarity(config.polarity)가 주어지면 극성 접두("cathode "/"anode ") 골격 노드에 electrode_type를
    부여한다(극성 잔존 공정 — 명세 §5.2 ②, Process 레벨 극성 분기). 접두 없는 노드는 electrode 무관.
    """
    typ = skeleton.get("type")
    category = skeleton["category"]
    pol_values = list((polarity or {}).get("values", []))
    seen = set()  # 이번 호출에서 만난 canonical (중복 = 층 내 유일 위반)

    if typ == "tree":
        relations = skeleton.get("relations", {})
        child_rel = relations.get("child")
        sibling_rel = relations.get("sibling")
        _plant_children(graph, skeleton["data"], category,
                        child_rel, sibling_rel, parent_id=None,
                        dictionary=dictionary, seen=seen, pol_values=pol_values)
    elif typ == "flat":
        for name in skeleton["data"]:
            _ensure_node(graph, name, category, dictionary, seen, pol_values)
    else:
        raise ValueError(
            f"skeleton.type '{typ}' 미지원 — config 표현 밖(§3.6 탈출구). "
            f"tree|flat만 지원. core 패턴 추가가 필요한 지점."
        )
    log.info("skeleton planted: layer=%s type=%s category=%s nodes=%d",
             graph.layer, typ, category, len(seen))


def _plant_children(graph, children_spec, category, child_rel, sibling_rel,
                    parent_id, dictionary, seen, pol_values):
    """children_spec(dict 또는 list)의 항목을 parent_id 아래에 심고, 형제 precedes 체인 생성.

    - dict  {name: subtree}     : name이 자식, subtree가 그 자식의 하위(list|dict|None)
    - list  [name | {name:sub}] : 각 항목이 자식(문자열=잎, dict=하위 보유)
    가변 깊이 허용(명세 §5.2) — 재귀로 임의 깊이 처리, core는 깊이를 가정하지 않는다.
    """
    items = _normalize_children(children_spec)  # [(name, subtree|None), ...]
    child_ids = []
    for name, subtree in items:
        nid = _ensure_node(graph, name, category, dictionary, seen, pol_values)
        if parent_id is not None and child_rel:
            graph.add_edge(nid, child_rel, parent_id, status="confirmed", provenance=["seed"])
        child_ids.append(nid)
        if subtree:
            _plant_children(graph, subtree, category, child_rel, sibling_rel,
                            parent_id=nid, dictionary=dictionary, seen=seen, pol_values=pol_values)
    # 형제 간 순서 = seed 나열 순서(명세 §5.3). 형제 1개 이하면 엣지 0.
    if sibling_rel:
        for i in range(len(child_ids) - 1):
            graph.add_edge(child_ids[i], sibling_rel, child_ids[i + 1],
                           status="confirmed", provenance=["seed"])
    return child_ids


def _normalize_children(spec):
    if isinstance(spec, dict):
        return list(spec.items())
    if isinstance(spec, list):
        items = []
        for it in spec:
            if isinstance(it, dict):
                items.extend(it.items())
            else:
                items.append((it, None))
        return items
    raise ValueError(f"skeleton.data 하위 형식 미지원(dict|list만): {type(spec).__name__}")


def _ensure_node(graph, canonical, category, dictionary, seen, pol_values):
    if canonical in seen:
        raise ValueError(f"skeleton canonical 중복 — 층 내 유일 위반(명세 §5.2): {canonical}")
    seen.add(canonical)
    # 재실행 idempotent — 같은 canonical/category/layer 노드가 이미 있으면 재사용
    for nid, n in graph.nodes.items():
        if (n["canonical"] == canonical and n["category"] == category
                and n["layer"] == graph.layer):
            return nid
    # 극성 접두 골격 노드(극성 잔존 공정)면 electrode_type 부여 — mirrors 자동 규칙의 전제(§5.2 ②)
    electrode_type = None
    for v in pol_values:
        if canonical.startswith(v + " "):
            electrode_type = v
            break
    nid = graph.add_node(canonical, category, status="confirmed", provenance=["seed"],
                         electrode_type=electrode_type)
    if dictionary is not None:
        dictionary.register(canonical, nid, ["seed"])
    return nid
