"""Project blocks injected into the chat system prompt."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.orm import Project, ProjectItem, User
from app.repositories import project_items as project_items_repo
from app.repositories import projects as projects_repo
from app.services.projects import stats as project_stats
from app.services.projects.common import (
    DEFAULT_LIST,
    _is_language_project,
    _is_trivia_project,
    _item_status,
    _language_daily_goal,
    _trivia_daily_goal,
)
from app.services.projects.prompts import (
    LANGUAGE_TUTOR_HINT,
    TRIVIA_TUTOR_HINT,
    _language_tutor_hint,
    _level_guidance,
    _quiz_mode_banner,
    _trivia_level_guidance,
    _trivia_tutor_hint,
)
from app.services.projects.quiz_context import (
    _covered_quiz_prompt_lines,
    _format_failed_review_lines,
)


def format_projects_block(projects: list[Project], items: list[ProjectItem]) -> str:
    if not projects:
        return ""
    by_project: dict[UUID, list[ProjectItem]] = {}
    for item in items:
        by_project.setdefault(item.project_id, []).append(item)

    lines = ["User learning topics (title, type, lists, and study progress):"]
    for project in sorted(projects, key=lambda p: p.title.casefold()):
        project_items = by_project.get(project.id, [])
        stats = _stats_for_items(project_items)
        desc = f" — {project.description}" if project.description else ""
        level = getattr(project, "level", "level1") or "level1"
        guidance = _level_guidance(level)
        meta = project.kind
        if _is_language_project(project):
            meta = f"{project.kind}, {level}"
        elif _is_trivia_project(project):
            meta = f"{project.kind}, topics={project.description or 'general'}"
        skill_line = ""
        if _is_language_project(project):
            skill_line = (
                f"English skill: {guidance}\n"
                f"Daily goal: {_language_daily_goal(project)} new words per session\n"
            )
        elif _is_trivia_project(project):
            skill_line = (
                f"Daily quiz goal: {_trivia_daily_goal(project)} correct answers per session\n"
                f"Topics: {project.description or 'general'}\n"
            )
        lines.append(
            f"\n### {project.title} ({meta}){desc}\n"
            f"{skill_line}"
            f"Progress: {stats['mastered_count']}/{stats['total']} mastered, "
            f"{stats['new_count']} new, {stats['learning_count']} learning, "
            f"{stats['added_this_week']} added this week, "
            f"{stats['due_for_review']} due for review"
        )
        if not project_items:
            lines.append("- (no words yet)")
            continue
        by_list: dict[str, list[ProjectItem]] = {}
        for item in project_items:
            lst = item.list_title.strip() or DEFAULT_LIST
            by_list.setdefault(lst, []).append(item)
        if _is_language_project(project):
            for list_title in sorted(by_list.keys(), key=str.casefold):
                lines.append(f"\n#### {list_title}")
                for item in by_list[list_title]:
                    lines.append(_format_vocab_line(item))
            continue
        for list_title in sorted(by_list.keys(), key=str.casefold):
            lines.append(f"\n#### {list_title}")
            for item in by_list[list_title]:
                mark = "✓" if item.mastered else "○"
                status = "mastered" if item.mastered else "learning"
                note_suffix = f' — e.g. "{item.note}"' if item.note else ""
                lines.append(f"- {mark} {item.content} ({status}{note_suffix})")
    return "\n".join(lines)


def _format_vocab_line(item: ProjectItem) -> str:
    status = _item_status(item)
    mark = "✓" if status == "mastered" else ("◐" if status == "learning" else "○")
    defn = f" — {item.definition}" if item.definition else ""
    example = item.example_sentence or item.note
    ex = f' e.g. "{example}"' if example else ""
    return f"- {mark} {item.content}{defn}{ex} ({status})"


def _stats_for_items(items: list[ProjectItem]) -> dict[str, int]:
    """Prompt-side project stats.

    Delegates to ``repositories.project_items.stats_from_items`` so the
    ``due_for_review`` count the model sees in the prompt matches the count
    the mobile UI renders from the API response. Previously this function
    reimplemented the logic with two divergences: it counted ``new`` items
    as due (the API does not), and it used ``last_reviewed_at`` for learning
    items where the API uses ``due_at`` if set (falling back to
    ``last_reviewed_at or created_at``). The mismatch meant the prompt
    claimed a different review queue than the app showed.
    """
    return project_stats.stats_from_items(items)


def _format_today_session_line(project: Project, stats: dict[str, int]) -> str:
    from app.services import daily_learning

    daily_goal = daily_learning.resolve_daily_goal(project)
    mastered_today = int(stats.get("mastered_today") or 0)
    missed_today = int(stats.get("missed_today") or 0)
    completed_today = mastered_today + missed_today
    remaining = max(0, daily_goal - completed_today)
    if completed_today >= daily_goal:
        return (
            f"**Today:** {completed_today}/{daily_goal} done — daily goal complete "
            f"({mastered_today} correct, {missed_today} failed). "
            "This is the authoritative progress line — do not restate or contradict it."
        )
    return (
        f"**Today:** {completed_today}/{daily_goal} done "
        f"({mastered_today} correct, {missed_today} failed; {remaining} more needed). "
        "This is the authoritative progress line — do not restate or contradict it."
    )


def _quiz_pool_items(items: list[ProjectItem]) -> tuple[list[ProjectItem], int]:
    pool = [i for i in items if _item_status(i) != "mastered"]
    return pool, len(items) - len(pool)


def _quiz_pool_note(project: Project, pool: list[ProjectItem], mastered_skip: int) -> str:
    if mastered_skip <= 0:
        return ""
    if pool:
        return (
            f"\n\n({mastered_skip} already-mastered items omitted above — do not re-quiz them "
            "in today's session unless the user asks for review.)"
        )
    if _is_trivia_project(project):
        topics = project.description or "general knowledge"
        return (
            "\n\n**Quiz pool:** all saved facts are mastered. Ask a **new** question from "
            f"topics ({topics}) — not a repeat of previously learned facts."
        )
    return (
        "\n\n**Quiz pool:** all saved words are mastered. Teach/quiz **new** words at the "
        "user's level toward today's goal."
    )


async def load_project_for_prompt(
    session: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    settings: Settings,
    *,
    quiz_mode: str | None = None,
    client_timezone: str | None = None,
) -> str:
    from app.repositories import users as users_repo
    from app.services import time_context as time_context_service

    project = await projects_repo.get_by_id(session, project_id, user_id)
    if project is None:
        return ""
    items = await project_items_repo.list_for_user(
        session,
        user_id,
        project_id=project_id,
        limit=settings.project_item_inject_limit,
    )
    display_items = items
    pool_note = ""
    if quiz_mode != "exam" and (_is_language_project(project) or _is_trivia_project(project)):
        pool, mastered_skip = _quiz_pool_items(items)
        if mastered_skip > 0:
            display_items = pool
            pool_note = _quiz_pool_note(project, pool, mastered_skip)
    block = format_projects_block([project], display_items)
    if pool_note:
        block = f"{block}{pool_note}"
    if _is_language_project(project) or _is_trivia_project(project):
        # Session start: inject the DB ledger ban list (not just "don't repeat").
        covered_lines = await _covered_quiz_prompt_lines(
            session,
            user_id,
            project_id,
            include_learning=_is_trivia_project(project),
        )
        if covered_lines:
            block = f"{block}{''.join(covered_lines)}"
        failed_lines = _format_failed_review_lines(items)
        if failed_lines:
            block = f"{block}{''.join(failed_lines)}"
    today_line = ""
    if _is_language_project(project) or _is_trivia_project(project):
        user = await users_repo.get_by_id(session, user_id)
        tz_name = time_context_service.effective_timezone(
            user.timezone if user else None,
            client_timezone,
        )
        stats = await project_stats.count_stats(
            session,
            project_id,
            user_id,
            timezone_name=tz_name,
        )
        today_line = _format_today_session_line(project, stats)
    if _is_language_project(project):
        hint = _language_tutor_hint(quiz_mode)
        if today_line:
            hint = f"{today_line}\n\n{hint}"
        block = f"{block}\n\n{hint}" if block else hint
    if _is_trivia_project(project):
        hint = _trivia_tutor_hint(quiz_mode)
        level_line = f"Trivia difficulty: {_trivia_level_guidance(project.level or 'level1')}"
        hint = f"{level_line}\n\n{hint}"
        if today_line:
            hint = f"{today_line}\n\n{hint}"
        block = f"{block}\n\n{hint}" if block else hint
    if block:
        block = (
            "This chat is linked to ONE learning topic — focus on it unless the user "
            f"explicitly asks about something else.\n\n"
            f"{_quiz_mode_banner(quiz_mode, kind=project.kind)}\n\n{block}"
        )
    return block


async def load_projects_for_prompt(
    session: AsyncSession,
    user_id: UUID,
    settings: Settings,
) -> str:
    projects = await projects_repo.list_for_user(
        session, user_id, limit=settings.project_inject_limit
    )
    if not projects:
        return ""
    project_ids = [p.id for p in projects]
    items = await project_items_repo.list_for_user(
        session,
        user_id,
        project_ids=project_ids,
        limit=settings.project_item_inject_limit,
    )
    block = format_projects_block(projects, items)
    if any(_is_language_project(p) for p in projects):
        block = f"{block}\n\n{LANGUAGE_TUTOR_HINT}" if block else LANGUAGE_TUTOR_HINT
    if any(_is_trivia_project(p) for p in projects):
        block = f"{block}\n\n{TRIVIA_TUTOR_HINT}" if block else TRIVIA_TUTOR_HINT
    return block


def _daily_learning_quiz_label(project: Project) -> tuple[str, str]:
    """Return (quiz_type_label, progress_unit) for prompt injection."""
    if _is_language_project(project):
        return "vocabulary quiz", "words mastered today"
    return "general knowledge quiz", "correct answers today"


async def load_daily_learning_summary_for_prompt(
    session: AsyncSession,
    user: User,
    settings: Settings,
    *,
    client_timezone: str | None = None,
) -> str:
    """Compact today-only stats for day-planning turns (not full word lists)."""
    from app.services import daily_learning
    from app.services import time_context as time_context_service

    projects = await projects_repo.list_for_user(
        session, user.id, limit=settings.project_inject_limit
    )
    tz_name = time_context_service.effective_timezone(user.timezone, client_timezone)
    learning_projects = [
        project
        for project in projects
        if _is_language_project(project) or _is_trivia_project(project)
    ]
    if not learning_projects:
        # Explicit empty state so the model does not invent 0/N quiz stats from
        # leftover memories after the user deleted their class.
        return (
            "Today's learning progress (local calendar day, authoritative):\n"
            "- No active learning class.\n"
            "Do not mention vocabulary quiz, general knowledge quiz, invent 0/N stats, "
            "or urge practice — even if older memories mention English learning."
        )
    stats_by_project = await project_stats.count_stats_by_project(
        session,
        [project.id for project in learning_projects],
        timezone_by_project={project.id: tz_name for project in learning_projects},
    )
    incomplete_lines: list[str] = []
    complete_lines: list[str] = []
    has_language = any(_is_language_project(p) for p in learning_projects)
    has_trivia = any(_is_trivia_project(p) for p in learning_projects)
    for project in learning_projects:
        stats = stats_by_project.get(project.id, {})
        total = int(stats.get("total") or 0)
        daily_goal = daily_learning.resolve_daily_goal(project)
        mastered_today = int(stats.get("mastered_today") or 0)
        missed_today = int(stats.get("missed_today") or 0)
        completed_today = mastered_today + missed_today
        quiz_label, _unit = _daily_learning_quiz_label(project)
        if completed_today >= daily_goal:
            complete_lines.append(
                f"- {project.title} ({quiz_label}): {completed_today}/{daily_goal} done "
                "— daily goal complete"
            )
            continue
        remaining = max(0, daily_goal - completed_today)
        if total == 0:
            status = f"not started — {remaining} left for today's {quiz_label}"
        elif completed_today == 0:
            status = f"not started — {remaining} left for today's {quiz_label}"
        else:
            status = f"{remaining} left for today's {quiz_label}"
        incomplete_lines.append(
            f"- {project.title} ({quiz_label}): {completed_today}/{daily_goal} done "
            f"({mastered_today} correct, {missed_today} failed; {status})"
        )
    absent: list[str] = []
    if not has_language:
        absent.append("vocabulary quiz")
    if not has_trivia:
        absent.append("general knowledge quiz")
    absent_rule = (
        f"Do not mention {' or '.join(absent)} — the user has no such class."
        if absent
        else "Only mention learning tracks listed above."
    )
    track_rule = f"Only mention learning tracks listed above. {absent_rule}"
    header = "Today's learning progress (local calendar day, authoritative):"
    if incomplete_lines:
        return f"{header}\n" + "\n".join(incomplete_lines) + f"\n{track_rule}"
    return f"{header}\n" + "\n".join(complete_lines) + f"\n{track_rule}"
