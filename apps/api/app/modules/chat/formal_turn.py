"""The one authority for a physics answer the solvers did not check: the server, held to
the reply's own reading.

On a physics turn the solvers did not answer (the reply is the model's alone), a model
writes the question down as maths beside the reply, in any wording and any language: its
givens, what each part asks, the equations, and the relations the values must keep. The
server solves it (``physics.formal_read``); a part whose setup answer is not the server's
is left out. Finalize waits at most ``formal_wait_seconds`` for it, once the reply's own
answers are its cards, and then:

- the question's values break a relation they must keep (a lever said to balance whose
  moments differ, a mechanical advantage above the velocity ratio): the reply opens with
  one plain line per broken relation, its two sides in numbers, and no card changes, as no
  value answers a question that contradicts itself (live, 2026-11-18);
- otherwise each card is held to the server's value for its part, card to card, in any
  unit of its kind (``formal_cards``). A card within its rounding of the server's value,
  for any standard value of a constant it uses (g as 9.8, 9.81 or 10), stands: the book's
  g is an assumption, not an error (245 Pa stamped over a working of 250 Pa at g = 10,
  G8 round, 2026-11-18). A card worked from numbers the reply never wrote read the question
  another way and stands too. Any other card gets the server's value, with a line in the
  reply's language saying where it comes from: an arithmetic or law slip (in 36 of 36
  disagreements measured 2026-11-16 the server was right). A card is never added: a
  second "Answer" card under an identical first one (50 Ω twice, G8 round) is gone.

A replaced card is marked ``verified: false``: the server did the arithmetic, the reading
is the model's.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from app.core.config import Settings
from app.modules.chat.finalize_subjects import fallback_text
from app.modules.chat.formal_cards import held_to_server
from app.modules.chat.reply_language import line_language
from app.modules.chat.turn_decision import TurnDecision
from app.services.formal.answer import FormalAnswer, StatedConflict
from app.services.subjects.registry import subject_adapter

if TYPE_CHECKING:
    from app.modules.chat.finalize_passes import FinalizeState
    from app.modules.chat.turn_prep.context import StreamContext

logger = logging.getLogger(__name__)

# Above a card the server's value replaced, in the language of the reply.
_LINES = {
    "en": "Worked out again from the values in the question:",
    "es": "Calculado de nuevo con los valores de la pregunta:",
    "fr": "Recalculé à partir des valeurs de la question :",
    "de": "Aus den Werten der Frage neu berechnet:",
    "it": "Ricalcolato dai valori della domanda:",
    "pt": "Recalculado a partir dos valores da pergunta:",
    "ru": "Пересчитано по данным задачи:",
    "tr": "Sorudaki değerlerden yeniden hesaplandı:",
    "am": "ከጥያቄው እሴቶች እንደገና የተሰላ፦",
}
# A relation the question's values break ({meaning} is the setup's words, {sides} maths).
_CONFLICTS = {
    "en": "These values can't all be right: {meaning}, but here {sides}.",
    "es": "Estos valores no pueden ser todos correctos: {meaning}, pero aquí {sides}.",
    "fr": "Ces valeurs ne peuvent pas être toutes justes : {meaning}, mais ici {sides}.",
    "de": "Diese Werte können nicht alle stimmen: {meaning}, aber hier {sides}.",
    "it": "Questi valori non possono essere tutti giusti: {meaning}, ma qui {sides}.",
    "pt": "Esses valores não podem estar todos certos: {meaning}, mas aqui {sides}.",
    "ru": "Эти значения не могут быть верны одновременно: {meaning}, но здесь {sides}.",
    "tr": "Bu değerlerin hepsi doğru olamaz: {meaning}, ama burada {sides}.",
    "am": "እነዚህ እሴቶች ሁሉም ትክክል ሊሆኑ አይችሉም፦ {meaning}፣ ግን እዚህ {sides}።",
}


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


async def _waited(state: FinalizeState) -> FormalAnswer | None:
    """The server's answer, if it is in within ``formal_wait_seconds``."""
    task = state.ctx.formal
    if task is None:
        return None
    started = time.monotonic()
    # Waited on, never awaited: a stopped or failed task is no answer.
    await asyncio.wait([task], timeout=state.settings.formal_wait_seconds)
    if not task.done():
        stop_formal(state.ctx)
        logger.info(
            "formal answer: not in after %.2f s, the reply stands", time.monotonic() - started
        )
        return None
    if task.cancelled() or task.exception() is not None:
        return None
    answer: FormalAnswer | None = task.result()
    return answer


def stated_conflicts(text: str, conflicts: Sequence[StatedConflict], language: str) -> str:
    """The reply opened by one line for each relation the question's values break."""
    template = _CONFLICTS.get(language, _CONFLICTS["en"])
    lines = [
        template.format(
            meaning=conflict.meaning, sides=f"${conflict.left} {conflict.broken} {conflict.right}$"
        )
        for conflict in conflicts
        if conflict.meaning
    ]
    return "\n\n".join([*lines, text]) if lines else text


async def attach_formal(state: FinalizeState) -> str:
    """The reply held to the server's answer, as the module docstring says."""
    ctx = state.ctx
    if ctx.formal is None:
        return state.text
    if state.was_cancelled or ctx.live_read is None or not _physics(ctx.live_read):
        stop_formal(ctx)
        return state.text
    answer = await _waited(state)
    if answer is None:
        return state.text
    locale = ctx.user.locale if ctx.user is not None else None
    language = line_language(ctx.user_message_content or "", locale)
    if answer.conflicts:
        # The question's values cannot all hold: no value is the answer, so no card changes.
        logger.info("formal answer: %d stated values conflict", len(answer.conflicts))
        text = stated_conflicts(state.text, answer.conflicts, language)
    else:
        text = held_to_server(state.text, answer.values, _LINES.get(language, _LINES["en"]))
    if text != state.text:
        # Committed, so a later pass that falls back keeps the server's value.
        state.committed = fallback_text(text, server_text=state.server_text)
    return text
