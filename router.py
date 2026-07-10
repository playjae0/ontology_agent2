"""router.py — 층 폴더 자동 발견 (구현문서 §1, 명세 §8-R1).

layers/<이름>/config.json 을 스캔해 {층이름: config} 반환. 등록 배선 코드 없음 —
폴더를 놓으면 발견된다(층 추가 = config.json + 스키마, 코드 0). 발견 순서는 이름 정렬(결정적).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)


def discover_layers(layers_dir):
    layers_dir = Path(layers_dir)
    out = {}
    if not layers_dir.exists():
        return out
    for child in sorted(layers_dir.iterdir()):
        cfg = child / "config.json"
        if child.is_dir() and cfg.exists():
            out[child.name] = json.loads(cfg.read_text(encoding="utf-8"))
    log.info("discover_layers: %s", list(out))
    return out
