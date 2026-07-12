"""Embedding gateway — product alias only."""

from __future__ import annotations

import json
import logging

from litellm import aembedding

from app.core.config import Settings
from app.gateways import mock_llm
from app.services.model_catalog import get as get_model

logger = logging.getLogger(__name__)


async def embed_text(settings: Settings, text: str) -> list[float] | None:
    if mock_llm.should_mock_llm(settings):
        # Deterministic tiny vector for tests
        return [0.1] * 8

    route = get_model("embedding-model")
    api_key = getattr(settings, route.api_key_field, "")
    if not api_key:
        return None

    kwargs: dict = {"api_key": api_key}
    if route.api_base:
        kwargs["api_base"] = route.api_base

    try:
        response = await aembedding(
            model=route.model, input=[text[: settings.embedding_input_max_chars]], **kwargs
        )
        data = response.data[0]["embedding"]
        return list(data)
    except Exception:
        logger.exception("Embedding failed")
        return None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def parse_embedding(raw: str | None) -> list[float] | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [float(x) for x in data]
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    return None


def serialize_embedding(vec: list[float]) -> str:
    return json.dumps(vec)
