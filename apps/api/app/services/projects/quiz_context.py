"""Quiz-turn prompt context: exclusion lists, missed items, tutor slice."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.orm import ProjectItem
from app.repositories import project_items as project_items_repo
from app.repositories import projects as projects_repo
from app.services.projects.common import (
    _is_language_project,
    _is_trivia_project,
    _item_status,
    _trivia_daily_goal,
)
from app.services.projects.prompts import (
    _LEVEL_LABELS,
    TRIVIA_QUIZ_FENCE_EXAMPLE,
    VOCAB_LEARNING_FORMATS_BLOCK,
    _level_guidance,
)
from app.services.vocab_quiz import QuizAnswerGrade


def _format_missed_quiz_lines(items: list[ProjectItem], *, limit: int = 30) -> list[str]:
    learning = [item for item in items if _item_status(item) == "learning"]
    if not learning:
        return []
    lines = [
        "\nStill learning / failed recently — prefer a NEW item next in this session; "
        "bring these back on a later day (do NOT re-ask the one just missed):"
    ]
    for item in learning[:limit]:
        missed_at = getattr(item, "last_incorrect_at", None)
        when = (
            missed_at.astimezone(UTC).date().isoformat()
            if isinstance(missed_at, datetime)
            else "recent"
        )
        detail = (item.definition or item.note or item.example_sentence or "").strip()
        suffix = f" — {detail[:120]}" if detail else ""
        lines.append(f"- {item.content}{suffix} (failed {when})")
    return lines


# Fails stay out of the "quiz FIRST today" list until SM-2 due (usually next day),
# so a mid-session fail is not immediately re-prioritized against "never re-ask".
_FAILED_REVIEW_FALLBACK_MIN_AGE = timedelta(hours=12)


def _format_failed_review_lines(items: list[ProjectItem], *, limit: int = 12) -> list[str]:
    """Session-start nudge: bring back due failed items first (not same-session misses)."""
    now = datetime.now(UTC)
    failed: list[ProjectItem] = []
    for item in items:
        if _item_status(item) != "learning":
            continue
        missed = getattr(item, "last_incorrect_at", None)
        if not isinstance(missed, datetime):
            continue
        missed_utc = missed.astimezone(UTC) if missed.tzinfo else missed.replace(tzinfo=UTC)
        due = getattr(item, "due_at", None)
        if isinstance(due, datetime):
            due_utc = due.astimezone(UTC) if due.tzinfo else due.replace(tzinfo=UTC)
            if due_utc > now:
                continue
        elif now - missed_utc < _FAILED_REVIEW_FALLBACK_MIN_AGE:
            continue
        failed.append(item)
    if not failed:
        return []

    def _miss_key(item: ProjectItem) -> datetime:
        missed = getattr(item, "last_incorrect_at", None)
        if isinstance(missed, datetime):
            return missed.astimezone(UTC) if missed.tzinfo else missed.replace(tzinfo=UTC)
        return datetime.min.replace(tzinfo=UTC)

    failed.sort(key=_miss_key, reverse=True)
    lines = [
        "\n**Failed and due for review — quiz these FIRST today** (then new words). "
        "Do not skip them for brand-new items. Do not re-ask a word already missed "
        "earlier in this same session:"
    ]
    for item in failed[:limit]:
        lines.append(f"- {item.content}")
    return lines


# Hard ban list for quiz prompts — raised so large decks stay out of the model's
# "invent a new one" path. Soft "don't repeat" alone is not enough.
_COVERED_QUIZ_LIMIT = 200


def _format_covered_quiz_lines(
    contents: list[str],
    *,
    just_answered: str | None = None,
    limit: int = _COVERED_QUIZ_LIMIT,
) -> list[str]:
    """Format a DB-backed exclusion list for the quiz prompt.

    ``contents`` should already be ledger texts (mastered, and for trivia also
    learning). Soft "don't repeat" in the system prompt is not enough on its own.
    """
    covered: list[str] = []
    seen: set[str] = set()

    def _add(text: str) -> bool:
        """Add text; return True when the covered list is full."""
        cleaned = text.strip()
        key = cleaned.lower()
        if not cleaned or key in seen:
            return len(covered) >= limit
        seen.add(key)
        covered.append(cleaned)
        return len(covered) >= limit

    truncated = False
    if just_answered and _add(just_answered):
        truncated = True
    for text in contents:
        if truncated:
            break
        if _add(text):
            # More ledger rows may remain after this cap.
            truncated = True
            break
    if not covered:
        return []
    lines = [
        "\n**Do NOT ask these again** (saved in the user's quiz ledger — "
        "exact or paraphrased repeats count as repeats):"
    ]
    lines.extend(f"- {text}" for text in covered)
    if truncated and len(contents) >= limit:
        lines.append(
            "- …and more ledger items not listed — "
            "still do not repeat any previously saved word/question."
        )
    return lines


async def _covered_quiz_prompt_lines(
    session: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    *,
    include_learning: bool,
    just_answered: str | None = None,
    limit: int = _COVERED_QUIZ_LIMIT,
) -> list[str]:
    """Load exclusion texts from the DB and format them for the quiz prompt."""
    contents = await project_items_repo.list_quiz_exclusion_contents(
        session,
        user_id,
        project_id,
        include_learning=include_learning,
        limit=limit,
    )
    return _format_covered_quiz_lines(
        contents,
        just_answered=just_answered,
        limit=limit,
    )


async def load_project_quiz_context(
    session: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    settings: Settings,
    *,
    quiz_grade: QuizAnswerGrade | None = None,
) -> str:
    """Lightweight tutor slice for quiz answer turns — level, pool, and card format."""
    from app.services.vocab_quiz import MAX_QUIZ_TRIES_PER_QUESTION

    project = await projects_repo.get_by_id(session, project_id, user_id)
    if project is None:
        return ""

    retry_same = (
        quiz_grade is not None and not quiz_grade.is_correct and not quiz_grade.tries_exhausted
    )
    just_correct = quiz_grade is not None and quiz_grade.is_correct
    tries_exhausted = quiz_grade is not None and quiz_grade.tries_exhausted
    answered_label = ""
    attempt = quiz_grade.attempt if quiz_grade is not None else 1
    if quiz_grade is not None:
        # Trivia: question text; vocab: the word.
        answered_label = (
            (quiz_grade.question or quiz_grade.word)
            if quiz_grade.quiz_type == "trivia"
            else quiz_grade.word
        ).strip()

    if _is_trivia_project(project):
        items = await project_items_repo.list_for_user(
            session,
            user_id,
            project_id=project_id,
            limit=settings.project_item_inject_limit,
        )
        if retry_same and answered_label:
            follow = (
                f'WRONG on "{answered_label}" (try {attempt}/{MAX_QUIZ_TRIES_PER_QUESTION}) — '
                "reply with brief feedback + a short hint only. "
                "Do NOT redisplay the question, choices, or a ```vocab_quiz fence. "
                "Never switch to vocabulary words."
            )
        elif tries_exhausted and answered_label:
            follow = (
                f'FAILED after {attempt} tries — "{answered_label}" stays learning for next time. '
                "Briefly reveal the correct answer, then ask a DIFFERENT next general-knowledge "
                'question (quiz_type trivia — never vocabulary / "what does X mean?"):'
            )
        elif just_correct and answered_label:
            follow = (
                f'CORRECT — "{answered_label}" is done. Do NOT repeat that question. '
                "Ask a DIFFERENT next general-knowledge question using this format "
                '(quiz_type trivia only — never vocabulary / "what does X mean?"):'
            )
        else:
            follow = (
                "CORRECT (or starting) — after brief feedback, ask the NEXT general-knowledge "
                "question using this format (quiz_type trivia only — never vocabulary/"
                '"what does X mean?"). Never repeat a question already asked in this chat.'
            )
        lines = [
            f"Active trivia quiz — project: {project.title}.",
            f"Daily goal: {_trivia_daily_goal(project)} correct answers per session.",
            follow,
        ]
        if not retry_same:
            lines.extend(
                [
                    f"{TRIVIA_QUIZ_FENCE_EXAMPLE}",
                    "Correct answers are saved automatically. Never master on a wrong answer.",
                ]
            )
        else:
            lines.append("Correct answers are saved automatically. Never master on a wrong answer.")
        if just_correct or tries_exhausted or not retry_same:
            lines.extend(
                await _covered_quiz_prompt_lines(
                    session,
                    user_id,
                    project_id,
                    include_learning=True,
                    just_answered=answered_label or None,
                )
            )
        if retry_same or tries_exhausted:
            lines.extend(_format_missed_quiz_lines(items))
        return "\n".join(lines)
    if not _is_language_project(project):
        return ""
    items = await project_items_repo.list_for_user(
        session,
        user_id,
        project_id=project_id,
        limit=settings.project_item_inject_limit,
    )
    # Exclude the word they just got right / exhausted even if the session snapshot is briefly stale.
    quiz_pool = [
        i
        for i in items
        if _item_status(i) in ("new", "learning")
        and not (
            (just_correct or tries_exhausted)
            and answered_label
            and (i.content or "").strip().lower() == answered_label.lower()
        )
    ]
    level = project.level or "level1"
    if retry_same and answered_label:
        follow = (
            f'WRONG on "{answered_label}" (try {attempt}/{MAX_QUIZ_TRIES_PER_QUESTION}) — '
            "reply with brief feedback + a short hint only. "
            "Do NOT redisplay the question, choices, or a ```vocab_quiz fence."
        )
    elif tries_exhausted and answered_label:
        follow = (
            f'FAILED after {attempt} tries — "{answered_label}" stays learning for next time. '
            "Briefly reveal the correct answer, then continue with a DIFFERENT next word "
            "using a different learning format (teach→use, use→define, or MCQ):"
        )
    elif just_correct and answered_label:
        follow = (
            f'CORRECT — "{answered_label}" is done. Do NOT re-ask that word. '
            "Continue with a DIFFERENT next word using a different learning format:"
        )
    else:
        follow = (
            "After brief feedback, continue with the NEXT word using a learning format "
            "(teach→use, use→define, or occasional MCQ). Never repeat a mastered word."
        )
    lines = [
        f"Active vocabulary session — project: {project.title} ({_LEVEL_LABELS.get(level, level)}).",
        f"English skill: {_level_guidance(level)}",
        follow,
    ]
    if not retry_same:
        lines.extend(
            [
                VOCAB_LEARNING_FORMATS_BLOCK,
                "Pick words only from new/learning items at this level (except when re-asking a miss).",
                "On MCQ correct answers mastery is automatic; on open-ended correct answers, "
                "confirm clearly so project sync can record mastery. Never master on a wrong answer.",
            ]
        )
    else:
        lines.append("Correct answers are saved automatically. Never master on a wrong answer.")
    if quiz_pool and not retry_same:
        lines.append("\nNew/learning words available:")
        for item in quiz_pool[:40]:
            lines.append(f"- {item.content}")
    elif just_correct or tries_exhausted:
        lines.append(
            "\nNo new/learning words left in the pool — invent a NEW word at this level "
            "(not one already covered)."
        )
    if just_correct or tries_exhausted or not retry_same:
        lines.extend(
            await _covered_quiz_prompt_lines(
                session,
                user_id,
                project_id,
                include_learning=False,
                just_answered=answered_label or None,
            )
        )
    if retry_same or tries_exhausted:
        lines.extend(_format_missed_quiz_lines(items))
    return "\n".join(lines)


_VOCAB_QUESTION_MARKERS = re.compile(
    r"(?:"
    r"What does .+ mean\??|"
    r"Which sentence uses|"
    r"use .+ in a sentence|"
    r"write (?:your own |a )?sentence|"
    r"in your own words|"
    r"Reply with (?:the )?letter|"
    r"\bA\)\s|"
    r"\bB\)\s|"
    r"```vocab_quiz|"
    r"```vocab_card"
    r")",
    re.IGNORECASE,
)


def looks_like_vocab_question(content: str) -> bool:
    """Heuristic: prior assistant turn was asking a vocab/trivia question."""
    if not content or not content.strip():
        return False
    tail = content.strip()[-1200:]
    if _VOCAB_QUESTION_MARKERS.search(tail):
        return True
    if re.search(r"\*\*[^*\n]{2,40}\*\*", tail) and "?" in tail[-400:]:
        return True
    return False
