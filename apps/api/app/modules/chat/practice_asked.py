"""The practice cards a chat already showed: listed beside the message, held at finalize.

In the owner's study chat (2026-11-14) a mock set promised "no repeats" and asked
magnesium-25's neutrons again, seventeen turns after the first time, and a mixed set asked
two of the first lesson's questions again. The history window (twenty messages) had long
dropped them, so the model could not see what it had asked; the chat's own rows still hold
every card. A turn that may set practice (a lesson, a teach-me, a quiz, a chat whose window
holds cards) reads them and lists each card beside the message (``NEARBY_CONTRACTS``) on one
line: its question, code and options, since a Python quiz asks "What will this Python code
print?" of every card.

The finalize pass holds the rest: a card the reply shows again whole, its question, code and
options ("Here it is again, with the answer hidden behind your own reasoning", after the text
had worked it out), goes when the reply has another card, or gives way to a fresh card on the
same idea from a cheap model (``lesson_calls.fresh_practice``). A reworded repeat is the
listing's to prevent; a call that fails leaves the card as written.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.modules.chat import prompt_context
from app.modules.chat.lesson_calls import QuizCard, fresh_practice
from app.modules.chat.prompt_constants.practice import PRACTICE_ASKED_OPENING
from app.modules.chat.quiz_cards import CUT_MARK, QUIZ_LANG, PracticeCard, practice_cards
from app.modules.turn_reading.lesson_flow import active_lesson_step, outline_awaits_pick
from app.modules.turn_reading.practice import is_practice_request
from app.modules.turn_reading.turn import teaching_of
from app.modules.turn_reading.walkthrough import is_walkthrough_request
from app.services.md_fence_scan import Fence, block_end, map_fence_blocks

if TYPE_CHECKING:
    from app.modules.chat.finalize_passes import FinalizeState

logger = logging.getLogger(__name__)

# The chat's newest replies that hold a card, read among its newest replies, and the cards
# listed from them.
REPLIES_READ = 40
REPLIES_SCANNED = 200
_CARDS_LISTED = 24
_NOT_WORDS = re.compile(r"[\W_]+")


def may_set_practice(query: str | None, exchange: Sequence[Any]) -> bool:
    """The reply may write practice: a lesson goes on or starts, a quiz is asked for, or the
    chat's window already holds cards (another round, a mock set)."""
    text = query or ""
    if active_lesson_step(list(exchange)) or outline_awaits_pick(list(exchange)):
        return True
    if text and (teaching_of(text) or is_walkthrough_request(text) or is_practice_request(text)):
        return True
    return any(
        getattr(message, "role", None) == "assistant"
        and f"```{QUIZ_LANG}" in (getattr(message, "content", None) or "")
        for message in exchange
    )


async def _chat_replies(chat_id: UUID, omit: set[UUID] | None = None) -> list[str]:
    """The chat's replies that hold a card, oldest first. A reply being regenerated is still
    stored while it is redone: its cards are the ones asked again, never ones already shown
    (review of #2456)."""
    return await prompt_context.practice_replies(
        chat_id, f"```{QUIZ_LANG}", limit=REPLIES_READ, scan=REPLIES_SCANNED, exclude=omit or ()
    )


def _through_last_reply(recent: Sequence[Any], omit: set[UUID] | None) -> list[Any]:
    """The chat's loaded rows through its last reply, a regenerated one left out: what came
    before this message."""
    rows = [row for row in recent if not omit or getattr(row, "id", None) not in omit]
    while rows and getattr(rows[-1], "role", None) != "assistant":
        rows.pop()
    return rows


async def practice_questions(
    chat_id: UUID, query: str | None, recent: Sequence[Any], *, omit: set[UUID] | None = None
) -> tuple[str, ...]:
    """The chat's cards, oldest first, each on one line (its question, code and options), when
    the reply may set practice; none when the read fails (the turn goes on without the
    listing). ``recent``: the chat's loaded rows, oldest first, so the read runs beside the
    history window's."""
    if not may_set_practice(query, _through_last_reply(recent, omit)):
        return ()
    try:
        replies = await _chat_replies(chat_id, omit)
    except Exception as exc:  # A listing is a hint: the turn never waits on its failure.
        logger.info("practice questions not read (%s)", type(exc).__name__)
        return ()
    try:
        lines = dict.fromkeys(card.line for reply in replies for card in practice_cards(reply))
    except Exception as exc:  # A reply it cannot read lists nothing, never a failed turn.
        logger.info("practice cards not read (%s)", type(exc).__name__)
        return ()
    return tuple(lines)[-_CARDS_LISTED:]


