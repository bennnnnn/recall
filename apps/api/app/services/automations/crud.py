"""HTTP-facing CRUD for the legacy generic automation primitive.

My Job is now a dedicated job-search product under ``/job-search``. These
endpoints remain for backward compatibility but never expose job-search rows.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.orm import Automation, User
from app.repositories import automations as automations_repo
from app.repositories import chats as chats_repo
from app.services import chats as chats_service
from app.services import plan as plan_service
from app.services.time_context import normalize_due_at


class AutomationsError(Exception):
    def __init__(self, detail: str, *, status_code: int) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def _require_enabled(settings: Settings) -> None:
    if not settings.automations_enabled:
        raise AutomationsError("Not available", status_code=404)


def _generic_or_not_found(automation: Automation | None) -> Automation:
    # Rows created before the kind column existed are generic by definition.
    # Only an explicit job_search kind is hidden from the legacy endpoint.
    if automation is None or getattr(automation, "kind", "generic") == "job_search":
        raise AutomationsError("Automation not found", status_code=404)
    return automation


async def list_automations(
    session: AsyncSession, user: User, settings: Settings
) -> list[Automation]:
    _require_enabled(settings)
    return await automations_repo.list_for_user(session, user.id, kind="generic")


async def get_automation(
    session: AsyncSession, user: User, settings: Settings, automation_id: UUID
) -> Automation:
    _require_enabled(settings)
    return _generic_or_not_found(await automations_repo.get_by_id(session, automation_id, user.id))


async def create_automation(
    session: AsyncSession,
    user: User,
    settings: Settings,
    *,
    prompt: str,
    frequency: str,
    next_run_at: Any,
) -> Automation:
    _require_enabled(settings)
    if not plan_service.is_pro(user):
        raise AutomationsError("Automations require Recall Pro", status_code=403)

    active_count = await automations_repo.count_active_for_user(session, user.id, kind="generic")
    if active_count >= settings.automations_max_active_per_user:
        raise AutomationsError(
            f"You can have up to {settings.automations_max_active_per_user} "
            "active automations at a time",
            status_code=422,
        )

    normalized_next_run = normalize_due_at(next_run_at, user.timezone)
    if normalized_next_run is None:
        raise AutomationsError("next_run_at is required", status_code=422)

    chat = await chats_repo.create(session, user_id=user.id, model="smart-chat", commit=False)
    automation = await automations_repo.create(
        session,
        user_id=user.id,
        chat_id=chat.id,
        prompt=prompt,
        frequency=frequency,
        next_run_at=normalized_next_run,
        kind="generic",
        commit=False,
    )
    await session.commit()
    await session.refresh(automation)
    return automation


async def update_automation(
    session: AsyncSession,
    user: User,
    settings: Settings,
    automation_id: UUID,
    fields: dict[str, Any],
) -> Automation:
    _require_enabled(settings)
    automation = _generic_or_not_found(
        await automations_repo.get_by_id(session, automation_id, user.id)
    )

    patch = dict(fields)
    if "next_run_at" in patch and patch["next_run_at"] is not None:
        patch["next_run_at"] = normalize_due_at(patch["next_run_at"], user.timezone)

    return await automations_repo.update(session, automation, **patch)


async def delete_automation(
    session: AsyncSession, user: User, settings: Settings, automation_id: UUID
) -> None:
    _require_enabled(settings)
    automation = _generic_or_not_found(
        await automations_repo.get_by_id(session, automation_id, user.id)
    )
    try:
        await chats_service.delete_chat(session, user, automation.chat_id, settings=settings)
    except chats_service.ChatsError as exc:
        raise AutomationsError(exc.detail, status_code=exc.status_code) from exc
