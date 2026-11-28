"""The history a turn's prompt carries: the recent window, the gap, and the last exchange.

Never the whole chat (CLAUDE.md, Golden Rule 3): every message after the summary's edge
while they fit the token budget (``load_anchored_history``), so the history starts where
the last turn's did; past the budget, the recent rows it keeps plus the unsummarized gap
before them, cut to the tokens the window left. Omitted rows (a regenerated reply) are
dropped by id.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.core.config import Settings
from app.models.orm import Chat
from app.modules import todos as todos_service
from app.modules.chat import shown_pictures
from app.modules.chat.clarify_card import CLARIFY_FENCE
from app.modules.chat.clarify_turn import card_as_line
from app.modules.chat.context_window import (
    estimate_tokens,
    select_recent_window,
    total_tokens,
    trim_message_for_summary,
)
from app.modules.chat.prompt_context import _load_unsummarized_gap, load_anchored_history
from app.modules.chat.shown_pictures import ShownPictures
from app.services.answer_fence import answer_fence_value
from app.services.md_fence_scan import map_closed_fences, strip_closed_fences
from app.services.prompt_safety import wrap_persisted_attachment_excerpts
from app.services.subjects.registry import subject_adapter

_PROMPT_STRIP_FENCE_LANGS = ("geometry", "graph", "sources", "places", "photo", "calculator")
# An old reply's reminder card (chat no longer offers one) reads as the line chat says now.
_OLD_REMINDER_CARD = "reminder_proposal"


@dataclass(frozen=True)
class PromptWindow:
    """The stored messages one prompt carries, oldest first."""

    # Verbatim, cut to the token budget.
    recent: list[Any]
    # After the summary and before ``recent``; each one trimmed in the prompt.
    gap: list[Any]
    # The completed exchange before this turn: ``recent`` without the current user row.
    exchange: list[Any]
    # What each picture the replies showed was, read beside the turn (``shown_pictures``).
    pictures: ShownPictures = field(default_factory=dict)
    # ``recent`` is every message after the summary's edge: the compress job's fold rule
    # can read the chat's unsummarized size from it (``history_size``).
    anchored: bool = False

    @property
    def history_size(self) -> tuple[int, int] | None:
        """Messages and estimated tokens after the summary's edge, this turn's line
        included; None when the prompt slid and they were not all read."""
        if not self.anchored:
            return None
        return len(self.recent), total_tokens(self.recent)

    @property
    def message_ids(self) -> set[UUID]:
        return {m.id for m in self.recent} | {m.id for m in self.gap}


async def load_prompt_window(
    chat_id: UUID,
    chat: Chat | None,
    recent_all: list[Any],
    settings: Settings,
    *,
    query_text: str | None,
    omit_message_ids: set[UUID] | None,
    current_user_message_id: UUID | None,
    prior_count: int | None = None,
) -> PromptWindow:
    """Every message after the summary's edge when they fit; else what the token budget
    allows of the loaded rows, then the gap before them."""
    recent_limit = settings.recent_message_window
    anchored = await load_anchored_history(
        chat_id,
        chat,
        recent_all,
        loaded_limit=recent_limit,
        budget=settings.context_token_budget,
        max_count=settings.history_max_messages,
        current_user_message_id=current_user_message_id,
        prior_count=prior_count,
        omit_message_ids=omit_message_ids,
    )
    if anchored is not None:
        return PromptWindow(
            recent=anchored,
            gap=[],
            exchange=_completed_exchange(
                anchored,
                recent_all,
                query_text=query_text,
                omit_message_ids=omit_message_ids,
                current_user_message_id=current_user_message_id,
            ),
            pictures=await shown_pictures.labels_for_turn(),
            anchored=True,
        )
    source = recent_all
    if omit_message_ids:
        source = [m for m in source if m.id not in omit_message_ids]
    keep = select_recent_window(source, settings.context_token_budget, recent_limit)
    recent = source[-keep:] if keep else []
    tail_tokens = sum(
        estimate_tokens(message.content)
        for message in recent
        if isinstance(getattr(message, "content", None), str)
    )
    gap = await _load_unsummarized_gap(
        chat_id,
        chat,
        recent_all,
        recent,
        recent_limit=recent_limit,
        token_budget=max(0, settings.context_token_budget - tail_tokens),
        current_user_message_id=current_user_message_id,
        prior_count=prior_count,
    )
    if omit_message_ids:
        gap = [m for m in gap if m.id not in omit_message_ids]
    recent_ids = {m.id for m in recent}
    gap = [m for m in gap if m.id not in recent_ids]
    exchange = _completed_exchange(
        recent,
        recent_all,
        query_text=query_text,
        omit_message_ids=omit_message_ids,
        current_user_message_id=current_user_message_id,
    )
    pictures = await shown_pictures.labels_for_turn()
    return PromptWindow(recent=recent, gap=gap, exchange=exchange, pictures=pictures)


def _completed_exchange(
    recent: list[Any],
    recent_all: list[Any],
    *,
    query_text: str | None,
    omit_message_ids: set[UUID] | None,
    current_user_message_id: UUID | None,
) -> list[Any]:
    """``recent`` without its last row when that row is proven to be this turn's user."""
    if not recent or recent[-1].role != "user" or recent[-1].content != query_text:
        return recent
    # New-turn preparation includes its current user in history, sometimes
    # before persistence completes. Only the caller's explicit ID proves that
    # it is the current turn, rather than an incomplete previous exchange.
    if current_user_message_id is not None and recent[-1].id == current_user_message_id:
        return recent[:-1]
    # Regeneration retains the persisted current user while omitting its newest
    # assistant. Classify the preceding completed exchange only with that proof.
    if (
        omit_message_ids
        and len(recent_all) >= 2
        and recent_all[-1].role == "assistant"
        and recent_all[-1].id in omit_message_ids
        and recent[-1] is recent_all[-2]
    ):
        return recent[:-1]
    return recent


