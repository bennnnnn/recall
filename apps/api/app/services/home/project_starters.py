"""Learning-project home starters and highlight card."""

from __future__ import annotations

from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Project
from app.models.schemas import HomeProjectHighlight, HomeStarter, ProjectStats
from app.repositories import project_items as project_items_repo
from app.repositories import projects as projects_repo
from app.services import daily_learning, learning_insights
from app.services.home.util import CompletedDaily, ProjectHomeContent
from app.services.projects import stats as project_stats


def is_language_project(project: Project) -> bool:
    return project.kind in ("language", "vocabulary")


def is_trivia_project(project: Project) -> bool:
    return project.kind == "trivia"


def is_daily_home_project(project: Project) -> bool:
    return is_language_project(project) or is_trivia_project(project)


def daily_home_kind(project: Project) -> Literal["language", "trivia"]:
    return "trivia" if is_trivia_project(project) else "language"


def project_progress_line(project: Project, stats: ProjectStats) -> str:
    if is_language_project(project):
        if stats.total == 0:
            return "I have no words yet — help me add some first."
        return (
            f"{stats.mastered_count} mastered, {stats.new_count} new, "
            f"{stats.learning_count} learning, {stats.due_for_review} due for review."
        )
    if is_trivia_project(project):
        if stats.total == 0:
            return "I have not answered any trivia questions yet."
        return (
            f"{stats.mastered_count} facts learned, {stats.mastered_today} correct today, "
            f"{stats.learning_count} still learning."
        )
    if stats.total == 0:
        return "I have not started this project yet."
    return f"I have {stats.total} items tracked on this project."


def completed_today(stats: ProjectStats) -> int:
    return max(0, int(stats.mastered_today) + int(getattr(stats, "missed_today", 0) or 0))


def project_chip_label(project: Project, stats: ProjectStats) -> str:
    title = project.title.strip()
    if is_daily_home_project(project):
        daily_goal = daily_learning.resolve_daily_goal(project)
        completed = completed_today(stats)
        if completed >= daily_goal:
            return ""
        if stats.total == 0 or completed == 0:
            return f"Start {title}"[:48]
        return f"Continue {title}"[:48]
    if stats.total == 0:
        return f"Start {title}"[:48]
    return f"Continue {title}"[:48]


def project_starters(project: Project, stats: ProjectStats) -> list[HomeStarter]:
    title = project.title.strip()
    goal = (
        f" Goal: {project.description.strip()}."
        if project.description and project.description.strip()
        else ""
    )
    progress = project_progress_line(project, stats)
    label = project_chip_label(project, stats)

    if is_language_project(project):
        daily_goal = daily_learning.resolve_daily_goal(project)
        completed = completed_today(stats)
        if completed >= daily_goal:
            return []
        remaining = max(0, daily_goal - completed)
        if stats.total == 0:
            prompt = (
                f'Help me start my "{title}" vocabulary project.{goal} '
                "Suggest how to add my first words and a simple first session."
            )
        elif completed == 0:
            prompt = (
                f'Help me start today\'s "{title}" vocabulary session.{goal} {progress} '
                f"My daily goal is {daily_goal} words. One word at a time — mix teach→use "
                "(vocab_card then a sentence), use→define (sentence then open definition), "
                "and occasional A-D ```vocab_quiz. "
                "Start with words I failed recently (learning), then due for review, then new."
            )
        elif stats.due_for_review > 0 or stats.learning_count > 0:
            prompt = (
                f'Help me review my "{title}" vocabulary.{goal} {progress} '
                f"I still need {remaining} more today to hit my daily goal of "
                f"{daily_goal}. Practice failed/learning words first with mixed learning "
                "formats (teach→use, use→define, occasional MCQ) — do not add fresh words yet."
            )
        else:
            prompt = (
                f'Help me with my "{title}" vocabulary.{goal} {progress} '
                f"I need {remaining} more today (daily goal: {daily_goal}). "
                "Practice my new and learning words first with mixed learning formats "
                "(teach→use, use→define, occasional MCQ) — only add fresh words if I still "
                "need them for today's goal."
            )
    elif is_trivia_project(project):
        daily_goal = daily_learning.resolve_daily_goal(project)
        completed = completed_today(stats)
        if completed >= daily_goal:
            return []
        remaining = max(0, daily_goal - completed)
        if stats.total == 0:
            prompt = (
                f'Start my daily "{title}" general-knowledge session.{goal} '
                f"Quiz me in chat — one multiple-choice ```vocab_quiz at a time "
                f"(A-D only, no open-ended), {daily_goal} today. Begin now."
            )
        elif completed == 0:
            prompt = (
                f'Start my daily "{title}" general-knowledge session.{goal} {progress} '
                f"Quiz me with multiple-choice ```vocab_quiz only until {daily_goal} done today. "
                "Start with questions I failed recently, then new ones."
            )
        else:
            prompt = (
                f'Continue my daily "{title}" session.{goal} {progress} '
                f"I need {remaining} more today (daily goal: {daily_goal}). "
                "Ask the next multiple-choice ```vocab_quiz — prioritize failed/learning first."
            )
    else:
        # Legacy kinds (programming / general / …) are not product surfaces.
        return []

    return [
        HomeStarter(
            text=label,
            prompt=prompt,
            kind="project",
        ),
    ]


