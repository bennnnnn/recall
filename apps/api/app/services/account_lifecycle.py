"""Authenticated account update, logout, and deletion workflows."""

import logging
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.jobs import enqueue
from app.core.validation import normalize_avatar_url
from app.gateways.google_auth import GoogleAuthError
from app.models.orm import User
from app.repositories import attachments as attachments_repo
from app.repositories import users as users_repo
from app.services import attachment_lifecycle
from app.services import google_integrations as google_integrations_service
from app.services import home as home_service
from app.services import memory as memory_service
from app.services import plan as plan_service
from app.services import tokens as tokens_service
from app.services.attachment_content import MAX_ATTACHMENT_SIZE, is_image_content_type

logger = logging.getLogger(__name__)


class SessionPurgeError(Exception):
    """Account deletion could not safely revoke all active sessions."""


async def update_account(
    session: AsyncSession,
    user: User,
    settings: Settings,
    fields: dict[str, Any],
) -> User:
    if "enabled_models" in fields:
        fields["enabled_models"] = plan_service.validate_enabled_models_for_update(
            user,
            fields["enabled_models"],
            settings,
        )
    memory_toggled = "memory_enabled" in fields and fields["memory_enabled"] != user.memory_enabled
    if fields.get("avatar_url"):
        try:
            avatar_url = normalize_avatar_url(fields["avatar_url"])
            if avatar_url is None:
                raise ValueError("Choose an uploaded photo that has finished uploading.")
            attachment_id = UUID(avatar_url.split("/")[2])
            photo = await attachments_repo.get_by_id(
                session, attachment_id, user.id, for_update=True
            )
            if (
                photo is None
                or photo.verified_at is None
                or photo.message_id is not None
                or photo.source != "upload"
                or not is_image_content_type(photo.content_type)
                or not 0 < photo.size_bytes <= MAX_ATTACHMENT_SIZE
            ):
                raise ValueError("Choose an uploaded photo that has finished uploading.")
            fields["avatar_url"] = avatar_url
            await attachments_repo.hide_from_gallery(session, photo)
            updated = await users_repo.update(session, user, commit=False, **fields)
            await session.commit()
            await session.refresh(updated)
        except BaseException:
            await session.rollback()
            raise
    else:
        updated = await users_repo.update(session, user, **fields)
    if memory_toggled:
        await memory_service.invalidate_memory_block(user.id)
    await home_service.invalidate_home_cache(user.id)
    return updated


async def upgrade_to_pro_for_dev(
    session: AsyncSession,
    user: User,
) -> User:
    return await users_repo.update(session, user, plan="pro")


async def logout(
    redis: Redis,
    settings: Settings,
    *,
    access_token: str | None,
    refresh_token: str | None,
) -> None:
    if access_token and refresh_token:
        await tokens_service.revoke_access_token(redis, access_token, settings)
        await tokens_service.revoke_refresh_token(redis, refresh_token)
    elif refresh_token:
        await tokens_service.revoke_refresh_token(redis, refresh_token)
    elif access_token:
        user_id = await tokens_service.verify_access_token(redis, access_token, settings)
        await tokens_service.revoke_access_token(redis, access_token, settings)
        await tokens_service.purge_user_sessions(redis, user_id, settings)


async def delete_account(
    session: AsyncSession,
    redis: Redis,
    settings: Settings,
    user: User,
) -> None:
    try:
        await tokens_service.purge_user_sessions(redis, user.id, settings)
    except Exception as exc:
        logger.warning(
            "Session purge failed during account delete user_id=%s",
            user.id,
            exc_info=True,
        )
        raise SessionPurgeError(user.id) from exc

    try:
        await google_integrations_service.revoke_all_google_tokens_for_user(
            session,
            settings,
            user.id,
        )
    except google_integrations_service.GoogleConnectError:
        logger.warning(
            "Google token revoke failed during account delete; continuing wipe user_id=%s",
            user.id,
            exc_info=True,
        )

    await attachment_lifecycle.purge_attachments_for_user(session, settings, user.id)
    user_id = user.id
    await users_repo.delete_user(session, user.id)
    await enqueue(
        redis,
        "storage_sweep",
        {"user_id": str(user_id)},
        dedupe_key=f"storage_sweep:{user_id}",
    )


__all__ = [
    "GoogleAuthError",
    "SessionPurgeError",
    "delete_account",
    "logout",
    "update_account",
    "upgrade_to_pro_for_dev",
]
