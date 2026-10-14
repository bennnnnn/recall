from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Chat
from app.modules.chat.prompt_constants import (
    could_continue_draft,
    draft_followup,
    is_broad_self_question,
    is_capabilities_question,
    is_career_personal_question,
    is_lightweight_chat_turn,
    is_personal_advice_question,
    is_profile_fact_question,
    is_profile_recall_pushback,
    is_short_reply,
    is_teaching_request,
    needs_rich_context,
    profile_question_to_answer,
)
from app.modules.memory import is_food_or_diet_query
from app.repositories import messages as messages_repo
from app.services import day_planning as day_planning_service
from app.services.text_normalize import collapse_ws


def _should_augment_web_and_tools(
    *,
    instant_reply: str | None,
    lightweight: bool,
    minimal_personal: bool,
    day_planning: bool,
    ambiguous_nearby: bool,
    rich_context: bool = True,
    needs_math: bool = False,
    needs_search: bool = False,
    needs_chem: bool = False,
) -> bool:
    """Shared gate for routing-context prefetch and web/tools augmentation.

    Evaluated at both call sites (not cached) so mid-turn ``instant_reply``
    updates still suppress augmentation the same way as before.

    Slim/casual chat (not ``rich_context``) still augments when the turn
    actually needs math, web search, or chemistry — otherwise skip prior
    messages, Tavily/SymPy, and PubChem.
    """
    if not (
        instant_reply is None
        and not lightweight
        and not minimal_personal
        and not day_planning
        and not ambiguous_nearby
    ):
        return False
    return rich_context or needs_math or needs_search or needs_chem


@dataclass
class _TurnMode:
    lightweight: bool
    rich_context: bool
    minimal_personal: bool
    day_planning: bool
    day_reflection: bool
    advice_memory: bool = False


def _turn_needs_rich_context(
    content: str,
    *,
    day_planning: bool,
    day_reflection: bool,
) -> bool:
    """Opt-in personal/tool context — default casual chat stays slim."""
    from app.modules import todos as todos_service

    if needs_rich_context(
        content,
        day_planning=day_planning,
        day_reflection=day_reflection,
    ):
        return True
    if todos_service.query_implies_todos(content):
        return True
    return False


async def _prior_user_texts(
    session: AsyncSession,
    chat_id: UUID,
    content: str,
) -> list[str]:
    """User lines before this turn. The current line may already be stored."""
    recent = await messages_repo.list_recent(session, chat_id, limit=8)
    users = [
        message.content
        for message in recent
        if message.role == "user" and isinstance(message.content, str)
    ]
    if users and collapse_ws(users[-1]) == collapse_ws(content):
        users = users[:-1]
    return users


# A draft three exchanges back is the one a follow-up changes.
_DRAFT_HISTORY = 6


async def _continues_a_draft(session: AsyncSession, chat_id: UUID, content: str) -> bool:
    """ "Email" or "make it shorter" after a draft: one short history read decides."""
    if not could_continue_draft(content):
        return False
    recent = await messages_repo.list_recent(session, chat_id, limit=_DRAFT_HISTORY + 1)
    prior = [
        (message.role, message.content)
        for message in recent
        if message.role in {"user", "assistant"} and isinstance(message.content, str)
    ]
    # The current line may already be stored.
    if prior and prior[-1][0] == "user" and collapse_ws(prior[-1][1]) == collapse_ws(content):
        prior = prior[:-1]
    return draft_followup(content, prior) is not None


async def _classify_turn_mode(
    session: AsyncSession,
    chat: Chat,
    content: str,
) -> _TurnMode:
    """Classify lightweight/rich-context/day-planning modes for a turn.

    Short replies (yes / no / got it) load the last assistant only when
    needed so ``hi`` / ``thanks`` never pay that round trip.
    """
    minimal_personal = is_broad_self_question(content)
    day_planning = day_planning_service.is_day_planning_question(content)
    day_reflection = day_planning_service.is_day_reflection_question(content)
    prior_assistant: str | None = None
    if is_short_reply(content):
        prior = await messages_repo.get_last_assistant(session, chat.id)
        if prior is not None:
            prior_assistant = prior.content
    lightweight = is_lightweight_chat_turn(content, prior_assistant=prior_assistant)
    profile_followup = False
    if is_profile_recall_pushback(content):
        prior_users = await _prior_user_texts(session, chat.id, content)
        profile_followup = profile_question_to_answer(content, prior_users) is not None
    rich_context = _turn_needs_rich_context(
        content,
        day_planning=day_planning,
        day_reflection=day_reflection,
    )
    if not rich_context and not lightweight:
        # A change to a draft needs what the draft had: memory for names, and
        # the profile it is signed with. A slim turn signed it "[Your Name]".
        rich_context = await _continues_a_draft(session, chat.id, content)
    advice_memory = (
        (
            is_personal_advice_question(content)
            or is_food_or_diet_query(content)
            or is_capabilities_question(content)
            or is_teaching_request(content)
            or is_career_personal_question(content)
            or is_profile_fact_question(content)
            or profile_followup
        )
        and not day_planning
        and not day_reflection
        and not lightweight
    )
    return _TurnMode(
        lightweight=lightweight,
        rich_context=rich_context,
        minimal_personal=minimal_personal,
        day_planning=day_planning,
        day_reflection=day_reflection,
        advice_memory=advice_memory,
    )
