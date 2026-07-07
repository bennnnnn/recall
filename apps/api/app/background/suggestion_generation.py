import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import SessionLocal
from app.gateways import litellm_gateway
from app.models.schemas import SuggestionGenerationResult, SuggestionItem
from app.repositories import chats as chats_repo
from app.repositories import suggestions as suggestions_repo
from app.repositories import users as users_repo
from app.services import memory as memory_service

logger = logging.getLogger(__name__)

# Shared with the repository so the generator cap and the list endpoint stay
# in sync (see repositories/suggestions.py).
MAX_ACTIVE_SUGGESTIONS = suggestions_repo.MAX_ACTIVE_SUGGESTIONS

SUGGESTION_SYSTEM_PROMPT = (
    "You are a helpful assistant looking at a user's recent conversation history "
    "and remembered facts. Based on what you see, suggest 2-3 things the user "
    "might want to do next. These could be:\n"
    "- Continue a recent conversation topic\n"
    "- Start a new project or task based on their interests\n"
    "- Follow up on something they mentioned\n"
    "- Try a feature they haven't used yet\n\n"
    "Keep each suggestion to one short sentence. Be specific to what you see — "
    "not generic. Example: 'Write unit tests for your auth service' rather than "
    "'Continue working on your project.'"
)


@dataclass(frozen=True)
class _SuggestionSnapshot:
    user_context: str
    max_items: int


async def _load_suggestion_snapshot(
    session: AsyncSession,
    settings: Settings,
    user_id: UUID,
) -> _SuggestionSnapshot | None:
    user = await users_repo.get_by_id(session, user_id)
    if not user:
        return None

    await suggestions_repo.delete_expired(session)
    active_count = await suggestions_repo.count_active(session, user_id)
    if active_count >= MAX_ACTIVE_SUGGESTIONS:
        logger.debug(
            "Skipping suggestions for %s: %d active (cap %d)",
            user_id,
            active_count,
            MAX_ACTIVE_SUGGESTIONS,
        )
        return None

    recent = await chats_repo.list_for_user(session, user_id, limit=5)
    memory_block = await memory_service.get_memory_block(session, user, settings)

    recent_summary = "\n".join(
        f"- {c.title or 'New chat'} (updated {c.updated_at.strftime('%b %d')})" for c in recent
    )

    user_context = f"Recent conversations:\n{recent_summary}"
    if memory_block:
        user_context += f"\n\nKnown facts about user:\n{memory_block}"

    remaining = MAX_ACTIVE_SUGGESTIONS - active_count
    max_items = min(3, remaining)
    return _SuggestionSnapshot(user_context=user_context, max_items=max_items)


async def _apply_suggestion_result(
    session: AsyncSession,
    user_id: UUID,
    items: list[SuggestionItem],
) -> None:
    if not items:
        return
    await suggestions_repo.create_many(
        session,
        user_id,
        [{"text": item.text, "category": item.category, "source": "model"} for item in items],
    )
    await session.commit()


async def generate_suggestions(
    settings: Settings,
    user_id: UUID,
) -> None:
    """Generate 2-3 proactive suggestions based on recent history.

    Skips generation if the user already has enough active suggestions
    to avoid unbounded growth from the every-10th-message trigger in chat
    finalization (post_turn enqueues when prior_count % 10 == 0, where
    prior_count is the per-chat message count — so a long chat regenerates
    suggestions as it progresses).
    """
    try:
        async with SessionLocal() as session:
            snapshot = await _load_suggestion_snapshot(session, settings, user_id)
            await session.commit()

        if snapshot is None:
            return

        result = await litellm_gateway.complete_structured(
            settings=settings,
            model_alias="memory-model",
            messages=[
                {"role": "system", "content": SUGGESTION_SYSTEM_PROMPT},
                {"role": "user", "content": snapshot.user_context},
            ],
            schema=SuggestionGenerationResult,
            max_tokens=256,
        )

        if not result or not result.items:
            return

        new_items = result.items[: snapshot.max_items]
        if not new_items:
            return

        async with SessionLocal() as session:
            await _apply_suggestion_result(session, user_id, new_items)
    except Exception:
        logger.exception("Failed to generate suggestions for user %s", user_id)
