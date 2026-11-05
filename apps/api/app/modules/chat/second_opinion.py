"""A second opinion on a maths, physics or chemistry answer the server could not verify.

When no solver could check a question, the model works the answer out itself, and a
slip in one step reaches the answer. Two other readings are set beside its number, and the
reply changes only when two of the three agree:

1. The model reader's read of the question (``model_reader.service``, started beside the
   reply for such a turn, ``turn_prep.model_read_shadow``), solved by the subject's own
   solver (``model_reader.solve``). The read is never shown and its number never goes into
   the prose: alone it is wrong more often than the reply (docs/MODEL_READER.md).
2. When the solved read agrees with the reply, or either has no plain final value, the
   reply stays as it is.
3. When they differ, a stronger model answers the same prompt once. Its reply is kept
   only when its final value agrees with the solved read; otherwise the first reply stays
   (it agrees with the redo, or all three differ).

It runs on the finished stream, before the finalize passes (``finalize_passes``), so a
reply it chooses goes through every one of them, the safety passes included; it asks no
model about the reply itself. Its whole wait is bounded by ``second_opinion_seconds``;
past that, or on any failure, the reply stays.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Literal

from app.core.config import Settings
from app.core.sympy_executor import run_sympy
from app.models.routing_lanes import ROUTING
from app.modules.chat.stream_accum import StreamAccum
from app.modules.chat.stream_status import StreamStatusFn, announced_if_slow
from app.modules.chat.turn_deps import ChatTurnDeps
from app.modules.chat.turn_prep import StreamContext
from app.modules.chat.turn_trace import current_turn_trace
from app.modules.chat.worked_render import WorkedLayout
from app.modules.chat.worked_stream import ReplyFilter
from app.modules.model_reader.schemas import ModelRead
from app.modules.model_reader.service import read_with_model
from app.modules.model_reader.solve import read_card
from app.services.answer_check import stated_verdict

logger = logging.getLogger(__name__)

SUBJECTS = frozenset({"math", "physics", "chemistry"})
Outcome = Literal["agree", "no_read", "no_value", "kept", "redone", "timeout", "failed"]


def wants_second_opinion(settings: Settings, ctx: StreamContext, text: str) -> bool:
    """A model-written answer to a subject question no solver verified."""
    return bool(
        settings.second_opinion_enabled
        and ctx.solver_unverified
        and ctx.unverified_subject in SUBJECTS
        and ctx.verified_subject is None
        and ctx.instant_reply is None
        and ctx.user_message_content
        and text.strip()
    )


async def second_opinion_reply(
    deps: ChatTurnDeps,
    settings: Settings,
    ctx: StreamContext,
    text: str,
    usage: dict[str, int],
    *,
    on_status: StreamStatusFn | None = None,
) -> str:
    """The reply, or the stronger model's when it and the solved read agree; never raises."""
    if not wants_second_opinion(settings, ctx, text):
        return text
    record: dict[str, Any] = {"redo": False, "chosen": "original"}
    chosen, outcome = text, "failed"
    try:
        async with asyncio.timeout(settings.second_opinion_seconds):
            chosen, outcome = await _decide(deps, settings, ctx, text, usage, on_status, record)
    except TimeoutError:
        chosen, outcome = text, "timeout"
    except Exception as exc:
        logger.info("second opinion failed (%s); reply kept", type(exc).__name__)
        chosen = text
    record["verdict"] = outcome
    trace = current_turn_trace()
    if trace is not None:
        trace.second_opinion = record
    if outcome != "agree":
        logger.info("second opinion: %s", record)
    return chosen


async def _decide(
    deps: ChatTurnDeps,
    settings: Settings,
    ctx: StreamContext,
    text: str,
    usage: dict[str, int],
    on_status: StreamStatusFn | None,
    record: dict[str, Any],
) -> tuple[str, Outcome]:
    read = await _model_read(settings, ctx)
    card = await _solved_card(read, settings) if read is not None else None
    if card is None:
        return text, "no_read"
    first = stated_verdict(text, card)
    if first in {"same", "rounded"}:
        return text, "agree"
    if first != "conflict":
        return text, "no_value"
    record["redo"] = True
    redo = await announced_if_slow(
        _redo(deps, settings, ctx, usage), on_status, "checking", then="finishing"
    )
    if redo and stated_verdict(redo, card) in {"same", "rounded"}:
        record["chosen"] = "redo"
        return redo, "redone"
    return text, "kept"


async def _model_read(settings: Settings, ctx: StreamContext) -> ModelRead | None:
    """The read started beside the reply, awaited; or read now when none was started."""
    trace = current_turn_trace()
    task = None if trace is None else trace.model_read_task
    if trace is not None and task is not None:
        # Shielded: the turn's trace still logs the read if the wait runs out.
        await asyncio.shield(task)
        read = trace.model_read
        return read if isinstance(read, ModelRead) else None
    return await read_with_model(ctx.user_message_content or "", settings)


async def _solved_card(read: ModelRead, settings: Settings) -> str | None:
    if read.reason != "ok" or read.intent is None:
        return None
    return await run_sympy(read_card, read, settings, timeout=settings.stem_solve_timeout_seconds)


async def _redo(
    deps: ChatTurnDeps, settings: Settings, ctx: StreamContext, usage: dict[str, int]
) -> str | None:
    """The same prompt answered by the stronger model, as the reply it streams is shown
    (``shown_reply``), or None when it answers nothing."""
    tokens: list[str] = []
    async for token in deps.llm.stream_chat_completion(
        settings=settings,
        model_alias=ROUTING.hard,
        messages=[dict(message) for message in ctx.prompt_messages],
        max_tokens=ctx.max_output_tokens,
        usage=usage,
    ):
        tokens.append(token)
    return shown_reply(tokens, ctx.worked).strip() or None


def shown_reply(tokens: list[str], layout: WorkedLayout | None) -> str:
    """The reply the phone is sent for these tokens: the scaffold out and a ```worked block
    laid out (``worked_stream.ReplyFilter``), as the first reply was before it got here."""
    accum = StreamAccum()
    scaffold = ReplyFilter(accum, layout)
    for token in tokens:
        accum.parts.append(token)
        if visible := scaffold.feed(token):
            accum.shown.append(visible)
    if tail := scaffold.flush():
        accum.shown.append(tail)
    return accum.reply_text()
