"""Finalizing a reply: an ordered list of passes over the finished text.

``FINALIZE_PASSES`` is the order. Each pass takes the reply so far and returns
it changed. Its ``on_error`` says what an exception in it does:

- ``FALL_BACK`` (most passes): the passes stop and the reply is the last
  committed text, the text as of the last side effect (a linked photo, source
  chips), or the raw reply made safe when nothing was committed (ES-03). Either
  way the safety passes that text has not been through then run on it, each
  failing closed (``FinalizePass.closed``).
- ``OnError(log_as=step)``: the failure is logged as ``step`` (a timeout as a
  warning, any other failure captured) and the next pass gets the failed pass's
  input.
- ``OnError(log_as=step, rewrite=fn)``: logged the same way; the next pass gets
  what ``fn`` makes of that input.

Then the reminder pass (``finalize_reminders``) runs on whatever text the passes
leave: it is the one step with an effect outside the reply.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from redis.asyncio import Redis

from app.core.config import Settings
from app.modules.chat.claim_check import cut_unsupported_claims
from app.modules.chat.emoji_placement import place_reply_emoji
from app.modules.chat.finalize_money import attach_money_card
from app.modules.chat.finalize_parts import (
    add_settings_card,
    attach_reply_picture,
    divide_request_sections,
)
from app.modules.chat.finalize_reminders import apply_reminder_pass, drop_cut_reminder_fence
from app.modules.chat.finalize_subjects import (
    append_unverified_notes,
    check_chemistry_fences,
    check_math_fences,
    check_physics_fences,
    check_working,
    draw_formula_charts,
    drop_check_lines,
    enrich_chemistry_fences,
    fallback_text,
    mark_server_cards,
    prepare_model_reply,
    recover_chemistry_fences,
    recover_math_fences,
    recover_physics_fences,
    strip_solve_markers,
    strip_text_plots,
)
from app.modules.chat.finalize_text import (
    add_search_sources,
    attach_answer_photo,
    close_open_fences,
    fix_clock,
    normalize_prose,
    present_markdown,
    record_instant_usage,
    restore_case,
    sanitize_fences,
    settle_clarify,
    strip_recipient_placeholders,
)
from app.modules.chat.generic_closer import strip_generic_closer
from app.modules.chat.json_output import check_requested_json
from app.modules.chat.lesson_again import keep_to_lesson_again_pass
from app.modules.chat.meta_notes import unwrap_meta_notes
from app.modules.chat.prompt_leaks import drop_prompt_leaks_pass, drop_prompt_lines
from app.modules.chat.reply_labels import one_answer_label
from app.modules.chat.reply_meta import local_today, without_turn_meta
from app.modules.chat.search_links import unlink_unretrieved_links
from app.modules.chat.stream_status import StreamStatusFn
from app.modules.chat.turn_deps import ChatTurnDeps
from app.modules.chat.turn_outcome import TurnOutcome
from app.modules.chat.turn_prep import StreamContext
from app.modules.chat.untrusted_media import drop_media_lines, neutralize_untrusted_media
from app.modules.chat.worked_lead import drop_guessed_lead

logger = logging.getLogger(__name__)


@dataclass
class FinalizeState:
    """One reply on its way through the passes."""

    deps: ChatTurnDeps
    settings: Settings
    ctx: StreamContext
    raw: str
    text: str
    usage: dict[str, int]
    outcome: TurnOutcome | None
    was_cancelled: bool
    assistant_parts: list[str]
    should_cancel: Callable[[], bool] | None
    # The text as of the last side effect (a linked photo, source chips). A failed
    # pass falls back to it, never to the raw reply (ES-03).
    committed: str | None = None
    # The user stopped the reply: it saves as they saw it (STOPPED_REPLY_PASSES).
    user_stopped: bool = False
    # Tells the client what a slow pass is doing while the reply waits on it.
    on_status: StreamStatusFn | None = None
    # Safety passes that raised: whatever commits after them, a fallback runs them again.
    failed_safety: set[str] = field(default_factory=set)

    @property
    def server_text(self) -> bool:
        """An instant reply is wholly server text: every card in it is the server's."""
        return self.ctx.instant_reply is not None


@dataclass(frozen=True)
class OnError:
    """What an exception in one pass does to the reply (see the module docstring)."""

    # The step a failure is logged as; None falls back to the last committed text.
    log_as: str | None = None
    # Makes the failed pass's input into the next pass's; None hands it on as it was.
    rewrite: Callable[[FinalizeState], str] | None = None


FALL_BACK = OnError()


@dataclass(frozen=True)
class FinalizePass:
    """One pass: ``run`` returns the reply after it; ``name`` labels its timing."""

    name: str
    run: Callable[[FinalizeState], str | Awaitable[str]]
    on_error: OnError
    # Set on a safety pass, one that removes what no saved reply may keep (a forged
    # check, a URL that loads by itself, the prompt's own words). A fallback text runs
    # it too, and when it fails there this strip stands in, never the text it cleans.
    closed: Callable[[str], str] | None = None


