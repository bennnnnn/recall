"""Quiz-oriented message lookups (filtering lives here, not in the repo)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Message
from app.repositories import messages as messages_repo


async def get_last_quiz_assistant(
    session: AsyncSession,
    chat_id: UUID,
    *,
    lookback: int = 12,
) -> Message | None:
    """Most recent assistant message that is still an active learning/quiz prompt.

    Prefers a gradeable ```vocab_quiz fence (for MCQ chips). Falls back to
    open-ended vocab prompts (vocab_card / sentence / define) so those turns
    still get the vocab answer grading path. After a wrong MCQ the model may
    reply hint-only; the previous fence remains the one to grade against.
    """
    from app.services.projects import looks_like_vocab_question
    from app.services.vocab_quiz import parse_vocab_quiz

    messages = await messages_repo.list_recent_assistants(session, chat_id, limit=max(1, lookback))
    open_ended: Message | None = None
    for message in messages:
        if parse_vocab_quiz(message.content) is not None:
            return message
        if open_ended is None and looks_like_vocab_question(message.content):
            open_ended = message
    return open_ended


async def count_quiz_letter_answers_since(
    session: AsyncSession,
    chat_id: UUID,
    *,
    after: datetime,
    choices: tuple[tuple[str, str], ...] | None = None,
) -> int:
    """How many A-D (or matching choice-text) answers the user sent after the open quiz."""
    from app.services.vocab_quiz import quiz_answer_letter

    messages = await messages_repo.list_user_messages_since(session, chat_id, after=after)
    return sum(1 for message in messages if quiz_answer_letter(message.content, choices=choices))
