"""Record one retry-safe lesson question outcome and its progress effects."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import LearningPracticeEvent, ProjectItem, QuizMissEvent
from app.models.schemas.learning import LearningPracticeIn
from app.repositories import learning_practice as practice_repo
from app.services.learning.spaced_repetition import apply_sm2
from app.services.projects.common import _invalidate_home_for_user
from app.services.projects.crud import ProjectsError


def _check_replay(event: LearningPracticeEvent, item_id: UUID, body: LearningPracticeIn) -> None:
    if (event.item_id, event.was_correct, event.completes_word) != (
        item_id,
        body.was_correct,
        body.completes_word,
    ):
        raise ProjectsError("attempt_id already used for a different outcome", status_code=409)


async def record_practice(
    session: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    item_id: UUID,
    body: LearningPracticeIn,
    *,
    now: datetime | None = None,
) -> tuple[ProjectItem, bool, bool]:
    try:
        item = await practice_repo.lock_owned_item(session, user_id, project_id, item_id)
        if item is None:
            raise ProjectsError("Item not found", status_code=404)
        when = now or datetime.now(UTC)
        previous = await practice_repo.get_attempt(session, user_id, body.attempt_id)
        if previous is not None:
            _check_replay(previous, item_id, body)
            newly_mastered = previous.newly_mastered
            await session.commit()
            await _invalidate_home_for_user(user_id)
            return item, False, newly_mastered
        newly_mastered = bool(
            body.completes_word
            and item.mastered_at is None
            and not item.mastered
            and item.status != "mastered"
        )
        event = LearningPracticeEvent(
            attempt_id=body.attempt_id,
            user_id=user_id,
            project_id=project_id,
            item_id=item_id,
            was_correct=body.was_correct,
            completes_word=body.completes_word,
            newly_mastered=newly_mastered,
            occurred_at=when,
        )
        try:
            # Different items may receive the same retry UUID concurrently. Keep
            # that unique-key race inside a savepoint, without losing the item lock.
            async with session.begin_nested():
                session.add(event)
                await session.flush()
        except IntegrityError:
            previous = await practice_repo.get_attempt(session, user_id, body.attempt_id)
            if previous is None:
                raise
            _check_replay(previous, item_id, body)
            newly_mastered = previous.newly_mastered
            await session.refresh(item)
            await session.commit()
            await _invalidate_home_for_user(user_id)
            return item, False, newly_mastered

        item.quiz_attempts = int(item.quiz_attempts or 0) + 1
        item.quiz_correct = int(item.quiz_correct or 0) + int(body.was_correct)
        item.last_reviewed_at = when
        if not body.was_correct:
            item.last_incorrect_at = when
            session.add(QuizMissEvent(item_id=item.id, user_id=user_id, occurred_at=when))
        if body.completes_word:
            item.last_completed_at = when
            state = apply_sm2(
                quality=5,
                ease_factor=item.ease_factor,
                interval_days=item.interval_days,
                review_count=item.review_count,
                now=when,
            )
            item.status = "mastered"
            item.mastered = True
            if item.mastered_at is None:
                item.mastered_at = when
            item.ease_factor = state.ease_factor
            item.interval_days = state.interval_days
            item.review_count = state.review_count
            item.due_at = state.due_at
        elif not item.mastered and item.status != "mastered":
            item.status = "learning"
            if item.due_at is None:
                item.due_at = when
        await session.commit()
        await session.refresh(item)
    except Exception:
        await session.rollback()
        raise
    await _invalidate_home_for_user(user_id)
    return item, True, newly_mastered