# A failed subject pass recovers its subject's fences (no model answer card
# survives it) and logs under the name the one subject step had.
_SUBJECT_FENCES_STEP = "validate_math_fences"

FINALIZE_PASSES: tuple[FinalizePass, ...] = (
    # Before the fence repair below can close it for the reminder pass.
    FinalizePass("drop_cut_reminder_fence", lambda s: drop_cut_reminder_fence(s.text), FALL_BACK),
    FinalizePass("prepare_model_reply", prepare_model_reply, FALL_BACK, closed=drop_check_lines),
    # Before a subject lands its card under the reply's Answer heading.
    FinalizePass("answer_labels", lambda s: one_answer_label(s.text), FALL_BACK),
    FinalizePass("worked_lead", lambda s: drop_guessed_lead(s.text), FALL_BACK),
    FinalizePass("untrusted_media", neutralize_untrusted_media, FALL_BACK, closed=drop_media_lines),
    FinalizePass("search_links", unlink_unretrieved_links, OnError(log_as="search_links")),
    FinalizePass("generic_closer", strip_generic_closer, OnError(log_as="generic_closer")),
    FinalizePass("meta_notes", lambda s: unwrap_meta_notes(s.text), OnError(log_as="meta_notes")),
    FinalizePass(
        "prompt_leaks",
        drop_prompt_leaks_pass,
        OnError(log_as="prompt_leaks"),
        closed=drop_prompt_lines,
    ),
    FinalizePass(
        "turn_meta",
        lambda s: without_turn_meta(
            s.text, s.ctx.user_message_content or "", local_today(s.ctx.user_timezone)
        ),
        OnError(log_as="turn_meta"),
    ),
    FinalizePass("lesson_again", keep_to_lesson_again_pass, OnError(log_as="lesson_again")),
    FinalizePass("emoji_use", place_reply_emoji, OnError(log_as="emoji_use")),
    FinalizePass("answer_photo", attach_answer_photo, FALL_BACK),
    FinalizePass("reply_picture", attach_reply_picture, FALL_BACK),
    FinalizePass(
        "chemistry_fences",
        check_chemistry_fences,
        OnError(log_as=_SUBJECT_FENCES_STEP, rewrite=recover_chemistry_fences),
    ),
    FinalizePass(
        "physics_fences",
        check_physics_fences,
        OnError(log_as=_SUBJECT_FENCES_STEP, rewrite=recover_physics_fences),
    ),
    FinalizePass(
        "math_fences",
        check_math_fences,
        OnError(log_as=_SUBJECT_FENCES_STEP, rewrite=recover_math_fences),
    ),
    # After the maths pass: it strips a ```graph that no solver wrote.
    FinalizePass("formula_charts", draw_formula_charts, OnError(log_as="formula_charts")),
    FinalizePass("server_answer_cards", mark_server_cards, FALL_BACK),
    FinalizePass("unverified_notes", append_unverified_notes, FALL_BACK),
    FinalizePass("working_check", check_working, FALL_BACK),
    # Before the source chips: it reads the reply's prose, and a failure keeps it whole.
    FinalizePass("claim_check", cut_unsupported_claims, OnError(log_as="claim_check")),
    FinalizePass("text_plots", strip_text_plots, FALL_BACK),
    FinalizePass("solve_markers", strip_solve_markers, FALL_BACK),
    FinalizePass(
        "chemistry_enrich",
        enrich_chemistry_fences,
        OnError(log_as="enrich_chemistry_fences"),
    ),
    FinalizePass("settings_card", add_settings_card, FALL_BACK),
    FinalizePass("money_card", attach_money_card, FALL_BACK),
    FinalizePass("request_sections", divide_request_sections, FALL_BACK),
    FinalizePass("search_sources", add_search_sources, FALL_BACK),
    FinalizePass("instant_usage", record_instant_usage, FALL_BACK),
    # Layout, last, so it never interferes with fence parsing.
    FinalizePass("close_fences", close_open_fences, FALL_BACK),
    # After the closer: a card the model left open is read once it is closed.
    FinalizePass("clarify_card", settle_clarify, FALL_BACK),
    FinalizePass("requested_json", check_requested_json, OnError(log_as="requested_json")),
    FinalizePass("recipient_placeholders", strip_recipient_placeholders, FALL_BACK),
    FinalizePass("prose", normalize_prose, FALL_BACK),
    FinalizePass("mermaid_and_places", sanitize_fences, FALL_BACK),
    FinalizePass("proper_case", restore_case, FALL_BACK),
    FinalizePass("presentation", present_markdown, FALL_BACK),
    FinalizePass("clock", fix_clock, FALL_BACK),
)


# After the user's Stop the reply is what they saw: only the passes that remove
# or neutralize model text (forged checks, untrusted media, scaffolding) or lay it
# out run. A pass that adds server text (a verified card, a note, source chips, a
# 3D model, a clock) would grow a stopped answer, and a new pass is left out
# until it is listed here.
STOPPED_REPLY_PASSES = frozenset(
    {
        "drop_cut_reminder_fence",
        "prepare_model_reply",
        "answer_labels",
        "untrusted_media",
        "meta_notes",
        "prompt_leaks",
        "emoji_use",
        "answer_photo",
        "server_answer_cards",
        "text_plots",
        "solve_markers",
        "instant_usage",
        "close_fences",
        "clarify_card",
        "recipient_placeholders",
        "prose",
        "mermaid_and_places",
        "proper_case",
        "request_sections",
        "presentation",
    }
)


