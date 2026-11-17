"""A physics answer the server works out from the model's own setup, checked at finalize.

On a physics turn the solvers did not answer (the reply is the model's alone), a model
writes the question down as maths beside the reply, in any wording and any language, and
the server solves it (``physics.formal_read``). The server's answer is used only when the
setup's own answer agrees with it. Finalize waits at most ``formal_wait_seconds`` for it:

- the reply states the same value, or a rounding of it: the reply stands;
- the reply states another: its Answer becomes the server's card (measured 2026-11-16: in
  every one of 36 such disagreements the server was right and the reply wrong);
- the reply's final value cannot be read (an Answer heading in another language): the
  server's card is added under the reply, both shown;
- the question asks in parts, or the reply answers in several cards: the value answers one
  part, and the setup does not say which, so it is left out (a trailing card repeating
  part (a)'s value read as the final answer, phys30 2026-11-16).

Either way a line in the reply's language says where the value comes from, and the card is
marked ``verified: false``: the server did the arithmetic, the reading is the model's.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import TYPE_CHECKING, Any

from app.core.config import Settings
from app.modules.chat.finalize_subjects import fallback_text
from app.modules.chat.reply_language import line_language
from app.modules.chat.turn_decision import TurnDecision
from app.modules.chat.whole_question import ASKED_SENTENCE
from app.services.answer_check import stated_verdict
from app.services.answer_fence import (
    ANSWER_FENCE_LANGS,
    UNCHECKED_ANSWER_MARKER,
    land_answer_card,
)
from app.services.md_fence_scan import iter_fences
from app.services.question_parts import labelled_part_texts
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


def _in_parts(reply: str, question: str) -> bool:
    """The question asks in labelled parts, or the reply answers in several cards."""
    cards = sum(
        1 for fence in iter_fences(reply) if fence.closed and fence.lang in ANSWER_FENCE_LANGS
    )
    return cards >= 2 or _asks_in_parts(question)


# "find", "work out", "what are": an ask with no object of its own.
_BARE_ASK_WORDS = 2


def _asks_in_parts(question: str) -> bool:
    """Each labelled part asks something: each is a question or an instruction of its own
    ("(a) How long …? (b) How far …?", "(a) Find the flight time; (b) Find the range"), or
    the clause before them asks for the list and ends where it starts ("Find (a) the time,
    (b) the range", "… at 35°, find (a) … and (b) …", "Calculate the following: (a) …").
    A label inside the statement or its question ("blocks (A) and (B)", "Find the tension
    in the ropes holding blocks (A) of 2 kg and (B) of 3 kg") names a thing and asks
    nothing (review of phys30, 2026-11-16; Codex, Gemini and Claude on #2489)."""
    lead, parts = labelled_part_texts(question)
    if len(parts) < 2:
        return False
    if all("?" in part or ASKED_SENTENCE.match(part.strip()) for part in parts):
        return True
    # A sentence ends at its stop or at a line break ("… above the ground\nFind (a) …").
    last = re.split(r"(?<=[.!?])\s+|\s*\n\s*", lead.strip())[-1] if lead.strip() else ""
    clause = re.split(r"[,;:]\s*", last.rstrip(" :"))[-1].strip()
    if not clause or ASKED_SENTENCE.fullmatch(clause) is None:
        return False
    # The ask ends at the labels: a colon after it, or the asking word alone ("find",
    # "work out", "what are"), never an object the labels then name.
    return last.rstrip().endswith(":") or len(clause.split()) <= _BARE_ASK_WORDS


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
    if _in_parts(state.text, ctx.user_message_content or ""):
        # One value answers one part: a card under the last part repeating part (a)'s
        # value read as the whole question's answer (phys30, 2026-11-16). Which part it
        # answers the setup does not say, so it is left out.
        logger.info("formal answer: a reply in parts, left out")
        return state.text
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
