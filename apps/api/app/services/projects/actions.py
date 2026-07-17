"""Apply LLM-extracted or explicit project/item mutations."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Project, ProjectItem
from app.models.schemas import ProjectActionItem
from app.repositories import project_items as project_items_repo
from app.repositories import projects as projects_repo
from app.services.action_dispatch import ActionHandler, apply_action_batch
from app.services.projects.common import (
    DEFAULT_LIST,
    _find_item,
    _find_item_by_content,
    _find_language_project,
    _find_project,
    _is_trivia_project,
    _item_status,
    _list_key,
    _resolve_list_title,
    normalize_project_kind,
)
from app.services.projects.quiz_grading import _failed_quiz_today, _recently_missed_quiz

logger = logging.getLogger(__name__)

_ACTION_RELOAD_LIMIT = 500


# Defensive caps for LLM-inferred project mutations applied from a transcript.
MAX_PROJECT_ACTIONS_PER_TURN = 3


# Whole-project / whole-deck deletes are too destructive to apply from a model's
# interpretation of chat text — the user must remove those explicitly.
PROJECT_BLOCKED_FROM_TRANSCRIPT = frozenset({"delete_project", "delete_list"})


# BUG FIX: `add` was only bounded by MAX_PROJECT_ACTIONS_PER_TURN + content
# dedup, so a deck could grow unbounded over many turns. No documented
# product limit on deck size exists (FEATURES.md) — pick a generous but
# bounded cap.
MAX_PROJECT_ITEMS_PER_PROJECT = 2000


@dataclass
class _ProjectApplyState:
    session: AsyncSession
    user_id: UUID
    chat_id: UUID | None
    projects: list[Project]
    items: list[ProjectItem]


def _prepare_project_action(action: ProjectActionItem) -> ProjectActionItem | None:
    title = action.project_title.strip()
    if not title:
        return None
    if title != action.project_title:
        return action.model_copy(update={"project_title": title})
    return action


async def _project_action_create_project(
    state: _ProjectApplyState, action: ProjectActionItem
) -> int:
    # kind is already a bounded Literal on ProjectActionItem
    # (schemas.py: ProjectKind = "language" | "vocabulary" |
    # "trivia") validated by Pydantic before this is ever
    # reached, and normalize_project_kind maps "vocabulary" ->
    # "language" — so kind is always in LEARNING_PRODUCT_KINDS
    # here. The old `if kind not in LEARNING_PRODUCT_KINDS:
    # continue` guard was dead code; removed.
    title = action.project_title
    kind = normalize_project_kind(action.kind or "language")
    if kind == "language" and _find_language_project(state.projects, "en"):
        return 0
    if kind == "trivia" and any(_is_trivia_project(p) for p in state.projects):
        return 0
    if _find_project(state.projects, title):
        return 0
    try:
        project = await projects_repo.create(
            state.session,
            user_id=state.user_id,
            title=title,
            description=(action.description or "").strip() or None,
            kind=kind,
            level=action.level or "level1",
            target_language="en",
        )
    except IntegrityError:
        # BUG FIX (was silent): the in-memory checks above aren't
        # safe against two near-concurrent project-sync jobs for
        # the same user both passing before either commits. The
        # DB partial unique index (migration 0055) is the real
        # guard — a race loses here and should just no-op, not
        # raise into the background job or poison the rest of
        # this turn's actions with an un-rolled-back session.
        await state.session.rollback()
        logger.debug(
            "create_project raced with an existing active %s project for user_id=%s; skipping",
            kind,
            state.user_id,
        )
        return 0
    applied = 1
    state.projects = await projects_repo.list_for_user(state.session, state.user_id, limit=200)
    if action.content.strip():
        list_title = action.list_title.strip() or DEFAULT_LIST
        from app.services.projects.items import create_item

        await create_item(
            state.session,
            user_id=state.user_id,
            project_id=project.id,
            content=action.content,
            list_title=list_title,
            note=action.note,
            definition=action.definition,
            example_sentence=action.example_sentence or action.note,
            chat_id=state.chat_id,
        )
        applied += 1
        state.items = await project_items_repo.list_recent_for_user(
            state.session, state.user_id, limit=_ACTION_RELOAD_LIMIT
        )
    return applied


async def _project_action_delete_project(
    state: _ProjectApplyState, action: ProjectActionItem
) -> int:
    matched = _find_project(state.projects, action.project_title)
    if not matched:
        return 0
    await projects_repo.delete_by_id(state.session, matched.id, state.user_id)
    state.projects = [p for p in state.projects if p.id != matched.id]
    state.items = [i for i in state.items if i.project_id != matched.id]
    return 1


async def _project_action_set_description(
    state: _ProjectApplyState, action: ProjectActionItem
) -> int:
    matched = _find_project(state.projects, action.project_title)
    if not matched:
        return 0
    desc = (action.description or "").strip() or None
    await projects_repo.update(state.session, matched, description=desc)
    return 1


async def _project_action_set_level(state: _ProjectApplyState, action: ProjectActionItem) -> int:
    matched = _find_project(state.projects, action.project_title)
    if not matched or not action.level:
        return 0
    await projects_repo.update(state.session, matched, level=action.level)
    return 1


async def _project_action_add(state: _ProjectApplyState, action: ProjectActionItem) -> int:
    matched = _find_project(state.projects, action.project_title)
    if not matched:
        return 0
    project = matched
    list_title = _resolve_list_title(project, action)
    content = action.content.strip()
    if not content:
        return 0
    if _find_item(state.items, project.id, list_title, content):
        return 0
    item_count = await project_items_repo.count_for_project(
        state.session, project.id, state.user_id
    )
    if item_count >= MAX_PROJECT_ITEMS_PER_PROJECT:
        logger.info(
            "Skipping add: project_id=%s at item cap (%d) for user_id=%s",
            project.id,
            MAX_PROJECT_ITEMS_PER_PROJECT,
            state.user_id,
        )
        return 0
    from app.services.projects.items import create_item

    await create_item(
        state.session,
        user_id=state.user_id,
        project_id=project.id,
        content=content,
        list_title=list_title,
        note=action.note,
        definition=action.definition,
        example_sentence=action.example_sentence or action.note,
        chat_id=state.chat_id,
        status="new",
    )
    state.items = await project_items_repo.list_recent_for_user(
        state.session, state.user_id, limit=_ACTION_RELOAD_LIMIT
    )
    return 1


async def _project_action_start_learning(
    state: _ProjectApplyState, action: ProjectActionItem
) -> int:
    # Record a failed/incorrect quiz outcome (open-ended or exhausted).
    # Stamps last_incorrect_at so failed_today / day lists stay accurate.
    matched = _find_project(state.projects, action.project_title)
    if not matched:
        return 0
    project = matched
    list_title = _resolve_list_title(project, action)
    item = _find_item(state.items, project.id, list_title, action.content)
    if not item:
        item = _find_item_by_content(state.items, project.id, action.content)
    content = action.content.strip()
    if not item and content:
        from app.services.projects.items import create_item

        item = await create_item(
            state.session,
            user_id=state.user_id,
            project_id=project.id,
            content=content,
            list_title=list_title,
            note=action.note,
            definition=action.definition,
            example_sentence=action.example_sentence or action.note,
            chat_id=state.chat_id,
            status="new",
        )
        state.items = await project_items_repo.list_recent_for_user(
            state.session, state.user_id, limit=_ACTION_RELOAD_LIMIT
        )
    if item and _item_status(item) != "mastered":
        if not _failed_quiz_today(item):
            from app.services.projects.quiz_grading import apply_quiz_result

            await apply_quiz_result(state.session, item, is_correct=False, commit=False)
            return 1
        if _item_status(item) == "new":
            from app.services.projects.items import update_item

            await update_item(state.session, item, status="learning")
            return 1
    return 0


async def _project_action_master(state: _ProjectApplyState, action: ProjectActionItem) -> int:
    matched = _find_project(state.projects, action.project_title)
    if not matched:
        return 0
    project = matched
    list_title = _resolve_list_title(project, action)
    item = _find_item(state.items, project.id, list_title, action.content, mastered_only=False)
    if not item:
        item = _find_item_by_content(state.items, project.id, action.content)
    if item and _item_status(item) != "mastered":
        if _recently_missed_quiz(item):
            logger.info(
                "Skipping master for recently missed quiz item user_id=%s word=%s",
                state.user_id,
                action.content,
            )
            return 0
        from app.services.projects.items import update_item

        await update_item(state.session, item, status="mastered")
        return 1
    return 0


async def _project_action_unmaster(state: _ProjectApplyState, action: ProjectActionItem) -> int:
    matched = _find_project(state.projects, action.project_title)
    if not matched:
        return 0
    project = matched
    list_title = _resolve_list_title(project, action)
    item = _find_item(state.items, project.id, list_title, action.content, mastered_only=True)
    if item and _item_status(item) == "mastered":
        from app.services.projects.items import update_item

        await update_item(state.session, item, status="learning")
        return 1
    return 0


async def _project_action_delete(state: _ProjectApplyState, action: ProjectActionItem) -> int:
    matched = _find_project(state.projects, action.project_title)
    if not matched:
        return 0
    project = matched
    list_title = _resolve_list_title(project, action)
    item = _find_item(state.items, project.id, list_title, action.content)
    if not item:
        return 0
    await project_items_repo.delete_by_id(state.session, item.id, state.user_id)
    state.items = [i for i in state.items if i.id != item.id]
    return 1


async def _project_action_delete_list(state: _ProjectApplyState, action: ProjectActionItem) -> int:
    matched = _find_project(state.projects, action.project_title)
    if not matched:
        return 0
    project = matched
    list_title = _resolve_list_title(project, action)
    removed = await project_items_repo.delete_by_list(
        state.session, state.user_id, project.id, list_title
    )
    if not removed:
        return 0
    state.items = [
        i
        for i in state.items
        if not (i.project_id == project.id and _list_key(i.list_title) == _list_key(list_title))
    ]
    return 1


_PROJECT_ACTION_HANDLERS: dict[str, ActionHandler[_ProjectApplyState, ProjectActionItem]] = {
    "create_project": _project_action_create_project,
    "delete_project": _project_action_delete_project,
    "set_description": _project_action_set_description,
    "set_level": _project_action_set_level,
    "add": _project_action_add,
    "start_learning": _project_action_start_learning,
    "master": _project_action_master,
    "unmaster": _project_action_unmaster,
    "delete": _project_action_delete,
    "delete_list": _project_action_delete_list,
}


async def apply_project_actions(
    session: AsyncSession,
    *,
    user_id: UUID,
    actions: list[ProjectActionItem],
    chat_id: UUID | None = None,
    from_transcript: bool = True,
) -> int:
    """Apply LLM-extracted or explicit-user project/item actions.

    ``from_transcript`` defaults to True (safe): whole-project/whole-deck
    deletes are blocked unless a caller explicitly opts out with
    ``from_transcript=False`` for a genuine user-initiated action (e.g. a
    dedicated "delete project" endpoint). Defaulting to the permissive
    behavior would mean a future caller that forgets this parameter silently
    inherits the ability to let a model delete data via chat.
    """
    if not actions:
        return 0
    if from_transcript:
        # BUG FIX (was silent): this guard used to live only in
        # _apply_project_extraction_result, this function's one caller —
        # nothing stopped a future second caller from invoking
        # apply_project_actions directly and bypassing it entirely. Enforce
        # it here instead.
        for action in actions:
            if action.action in PROJECT_BLOCKED_FROM_TRANSCRIPT:
                logger.warning(
                    "Refused destructive project action %s from transcript for "
                    "user_id=%s project=%s (requires explicit user action)",
                    action.action,
                    user_id,
                    action.project_title,
                )
        actions = [a for a in actions if a.action not in PROJECT_BLOCKED_FROM_TRANSCRIPT]
        if not actions:
            return 0
    projects = await projects_repo.list_for_user(session, user_id, limit=200)
    items = await project_items_repo.list_recent_for_user(
        session, user_id, limit=_ACTION_RELOAD_LIMIT
    )
    state = _ProjectApplyState(
        session=session,
        user_id=user_id,
        chat_id=chat_id,
        projects=projects,
        items=items,
    )

    def _on_error(action: ProjectActionItem) -> None:
        logger.exception(
            "Failed project action %s for user_id=%s project=%s",
            action.action,
            user_id,
            action.project_title,
        )

    def _log_summary(applied: int) -> None:
        logger.info(
            "Applied %d project action(s) for user_id=%s chat_id=%s",
            applied,
            user_id,
            chat_id,
        )

    async def _invalidate_home() -> None:
        # Resolve via common so tests can patch
        # app.services.projects.common._invalidate_home_for_user.
        from app.services.projects.common import _invalidate_home_for_user

        await _invalidate_home_for_user(user_id)

    return await apply_action_batch(
        actions=actions,
        state=state,
        handlers=_PROJECT_ACTION_HANDLERS,
        action_name=lambda a: a.action,
        prepare=_prepare_project_action,
        on_error=_on_error,
        log_summary=_log_summary,
        invalidate_home=_invalidate_home,
    )