async def _run_pass(finalize_pass: FinalizePass, state: FinalizeState) -> str:
    on_error = finalize_pass.on_error
    started = time.perf_counter()
    try:
        text = finalize_pass.run(state)
        return text if isinstance(text, str) else await text
    except Exception as exc:
        if finalize_pass.closed is not None:
            state.failed_safety.add(finalize_pass.name)
        if on_error.log_as is None:
            raise
        # A safety pass fails closed: its strip goes on, never the text it cleans.
        kept = "stripping closed" if finalize_pass.closed else "keeping raw assistant text"
        if isinstance(exc, TimeoutError):
            logger.warning("%s timed out; %s", on_error.log_as, kept)
        else:
            logger.exception("%s failed; %s", on_error.log_as, kept)
        if finalize_pass.closed is not None:
            return finalize_pass.closed(state.text)
        return on_error.rewrite(state) if on_error.rewrite is not None else state.text
    finally:
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.debug("finalize pass %s took %.1f ms", finalize_pass.name, elapsed_ms)


async def run_finalize_passes(state: FinalizeState) -> bool:
    """Every pass in order (a stopped reply's own list). False when one failed and
    the text fell back."""
    # How many passes the committed text has been through: its fallback runs the
    # safety passes from there on, and any that failed before.
    passed = 0
    try:
        for index, finalize_pass in enumerate(FINALIZE_PASSES):
            if state.user_stopped and finalize_pass.name not in STOPPED_REPLY_PASSES:
                continue
            committed = state.committed
            try:
                state.text = await _run_pass(finalize_pass, state)
            finally:
                if state.committed is not committed:
                    passed = index + 1
    except Exception:
        logger.exception("Post-stream enrichment failed; persisting the last committed text")
        if state.committed is None:
            state.committed = fallback_text(state.raw, server_text=state.server_text)
            state.ctx.answer_photo_ids = []
        unclean = tuple(
            finalize_pass
            for index, finalize_pass in enumerate(FINALIZE_PASSES)
            if index >= passed or finalize_pass.name in state.failed_safety
        )
        state.committed = await _made_safe(state, state.committed, unclean)
        state.text = state.committed
        return False
    return True


async def _made_safe(state: FinalizeState, text: str, passes: tuple[FinalizePass, ...]) -> str:
    """``text`` through each safety pass in ``passes``; one that fails there gives way
    to its closed strip, and a strip that fails too leaves nothing."""
    for finalize_pass in passes:
        if finalize_pass.closed is None:
            continue
        state.text = text
        try:
            cleaned = finalize_pass.run(state)
            text = cleaned if isinstance(cleaned, str) else await cleaned
        except Exception:
            logger.exception("%s failed on the fallback text; stripping closed", finalize_pass.name)
            try:
                text = finalize_pass.closed(text)
            except Exception:
                logger.exception("%s closed strip failed; saving no text", finalize_pass.name)
                return ""
    return text


async def enrich_final_content(
    deps: ChatTurnDeps,
    redis: Redis,
    settings: Settings,
    ctx: StreamContext,
    *,
    assistant_text: str,
    usage: dict[str, int],
    outcome: TurnOutcome | None,
    was_cancelled: bool,
    assistant_parts: list[str],
    should_cancel: Callable[[], bool] | None,
    user_stopped: bool = False,
    on_status: StreamStatusFn | None = None,
) -> str:
    """The reply as it persists: the finalize passes, then the reminder pass.

    A reply the user stopped runs only ``STOPPED_REPLY_PASSES`` and no reminder
    pass: it changes nothing outside itself, and ``done`` carries the text the
    user saw, made safe, never a longer one.
    """
    state = FinalizeState(
        deps=deps,
        settings=settings,
        ctx=ctx,
        raw=assistant_text,
        text=assistant_text,
        usage=usage,
        outcome=outcome,
        was_cancelled=was_cancelled,
        assistant_parts=assistant_parts,
        should_cancel=should_cancel,
        user_stopped=user_stopped,
        on_status=on_status,
    )
    enriched = await run_finalize_passes(state)
    # Last, on the finished text: no later pass can fail and lose its card.
    text = (
        state.text
        if user_stopped
        else await apply_reminder_pass(deps, redis, settings, ctx, state.text, outcome)
    )

    # One write: done.final_content must equal the string we persist. Skip on
    # an unchanged normal turn so done payloads stay small. After a failure the
    # client settles what it streamed unless done carries the text, so a fallback
    # that differs (a stripped forged marker, a marked instant card, a reply its
    # safety passes emptied) is always sent back.
    if outcome is not None:
        if was_cancelled and text:
            outcome.final_content = text
        elif text != assistant_text and (text or not enriched):
            outcome.final_content = text
    return text
