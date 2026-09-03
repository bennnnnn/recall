from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Chat, Message
from app.services import calendar as calendar_service
from app.services import day_planning as day_planning_service
from app.services import email as email_service
from app.services import projects as projects_service
from app.services import time_context as time_context_service
from app.services.chat.prompt_constants import (
    is_broad_self_question,
    is_lightweight_chat_turn,
    is_personal_advice_question,
    needs_rich_context,
)

if TYPE_CHECKING:
    from app.services.chat.turn_prep.context import ClientGeoContext


def _should_augment_web_and_tools(
    *,
    instant_reply: str | None,
    lightweight: bool,
    minimal_personal: bool,
    minimal_quiz: bool,
    active_vocab_turn: bool,
    day_planning: bool,
    ambiguous_nearby: bool,
    is_external_calendar_question: bool,
    is_external_email_question: bool,
    rich_context: bool = True,
    needs_math: bool = False,
    needs_search: bool = False,
    needs_chem: bool = False,
) -> bool:
    """Shared gate for routing-context prefetch and web/tools augmentation.

    Evaluated at both call sites (not cached) so mid-turn ``instant_reply``
    updates still suppress augmentation the same way as before.

    Active vocab turns (an answer following an in-chat quiz/vocab prompt) are
    learning turns: they need project context (rich_context stays on) but not
    web search or calendar/gmail context. ``minimal_quiz`` covers the
    letter-answer path; ``active_vocab_turn`` also covers the open-ended
    answer path (``minimal_vocab_answer``), which sets neither
    ``minimal_quiz`` nor ``lightweight``.

    Slim/casual chat (not ``rich_context``) still augments when the turn
    actually needs math, web search, or chemistry — otherwise skip prior
    messages, calendar-write, Tavily/SymPy, and PubChem.
    """
    if not (
        instant_reply is None
        and not lightweight
        and not minimal_personal
        and not minimal_quiz
        and not active_vocab_turn
        and not day_planning
        and not ambiguous_nearby
        and not is_external_calendar_question
        and not is_external_email_question
    ):
        return False
    return rich_context or needs_math or needs_search or needs_chem


def _should_fetch_integrations(
    *,
    instant_reply: str | None,
    lightweight: bool,
    minimal_personal: bool,
    minimal_quiz: bool,
    active_vocab_turn: bool,
    rich_context: bool,
    load_calendar: bool,
    load_gmail: bool,
) -> bool:
    """Load calendar/gmail/nudge only for rich turns or calendar/gmail intent.

    Casual coaching (Help me think) must not pay the Gmail-nudge query.
    Calendar/gmail questions still fetch even when ``rich_context`` is false.
    """
    if instant_reply is not None or lightweight or minimal_personal or minimal_quiz:
        return False
    if active_vocab_turn:
        return False
    return rich_context or load_calendar or load_gmail


async def _should_minimal_quiz_context(
    session: AsyncSession,
    chat_id: UUID,
    content: str,
) -> bool:
    """Letter/choice-text answers after an in-chat ```vocab_quiz use the quiz prompt path."""
    from app.services import vocab_quiz as vocab_quiz_service
    from app.services.chat.quiz_messages import get_last_quiz_assistant

    prior = await get_last_quiz_assistant(session, chat_id)
    if prior is None:
        return False
    quiz = vocab_quiz_service.parse_vocab_quiz(prior.content)
    choices = quiz.choices if quiz is not None else None
    return vocab_quiz_service.is_vocab_quiz_answer(content, choices=choices)


@dataclass
class _TurnMode:
    lightweight: bool
    rich_context: bool
    minimal_personal: bool
    minimal_quiz: bool
    minimal_vocab_answer: bool
    active_vocab_turn: bool
    day_planning: bool
    day_reflection: bool
    quiz_assistant: Message | None = None
    advice_memory: bool = False


def _turn_needs_rich_context(
    content: str,
    *,
    active_vocab_turn: bool,
    day_planning: bool,
    day_reflection: bool,
) -> bool:
    """Opt-in personal/tool context — default casual chat stays slim."""
    from app.services import todos as todos_service

    if needs_rich_context(
        content,
        active_vocab_turn=active_vocab_turn,
        day_planning=day_planning,
        day_reflection=day_reflection,
    ):
        return True
    if calendar_service.is_external_calendar_question(content):
        return True
    if email_service.is_external_email_question(content):
        return True
    if todos_service.query_implies_todos(content):
        return True
    # Do not pass chat.project_id — that helper treats any linked project as
    # "always sync", which would force memory theater on casual chitchat.
    if projects_service.transcript_implies_project_sync(content):
        return True
    return False


async def _classify_turn_mode(
    session: AsyncSession,
    chat: Chat,
    content: str,
) -> _TurnMode:
    """Classify lightweight/rich-context/day-planning modes for a turn.

    Study checks live on the lesson screen. Chat never grades A-D or continues
    an in-chat vocab quiz, so this skips the assistant quiz lookback even when
    a Learning project is linked.
    """
    _ = (session, chat)
    minimal_personal = is_broad_self_question(content)
    day_planning = day_planning_service.is_day_planning_question(content)
    day_reflection = day_planning_service.is_day_reflection_question(content)
    lightweight = is_lightweight_chat_turn(content, active_vocab_turn=False)
    rich_context = _turn_needs_rich_context(
        content,
        active_vocab_turn=False,
        day_planning=day_planning,
        day_reflection=day_reflection,
    )
    advice_memory = (
        is_personal_advice_question(content)
        and not day_planning
        and not day_reflection
        and not lightweight
    )
    return _TurnMode(
        lightweight=lightweight,
        rich_context=rich_context,
        minimal_personal=minimal_personal,
        minimal_quiz=False,
        minimal_vocab_answer=False,
        active_vocab_turn=False,
        day_planning=day_planning,
        day_reflection=day_reflection,
        quiz_assistant=None,
        advice_memory=advice_memory,
    )


async def _resolve_instant_reply(
    session: AsyncSession,
    content: str,
    *,
    local_tz: str,
    user_locale: str | None,
    geo: ClientGeoContext,
    user_id: UUID,
) -> str | None:
    """Time/location/calendar/email short-circuits that skip the LLM."""
    if time_context_service.is_time_question(content):
        return time_context_service.format_time_answer(local_tz, user_locale)
    if time_context_service.is_location_question(content):
        return time_context_service.format_location_answer(geo.user_location, local_tz)
    if calendar_service.is_external_calendar_question(content):
        if not await calendar_service.is_connected(session, user_id):
            return calendar_service.format_not_connected_answer()
        return None
    if email_service.is_external_email_question(content):
        if not await email_service.is_connected(session, user_id):
            return email_service.format_not_connected_answer()
        return None
    return None


def _instant_reply_needs_db(content: str) -> bool:
    """Calendar/email short-circuits need a connection check; time/location do not."""
    return calendar_service.is_external_calendar_question(
        content
    ) or email_service.is_external_email_question(content)
