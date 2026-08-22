"""Copy curated chapter words onto a language project."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.content.vocab_catalog import catalog_path_titles, decks_for_language, word_id
from app.services.learning.path import parse_learning_path
from app.services.projects.common import _is_language_project, _list_key

logger = logging.getLogger(__name__)

_CATALOG_LANGUAGES = frozenset({"en", "es"})


class _ProjectRow(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    level: str
    target_language: str
    native_language: str | None
    daily_goal: int | None
    learning_path: list[str]
    item_count: int


def needs_catalog_sync(project: object, items: Sequence[Any]) -> bool:
    lang = (getattr(project, "target_language", None) or "en").strip().lower()
    if lang not in _CATALOG_LANGUAGES:
        return False
    titles = catalog_path_titles(lang)
    if parse_learning_path(project) != titles:
        return True
    have_pairs = {
        (_list_key(getattr(item, "list_title", "")), _list_key(getattr(item, "content", "")))
        for item in items
    }
    for deck in decks_for_language(lang):
        for word in deck.words:
            if (_list_key(deck.title), _list_key(word.content)) not in have_pairs:
                return True
    return False


_STATUS_RANK = {"mastered": 2, "learning": 1, "new": 0}


async def _load_seed_row(project_id: UUID, user_id: UUID) -> _ProjectRow | None:
    from app.core.db import SessionLocal
    from app.repositories import project_items as project_items_repo
    from app.repositories import projects as projects_repo

    async with SessionLocal() as session:
        project = await projects_repo.get_by_id(session, project_id, user_id)
        if project is None or not _is_language_project(project):
            return None
        items = await project_items_repo.list_for_user(
            session, user_id, project_id=project_id, limit=2000
        )
        return _ProjectRow(
            id=project.id,
            user_id=project.user_id,
            title=project.title,
            level=project.level or "level1",
            target_language=project.target_language or "en",
            native_language=project.native_language,
            daily_goal=project.daily_goal,
            learning_path=parse_learning_path(project),
            item_count=len(items),
        )


async def seed_language_path(settings: Any, *, user_id: UUID, project_id: UUID) -> None:
    """Replace the path with catalog titles and insert missing words."""
    from app.core.db import SessionLocal
    from app.repositories import project_items as project_items_repo
    from app.repositories import projects as projects_repo
    from app.services.projects.common import _invalidate_home_for_user
    from app.services.projects.items import create_item

    del settings
    try:
        row = await _load_seed_row(project_id, user_id)
        if row is None:
            return
        lang = (row.target_language or "en").strip().lower()
        if lang not in _CATALOG_LANGUAGES:
            return
        decks = decks_for_language(lang)
        if not decks:
            return
        path = [deck.title for deck in decks]

        async with SessionLocal() as session:
            project = await projects_repo.get_by_id(session, project_id, user_id)
            if project is None or not _is_language_project(project):
                return
            existing = await project_items_repo.list_for_user(
                session, user_id, project_id=project_id, limit=2000
            )
            if not needs_catalog_sync(project, existing):
                return
            project.learning_path = path
            catalog_lists = {_list_key(title) for title in path}
            have_pairs = {
                (_list_key(item.list_title), _list_key(item.content)) for item in existing
            }
            leftovers: dict[str, Any] = {}
            leftover_ranks: dict[str, int] = {}
            for item in existing:
                content_key = _list_key(item.content)
                if not content_key or _list_key(item.list_title) in catalog_lists:
                    continue
                rank = _STATUS_RANK.get(item.status or "", 0)
                if content_key not in leftovers or rank > leftover_ranks.get(content_key, -1):
                    leftovers[content_key] = item
                    leftover_ranks[content_key] = rank
            for deck in decks:
                for word in deck.words:
                    pair = (_list_key(deck.title), _list_key(word.content))
                    if pair in have_pairs:
                        continue
                    leftover = leftovers.pop(_list_key(word.content), None)
                    if leftover is not None:
                        leftover.list_title = deck.title
                        have_pairs.add(pair)
                        continue
                    await create_item(
                        session,
                        user_id=user_id,
                        project_id=project_id,
                        content=word.content,
                        list_title=deck.title,
                        definition=word.definition,
                        example_sentence=word.example_sentence,
                        status="new",
                        catalog_entry_id=word_id(deck, word),
                        commit=False,
                    )
                    have_pairs.add(pair)
            await session.commit()
        await _invalidate_home_for_user(user_id)
    except Exception:
        logger.exception("language_path seed failed project_id=%s", project_id)