def project_subtitle(
    project: Project,
    stats: ProjectStats,
    *,
    seed: int,
    has_highlight: bool,
) -> str | None:
    if has_highlight:
        return None
    title = project.title.strip()
    if is_language_project(project):
        if stats.total == 0:
            return f'Start building your "{title}" word list.'
        if stats.due_for_review > 0:
            variants = [
                (
                    f'You have {stats.total} words in "{title}" — '
                    f"{stats.due_for_review} ready to review."
                ),
                f'{stats.due_for_review} words in "{title}" are due for review.',
                f'Review time — {stats.due_for_review} of {stats.total} words in "{title}".',
            ]
            return variants[seed % len(variants)]
        return f'You have {stats.total} words in "{title}" — ready to practice?'
    if is_trivia_project(project):
        daily_goal = daily_learning.resolve_daily_goal(project)
        if stats.total == 0:
            return f'Start your daily "{title}" quiz.'
        if stats.mastered_today > 0:
            return f'{stats.mastered_today}/{daily_goal} correct on "{title}" today — keep going?'
        return f'Ready for today\'s "{title}" quiz?'
    if stats.total > 0:
        return f'Pick up your "{title}" project?'
    return None


def project_highlight(
    project: Project,
    stats: ProjectStats,
    *,
    home_tz: ZoneInfo,
    project_items: list | None = None,
) -> HomeProjectHighlight | None:
    if not is_daily_home_project(project):
        return None
    daily_goal = daily_learning.resolve_daily_goal(project)
    cue = daily_learning.daily_home_cue(
        total=stats.total,
        mastered_today=stats.mastered_today,
        missed_today=int(getattr(stats, "missed_today", 0) or 0),
        pending_today=stats.pending_today,
        learning_count=stats.learning_count,
        due_for_review=stats.due_for_review,
        daily_goal=daily_goal,
        last_mastery=stats.last_mastery_at,
        home_tz=home_tz,
    )
    if cue is None:
        return None
    enriched = learning_insights.enrich_learning_stats(
        stats.model_dump(),
        project=project,
        items=project_items or [],
        timezone_name=str(home_tz.key),
        daily_history=daily_learning.build_daily_history(
            project_items or [],
            timezone_name=str(home_tz.key),
            daily_goal=daily_goal,
            active_since=project.created_at,
            daily_goal_history=daily_learning.ensure_daily_goal_history(
                project,
                project_items or [],
                timezone_name=str(home_tz.key),
            ),
        )
        if project_items
        else None,
    )
    return HomeProjectHighlight(
        project_id=project.id,
        title=project.title.strip(),
        kind=daily_home_kind(project),
        daily_goal=daily_goal,
        mastered_today=stats.mastered_today,
        missed_today=int(getattr(stats, "missed_today", 0) or 0),
        cue=cue,
        streak_days=int(enriched.get("streak_days") or 0),
        days_inactive=enriched.get("days_inactive"),
        due_for_review=stats.due_for_review,
        suggested_level=enriched.get("suggested_level"),
    )


async def load_project_home_content(
    session: AsyncSession,
    user_id: UUID,
    *,
    seed: int,
    home_tz: ZoneInfo,
) -> ProjectHomeContent:
    projects = await projects_repo.list_for_user(session, user_id, limit=20)
    if not projects:
        return ProjectHomeContent([], None, None, [])

    daily_projects = sorted(
        [p for p in projects if is_daily_home_project(p)],
        key=lambda p: (0 if is_language_project(p) else 1, p.title.casefold()),
    )
    tz_name = str(home_tz.key)

    if daily_projects:
        project_ids = [candidate.id for candidate in daily_projects]
        # One item fetch for all daily projects — reuse for stats + highlight enrich.
        all_items = await project_items_repo.list_for_projects(session, project_ids)
        items_by_project: dict[UUID, list] = {pid: [] for pid in project_ids}
        for row in all_items:
            items_by_project.setdefault(row.project_id, []).append(row)
        stats_by_project = {
            pid: project_stats.stats_from_items(
                items_by_project.get(pid, []),
                timezone_name=tz_name,
            )
            for pid in project_ids
        }
        completed_daily: list[CompletedDaily] = []
        for candidate in daily_projects:
            stats = ProjectStats.model_validate(stats_by_project.get(candidate.id, {}))
            daily_goal = daily_learning.resolve_daily_goal(candidate)
            if completed_today(stats) >= daily_goal:
                completed_daily.append((candidate.title.strip(), daily_home_kind(candidate)))
                continue
            # Cue can be decided from stats alone; only enrich the first highlight.
            cue = daily_learning.daily_home_cue(
                total=stats.total,
                mastered_today=stats.mastered_today,
                missed_today=int(getattr(stats, "missed_today", 0) or 0),
                pending_today=stats.pending_today,
                learning_count=stats.learning_count,
                due_for_review=stats.due_for_review,
                daily_goal=daily_goal,
                last_mastery=stats.last_mastery_at,
                home_tz=home_tz,
            )
            if cue is None:
                continue
            project_items = items_by_project.get(candidate.id, [])
            highlight = project_highlight(
                candidate,
                stats,
                home_tz=home_tz,
                project_items=project_items,
            )
            if highlight is not None:
                starters: list[HomeStarter] = []
                subtitle = project_subtitle(
                    candidate,
                    stats,
                    seed=seed,
                    has_highlight=True,
                )
                return ProjectHomeContent(starters, subtitle, highlight, completed_daily)
        return ProjectHomeContent([], None, None, completed_daily)

    # No English/trivia daily cue — do not fall back to legacy project kinds
    # (old programming topics used to show up as "Continue TypeScript · …").
    return ProjectHomeContent([], None, None, [])
