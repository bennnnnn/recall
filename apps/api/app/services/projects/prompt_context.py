"""Project blocks injected into the chat system prompt."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.orm import Project, ProjectItem, User
from app.models.schemas.projects import PathChapterProgress
from app.repositories import project_items as project_items_repo
from app.repositories import projects as projects_repo
from app.services.learning.path import (
    build_path_progress,
    format_path_prompt_lines,
    items_in_chapter,
    parse_learning_path,
    sort_list_titles,
    up_next_chapter,
)
from app.services.projects import stats as project_stats
from app.services.projects.common import (
    DEFAULT_LIST,
    _is_language_project,
    _item_status,
    _language_daily_goal,
    _list_key,
    language_display_name,
)
from app.services.projects.prompts import (
    CHAT_LEARNING_HANDOFF_HINT,
    _language_tutor_hint,
    _quiz_mode_banner,
)
from app.services.projects.quiz_context import (
    _format_covered_quiz_lines,
    _format_failed_review_lines,
)

# Progress reads need the full catalog; prompt inject must not dump it.
_PROGRESS_ITEM_LIMIT = 2000


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
        meta = project.kind
        skill_line = ""
        if _is_language_project(project):
            name = language_display_name(project.target_language)
            skill_line = f"Daily goal: {_language_daily_goal(project)} new words per session\n"
            # LANG-TEACH-007/008: tell the model which language to teach and
            # which language the user speaks natively so explanations use
            # the right contrast language.
            native_lang = getattr(project, "native_language", None)
            if native_lang:
                skill_line += (
                    f"The user is a {language_display_name(native_lang)} speaker "
                    f"learning {name}. Give brief explanations in the user's "
                    f"native language when helpful, but teach words, examples, "
                    f"and quizzes in {name}.\n"
                )
            else:
                skill_line += (
                    f"Teach {name} vocabulary. Use {name} for words, examples, "
                    f"and quizzes; use English for brief explanations when helpful.\n"
                )
        lines.append(
            f"\n### {project.title} (id={project.id}, {meta}){desc}\n"
            f"{skill_line}"
            f"Progress: {stats['mastered_count']}/{stats['total']} mastered, "
            f"{stats['new_count']} new, {stats['learning_count']} learning, "
            f"{stats['added_this_week']} added this week, "
            f"{stats['due_for_review']} due for review"
        )
        if _is_language_project(project):
            path_lines = format_path_prompt_lines(project, project_items)
            if path_lines:
                lines.extend(path_lines)
        if not project_items:
            lines.append("- (no words yet)")
            continue
        by_list: dict[str, list[ProjectItem]] = {}
        for item in project_items:
            lst = item.list_title.strip() or DEFAULT_LIST
            by_list.setdefault(lst, []).append(item)
        if _is_language_project(project):
            path = parse_learning_path(project)
            for list_title in sort_list_titles(list(by_list.keys()), path):
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


def format_path_overview_lines(project: object, items: list[ProjectItem]) -> list[str]:
    """Domain + current-domain branch checkmarks — no lemmas."""
    progress = build_path_progress(project, items)
    if not progress:
        return []
    current = up_next_chapter(project, items)
    current_key = _list_key(current) if current else ""
    grouped: list[tuple[str, list[PathChapterProgress]]] = []
    for chapter in progress:
        domain = (getattr(chapter, "domain", None) or chapter.title).strip() or chapter.title
        if grouped and grouped[-1][0].casefold() == domain.casefold():
            grouped[-1][1].append(chapter)
        else:
            grouped.append((domain, [chapter]))
    lines = ["Learning path (progress only — no word list). Do NOT invent or add words."]
    for domain, chapters in grouped:
        mastered = sum(int(chapter.mastered) for chapter in chapters)
        total = sum(int(chapter.total) for chapter in chapters)
        complete = bool(chapters) and all(chapter.complete for chapter in chapters)
        mark = "✓" if complete else "○"
        lines.append(f"- {mark} {domain} ({mastered}/{total})")
        in_current = any(_list_key(chapter.title) == current_key for chapter in chapters)
        if in_current:
            for chapter in chapters:
                cmark = "✓" if chapter.complete else "○"
                lines.append(f"  - {cmark} {chapter.title} ({chapter.mastered}/{chapter.total})")
    if current:
        lines.append(f"Current chapter: {current}")
    return lines


def format_learning_overview_block(projects: list[Project], items: list[ProjectItem]) -> str:
    """Main-chat Learning inject: class + path checkmarks, no catalog dump."""
    if not projects:
        return ""
    by_project: dict[UUID, list[ProjectItem]] = {}
    for item in items:
        by_project.setdefault(item.project_id, []).append(item)

    lines = ["User learning classes (progress only — answer from this, do not dump it):"]
    for project in sorted(projects, key=lambda p: p.title.casefold()):
        project_items = by_project.get(project.id, [])
        stats = _stats_for_items(project_items)
        desc = f" — {project.description}" if project.description else ""
        meta = project.kind
        skill_line = ""
        if _is_language_project(project):
            skill_line = f"Daily goal: {_language_daily_goal(project)} new words per session\n"
        lines.append(
            f"\n### {project.title} (id={project.id}, {meta}){desc}\n"
            f"{skill_line}"
            f"Progress: {stats['mastered_count']}/{stats['total']} mastered, "
            f"{stats['new_count']} new, {stats['learning_count']} learning, "
            f"{stats['due_for_review']} due for review"
        )
        if _is_language_project(project):
            path_lines = format_path_overview_lines(project, project_items)
            if path_lines:
                lines.extend(path_lines)
        elif not project_items:
            lines.append("- (no words yet)")
    return "\n".join(lines)


def format_current_chapter_block(project: Project, items: list[ProjectItem]) -> str:
    """Project-chat inject: current chapter ○/◐ words only."""
    current = up_next_chapter(project, items)
    chapter_items = items_in_chapter(items, current)
    pool, mastered_skip = _quiz_pool_items(chapter_items)
    lines = [
        f"### {project.title} (id={project.id})",
    ]
    if current:
        lines.append(f"Now: {current} — teach only these words. Do NOT invent or add words.")
    else:
        lines.append("Teach only the words listed below. Do NOT invent or add words.")
    path_lines = format_path_overview_lines(project, items)
    if path_lines:
        lines.extend(path_lines)
    if not pool:
        if mastered_skip > 0:
            lines.append("- (this chapter is mastered — review a due word or say it is complete)")
        else:
            lines.append("- (no words yet)")
        return "\n".join(lines)
    lines.append(f"\n#### {current or DEFAULT_LIST}")
    for item in pool:
        lines.append(_format_vocab_line(item))
    if mastered_skip > 0:
        lines.append(
            f"({mastered_skip} already-mastered words in this chapter omitted — "
            "do not re-quiz them unless the user asks for review.)"
        )
    return "\n".join(lines)


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
        limit=max(settings.project_item_inject_limit, _PROGRESS_ITEM_LIMIT),
    )
    if _is_language_project(project):
        block = format_current_chapter_block(project, items)
        current = up_next_chapter(project, items)
        chapter_items = items_in_chapter(items, current)
        covered = [
            (item.content or "").strip()
            for item in chapter_items
            if _item_status(item) == "mastered" and (item.content or "").strip()
        ]
        covered_lines = _format_covered_quiz_lines(
            covered,
            max_chars=settings.quiz_exclusion_max_chars,
        )
        if covered_lines:
            block = f"{block}{''.join(covered_lines)}"
        failed_lines = _format_failed_review_lines(items)
        if failed_lines:
            block = f"{block}{''.join(failed_lines)}"
    else:
        block = format_projects_block([project], items)
    today_line = ""
    if _is_language_project(project):
        user = await users_repo.get_by_id(session, user_id)
        tz_name = time_context_service.effective_timezone(
            user.timezone if user else None,
            client_timezone,
        )
        stats = project_stats.stats_from_items(items, timezone_name=tz_name)
        today_line = _format_today_session_line(project, stats)
    if _is_language_project(project):
        hint = _language_tutor_hint(quiz_mode, target_language=project.target_language)
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
        limit=max(settings.project_item_inject_limit, _PROGRESS_ITEM_LIMIT),
    )
    block = format_learning_overview_block(projects, items)
    if block:
        block = f"{block}\n\n{CHAT_LEARNING_HANDOFF_HINT}"
    return block


def _daily_learning_quiz_label(project: Project) -> tuple[str, str]:
    """Return (quiz_type_label, progress_unit) for prompt injection."""
    return "vocabulary quiz", "words mastered today"


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
    learning_projects = [project for project in projects if _is_language_project(project)]
    if not learning_projects:
        # Explicit empty state so the model does not invent 0/N quiz stats from
        # leftover memories after the user deleted their class.
        return (
            "Today's learning progress (local calendar day, authoritative):\n"
            "- No active learning class.\n"
            "Do not mention vocabulary quiz, invent 0/N stats, "
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


_TODAY_WORDS_ACCESS_HINT = (
    "You ARE connected to the user's Recall Learning class. Answer from this list. "
    "Never say you are not connected to their learning app or data."
)


def _today_local_date(timezone_name: str) -> date:
    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        tz = ZoneInfo("UTC")
    return datetime.now(UTC).astimezone(tz).date()


def _format_today_word_names(items: list[ProjectItem]) -> str:
    names = [item.content.strip() for item in items if (item.content or "").strip()]
    return ", ".join(names)


async def load_today_learning_words_for_prompt(
    session: AsyncSession,
    user: User,
    settings: Settings,
    *,
    client_timezone: str | None = None,
) -> str:
    """Today's mastered and missed lemmas — for 'what did I learn today'."""
    from app.core.learning_policy import day_bounds_utc
    from app.services import time_context as time_context_service

    projects = await projects_repo.list_for_user(
        session, user.id, limit=settings.project_inject_limit
    )
    learning_projects = [project for project in projects if _is_language_project(project)]
    header = "Words from today's session (authoritative):"
    if not learning_projects:
        return (
            f"{header}\n"
            "- No active learning class — do not invent words they studied.\n"
            f"{_TODAY_WORDS_ACCESS_HINT}"
        )

    tz_name = time_context_service.effective_timezone(user.timezone, client_timezone)
    start, end = day_bounds_utc(_today_local_date(tz_name), tz_name)
    lines = [header, _TODAY_WORDS_ACCESS_HINT]
    any_words = False
    for project in learning_projects:
        mastered = await project_items_repo.list_by_activity_date(
            session,
            user.id,
            project.id,
            start=start,
            end=end,
        )
        missed = await project_items_repo.list_missed_by_activity_date(
            session,
            user.id,
            project.id,
            start=start,
            end=end,
        )
        mastered_names = _format_today_word_names(mastered)
        missed_names = _format_today_word_names(missed)
        if not mastered_names and not missed_names:
            lines.append(f"- {project.title}: no words practiced today yet.")
            continue
        any_words = True
        parts: list[str] = []
        if mastered_names:
            parts.append(f"learned/mastered: {mastered_names}")
        if missed_names:
            parts.append(f"still learning (missed): {missed_names}")
        lines.append(f"- {project.title}: {'; '.join(parts)}")
    if not any_words:
        lines.append(
            "If they ask what they learned today, say they have not practiced any words yet today."
        )
    return "\n".join(lines)
