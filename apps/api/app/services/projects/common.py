"""Shared project helpers and product-surface constants."""

from __future__ import annotations

import re
from uuid import UUID

from app.models.orm import Project, ProjectItem
from app.models.schemas import ProjectActionItem


async def _invalidate_home_for_user(user_id: UUID) -> None:
    """Home cards depend on project stats — bust cache after learning mutations."""
    from app.services import home as home_service

    await home_service.invalidate_home_cache(user_id)


DEFAULT_LIST = "General"


# Product surface: English vocabulary + general knowledge only.
LEARNING_PRODUCT_KINDS = frozenset({"language", "trivia"})


LEARNING_KIND_ALIASES = {"vocabulary": "language"}


def normalize_project_kind(kind: str) -> str:
    """Map write aliases (vocabulary → language); leave unknown kinds unchanged."""
    return LEARNING_KIND_ALIASES.get(kind, kind)


def is_learning_product_kind(kind: str) -> bool:
    return normalize_project_kind(kind) in LEARNING_PRODUCT_KINDS


def _resolve_list_title(project: Project, action: ProjectActionItem) -> str:
    return action.list_title.strip() or DEFAULT_LIST


def _item_status(item: ProjectItem) -> str:
    if item.status:
        return item.status
    return "mastered" if item.mastered else "new"


def _find_item_by_content(
    items: list[ProjectItem], project_id: UUID, content: str
) -> ProjectItem | None:
    needle = _normalize(content)
    for item in items:
        if item.project_id == project_id and _normalize(item.content) == needle:
            return item
    return None


def _is_language_project(project: Project) -> bool:
    return project.kind in ("language", "vocabulary")


def _is_trivia_project(project: Project) -> bool:
    return project.kind == "trivia"


def _trivia_daily_goal(project: Project) -> int:
    goal = getattr(project, "daily_goal", None)
    if isinstance(goal, int) and goal >= 1:
        return goal
    return DEFAULT_DAILY_VOCAB_GOAL


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _list_key(list_title: str) -> str:
    return _normalize(list_title or DEFAULT_LIST)


def _find_language_project(
    projects: list[Project],
    target_language: str = "en",
) -> Project | None:
    lang = (target_language or "en").strip().lower()
    for project in projects:
        if (
            _is_language_project(project)
            and (project.target_language or "en").strip().lower() == lang
        ):
            return project
    return None


def _find_project(projects: list[Project], title: str) -> Project | None:
    # BUG FIX (was silent): dropped the substring fallback (`needle in title
    # or title in needle`) — it could resolve a mutating action (delete/set_*
    # /add target, etc.) against the wrong project by title fragment (e.g.
    # "En" matching "English" when another project also existed). Exact
    # normalized-title match only now; the single-project fallback below
    # stays for when the title is blank/unmatched and there's just one
    # project it could mean.
    needle = _normalize(title)
    if needle:
        for project in projects:
            if _normalize(project.title) == needle:
                return project
    if len(projects) == 1:
        return projects[0]
    return None


def _find_item(
    items: list[ProjectItem],
    project_id: UUID,
    list_title: str,
    content: str,
    *,
    mastered_only: bool | None = None,
) -> ProjectItem | None:
    # BUG FIX (was silent): dropped the substring fallback (`needle in
    # content or content in needle`) after an exact-match miss. It let e.g.
    # "cat" match an existing "category" item — wrongly hitting
    # delete/master/unmaster/start_learning on the wrong word, and (via this
    # same function's use as the `add` dedup check) wrongly skipping "add
    # cat" as a duplicate of "category". Exact normalized match only, for
    # both target-resolution and dedup use — a fuzzy dedup silently dropping
    # a legitimately different word is worse than an occasional near-duplicate.
    needle = _normalize(content)
    list_norm = _list_key(list_title)
    candidates = [
        i for i in items if i.project_id == project_id and _list_key(i.list_title) == list_norm
    ]
    if mastered_only is True:
        candidates = [i for i in candidates if _item_status(i) == "mastered"]
    elif mastered_only is False:
        candidates = [i for i in candidates if _item_status(i) != "mastered"]
    if not candidates:
        candidates = [i for i in items if i.project_id == project_id]
    for item in candidates:
        if _normalize(item.content) == needle:
            return item
    return None


DEFAULT_DAILY_VOCAB_GOAL = 10


def _language_daily_goal(project: Project) -> int:
    goal = getattr(project, "daily_goal", None)
    if isinstance(goal, int) and goal >= 1:
        return goal
    return DEFAULT_DAILY_VOCAB_GOAL
