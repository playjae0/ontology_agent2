"""core/llm.py — LLM 게이트웨이 호출 + JSON 파싱, USE_MOCK 분기 (구현문서 §8).

설정 접근(USE_MOCK, 게이트웨이 URL/키, 모델)은 이 파일 한 곳으로 수렴(§8).
USE_MOCK=1(기본)에서는 외부 의존(게이트웨이, sentence-transformers) 없이 규칙 폴백으로 동작(§0-8).
실물 경로는 지연 import로 격리 — USE_MOCK=1에서는 import되지 않는다.
"""
from __future__ import annotations

import os
import logging

log = logging.getLogger(__name__)


def use_mock() -> bool:
    return os.environ.get("USE_MOCK", "1") != "0"


def extract_mentions(chunk, config):
    """prose 청크에서 언급 추출 → [{surface, category}] (명세 §5.4-1, §7).

    USE_MOCK: LLM 대체 — 청크 meta.mock_mentions(파서 mock이 넣은 추출 시뮬레이션)를 사용.
    힌트가 없으면 추출 0(훅). 실물 경로는 정의문 3종을 삽입한 추출 프롬프트로 게이트웨이 호출.
    (mock = 메커니즘 검증용이며 추출 품질 측정이 아님 — 명세 §16.3.)
    """
    if use_mock():
        meta = chunk.get("meta") or {}
        return list(meta.get("mock_mentions", []))
    raise RuntimeError("실물 추출 경로 미구현 — USE_MOCK=1로 실행하거나 게이트웨이 연결 필요")


def gateway_config():
    return {
        "url": os.environ.get("LLM_GATEWAY_URL"),
        "key": os.environ.get("LLM_API_KEY"),
        "model": os.environ.get("CHAT_MODEL"),
    }


def call_gateway(prompt, *, system=None, json_out=True):
    """실물 게이트웨이 호출 (USE_MOCK=0 경로). 지연 import로 격리(§0-8, §9.1).

    PoC(USE_MOCK=1)에서는 호출되지 않는다. 호출 시 명확히 실패시켜 미구현을 드러낸다.
    """
    if use_mock():
        raise RuntimeError("call_gateway는 USE_MOCK=1에서 호출되면 안 된다 — 규칙 폴백 경로 누락")
    import json
    import urllib.request  # 표준 라이브러리 — 지연 import

    cfg = gateway_config()
    if not cfg["url"]:
        raise RuntimeError("LLM_GATEWAY_URL 미설정 — 실물 경로 요구")
    payload = json.dumps({"model": cfg["model"], "system": system, "prompt": prompt}).encode("utf-8")
    req = urllib.request.Request(cfg["url"], data=payload,
                                 headers={"Authorization": f"Bearer {cfg['key']}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:  # noqa: S310 (사내 게이트웨이)
        body = resp.read().decode("utf-8")
    return json.loads(body) if json_out else body
