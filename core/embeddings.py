"""core/embeddings.py — 판정용 노드 임베딩 (구현문서 §1·§8, 명세 §5.6.6(a)).

임베딩 2종 구분(P4 해석, §5.6.6): 본 파일은 (a) **판정용 노드 임베딩** —
canonical+정의문 기반, 비저장·매 로드 재생성. (b) 검색용 청크 인덱스(하이브리드 서치)는
별개이며 이연 항목.

v1.12(FABLE F16 준비): embed() 계약만 제공한다. 후보검색 확장
(handle_entity/handle_anchor의 사전 정확 일치 + 임베딩 top-k)은 이연 — 배선 시
이 함수를 소비한다. 층 어휘 없음(§0-1) — 입력은 임의 텍스트.

- USE_MOCK=1: sha256 해시 → L2 정규화 벡터(32차원). 수치 무의미 — 경고 로그(§8).
- 실물: sentence-transformers 지연 import(§0-8 — USE_MOCK=1에서 import되지 않음).
"""
from __future__ import annotations

import hashlib
import logging
import math
import os

from core import llm

log = logging.getLogger(__name__)

_warned = False
_model = None


def embed(text) -> list:
    """텍스트 1건 → L2 정규화 벡터(list[float]). 비저장 — 호출 시 재생성(P4)."""
    if llm.use_mock():
        global _warned
        if not _warned:
            log.warning("MOCK 임베딩 — 수치 무의미(구현문서 §8). 유사도 판단에 쓰지 말 것.")
            _warned = True
        digest = hashlib.sha256(str(text).encode("utf-8")).digest()   # 32바이트 → 32차원
        vec = [b / 255.0 for b in digest]
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]
    return _real_embed(str(text))


def _real_embed(text):
    """실물 경로 — sentence-transformers 지연 import(설치는 실물 전환 시에만, requirements 참조)."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer  # 지연 import(§0-8)
        except ImportError as exc:
            raise RuntimeError(
                "실물 임베딩 경로에 sentence-transformers 필요 — "
                "USE_MOCK=1로 실행하거나 requirements의 선택 의존을 설치") from exc
        _model = SentenceTransformer(
            os.environ.get("EMBED_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"))
    vec = _model.encode([text], normalize_embeddings=True)[0]
    return [float(x) for x in vec]
