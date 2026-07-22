from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Chat
from app.services import calendar as calendar_service
from app.services import day_planning as day_planning_service
from app.services import email as email_service
from app.services import projects as projects_service
from app.services import time_context as time_context_service
from app.services.chat.prompt_constants import (
    is_broad_self_question,
    is_lightweight_chat_turn,
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
    day_planning: bool,
    ambiguous_nearby: bool,
    is_external_calendar_question: bool,
    is_external_email_question: bool,
) -> bool:
    """Shared gate for routing-context prefetch and web/tools augmentation.

    Evaluated at both call sites (not cached) so mid-turn ``instant_reply``
    updates still suppress augmentation the same way as before.
    """
    return (
        instant_reply is None
        and not lightweight
        and not minimal_personal
        and not minimal_quiz
        and not day_planning
        and not ambiguous_nearby
        and not is_external_calendar_question
        and not is_external_email_question
    )


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
    """Classify quiz/vocab/lightweight/rich-context/day-planning modes for a turn.

    Fetches the last quiz assistant once (same session) instead of the prior
    double lookup via ``_should_minimal_quiz_context`` + vocab-turn block.
    """
    from app.services import vocab_quiz as vocab_quiz_service

    minimal_personal = is_broad_self_question(content)
    minimal_quiz = False
    minimal_vocab_answer = False
    active_vocab_turn = False
    day_planning = day_planning_service.is_day_planning_question(content)
    day_reflection = day_planning_service.is_day_reflection_question(content)

    from app.services.chat.quiz_messages import get_last_quiz_assistant

    quiz_assistant = await get_last_quiz_assistant(session, chat.id)
    parsed_quiz = None
    quiz_choices: tuple[tuple[str, str], ...] | None = None
    if quiz_assistant is not None:
        parsed_quiz = vocab_quiz_service.parse_vocab_quiz(quiz_assistant.content)
        quiz_choices = parsed_quiz.choices if parsed_quiz is not None else None
        # Same predicate as ``_should_minimal_quiz_context``.
        minimal_quiz = vocab_quiz_service.is_vocab_quiz_answer(content, choices=quiz_choices)

    if getattr(chat, "quiz_mode", None) == "exam":
        minimal_quiz = False

    if chat.project_id is not None and quiz_assistant is not None:
        has_fence = parsed_quiz is not None
        if has_fence or projects_service.looks_like_vocab_question(quiz_assistant.content):
            active_vocab_turn = True
            has_letter = (
                vocab_quiz_service.quiz_answer_letter(content, choices=quiz_choices) is not None
            )
            if has_letter and has_fence:
                minimal_quiz = True
            elif not minimal_quiz and has_letter:
                minimal_vocab_answer = True
            elif not minimal_quiz and not has_letter:
                minimal_vocab_answer = True

    lightweight = is_lightweight_chat_turn(content, active_vocab_turn=active_vocab_turn)
    rich_context = _turn_needs_rich_context(
        content,
        active_vocab_turn=active_vocab_turn,
        day_planning=day_planning,
        day_reflection=day_reflection,
    )
    return _TurnMode(
        lightweight=lightweight,
        rich_context=rich_context,
        minimal_personal=minimal_personal,
        minimal_quiz=minimal_quiz,
        minimal_vocab_answer=minimal_vocab_answer,
        active_vocab_turn=active_vocab_turn,
        day_planning=day_planning,
        day_reflection=day_reflection,
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
