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
from app.modules.chat.whole_question import ASK_QUESTION_WORDS, ASK_VERBS, ASKED_SENTENCE
from app.modules.chat.worked_language import WORKED_WORDS
from app.services.answer_check import Verdict, stated_verdict
from app.services.answer_fence import (
    ANSWER_FENCE_LANGS,
    UNCHECKED_ANSWER_MARKER,
    answer_fence_value,
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


# A part's own Answer heading in any language a worked layout is written in: "**Answer (a)**",
# "**Respuesta (b)**". A ```worked reply in parts has these, and no card yet, when this runs.
_PART_ANSWER_HEADING = re.compile(
    r"^[ \t]*(?:#{1,4}[ \t]+)?\*\*(?:"
    + "|".join(sorted({re.escape(words["answer"]) for words in WORKED_WORDS.values()}))
    + r") \([a-h]\):?\*\*",
    re.MULTILINE,
)


def _in_parts(reply: str, question: str) -> bool:
    """The question asks in labelled parts, or the reply answers in several cards or under
    several part headings: a ```worked reply's cards land after this pass, so its parts
    are its headings (Gemini on #2489)."""
    cards = sum(
        1 for fence in iter_fences(reply) if fence.closed and fence.lang in ANSWER_FENCE_LANGS
    )
    headings = len(_PART_ANSWER_HEADING.findall(reply))
    return cards >= 2 or headings >= 2 or _asks_in_parts(question)


# The text before the first label ends on an ask, the labels its objects: "… find (a)",
# "Can you work out (a)", "Could you find both (a)", "Calculate the following: (a)", "What
# are (a)". "… holding blocks (A)" ends on a noun the labels name, and so do "Which mass
# (A) …" and "How far do blocks (A) …": a question word asks for the labels only alone or
# with is, are, was or were (Gemini on #2489).
_ASKS_FOR_LABELS = re.compile(
    rf"\b(?:(?:{ASK_VERBS})(?:\s+(?:both|the\s+following))?"
    rf"|(?:{ASK_QUESTION_WORDS})(?:\s+(?:is|are|was|were))?)"
    r"\s*:?$",
    re.IGNORECASE,
)


def _asks_in_parts(question: str) -> bool:
    """Each labelled part asks something: each is a question or an instruction of its own
    ("(a) How long …? (b) How far …?", "(a) Find the flight time; (b) Find the range"), or
    the text before the labels ends on the ask they complete (``_ASKS_FOR_LABELS``),
    whatever words come before it. A label inside the statement or its question ("blocks
    (A) and (B)", "Find the tension in the ropes holding blocks (A) of 2 kg and (B) of
    3 kg") names a thing and asks nothing (review of phys30, 2026-11-16; Codex, Gemini and
    Claude on #2489)."""
    lead, parts = labelled_part_texts(question)
    if len(parts) < 2:
        return False
    if all("?" in part or ASKED_SENTENCE.match(part.strip()) for part in parts):
        return True
    return _ASKS_FOR_LABELS.search(lead.rstrip()) is not None


# A value's other form in brackets after it: "0.840 (84.0 percent)".
_BRACKETED = re.compile(r"\\?\(|\\?\)")
# TeX spacing at a piece's ends ("0.840\ "), which closes no maths on its own.
_EDGE_SPACE = re.compile(r"^(?:\s|\\[ ,;])+|(?:\s|\\(?:[ ,;]|$))+$")


def _card_states(reply: str, forms: list[str]) -> Verdict:
    """What the reply's own last answer card states, read as the Answer it is, against the
    server's value in its ``forms``: "same" when every value it states agrees, "conflict"
    when any disagrees, "absent" when it states none the reader reads. "0.840 (84.0
    percent)" for 84 % is the same value twice and got the server's card under it (owner's
    phone, 2026-11-17); "0.94 (84.0%)" is no 0.84, and "x(3 m) = 15 m" no 3 m (review of
    #2491)."""
    cards = [
        answer_fence_value(reply[fence.body_start : fence.body_end])
        for fence in iter_fences(reply)
        if fence.closed and fence.lang in ANSWER_FENCE_LANGS
    ]
    if not cards:
        return "absent"
    split = [_EDGE_SPACE.sub("", piece) for piece in _BRACKETED.split(cards[-1])]
    verdicts = [_piece_verdict(piece, forms) for piece in split if piece]
    if "conflict" in verdicts:
        return "conflict"
    return "same" if "same" in verdicts else "absent"


def _piece_verdict(piece: str, forms: list[str]) -> Verdict:
    """One stated value against the server's: the same in any of its forms, or a conflict
    with its own form (0.94 against 84 %), else nothing read."""
    said = [stated_verdict(f"**Answer**\n\n${piece}$\n", form) for form in forms]
    if any(verdict in _AGREES for verdict in said):
        return "same"
    return "conflict" if said and said[0] == "conflict" else "absent"


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
    if verdict == "absent":
        # The reply's own card, when its prose states nothing the reader reads: the same
        # value keeps the reply as it is, a different one is replaced (land_answer_card).
        verdict = _card_states(state.text, answer.same_answers)
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
