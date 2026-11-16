"""A physics answer the server works out from the model's own setup, checked at finalize.

On a physics turn the solvers did not answer (the reply is the model's alone), a model
writes the question down as maths beside the reply, in any wording and any language, and
the server solves it (``physics.formal_read``). The server's answer is used only when the
setup's own answer agrees with it. Finalize waits at most ``formal_wait_seconds`` for it:

- the reply states the same value, or a rounding of it: the reply stands;
- the reply states another: its Answer becomes the server's card (measured 2026-11-16: in
  every one of 36 such disagreements the server was right and the reply wrong);
- the reply's final value cannot be read (an Answer heading in another language): the
  server's card is added under the reply, both shown.

Either way a line in the reply's language says where the value comes from, and the card is
marked ``verified: false``: the server did the arithmetic, the reading is the model's.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

from app.core.config import Settings
from app.modules.chat.finalize_subjects import fallback_text
from app.modules.chat.reply_language import line_language
from app.modules.chat.turn_decision import TurnDecision
from app.services.answer_check import stated_verdict
from app.services.answer_fence import UNCHECKED_ANSWER_MARKER, land_answer_card
from app.services.subjects.registry import subject_adapter

if TYPE_CHECKING:
    from app.modules.chat.finalize_passes import FinalizeState
    from app.modules.chat.turn_prep.context import StreamContext

logger = logging.getLogger(__name__)

# Where the value comes from, in the language of the reply ({value} is card maths).
_LINES = {
    "en": "Worked out from the values in the question: {value}.",
    "es": "Calculado con los valores de la pregunta: {value}.",
    "fr": "Calculé à partir des valeurs de la question : {value}.",
    "de": "Aus den Werten der Frage berechnet: {value}.",
    "it": "Calcolato dai valori della domanda: {value}.",
    "pt": "Calculado a partir dos valores da pergunta: {value}.",
    "ru": "Рассчитано по данным задачи: {value}.",
    "tr": "Sorudaki değerlerden hesaplandı: {value}.",
    "am": "ከጥያቄው እሴቶች የተሰላ ውጤት፦ {value}።",
}
# The reply already says the server's value: nothing to add.
_AGREES = frozenset({"same", "rounded"})


def start_formal(settings: Settings, ctx: StreamContext) -> asyncio.Task[Any] | None:
    """The server's answer's task, on a turn whose reply is the model's alone: never when a
    solver answered (``verified_subject``) or the server wrote the reply itself."""
    line = ctx.user_message_content or ""
    if (
        not (settings.formal_reader_enabled and settings.physics_enabled)
        or ctx.live_read is None
        or ctx.verified_subject is not None
        or ctx.instant_reply is not None
        or not line.strip()
    ):
        return None
    return asyncio.create_task(_work_out(settings, ctx.live_read, line))


def _physics(read: asyncio.Task[TurnDecision | None]) -> bool:
    if not read.done() or read.cancelled() or read.exception() is not None:
        return False
    decision = read.result()
    return decision is not None and decision.subject == "physics"


async def _work_out(settings: Settings, read: asyncio.Task[TurnDecision | None], line: str) -> Any:
    # Waited on, never awaited: the reply may cancel the read when it stops waiting for it.
    await asyncio.wait([read])
    formal = subject_adapter("physics").formal
    if not _physics(read) or formal is None:
        return None
    return await formal.answer(line, settings)


def stop_formal(ctx: StreamContext) -> None:
    if ctx.formal is not None and not ctx.formal.done():
        ctx.formal.cancel()


async def attach_formal(state: FinalizeState) -> str:
    """The reply's final value held to the server's, as the module docstring says."""
    ctx = state.ctx
    task = ctx.formal
    if task is None:
        return state.text
    if state.was_cancelled or ctx.live_read is None or not _physics(ctx.live_read):
        stop_formal(ctx)
        return state.text
    started = time.monotonic()
    # Waited on, never awaited: a stopped or failed task is no answer.
    await asyncio.wait([task], timeout=state.settings.formal_wait_seconds)
    waited = time.monotonic() - started
    if not task.done():
        stop_formal(ctx)
        logger.info("formal answer: not in after %.2f s, the reply stands", waited)
        return state.text
    if task.cancelled() or task.exception() is not None or task.result() is None:
        return state.text
    answer = task.result()
    body = answer.card_value
    verdict = stated_verdict(state.text, body)
    if verdict not in _AGREES and any(
        stated_verdict(state.text, same) in _AGREES for same in answer.same_answers[1:]
    ):
        # The same answer another way: 90% for 0.9, 7500 N for a braking force of -7500 N.
        verdict = "same"
    logger.info("formal answer: reply %s, waited %.2f s", verdict, waited)
    if verdict in _AGREES:
        return state.text
    locale = ctx.user.locale if ctx.user is not None else None
    language = line_language(ctx.user_message_content or "", locale)
    said = _LINES.get(language, _LINES["en"]).format(value=f"${body}$")
    if verdict == "conflict":
        text = land_answer_card(state.text, body, above=said, verified=False)
    else:
        # A final value the readers cannot find (an Answer heading in another language):
        # both shown, the server's under the reply, with no heading of the server's words.
        card = f"```answer\n{UNCHECKED_ANSWER_MARKER}\n{body}\n```"
        text = f"{state.text.rstrip()}\n\n{said}\n\n{card}\n"
    # Committed, so a later pass that falls back keeps the server's value.
    state.committed = fallback_text(text, server_text=state.server_text)
    return text
