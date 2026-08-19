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
    lookback: int = 20,
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


async def find_original_quiz_fence_created_at(
    session: AsyncSession,
    chat_id: UUID,
    *,
    prior_assistant: Message,
    lookback: int = 20,
) -> datetime:
    """Find the ``created_at`` of the ORIGINAL quiz fence for the same word.

    When the model re-emits a ``vocab_quiz`` fence in a hint-only reply (despite
    the prompt saying "do NOT redisplay"), the prior_assistant is the re-emitted
    fence, and counting answers since its timestamp resets the try counter to 0.
    This scans backward for an earlier assistant message with a quiz fence for
    the same word/question and returns its timestamp so the attempt counter
    continues from the original fence. (LANG-STATE-001)

    Returns ``prior_assistant.created_at`` if no earlier fence is found.
    """
    from app.services.vocab_quiz import parse_vocab_quiz

    parsed = parse_vocab_quiz(prior_assistant.content)
    if parsed is None:
        return prior_assistant.created_at
    target_word = (parsed.word or "").strip().lower()
    target_question = (parsed.question or "").strip().lower()

    messages = await messages_repo.list_recent_assistants(session, chat_id, limit=max(1, lookback))
    earliest = prior_assistant.created_at
    for message in messages:
        if message.id == prior_assistant.id:
            continue
        if message.created_at >= prior_assistant.created_at:
            continue
        earlier = parse_vocab_quiz(message.content)
        if earlier is None:
            continue
        if target_word and (earlier.word or "").strip().lower() == target_word:
            earliest = message.created_at
            break
        if (
            not target_word
            and target_question
            and (earlier.question or "").strip().lower() == target_question
        ):
            earliest = message.created_at
            break
    return earliest