def _answer_line(body: str) -> str:
    value = " ".join(answer_fence_value(body).split())
    # LaTeX stays maths: a bare "26.3\\,\\mathrm{N·m}" was copied into replies as text.
    if re.search(r"\\[A-Za-z]", value) and "$" not in value:
        value = f"${value}$"
    # The fence took its own line break with it; the line keeps one.
    return f"Answer: {value}\n" if value else ""


# The card's line under its own heading needs no second label: the model copied
# "**Answer**" then "Answer: …" into its replies, and the reply read Answer twice.
_LABEL_UNDER_HEADING = re.compile(r"(?m)^(\*\*Answer:?\*\*:?[ \t]*\n(?:[ \t]*\n)*)Answer: ")


def _todo_screen_line(_body: str) -> str:
    return todos_service.todo_screen_line("en")


def strip_prompt_owned_fences(content: str) -> str:
    """Drop solver/search fences from assistant history before the model sees them.

    Persisted messages keep the fences for the client. Re-injecting ```answer /
    ```graph / ```sources / ```photo into the recent window teaches the model to copy them.
    The answer card stays as a line, ``Answer:`` when no heading names it: "in km/h?" or
    "just the answer" then reads the verified value instead of working the problem again
    unchecked.
    """
    out = _LABEL_UNDER_HEADING.sub(r"\1", map_closed_fences(content, "answer", _answer_line))
    # A clarify card is read as what it asked, never as JSON to copy.
    out = map_closed_fences(out, CLARIFY_FENCE, card_as_line)
    out = map_closed_fences(out, _OLD_REMINDER_CARD, _todo_screen_line)
    for lang in _PROMPT_STRIP_FENCE_LANGS:
        out = strip_closed_fences(out, lang)
    return out


def history_messages(window: PromptWindow, *, math_followup: bool) -> list[dict[str, str]]:
    """The window as chat messages: gap rows trimmed, prompt-owned fences out of replies,
    and each picture a reply showed said in words (``shown_pictures``)."""
    gap_ids = {m.id for m in window.gap}
    messages: list[dict[str, str]] = []
    for msg in (*window.gap, *window.recent):
        content = msg.content
        if msg.id in gap_ids:
            content = trim_message_for_summary(content)
        if msg.role == "user":
            content = wrap_persisted_attachment_excerpts(content)
        elif msg.role == "assistant":
            prior_result = (
                subject_adapter("math").followups.previous_result(content)
                if math_followup and msg is window.exchange[-1]
                else None
            )
            content = prior_result or strip_prompt_owned_fences(content)
            model = getattr(msg, "model", None)
            content = shown_pictures.as_text(
                content, model=model if isinstance(model, str) else None, pictures=window.pictures
            )
        messages.append({"role": msg.role, "content": content})
    return messages
