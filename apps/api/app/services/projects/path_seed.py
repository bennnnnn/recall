"""Background seed for a language project's ordered path + first lesson."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.services.projects.common import (
    _is_language_project,
    _list_key,
    language_display_name,
    locale_language,
)
from app.services.projects.path import (
    PATH_MAX_CHAPTERS,
    PATH_MIN_CHAPTERS,
    PATH_SEED_WORD_CAP,
    normalize_path_titles,
    parse_learning_path,
    starter_path_for_level,
)

logger = logging.getLogger(__name__)


class LanguagePathWord(BaseModel):
    content: str = Field(min_length=1, max_length=100)
    definition: str = Field(min_length=1, max_length=500)
    example_sentence: str | None = Field(default=None, max_length=500)


class LanguagePathSeedResult(BaseModel):
    chapters: list[str] = Field(min_length=6, max_length=PATH_MAX_CHAPTERS)
    first_chapter_words: list[LanguagePathWord] = Field(default_factory=list, max_length=10)


class _ProjectRow(BaseModel):
    """Local load so the LLM call does not hold a DB connection."""

    id: UUID
    user_id: UUID
    title: str
    level: str
    target_language: str
    native_language: str | None
    daily_goal: int | None
    learning_path: list[str]
    first_chapter_word_count: int


async def _load_seed_row(project_id: UUID, user_id: UUID) -> _ProjectRow | None:
    from app.core.db import SessionLocal
    from app.repositories import project_items as project_items_repo
    from app.repositories import projects as projects_repo

    async with SessionLocal() as session:
        project = await projects_repo.get_by_id(session, project_id, user_id)
        if project is None or not _is_language_project(project):
            return None
        items = await project_items_repo.list_for_user(
            session, user_id, project_id=project_id, limit=500
        )
        path = parse_learning_path(project)
        first = path[0] if path else None
        first_count = 0
        if first:
            first_key = _list_key(first)
            first_count = sum(1 for item in items if _list_key(item.list_title) == first_key)
        return _ProjectRow(
            id=project.id,
            user_id=project.user_id,
            title=project.title,
            level=project.level or "level1",
            target_language=project.target_language or "en",
            native_language=project.native_language,
            daily_goal=project.daily_goal,
            learning_path=path,
            first_chapter_word_count=first_count,
        )


async def _suggest_language_path(
    settings: Any,
    row: _ProjectRow,
    *,
    locale: str,
) -> LanguagePathSeedResult | None:
    from app.gateways import litellm_gateway, mock_llm

    if mock_llm.should_mock_llm(settings):
        return None
    target = language_display_name(row.target_language)
    native = language_display_name(row.native_language or locale)
    word_n = min(row.daily_goal or PATH_SEED_WORD_CAP, PATH_SEED_WORD_CAP)
    messages = [
        {
            "role": "system",
            "content": (
                "Design a short vocabulary learning path. Return ONLY JSON: "
                '{"chapters":["..."],"first_chapter_words":['
                '{"content":"word","definition":"meaning","example_sentence":"sentence"}]} '
                f"chapters: {PATH_MIN_CHAPTERS}–{PATH_MAX_CHAPTERS} ordered lesson titles "
                f"in the user's app language ({locale}). "
                f"first_chapter_words: {word_n} beginner-appropriate {target} words "
                f"with definitions in {native}. No duplicates. No lesson essays."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Target language: {target} ({row.target_language}). "
                f"Level: {row.level}. Project: {row.title}."
            ),
        },
    ]
    try:
        return await litellm_gateway.complete_structured(
            settings=settings,
            model_alias="memory-model",
            messages=messages,
            schema=LanguagePathSeedResult,
            max_tokens=768,
        )
    except Exception:
        logger.exception("language_path LLM failed project_id=%s", row.id)
        return None


async def seed_language_path(settings: Any, *, user_id: UUID, project_id: UUID) -> None:
    """Set learning_path and seed the first chapter. Never raise into the worker."""
    from app.core.db import SessionLocal
    from app.repositories import project_items as project_items_repo
    from app.repositories import projects as projects_repo
    from app.repositories import users as users_repo
    from app.services.daily_learning import resolve_daily_goal
    from app.services.projects.common import _invalidate_home_for_user
    from app.services.projects.items import create_item

    try:
        row = await _load_seed_row(project_id, user_id)
        if row is None:
            return
        if row.learning_path and row.first_chapter_word_count > 0:
            return

        locale = "en"
        async with SessionLocal() as session:
            user = await users_repo.get_by_id(session, user_id)
            locale = locale_language(getattr(user, "locale", None) if user else None)

        suggested: LanguagePathSeedResult | None = None
        if not row.learning_path:
            suggested = await _suggest_language_path(settings, row, locale=locale)

        path = row.learning_path or (
            normalize_path_titles(suggested.chapters)
            if suggested is not None
            else starter_path_for_level(row.level)
        )
        if len(path) < PATH_MIN_CHAPTERS and not row.learning_path:
            path = starter_path_for_level(row.level)
        words = (
            suggested.first_chapter_words if suggested is not None and not row.learning_path else []
        )

        async with SessionLocal() as session:
            project = await projects_repo.get_by_id(session, project_id, user_id)
            if project is None or not _is_language_project(project):
                return
            if not parse_learning_path(project):
                project.learning_path = path
            current_path = parse_learning_path(project) or path
            first = current_path[0] if current_path else None
            if first and words:
                existing = await project_items_repo.list_for_user(
                    session, user_id, project_id=project_id, limit=200
                )
                first_key = _list_key(first)
                have = {
                    _list_key(item.content)
                    for item in existing
                    if _list_key(item.list_title) == first_key
                }
                goal = min(resolve_daily_goal(project), PATH_SEED_WORD_CAP)
                added = len(have)
                for word in words:
                    if added >= goal:
                        break
                    key = _list_key(word.content)
                    if key in have:
                        continue
                    await create_item(
                        session,
                        user_id=user_id,
                        project_id=project_id,
                        content=word.content.strip(),
                        list_title=first,
                        definition=word.definition.strip(),
                        example_sentence=(word.example_sentence or "").strip() or None,
                        status="new",
                        commit=False,
                    )
                    have.add(key)
                    added += 1
            await session.commit()
        await _invalidate_home_for_user(user_id)
    except Exception:
        logger.exception("language_path seed failed project_id=%s", project_id)
