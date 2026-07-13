#!/usr/bin/env python3
"""run.py — 파이프라인 단일 진입점 (표준 라이브러리만, 외부 패키지 0 — 구현문서 §9.1).

  python run.py init [--fresh]       data/ 초기화 + 전 층 골격 심기(§9.1). --fresh면 기존 data/ 삭제
  python run.py build [파일...]       mock/parsed/* 전부(기본) 또는 지정 파일 인입
  python run.py query "<질문>"         질의 실행 — 그래프 사실 + 문서 근거 두 채널 출력
  python run.py test                 tests/test_*.py 전체 실행
  python run.py status               현재 상태 요약(층·카테고리·큐·사전)
  python run.py all                  init → build → test (깨끗한 재현)

기존 CLI(cli/build.py·cli/query.py)를 감싸는 얇은 러너 — 플랫폼화 계약(§0-7, §16.1)의
"CLI 진입점 + 파일 입출력"은 그대로 유지된다. USE_MOCK 기본 1(§0-8).
읽기 전용 명령(query·status)은 진실(data/)을 수정하지 않는다.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("USE_MOCK", "1")   # 기본 mock — 네트워크·API키 없이 전 과정 동작(§0-8)

DEFAULT_DATA = PROJECT_ROOT / "data"
MOCK_PARSED = PROJECT_ROOT / "mock" / "parsed"

# 인입 순서 — 문서 간 순서 강제는 없으나(§5.5-4), mock 검증 시나리오는 CP→PPT→PFMEA 순을 전제
# (구현문서 §7 단계1~3의 관찰 순서). 지정 파일이 있으면 그 순서를 그대로 따른다.
MOCK_ORDER = ["CP01", "PPT01", "PFMEA01"]


# ----------------------------------------------------------------------
# 명령
# ----------------------------------------------------------------------
def cmd_init(args):
    """data/ 초기화 + 골격 심기. 기본은 보존(재실행 안전), --fresh면 비우고 새로 만든다.

    --fresh가 필요한 이유: init_data_tree는 기존 파일을 덮어쓰지 않으므로(재실행 안전),
    data/가 남은 채 build를 다시 돌리면 **재인입 경로**를 타서 노드가 중복 생성된다
    (KNOWN_ISSUES (나) — 재인입 사전 보존은 단위5). "깨끗한 재현"(all)은 fresh여야 한다.
    """
    from core import build
    data_root = Path(args.data)
    if getattr(args, "fresh", False) and data_root.exists():
        import shutil
        shutil.rmtree(data_root)
        print(f"🧹 기존 data/ 삭제 — 깨끗한 재현({data_root})")
    build.plant_skeletons(PROJECT_ROOT, data_root)
    print(f"✅ init 완료 — {data_root}")
    return 0


def cmd_build(args):
    from core import build as core_build
    data_root = Path(args.data)
    if not (data_root / "id_seq.json").exists():
        print(f"❌ data/ 미초기화 — 먼저 `python run.py init` 실행 ({data_root})", file=sys.stderr)
        return 1

    paths = [Path(p) for p in args.files] if args.files else _mock_docs()
    if not paths:
        print("❌ 인입할 파서 출력 JSON이 없다", file=sys.stderr)
        return 1

    for p in paths:
        if not p.exists():
            print(f"❌ 파일 없음: {p}", file=sys.stderr)
            return 1
        doc = json.loads(p.read_text(encoding="utf-8"))
        core_build.build_doc(doc, PROJECT_ROOT, data_root)
        print(f"✅ 인입 — {doc['doc_id']} ({doc['doc_type']}, {doc.get('payload_kind')})")
    print(f"인입 {len(paths)}건 완료 → {data_root}")
    return 0


def _mock_docs():
    """mock/parsed/*.json — MOCK_ORDER 우선, 나머지는 이름순(결정적)."""
    found = {p.stem: p for p in sorted(MOCK_PARSED.glob("*.json"))}
    ordered = [found.pop(k) for k in MOCK_ORDER if k in found]
    return ordered + list(found.values())


def cmd_query(args):
    from cli import query as qcli
    result = qcli.route(args.question, PROJECT_ROOT, args.data)
    print(result["answer_text"])
    if args.verbose:
        print(f"\n[진단] linked={result['linked']} path={result['answer_path']} "
              f"flow={result['is_flow']} facts={len(result['graph_facts'])} "
              f"chunks={len(result['chunk_ids'])} truncated={result['truncated']} "
              f"linking_miss={result['linking_miss']}")
    return 0


def cmd_test(args):
    """tests/test_*.py 전체를 각각 서브프로세스로 실행(각 파일의 __main__이 전 케이스 호출)."""
    tests = sorted((PROJECT_ROOT / "tests").glob("test_*.py"))
    if not tests:
        print("❌ 테스트 파일 없음", file=sys.stderr)
        return 1
    env = dict(os.environ, PYTHONPATH=str(PROJECT_ROOT), USE_MOCK=os.environ.get("USE_MOCK", "1"))
    failed = []
    for t in tests:
        proc = subprocess.run([sys.executable, str(t)], cwd=PROJECT_ROOT, env=env,
                              capture_output=True, text=True)
        if proc.returncode == 0:
            print(f"  ✅ {t.name}")
        else:
            failed.append(t.name)
            print(f"  ❌ {t.name}")
            tail = (proc.stdout + proc.stderr).strip().splitlines()[-6:]
            for line in tail:
                print(f"       {line}")
    print(f"\n테스트 {len(tests) - len(failed)}/{len(tests)} 통과")
    if failed:
        print(f"실패: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


def cmd_status(args):
    """현재 그래프 상태 요약 — 사람이 한눈에 읽는 표(읽기 전용)."""
    from core import build
    data_root = Path(args.data)
    if not (data_root / "id_seq.json").exists():
        print(f"❌ data/ 미초기화 — `python run.py init` 먼저 ({data_root})", file=sys.stderr)
        return 1
    s = build.Stores(PROJECT_ROOT, data_root)

    print(f"\n📊 온톨로지 상태 — {data_root}")

    # --- 층별 노드·엣지 ---
    rows = []
    for layer, g in s.graphs.items():
        live = [e for e in g.edges if e.get("status") != "deleted_by_user"]
        cross = sum(1 for e in live if _layer_of(s, e["dst"]) not in (layer, None))
        rows.append((layer, len(g.nodes), len(live), cross))
    _table(["층", "노드", "엣지", "cross-layer"], rows)

    # --- 카테고리 분포(status별) — 카테고리 이름은 데이터에서(코드 무가정 §3.6) ---
    cat_rows = []
    for layer, g in s.graphs.items():
        dist = {}
        for n in g.nodes.values():
            key = (n["category"], n.get("status", "?"))
            dist[key] = dist.get(key, 0) + 1
        for (cat, st), cnt in sorted(dist.items()):
            cat_rows.append((layer, cat, st, cnt))
    print("\n[카테고리 분포]")
    _table(["층", "카테고리", "status", "노드 수"], cat_rows)

    # --- 관계 분포 ---
    rel_rows = []
    for layer, g in s.graphs.items():
        dist = {}
        for e in g.edges:
            if e.get("status") == "deleted_by_user":
                continue
            dist[e["rel"]] = dist.get(e["rel"], 0) + 1
        for rel, cnt in sorted(dist.items()):
            rel_rows.append((layer, rel, cnt))
    print("\n[관계 분포]")
    _table(["층", "관계", "엣지 수"], rel_rows)

    # --- 수정 큐(kind별) — 차단 대기열 아니라 작업목록(§9) ---
    qdist = {}
    for item in s.queue.items:
        qdist[item["kind"]] = qdist.get(item["kind"], 0) + 1
    print(f"\n[수정 큐] 총 {len(s.queue.items)}건")
    _table(["kind", "건수"], sorted(qdist.items(), key=lambda x: -x[1]))

    # --- 청크·사전 ---
    linked = sum(1 for c in s.chunks.chunks.values() if c.get("linked"))
    print("\n[청크·사전]")
    _table(["항목", "값"], [
        ("청크 총수", len(s.chunks.chunks)),
        ("  linked", linked),
        ("  linked=false(보존)", len(s.chunks.chunks) - linked),
        ("describes 링크", len(s.chunks.describes)),
        ("사전 표면형(정규화 키)", len(s.dic.entries)),
        ("사전 엔트리(표면형→노드)", sum(len(v) for v in s.dic.entries.values())),
        ("다음 id", s.ids._next),
    ])
    print()
    return 0


def _layer_of(s, node_id):
    for layer, g in s.graphs.items():
        if node_id in g.nodes:
            return layer
    return None


def _table(headers, rows):
    if not rows:
        print("  (없음)")
        return
    cells = [[str(h) for h in headers]] + [[str(c) for c in r] for r in rows]
    widths = [max(_w(row[i]) for row in cells) for i in range(len(headers))]
    sep = "  " + "─┼─".join("─" * w for w in widths)
    for i, row in enumerate(cells):
        print("  " + " │ ".join(c + " " * (widths[j] - _w(c)) for j, c in enumerate(row)))
        if i == 0:
            print(sep)


def _w(text):
    """한글·전각은 폭 2로 계산(표 정렬)."""
    return sum(2 if ord(ch) > 0x1100 and not ch.isascii() else 1 for ch in text)


def cmd_all(args):
    """깨끗한 재현 — init(--fresh) → build(mock 전부) → test.

    data/를 비우고 시작한다 — 남겨두면 build가 재인입 경로를 타 노드가 중복된다((나)).
    진실을 지우는 유일한 명령이므로 mock 재현 용도로만 쓴다(운영은 init 없이 build).
    """
    args.fresh = True
    print("=" * 60)
    print("[1/3] init (fresh)")
    if cmd_init(args) != 0:
        return 1
    print("\n" + "=" * 60)
    print("[2/3] build")
    args.files = []
    if cmd_build(args) != 0:
        return 1
    print("\n" + "=" * 60)
    print("[3/3] test")
    rc = cmd_test(args)
    print("\n" + "=" * 60)
    print("✅ all 완료 — `python run.py status`로 상태 확인" if rc == 0 else "❌ all 실패(테스트)")
    return rc


# ----------------------------------------------------------------------
def main(argv=None):
    import logging
    parser = argparse.ArgumentParser(
        prog="run.py", description="온톨로지 파이프라인 단일 진입점(USE_MOCK 기본 1)")
    parser.add_argument("--data", default=str(DEFAULT_DATA), help="데이터 루트(기본 data/)")
    parser.add_argument("-q", "--quiet", action="store_true", help="INFO 로그 숨김")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="data/ 초기화 + 골격 심기")
    p_init.add_argument("--fresh", action="store_true",
                        help="기존 data/를 지우고 새로 만든다(깨끗한 재현 — 재인입 중복 방지)")
    p_build = sub.add_parser("build", help="파서 출력 인입(기본: mock/parsed 전부)")
    p_build.add_argument("files", nargs="*", help="파서 출력 JSON 경로(생략 시 mock/parsed/*)")
    p_query = sub.add_parser("query", help="질의 실행")
    p_query.add_argument("question", help="질문 문자열")
    p_query.add_argument("-v", "--verbose", action="store_true", help="진단 정보 출력")
    sub.add_parser("test", help="tests/test_*.py 전체 실행")
    sub.add_parser("status", help="현재 상태 요약")
    sub.add_parser("all", help="init → build → test")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING if args.quiet else logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")

    handlers = {"init": cmd_init, "build": cmd_build, "query": cmd_query,
                "test": cmd_test, "status": cmd_status, "all": cmd_all}
    try:
        return handlers[args.cmd](args)
    except Exception as exc:                      # 명시적 실패(§3.6)를 삼키지 않고 드러냄
        print(f"\n❌ 실패: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
