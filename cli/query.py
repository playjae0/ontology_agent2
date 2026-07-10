"""cli/query.py — 질의 단일 진입점 라우터 (구현문서 §1, 명세 §8-R1).

절차: 전역 링킹 → 해소 노드를 layer별로 묶어 각 층 config로 core.query 파이프라인 호출
      → cross-layer 브리지 1홉(비재귀·양방향) → 그래프 사실 + 문서 근거 두 채널 합성.
라우터·파이프라인 모두 제네릭 조립 코드(§3.4-(가)·§3.6) — 층별 확장 의미는 config.query_traverse 소유.

  python -m cli.query "<질문>"

답변 3단 규칙(명세 §5.6.4): ⑴근거 있음→근거+출처 / ⑵없음→"사내 근거 없음"+[일반지식—사내 검증 필요]+등록 개체 안내 / ⑶미스 로그.
읽기 전용(P6) — 질문 표현을 사전에 누적하지 않는다.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core import build, query  # noqa: E402

log = logging.getLogger(__name__)

# 질의 의도 분류 키워드 — 질문 언어 패턴(층 카테고리·관계·개체 이름이 아님). MOCK에서 LLM 채널 선택 대체.
_EXTERNAL = ["영어로", "영어로 뭐", "무슨 뜻", "뜻이 뭐", "동작 원리", "원리 설명"]
_VALUE = ["규격", "공차", "스펙", "얼마"]
_STRUCTURE = ["다음", "이전", "설비", "흐름", "관리하는", "무슨", "어떤 설비", "발생", "이어지", "불량"]
_FLOW = ["흐름"]


def classify(question, linked_count):
    """(answer_path, is_flow) 판정. 실물에선 답변 LLM이 채널을 고르는 지점(§5.6.4)의 MOCK 대체."""
    q = question
    if any(p in q for p in _EXTERNAL):
        return "general_knowledge", False
    if linked_count == 0:
        return "general_knowledge", False              # 근거 없음(3단 ⑵)
    if any(p in q for p in _FLOW) and ("전체" in q or "공정" in q):
        return "graph_fact", True                      # flow(Q3)
    if any(p in q for p in _VALUE):
        return "graph_fact", False                     # 값 조회(Q4)
    if any(p in q for p in _STRUCTURE):
        return "graph_fact", False                     # 구조 조회(Q2/Q5)
    return "chunk", False                              # 서술(Q1) 기본


def route(question, project_root=PROJECT_ROOT, data_root=None):
    """질의 라우팅 → 결과 dict(answer_path·graph_facts·chunk_ids·answer_text·linking_miss)."""
    data_root = Path(data_root) if data_root else Path(project_root) / "data"
    s = build.Stores(project_root, data_root)

    # 전역 링킹 (사전 스캔 — 읽기 전용)
    linked = query.link(question, s.dic)
    path, is_flow = classify(question, len(linked))

    # layer별로 해소 노드 묶기
    per_layer = {}
    for nid in linked:
        n = _node(s, nid)
        if n:
            per_layer.setdefault(n["layer"], []).append(nid)

    all_facts, all_chunks, truncated_any = [], [], False
    scopes = {}
    for layer, ids in per_layer.items():
        cfg = s.layers_cfg[layer]
        g = s.graphs[layer]
        expanded = query.flow_scope(cfg, g) if is_flow else query.expand(ids, cfg, g)
        scope = set(ids) | set(expanded)
        scopes[layer] = (g, scope, cfg)
        all_facts += query.graph_facts(scope, g, cfg)
        cids, trunc = query.collect_chunks(ids, expanded, s.chunks)
        all_chunks += cids
        truncated_any = truncated_any or trunc

    # cross-layer 브리지 1홉 (명세 §8-6·§8-R1) — config.cross_layer_traverse 보유 층에서 층을 넘음
    _bridge(scopes, s, all_facts)

    linking_miss = len(linked) == 0
    if linking_miss:
        log.info("링킹 미스: '%s' — 계기판5(하이브리드 서치 도입 판단) 재료", question)

    answer_text = _compose(question, path, all_facts, all_chunks, s, linked)
    return {
        "question": question,
        "linked": linked,
        "answer_path": path,
        "is_flow": is_flow,
        "graph_facts": all_facts,
        "chunk_ids": all_chunks,
        "truncated": truncated_any,
        "linking_miss": linking_miss,
        "answer_text": answer_text,
    }


def _node(s, node_id):
    for g in s.graphs.values():
        if node_id in g.nodes:
            return g.nodes[node_id]
    return None


def _bridge(scopes, s, all_facts):
    """cross-layer 1홉 브리지 — 상위층(cross_layer_traverse 보유)에서 타 층 노드로 뻗어 사실 추가."""
    for layer, (g, scope, cfg) in scopes.items():
        clt = cfg.get("cross_layer_traverse")
        if not clt:
            continue
        bridged = g.neighbors(scope, clt)               # 타 층 노드 id (전역 id, dst)
        # 브리지 엣지의 문장화는 상위층 fact_templates 사용(§8-R4) — scope에 브리지 엣지 포함해 재문장화
        for line in query.graph_facts(scope | bridged, g, cfg):
            if line not in all_facts:
                all_facts.append(line)


def _compose(question, path, facts, chunk_ids, s, linked):
    lines = [f"Q: {question}", f"[answer_path={path}]"]
    if path == "general_knowledge":
        lines.append("사내 문서에서 근거를 찾지 못했습니다.")
        lines.append("[일반지식 — 사내 검증 필요] (LLM 일반지식 답변 위치 — 실물 경로)")
        reg = _registered_hint(s, linked)
        if reg:
            lines.append(f"등록된 관련 개체: {reg}")
        return "\n".join(lines)
    if facts:
        lines.append("[그래프 사실]")
        lines += [f"  - {f}" for f in facts]
    if chunk_ids:
        lines.append("[문서 근거]")
        for cid in chunk_ids:
            ch = s.chunks.chunks.get(cid, {})
            lines.append(f"  - ({cid}) {ch.get('text','')}")
    if not facts and not chunk_ids:
        lines.append("(수집된 근거 없음)")
    return "\n".join(lines)


def _registered_hint(s, linked):
    canons = []
    for nid in linked:
        n = _node(s, nid)
        if n:
            canons.append(n["canonical"])
    return ", ".join(canons)


def main(argv=None):
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="온톨로지 질의(단일 진입점 라우터)")
    parser.add_argument("question", help="질문 문자열")
    parser.add_argument("--data", default=None, help="데이터 루트")
    args = parser.parse_args(argv)
    result = route(args.question, PROJECT_ROOT, args.data)
    print(result["answer_text"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
