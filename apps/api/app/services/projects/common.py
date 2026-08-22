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


# Product surface: vocabulary (one project per target language).
LEARNING_PRODUCT_KINDS = frozenset({"language"})

# Same codes as mobile UI locales (`apps/mobile/lib/i18n/languages.ts`).
LEARNING_TARGET_LANGUAGES = frozenset({"en", "es"})

LANGUAGE_DISPLAY_NAMES: dict[str, str] = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "ru": "Russian",
    "tr": "Turkish",
    "am": "Amharic",
}

_LANGUAGE_TITLE_ALIASES: dict[str, str] = {
    "english": "en",
    "spanish": "es",
    "español": "es",
    "espanol": "es",
    "french": "fr",
    "français": "fr",
    "francais": "fr",
    "german": "de",
    "deutsch": "de",
    "italian": "it",
    "italiano": "it",
    "portuguese": "pt",
    "português": "pt",
    "portugues": "pt",
    "russian": "ru",
    "русский": "ru",
    "turkish": "tr",
    "türkçe": "tr",
    "turkce": "tr",
    "amharic": "am",
    "አማርኛ": "am",
}


LEARNING_KIND_ALIASES = {"vocabulary": "language"}


def normalize_target_language(code: str | None) -> str | None:
    """Return an allowlisted ISO 639-1 code, or None if missing/unknown."""
    if not isinstance(code, str):
        return None
    raw = code.strip().lower().replace("_", "-")
    if not raw:
        return None
    iso = raw.split("-", 1)[0]
    if iso in LEARNING_TARGET_LANGUAGES:
        return iso
    return None


def locale_language(locale: str | None) -> str:
    """Best-effort app-language code from a user locale (defaults to English)."""
    if not isinstance(locale, str):
        return "en"
    iso = locale.strip().lower().replace("_", "-").split("-", 1)[0]
    if iso in LANGUAGE_DISPLAY_NAMES:
        return iso
    return "en"


def language_display_name(code: str | None) -> str:
    iso = locale_language(code)
    return LANGUAGE_DISPLAY_NAMES[iso]


def infer_target_language(title: str, explicit: str | None = None) -> str:
    """Prefer an explicit allowlisted code; else infer from the project title."""
    normalized = normalize_target_language(explicit)
    if normalized:
        return normalized
    lowered = title.strip().lower()
    for alias, code in _LANGUAGE_TITLE_ALIASES.items():
        if alias in lowered and code in LEARNING_TARGET_LANGUAGES:
            return code
    return "en"


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
