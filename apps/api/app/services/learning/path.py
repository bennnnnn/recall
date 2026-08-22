"""Ordered language-learning path (chapters = decks / list_title)."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from uuid import UUID

from app.models.orm import Project, ProjectItem
from app.models.schemas.projects import PathChapterProgress
from app.services.projects.common import (
    DEFAULT_LIST,
    _item_status,
    _list_key,
)

logger = logging.getLogger(__name__)

PATH_MIN_CHAPTERS = 8
PATH_MAX_CHAPTERS = 80
PATH_SEED_WORD_CAP = 10
CHAPTER_COMPLETE_RATIO = 0.8
CHAPTER_MIN_WORDS = 5


def is_unspecified_list(title: str) -> bool:
    return _list_key(title) in ("", _list_key(DEFAULT_LIST))


def normalize_path_titles(titles: Sequence[object]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in titles:
        if not isinstance(raw, str):
            continue
        title = raw.strip()[:200]
        if not title or is_unspecified_list(title):
            continue
        key = _list_key(title)
        if key in seen:
            continue
        seen.add(key)
        out.append(title)
    return out


def parse_learning_path(project: object) -> list[str]:
    raw = getattr(project, "learning_path", None)
    if not isinstance(raw, list):
        return []
    return normalize_path_titles(raw)


def chapter_is_complete(*, mastered: int, total: int, daily_goal: int) -> bool:
    min_total = min(max(daily_goal, 1), CHAPTER_MIN_WORDS)
    if total < min_total:
        return False
    return (mastered / total) >= CHAPTER_COMPLETE_RATIO


def build_path_progress(
    project: object,
    items: list[ProjectItem],
) -> list[PathChapterProgress]:
    from app.services.learning.daily import resolve_daily_goal

    path = parse_learning_path(project)
    if not path:
        return []
    daily_goal = resolve_daily_goal(project)
    project_id = getattr(project, "id", None)
    lang = (getattr(project, "target_language", None) or "en").strip().lower()
    from app.content.vocab_catalog import catalog_domain_by_title

    # Unfiltered lookup — chapter titles are globally unique per language, so a
    # title's domain never depends on the viewer's current level. Filtering this
    # by level (as opposed to filtering what's *in* the path, done separately in
    # path_seed.py) broke grouping for any pre-existing path with chapters below
    # the project's current level: those titles fell out of the level-filtered
    # lookup, and the `title` fallback below turned each one into its own
    # ungrouped top-level "domain" instead of nesting it under its real one.
    domain_by_title = catalog_domain_by_title(lang, include_sat=True)
    by_list: dict[str, list[ProjectItem]] = {}
    for item in items:
        item_project = getattr(item, "project_id", None)
        if project_id is not None and item_project not in (None, project_id):
            continue
        key = _list_key(getattr(item, "list_title", "") or DEFAULT_LIST)
        by_list.setdefault(key, []).append(item)
    progress: list[PathChapterProgress] = []
    for title in path:
        group = by_list.get(_list_key(title), [])
        mastered = sum(1 for item in group if _item_status(item) == "mastered")
        total = len(group)
        progress.append(
            PathChapterProgress(
                title=title,
                domain=domain_by_title.get(title.casefold(), title),
                mastered=mastered,
                total=total,
                complete=chapter_is_complete(mastered=mastered, total=total, daily_goal=daily_goal),
            )
        )
    return progress


def items_in_chapter(items: list[ProjectItem], chapter: str | None) -> list[ProjectItem]:
    """Filter items to one chapter; ``None`` keeps the full list."""
    if not chapter:
        return list(items)
    key = _list_key(chapter)
    return [
        item for item in items if _list_key(getattr(item, "list_title", "") or DEFAULT_LIST) == key
    ]


def up_next_chapter(project: object, items: list[ProjectItem]) -> str | None:
    progress = build_path_progress(project, items)
    for chapter in progress:
        if not chapter.complete:
            return chapter.title
    if progress:
        return progress[-1].title
    path = parse_learning_path(project)
    return path[0] if path else None


def sort_list_titles(titles: list[str], learning_path: list[str] | None) -> list[str]:
    path = normalize_path_titles(list(learning_path or []))
    if not path:
        return sorted(titles, key=str.casefold)
    order = {_list_key(title): index for index, title in enumerate(path)}
    return sorted(
        titles,
        key=lambda title: (order.get(_list_key(title), len(path)), title.casefold()),
    )


def append_chapter(project: Project, title: str) -> bool:
    if is_unspecified_list(title):
        return False
    path = parse_learning_path(project)
    if any(_list_key(existing) == _list_key(title) for existing in path):
        return False
    if len(path) >= PATH_MAX_CHAPTERS:
        return False
    path.append(title.strip()[:200])
    project.learning_path = path
    return True


def resolve_add_list_title(
    project: object,
    action_list_title: str,
    items: list[ProjectItem],
) -> str:
    title = (action_list_title or "").strip()
    if title and not is_unspecified_list(title):
        return title
    current = up_next_chapter(project, items)
    return current or DEFAULT_LIST


def format_path_prompt_lines(project: object, items: list[ProjectItem]) -> list[str]:
    path = parse_learning_path(project)
    if not path:
        return []
    progress = build_path_progress(project, items)
    lines = [
        "Learning path (teach in this order). Words are preloaded — do NOT invent or add new words."
    ]
    for chapter in progress:
        mark = "✓" if chapter.complete else "○"
        lines.append(f"- {mark} {chapter.title} ({chapter.mastered}/{chapter.total})")
    current = up_next_chapter(project, items)
    if current:
        lines.append(f"Teach only words listed under: {current}")
        lines.append("○ = not started, ◐ = learning, ✓ = done. Pick the next ○ or ◐ word.")
    return lines


async def enqueue_language_path_job(user_id: UUID, project_id: UUID) -> None:
    """Best-effort — never raise into create / chat sync."""
    try:
        from app.core import jobs
        from app.core.redis import get_redis_client

        await jobs.enqueue(
            get_redis_client(),
            "language_path",
            {"user_id": str(user_id), "project_id": str(project_id)},
            dedupe_key=f"language_path:{project_id}",
        )
    except Exception:
        logger.exception(
            "Failed to enqueue language_path job user_id=%s project_id=%s",
            user_id,
            project_id,
        )
