"""Deterministic quiz grading and ledger writes."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import ProjectItem
from app.repositories import project_items as project_items_repo
from app.repositories import projects as projects_repo
from app.services.projects.common import (
    DEFAULT_LIST,
    _find_item,
    _find_item_by_content,
    _is_language_project,
    _is_trivia_project,
)
from app.services.projects.items import create_item
from app.services.sm2 import apply_sm2, quality_for_status
from app.services.vocab_quiz import QuizAnswerGrade


def _item_status_label(item: ProjectItem) -> str:
    if item.status:
        return item.status
    return "mastered" if item.mastered else "new"


async def apply_quiz_result(
    session: AsyncSession,
    item: ProjectItem,
    *,
    is_correct: bool,
    commit: bool = True,
) -> ProjectItem:
    """Derive status + SM-2 schedule, then persist via the repository."""
    now = datetime.now(UTC)
    prior_status = _item_status_label(item)
    if is_correct:
        new_status = "mastered"
    elif prior_status == "mastered":
        new_status = "learning"
    elif prior_status == "new":
        new_status = "learning"
    else:
        new_status = prior_status

    quality = quality_for_status(new_status, was_correct=is_correct)
    state = apply_sm2(
        quality=quality,
        ease_factor=float(getattr(item, "ease_factor", 2.5) or 2.5),
        interval_days=int(getattr(item, "interval_days", 0) or 0),
        review_count=int(item.review_count or 0),
        now=now,
    )
    return await project_items_repo.apply_quiz_result(
        session,
        item,
        is_correct=is_correct,
        new_status=new_status,
        prior_status=prior_status,
        now=now,
        ease_factor=state.ease_factor,
        interval_days=state.interval_days,
        review_count=state.review_count,
        due_at=state.due_at,
        commit=commit,
    )


def _recently_missed_quiz(item: ProjectItem, *, within_seconds: int = 86_400) -> bool:
    """Block sync-master for a day after a fail so failed words stay learning."""
    missed = getattr(item, "last_incorrect_at", None)
    if not isinstance(missed, datetime):
        return False
    return (datetime.now(UTC) - missed.astimezone(UTC)).total_seconds() < within_seconds


def _failed_quiz_today(item: ProjectItem) -> bool:
    """True when last_incorrect_at is already on today's UTC calendar day."""
    missed = getattr(item, "last_incorrect_at", None)
    if not isinstance(missed, datetime):
        return False
    return missed.astimezone(UTC).date() == datetime.now(UTC).date()


async def _persist_quiz_outcome(
    session: AsyncSession,
    *,
    user_id: UUID,
    project_id: UUID,
    chat_id: UUID,
    existing: ProjectItem | None,
    content: str,
    list_title: str,
    is_correct: bool,
    definition: str | None = None,
) -> None:
    """Record a graded answer on the matched item, creating it on first sight.

    Shared ledger write for the trivia and vocab branches; the commit stays
    with the caller's outer transaction (commit=False throughout).
    For trivia, ``definition`` holds the correct answer text shown on the day list.
    """
    answer = (definition or "").strip() or None
    item = existing
    if item is None:
        item = await create_item(
            session,
            user_id=user_id,
            project_id=project_id,
            content=content,
            list_title=list_title,
            definition=answer,
            chat_id=chat_id,
            status="new",
            commit=False,
        )
    elif answer and not (item.definition or "").strip():
        # Backfill answer on older trivia rows that only stored the question.
        item.definition = answer
    await apply_quiz_result(session, item, is_correct=is_correct, commit=False)


async def apply_deterministic_quiz_answer(
    session: AsyncSession,
    *,
    user_id: UUID,
    chat_id: UUID,
    project_id: UUID | None,
    assistant_content: str,
    user_answer: str,
    attempt: int = 1,
) -> QuizAnswerGrade | None:
    """Persist quiz results without waiting on background LLM project sync."""
    from app.services import vocab_quiz as vocab_quiz_service

    quiz = vocab_quiz_service.parse_vocab_quiz(assistant_content)
    choices = quiz.choices if quiz is not None else ()
    letter = vocab_quiz_service.quiz_answer_letter(user_answer, choices=choices)
    if letter is None or quiz is None:
        return None

    # Only score in project-linked chats — never guess trivia/vocab project from user id.
    if project_id is None:
        return None

    project = await projects_repo.get_by_id(session, project_id, user_id)
    if project is None:
        return None

    is_trivia = _is_trivia_project(project) or quiz.quiz_type == "trivia"
    if not quiz.correct:
        return None
    is_correct = letter == quiz.correct.upper()
    correct_letter = quiz.correct.upper()
    if not re.fullmatch(r"[A-D]", correct_letter):
        return None

    try_number = max(1, attempt)
    tries_exhausted = (not is_correct) and (
        try_number >= vocab_quiz_service.MAX_QUIZ_TRIES_PER_QUESTION
    )
    # Persist correct immediately; persist misses only after 3 wrong tries.
    should_persist = is_correct or tries_exhausted

    if is_trivia:
        topic = quiz.word.strip()
        question = (quiz.question or quiz.word).strip()
        if not question:
            return None
        list_title = topic or DEFAULT_LIST
        items = await project_items_repo.find_quiz_candidates(
            session, user_id, project.id, question
        )
        existing = _find_item(items, project.id, list_title, question)
        if should_persist:
            await _persist_quiz_outcome(
                session,
                user_id=user_id,
                project_id=project.id,
                chat_id=chat_id,
                existing=existing,
                content=question,
                list_title=list_title,
                is_correct=is_correct,
                definition=(quiz.correct_text or "").strip() or None,
            )
        return vocab_quiz_service.QuizAnswerGrade(
            is_correct=is_correct,
            user_letter=letter,
            correct_letter=correct_letter,
            # Feedback label = correct choice text (not the topic like "History").
            word=(quiz.correct_text or question)[:80],
            quiz_type="trivia",
            question=question,
            attempt=try_number,
            tries_exhausted=tries_exhausted,
        )

    if not _is_language_project(project):
        return None

    word = quiz.word.strip()
    if not word:
        return None
    list_title = DEFAULT_LIST
    items = await project_items_repo.find_quiz_candidates(session, user_id, project.id, word)
    existing = _find_item(items, project.id, list_title, word) or _find_item_by_content(
        items, project.id, word
    )
    if should_persist:
        await _persist_quiz_outcome(
            session,
            user_id=user_id,
            project_id=project.id,
            chat_id=chat_id,
            existing=existing,
            content=word,
            list_title=list_title,
            is_correct=is_correct,
        )
    return vocab_quiz_service.QuizAnswerGrade(
        is_correct=is_correct,
        user_letter=letter,
        correct_letter=correct_letter,
        word=word,
        quiz_type="vocab",
        question=quiz.question,
        attempt=try_number,
        tries_exhausted=tries_exhausted,
    )
