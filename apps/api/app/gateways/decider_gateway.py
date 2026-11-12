"""Perplexity's Decider through OpenRouter: closed questions about a text, answered with
probabilities.

Not a chat completion: ``POST /api/alpha/decisions`` takes a ``state`` (the text to judge)
and named questions, each a ``choice`` among described options, a ``noul`` (yes or no, as
the probability of yes) or a ``score`` over described levels, and answers each with its
probabilities. It writes no text. Output is validated before anyone reads it; a failure
raises for the caller to decide (the turn's read leaves the turn to the rules).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.config import Settings
from app.gateways.http_client import get_pooled_client

DECISIONS_URL = "https://openrouter.ai/api/alpha/decisions"
# The pooled client's ceiling; each call passes its own, shorter, budget.
_CLIENT_TIMEOUT_SECONDS = 5.0


class DeciderAnswer(BaseModel):
    """One question's answer: a choice with its probabilities, or a yes probability."""

    type: Literal["choice", "noul", "score"]
    choice: str | None = None
    probabilities: dict[str, float] = Field(default_factory=dict)
    confidence: float | None = None
    noul: float | None = None
    score: float | None = None


class DeciderUsage(BaseModel):
    input_tokens: int = 0
    cost: float = 0.0


class DeciderReply(BaseModel):
    answers: dict[str, DeciderAnswer]
    usage: DeciderUsage = Field(default_factory=DeciderUsage)


async def decide(
    settings: Settings,
    *,
    model: str,
    state: str,
    questions: dict[str, dict[str, Any]],
    seconds: float,
) -> DeciderReply:
    """The Decider's answers to ``questions`` about ``state``. Raises on any failure."""
    if not settings.openrouter_api_key:
        raise RuntimeError("no OpenRouter key")
    client = get_pooled_client(_CLIENT_TIMEOUT_SECONDS)
    response = await client.post(
        DECISIONS_URL,
        headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
        json={"model": model, "state": state, "questions": questions},
        timeout=seconds,
    )
    response.raise_for_status()
    return DeciderReply.model_validate(response.json())