def asked_in_prompt(prompt_messages: Sequence[dict[str, Any]]) -> tuple[str, ...]:
    """The cards the turn's prompt listed, read back from the note beside the message."""
    for message in prompt_messages:
        content = message.get("content")
        if message.get("role") != "system" or not isinstance(content, str):
            continue
        at = content.find(PRACTICE_ASKED_OPENING)
        if at < 0:
            continue
        lines = content[at:].split("\n")[1:]
        return tuple(line[2:] for line in lines if line.startswith("- "))
    return ()


def _key(question: str) -> str:
    return _NOT_WORDS.sub(" ", question.casefold()).strip()


def _card_body(label: str, quiz: QuizCard) -> str:
    return json.dumps({"label": label, **quiz.model_dump()}, ensure_ascii=False)


async def hold_new_practice(state: FinalizeState) -> str:
    """Pass entry: no card is one the chat's earlier cards showed, whole: its question, code
    and options. A Python quiz asks "What will this Python code print?" of every card, and
    keyed on the question alone, three new cards of five were cut (review, 2026-11-14)."""
    text = state.text
    if state.server_text or state.was_cancelled or f"```{QUIZ_LANG}" not in text:
        return text
    listed = asked_in_prompt(state.ctx.prompt_messages)
    # A card is a repeat only when it is a listed card whole: a line cut for length matches
    # none (two Python cards sharing their first 200 characters of code are two cards, and
    # the new one was deleted, review of #2456).
    asked = {_key(line) for line in listed if not line.endswith(CUT_MARK)}
    cards = practice_cards(text)
    repeats = [card for card in cards if _key(card.text) in asked]
    if not repeats:
        return text
    if len(repeats) < len(cards):
        # Another card is still new: the repeats go.
        return _without(text, {card.text for card in repeats})
    # Every card is one asked before (a mock set of five re-asked): each gets a fresh card of
    # its own, asked together; one that gets none, or a repeat, stays as it was.
    fresh = await asyncio.gather(*(fresh_practice(state, card, listed) for card in repeats))
    bodies: dict[str, str] = {}
    for card, quiz in zip(repeats, fresh, strict=True):
        key = None if quiz is None else _key(_fresh_text(quiz))
        if quiz is None or key in asked or card.text in bodies:
            continue
        asked.add(key or "")
        bodies[card.text] = _card_body(card.label, quiz)
    return _replaced(text, bodies) if bodies else text


def _fresh_text(quiz: QuizCard) -> str:
    return PracticeCard("", quiz.question, tuple(quiz.options), quiz.answer, quiz.code).text


def _text_of(text: str, fence: Fence) -> str | None:
    found = practice_cards(text[fence.start : block_end(text, fence)])
    return found[0].text if found else None


def _without(text: str, cards: set[str]) -> str:
    def replace(fence: Fence, _body: str) -> str:
        original = text[fence.start : block_end(text, fence)]
        return "" if _text_of(text, fence) in cards else original

    return re.sub(r"\n{3,}", "\n\n", map_fence_blocks(text, replace, lang=QUIZ_LANG)).strip()


def _replaced(text: str, bodies: dict[str, str]) -> str:
    """Each card in ``bodies`` replaced by its new body, once: the same card twice keeps its
    second copy as it was rather than two of one fresh card."""
    pending = dict(bodies)

    def replace(fence: Fence, _body: str) -> str:
        original = text[fence.start : block_end(text, fence)]
        body = pending.pop(_text_of(text, fence) or "", None)
        if body is None:
            return original
        opener = text[fence.start : fence.body_start]
        closer = text[fence.body_end : block_end(text, fence)]
        return f"{opener}{fence.opener.prefix}{body}\n{closer}"

    return map_fence_blocks(text, replace, lang=QUIZ_LANG)
