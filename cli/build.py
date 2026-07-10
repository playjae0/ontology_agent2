"""cli/build.py — 쓰기 CLI 진입점 (구현문서 §1, 명세 §16.1 플랫폼화 계약).

  python -m cli.build --init                 # data/ 초기화 + 전 층 골격 심기
  python -m cli.build <parsed.json>          # 파서 출력 1건 인입 → data/ 갱신

모든 단계는 CLI 진입점 + 파일 입출력(§0-7) — 플랫폼이 subprocess로 호출한다.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core import build  # noqa: E402


def main(argv=None):
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="온톨로지 쓰기 파이프라인")
    parser.add_argument("parsed", nargs="?", help="파서 출력 JSON 경로(계약 #1)")
    parser.add_argument("--init", action="store_true", help="data/ 초기화 + 골격 심기")
    parser.add_argument("--data", default=str(PROJECT_ROOT / "data"), help="데이터 루트")
    args = parser.parse_args(argv)

    data_root = Path(args.data)

    if args.init:
        build.plant_skeletons(PROJECT_ROOT, data_root)
        print(f"init 완료: {data_root}")
        return 0

    if not args.parsed:
        parser.error("parsed.json 경로 또는 --init 필요")

    doc = json.loads(Path(args.parsed).read_text(encoding="utf-8"))
    build.build_doc(doc, PROJECT_ROOT, data_root)
    print(f"인입 완료: {doc['doc_id']} ({doc['doc_type']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
