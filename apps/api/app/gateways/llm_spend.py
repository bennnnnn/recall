"""What each model call cost, added to the global spend counter.

Every completion and embedding passes through a gateway, so this is the one
place that prices them all: catalog price x the provider's reported tokens, at
the price of the model that ran the call. Memory jobs, titles, compression,
follow-up questions, OCR, embeddings, the query classifiers, a chat turn's tool
selection rounds and every attempt of its reply's stream are all metered here,
whether or not the turn then saves a reply: a turn stopped, refused or failed
after its calls ran was billed for them. A stream attempt's bill is also added to
the turn's usage when the reply kept it, which finalize charges to the user's own
quota (``modules/chat/turn_settle``); nothing is counted twice.

The write runs on its own task, so it never adds latency to the call it
measured or loses its result to the caller's deadline. Best-effort: a failed
write is logged.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping

from app.core.background_tasks import create_background_task
from app.core.redis import get_redis_client
from app.core.spend_counter import record_global_spend
from app.gateways.stream_signals import REQUEST_FAULT, StreamAttempt
from app.gateways.stream_usage import merge_attempt_usage
from app.models.model_catalog import estimate_cost_usd

logger = logging.getLogger(__name__)

# The counter is one INCRBY; a Redis this slow is already failing other calls.
_RECORD_TIMEOUT_SECONDS = 2.0
# A rough count for a prompt the provider ran but reported no usage for.
_CHARS_PER_TOKEN = 4
# Failures where the provider ran nothing (``stream_signals.provider_fault``).
_UNBILLED_CAUSES = frozenset({REQUEST_FAULT, "rate_limit", "connection", "server"})


def _tokens(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(0, value)


def response_cost_usd(alias: str, response: object) -> float:
    """Catalog price x the response's token usage; 0 when either is unknown."""
    usage = getattr(response, "usage", None)
    input_tokens = _tokens(getattr(usage, "prompt_tokens", None))
    output_tokens = _tokens(getattr(usage, "completion_tokens", None))
    if not input_tokens and not output_tokens:
        return 0.0
    cost = estimate_cost_usd(alias, input_tokens=input_tokens, output_tokens=output_tokens)
    return cost or 0.0


def meter_model_call(alias: str, response: object) -> None:
    """Add one provider response's cost to today's global spend, off the call's path."""
    _meter(alias, response_cost_usd(alias, response))


def billed_tokens(
    usage: Mapping[str, int], prompt_chars: int, cause: str | None, text_chars: int = 0
) -> tuple[int, int] | None:
    """(input, output) tokens one chat stream attempt was billed: what the provider
    reported, or, when it reported none and likely ran the prompt, the prompt's estimate
    and the text it streamed (a Stop or a cut ends the stream before its usage chunk).
    None when the provider refused it before running anything (a 4xx, a rate limit, no
    connection, a server error) and reported nothing. A stop (no cause) did run."""
    input_tokens = _tokens(usage.get("input"))
    output_tokens = _tokens(usage.get("output"))
    if "output" not in usage:
        output_tokens = max(0, text_chars) // _CHARS_PER_TOKEN
    if not input_tokens:
        if not output_tokens and cause in _UNBILLED_CAUSES:
            return None
        # An attempt cut off mid-thought has only its reasoning estimated: it read the prompt.
        input_tokens = max(0, prompt_chars) // _CHARS_PER_TOKEN
    return input_tokens, output_tokens


def settle_stream_attempt(
    alias: str,
    attempt_usage: Mapping[str, int],
    prompt_chars: int,
    attempt: StreamAttempt,
    reply_usage: dict[str, int] | None,
) -> None:
    """One chat stream attempt's bill, from its own usage alone (``billed_tokens``):
    counted toward today's global spend at its model's price, every attempt, and added to
    the reply's usage (``reply_usage``) when the reply kept any of it.

    The provider billed each attempt whatever the turn did next: a fallback, a retry, one
    cut off by the first-reply cap, one stopped before or during its text, a turn refused
    or failed after the stream ran. A reply the user stopped mid-stream is charged what
    its stream sent, never the shorter text the client says it drew: the usage chunk never
    came, and the turn's usage held only its earlier calls (security review, 2026-11-25)."""
    billed = billed_tokens(attempt_usage, prompt_chars, attempt.cause, attempt.text_chars)
    if billed is None:
        return
    merge_attempt_usage(reply_usage, {**attempt_usage, "input": billed[0], "output": billed[1]})
    cost = estimate_cost_usd(alias, input_tokens=billed[0], output_tokens=billed[1])
    _meter(alias, cost or 0.0)


def meter_reported_cost(alias: str, cost: float) -> None:
    """Add a cost the provider reported itself (the Decider's ``usage.cost``)."""
    _meter(alias, max(0.0, cost))


def _meter(alias: str, cost: float) -> None:
    if cost > 0:
        create_background_task(_record(alias, cost), name="model_spend")


async def _record(alias: str, cost: float) -> None:
    try:
        async with asyncio.timeout(_RECORD_TIMEOUT_SECONDS):
            await record_global_spend(get_redis_client(), cost)
    except Exception:
        logger.warning("Model spend not recorded alias=%s usd=%.6f", alias, cost, exc_info=True)
