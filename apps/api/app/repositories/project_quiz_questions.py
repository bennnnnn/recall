"""Persistence for pre-generated project quiz questions."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import ProjectQuizQuestion


def normalize_topic(topic: str) -> str:
    return topic.strip().casefold()


async def list_for_project_date(
    session: AsyncSession,
    project_id: UUID,
    quiz_date: date,
) -> list[ProjectQuizQuestion]:
    result = await session.execute(
        select(ProjectQuizQuestion)
        .where(
            ProjectQuizQuestion.project_id == project_id,
            ProjectQuizQuestion.quiz_date == quiz_date,
        )
        .order_by(ProjectQuizQuestion.sequence)
    )
    return list(result.scalars().all())


async def list_quizzed_topics(session: AsyncSession, project_id: UUID) -> set[str]:
    result = await session.execute(
        select(ProjectQuizQuestion.topic_normalized).where(
            ProjectQuizQuestion.project_id == project_id
        )
    )
    return {row[0] for row in result.all()}


async def get_by_id(
    session: AsyncSession,
    question_id: UUID,
    *,
    user_id: UUID,
    project_id: UUID,
) -> ProjectQuizQuestion | None:
    result = await session.execute(
        select(ProjectQuizQuestion).where(
            ProjectQuizQuestion.id == question_id,
            ProjectQuizQuestion.user_id == user_id,
            ProjectQuizQuestion.project_id == project_id,
        )
    )
    return result.scalar_one_or_none()


async def list_pending_for_date(
    session: AsyncSession,
    project_id: UUID,
    quiz_date: date,
) -> list[ProjectQuizQuestion]:
    result = await session.execute(
        select(ProjectQuizQuestion)
        .where(
            ProjectQuizQuestion.project_id == project_id,
            ProjectQuizQuestion.quiz_date == quiz_date,
            ProjectQuizQuestion.status == "pending",
        )
        .order_by(ProjectQuizQuestion.sequence)
    )
    return list(result.scalars().all())


async def delete_pending_by_ids(
    session: AsyncSession,
    project_id: UUID,
    quiz_date: date,
    question_ids: list[UUID],
) -> int:
    if not question_ids:
        return 0
    result = cast(
        CursorResult[Any],
        await session.execute(
            delete(ProjectQuizQuestion).where(
                ProjectQuizQuestion.project_id == project_id,
                ProjectQuizQuestion.quiz_date == quiz_date,
                ProjectQuizQuestion.status == "pending",
                ProjectQuizQuestion.id.in_(question_ids),
            )
        ),
    )
    return int(result.rowcount or 0)


async def next_pending(
    session: AsyncSession,
    project_id: UUID,
    quiz_date: date,
) -> ProjectQuizQuestion | None:
    result = await session.execute(
        select(ProjectQuizQuestion)
        .where(
            ProjectQuizQuestion.project_id == project_id,
            ProjectQuizQuestion.quiz_date == quiz_date,
            ProjectQuizQuestion.status == "pending",
        )
        .order_by(ProjectQuizQuestion.sequence)
        .limit(1)
    )
    return result.scalar_one_or_none()


async def count_answered_today(
    session: AsyncSession,
    project_id: UUID,
    quiz_date: date,
) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(ProjectQuizQuestion)
        .where(
            ProjectQuizQuestion.project_id == project_id,
            ProjectQuizQuestion.quiz_date == quiz_date,
            ProjectQuizQuestion.status == "answered",
            ProjectQuizQuestion.is_correct.is_(True),
        )
    )
    return int(result.scalar_one())


async def count_pending_today(
    session: AsyncSession,
    project_id: UUID,
    quiz_date: date,
) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(ProjectQuizQuestion)
        .where(
            ProjectQuizQuestion.project_id == project_id,
            ProjectQuizQuestion.quiz_date == quiz_date,
            ProjectQuizQuestion.status == "pending",
        )
    )
    return int(result.scalar_one())


async def insert_question(
    session: AsyncSession,
    *,
    user_id: UUID,
    project_id: UUID,
    project_item_id: UUID | None,
    quiz_date: date,
    sequence: int,
    quiz_kind: str,
    topic: str,
    part_of_speech: str | None,
    question_text: str,
    choices: list[dict[str, str]],
    correct_letter: str,
    reference_definition: str | None,
) -> ProjectQuizQuestion | None:
    """Insert one question; returns None if duplicate topic/item rejected."""
    topic_norm = normalize_topic(topic)
    stmt = (
        insert(ProjectQuizQuestion)
        .values(
            id=uuid.uuid4(),
            user_id=user_id,
            project_id=project_id,
            project_item_id=project_item_id,
            quiz_date=quiz_date,
            sequence=sequence,
            quiz_kind=quiz_kind,
            topic=topic.strip(),
            topic_normalized=topic_norm,
            part_of_speech=part_of_speech,
            question_text=question_text.strip(),
            choices=choices,
            correct_letter=correct_letter.upper(),
            reference_definition=reference_definition,
            status="pending",
        )
        .on_conflict_do_nothing()
        .returning(ProjectQuizQuestion)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def mark_answered(
    session: AsyncSession,
    question: ProjectQuizQuestion,
    *,
    modality: str,
    is_correct: bool,
    letter: str | None = None,
    text: str | None = None,
) -> ProjectQuizQuestion:
    question.status = "answered"
    question.answered_modality = modality
    question.is_correct = is_correct
    question.user_answer_letter = letter.upper() if letter else None
    question.user_answer_text = text.strip() if text else None
    question.answered_at = datetime.now(UTC)
    await session.flush()
    return question


async def batch_exists(
    session: AsyncSession,
    project_id: UUID,
    quiz_date: date,
    *,
    min_count: int,
) -> bool:
    result = await session.execute(
        select(func.count())
        .select_from(ProjectQuizQuestion)
        .where(
            ProjectQuizQuestion.project_id == project_id,
            ProjectQuizQuestion.quiz_date == quiz_date,
        )
    )
    return int(result.scalar_one()) >= min_count
