"""Reconcile curated chapter content while retaining each learner's progress."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Sequence
from dataclasses import asdict
from functools import lru_cache
from typing import Any
from uuid import UUID

from app.content.vocab_catalog import path_decks_for_language
from app.services.learning.catalog_items import plan_catalog_changes
from app.services.learning.catalog_sync import ensure_catalog_rows
from app.services.learning.path import parse_learning_path

logger = logging.getLogger(__name__)
_CATALOG_LANGUAGES = frozenset({"en", "es"})


@lru_cache(maxsize=1)
def catalog_seed_revision() -> str:
    """Keep old successful jobs from suppressing a changed catalog for 24 hours."""
    content = [
        asdict(deck)
        for language in sorted(_CATALOG_LANGUAGES)
        for deck in path_decks_for_language(language)
    ]
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()[:16]


def apply_full_catalog_path(project: object) -> list[str]:
    """Put every catalog chapter on the lesson map. Returns the titles used."""
    lang = (getattr(project, "target_language", None) or "en").strip().lower()
    if lang not in _CATALOG_LANGUAGES:
        return parse_learning_path(project)
    titles = [deck.title for deck in path_decks_for_language(lang)]
    project_any: Any = project
    project_any.learning_path = titles
    return titles


def needs_catalog_sync(project: object, items: Sequence[Any]) -> bool:
    lang = (getattr(project, "target_language", None) or "en").strip().lower()
    if lang not in _CATALOG_LANGUAGES:
        return False
    decks = path_decks_for_language(lang)
    return parse_learning_path(project) != [deck.title for deck in decks] or bool(
        plan_catalog_changes(decks, items)
    )


async def seed_language_path(settings: Any, *, user_id: UUID, project_id: UUID) -> None:
    """Commit content-only reconciliation, then invalidate dependent caches."""
    from app.core.db import SessionLocal
    from app.repositories import learning_catalog as catalog_repo
    from app.services.projects.common import _invalidate_home_for_user

    del settings
    try:
        async with SessionLocal() as session:
            project = await catalog_repo.lock_project(session, project_id, user_id)
            if project is None:
                return
            lang = (project.target_language or "en").strip().lower()
            if lang not in _CATALOG_LANGUAGES:
                return
            decks = path_decks_for_language(lang)
            if not decks:
                return
            existing = await catalog_repo.list_items(session, project_id, user_id)
            path = [deck.title for deck in decks]
            changes = plan_catalog_changes(decks, existing)
            if changes or parse_learning_path(project) != path:
                await ensure_catalog_rows(session)
                await catalog_repo.update_contents(
                    session,
                    user_id=user_id,
                    project_id=project_id,
                    changes=[
                        (change.item, change.values)
                        for change in changes
                        if change.item is not None
                    ],
                )
                await catalog_repo.insert_missing(
                    session,
                    user_id=user_id,
                    project_id=project_id,
                    rows=[change.values for change in changes if change.item is None],
                )
                project.learning_path = path
                await session.commit()
        # A previous attempt may have committed before cache invalidation failed.
        await _invalidate_home_for_user(user_id)
    except Exception:
        logger.exception("language_path seed failed project_id=%s", project_id)
        raise
