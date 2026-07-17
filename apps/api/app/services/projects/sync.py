"""Background project extraction / sync from chat transcripts."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.schemas import ProjectExtractionResult
from app.repositories import project_items as project_items_repo
from app.repositories import projects as projects_repo
from app.services.projects.actions import MAX_PROJECT_ACTIONS_PER_TURN
from app.services.projects.common import _item_status

logger = logging.getLogger(__name__)

_PROJECT_SYNC_TRANSCRIPT = re.compile(
    r"\b("
    r"learning topic|vocab(?:ulary)?|add(?:ed)? (?:word|words)|"
    r"master(?:ed)?|quiz|flashcard|"
    r"set_level|trivia|general knowledge|"
    r"save (?:to|this)|new list|word list|"
    r"create (?:a )?(?:learning )?(?:topic|project)"
    r")\b",
    re.IGNORECASE,
)


def transcript_implies_project_sync(
    transcript: str,
    *,
    chat_project_id: UUID | None = None,
) -> bool:
    """Skip project-extraction jobs on unrelated chit-chat."""
    if chat_project_id is not None:
        return True
    text = transcript.strip()
    if not text:
        return False
    return bool(_PROJECT_SYNC_TRANSCRIPT.search(text))


@dataclass(frozen=True)
class _ProjectSyncSnapshot:
    snapshot: dict[str, Any]


async def _load_project_sync_snapshot(
    session: AsyncSession,
    user_id: UUID,
    settings: Settings,
) -> _ProjectSyncSnapshot:
    projects = await projects_repo.list_for_user(
        session, user_id, limit=settings.project_inject_limit
    )
    items = await project_items_repo.list_for_user(
        session, user_id, limit=settings.project_item_inject_limit
    )
    return _ProjectSyncSnapshot(
        snapshot={
            "projects": [
                {
                    "title": p.title,
                    "kind": p.kind,
                    "level": getattr(p, "level", "level1"),
                    "target_language": getattr(p, "target_language", "en"),
                    "description": p.description,
                    "archived": p.archived,
                }
                for p in projects
            ],
            "items": [
                {
                    "project_title": next(
                        (pr.title for pr in projects if pr.id == i.project_id), ""
                    ),
                    "list_title": i.list_title,
                    "content": i.content,
                    "definition": i.definition,
                    "example_sentence": i.example_sentence or i.note,
                    "status": _item_status(i),
                    "mastered": i.mastered,
                }
                for i in items
            ],
        }
    )


async def _apply_project_extraction_result(
    session: AsyncSession,
    *,
    user_id: UUID,
    chat_id: UUID,
    result: ProjectExtractionResult | None,
) -> int:
    if not result or not result.actions:
        return 0
    # Defensive per-turn cap on how many actions an LLM extraction can apply.
    # The destructive-action block (delete_project/delete_list) now lives in
    # apply_project_actions itself (from_transcript=True, the default) —
    # this caller no longer needs to filter those out before calling it.
    # Resolve via package so tests can patch projects_service.apply_project_actions.
    from app.services.projects import apply_project_actions

    capped_actions = result.actions[:MAX_PROJECT_ACTIONS_PER_TURN]
    applied = await apply_project_actions(
        session,
        user_id=user_id,
        actions=capped_actions,
        chat_id=chat_id,
        from_transcript=True,
    )
    if result.actions and applied == 0:
        logger.warning(
            "Project sync extracted %d action(s) but applied 0 for user_id=%s",
            len(result.actions),
            user_id,
        )
    return applied


async def _run_extracted_project_actions(
    settings: Settings,
    *,
    user_id: UUID,
    chat_id: UUID,
    transcript: str,
) -> ProjectExtractionResult | None:
    from app.core.db import SessionLocal
    from app.gateways import litellm_gateway

    async with SessionLocal() as session:
        loaded = await _load_project_sync_snapshot(session, user_id, settings)
        await session.commit()

    try:
        result = await litellm_gateway.extract_project_actions(
            settings,
            transcript,
            loaded.snapshot,
        )
    except Exception:
        logger.exception("Project action extraction failed for user_id=%s", user_id)
        return None

    async with SessionLocal() as session:
        await _apply_project_extraction_result(
            session,
            user_id=user_id,
            chat_id=chat_id,
            result=result,
        )
        await session.commit()
    return result


async def sync_projects_from_transcript(
    settings: Settings,
    *,
    user_id: UUID,
    chat_id: UUID,
    transcript: str,
) -> ProjectExtractionResult | None:
    try:
        return await _run_extracted_project_actions(
            settings,
            user_id=user_id,
            chat_id=chat_id,
            transcript=transcript,
        )
    except Exception:
        logger.exception("Project sync failed for user_id=%s", user_id)
        return None
