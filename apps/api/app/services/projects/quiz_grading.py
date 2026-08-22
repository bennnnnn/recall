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
    _find_item_by_content,
    _is_language_project,
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
        # MCQ recognition shouldn't single-shot promote to "mastered" —
        # only open-ended production (teach→use / use→define) mastery via
        # the background `master` action sets "mastered". MCQ correct on an
        # already-mastered word reinforces it (stays mastered). (LANG-TEACH-003)
        if prior_status == "mastered":
            new_status = "mastered"
        else:
            new_status = "learning"
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


def _missed_on_local_today(item: ProjectItem, *, timezone_name: str) -> bool:
    """True when last_incorrect_at is on the user's local calendar day.

    Same midnight as ``count_today_vocab_stats`` — not UTC date.
    """
    from app.services.daily_learning import start_of_today_utc

    missed = getattr(item, "last_incorrect_at", None)
    if not isinstance(missed, datetime):
        return False
    missed_utc = missed.astimezone(UTC) if missed.tzinfo else missed.replace(tzinfo=UTC)
    return missed_utc >= start_of_today_utc(timezone_name)


def _recently_missed_quiz(item: ProjectItem, *, timezone_name: str = "UTC") -> bool:
    """Block sync-master after a fail on the user's local today."""
    return _missed_on_local_today(item, timezone_name=timezone_name)


def _failed_quiz_today(item: ProjectItem, *, timezone_name: str = "UTC") -> bool:
    """True when last_incorrect_at is already on today's local calendar day."""
    return _missed_on_local_today(item, timezone_name=timezone_name)


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

    Shared ledger write for quiz outcomes; the commit stays
    with the caller's outer transaction (commit=False throughout).
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
        # Backfill definition when an older row stored only the lemma.
        item.definition = answer
    # Lock the item row so concurrent quiz submits can't both read the same
    # SM-2 fields and clobber each other's updates (LANG-BE-011).
    if existing is not None:
        locked = await project_items_repo.lock_for_update(session, item.id)
        if locked is not None:
            item = locked
    await apply_quiz_result(session, item, is_correct=is_correct, commit=False)


async def _apply_deterministic_quiz_answer(
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

    # Only score in project-linked chats — never guess a language project from user id.
    if project_id is None:
        return None

    project = await projects_repo.get_by_id(session, project_id, user_id)
    if project is None:
        return None

    # Project kind is authoritative — the quiz fence's quiz_type must not
    # override it. A vocabulary project with a quiz_type:"trivia" fence is
    # still graded as vocabulary.
    if not quiz.correct:
        return None
    correct_letter = quiz.correct.upper()
    if not re.fullmatch(r"[A-D]", correct_letter):
        return None
    # Grade against the card's own answer key — never let the verifier replace
    # it. A second LLM call is non-deterministic and context-blind; overriding
    # would let the same card grade differently across retries and write a
    # false miss into SM-2.
    is_correct = letter == correct_letter

    try_number = max(1, attempt)
    tries_exhausted = (not is_correct) and (
        try_number >= vocab_quiz_service.MAX_QUIZ_TRIES_PER_QUESTION
    )
    # Persist correct immediately; persist misses only after 3 wrong tries.
    should_persist = is_correct or tries_exhausted
    if should_persist:
        # Advisory verifier: log disagreement but always persist on the
        # fence key. The verifier was added to catch bad cards, not to
        # override the user-visible answer key. Abstaining drops progress
        # (LANG-GRAD-001/002) and blocks the background sync fallback
        # (LANG-POST-001) with no recovery path. The grade returned to the
        # model always uses quiz.correct so the hint matches the card.
        verified = await vocab_quiz_service.verified_correct_letter(quiz)
        if verified is not None and verified != correct_letter:
            import logging

            logging.getLogger(__name__).warning(
                "quiz verifier disagrees with fence key: "
                "question=%r fence=%r verifier=%r — persisting on fence key",
                quiz.question or quiz.word,
                correct_letter,
                verified,
            )

    if not _is_language_project(project):
        return None

    word = quiz.word.strip()
    if not word:
        return None
    items = await project_items_repo.find_quiz_candidates(session, user_id, project.id, word)
    existing = _find_item_by_content(items, project.id, word)
    list_title = (existing.list_title.strip() if existing else "") or DEFAULT_LIST
    if should_persist and existing is None:
        from app.services.projects.path import resolve_add_list_title

        deck_items = await project_items_repo.list_for_user(
            session, user_id, project_id=project.id, limit=500
        )
        list_title = resolve_add_list_title(project, DEFAULT_LIST, deck_items)
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
    elif existing is not None and not is_correct:
        # Record the wrong attempt (tries 1-2) without SM-2 scheduling so
        # missed_today counts it toward the daily goal. (LANG-TEACH-011)
        await project_items_repo.record_quiz_attempt(
            session, existing, now=datetime.now(UTC), commit=False
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


async def apply_deterministic_quiz_answer(
    session: AsyncSession,
    *,
    user_id: UUID,
    chat_id: UUID,
    project_id: UUID | None,
    assistant_content: str,
    user_answer: str,
    attempt: int = 1,
    commit: bool = True,
) -> QuizAnswerGrade | None:
    """Grade one answer within a single explicit transaction boundary.

    Repository writes inside the grading workflow always use ``commit=False``.
    The default preserves the standalone service behavior by committing once;
    callers composing a larger unit may pass ``commit=False`` and then own both
    commit and rollback.
    """
    try:
        grade = await _apply_deterministic_quiz_answer(
            session,
            user_id=user_id,
            chat_id=chat_id,
            project_id=project_id,
            assistant_content=assistant_content,
            user_answer=user_answer,
            attempt=attempt,
        )
        if commit:
            await session.commit()
        return grade
    except Exception:
        if commit:
            await session.rollback()
        raise
