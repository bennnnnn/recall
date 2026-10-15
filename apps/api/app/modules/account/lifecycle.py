"""Authenticated account update, logout, and deletion workflows."""

import logging
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access_tokens import REVOKED_SINCE_PREFIX
from app.core.config import Settings
from app.core.jobs import enqueue
from app.core.validation import normalize_avatar_url
from app.gateways.google_auth import GoogleAuthError
from app.models.orm import User
from app.modules import home as home_service
from app.modules import memory as memory_service
from app.modules.account import tokens as tokens_service
from app.modules.attachments import service as attachments_service
from app.modules.billing import plan as plan_service
from app.modules.chat import service as chats_service
from app.repositories import users as users_repo

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
            photo = await attachments_service.get_by_id(
                session, attachment_id, user.id, for_update=True
            )
            if (
                photo is None
                or photo.verified_at is None
                or photo.message_id is not None
                or photo.source != "upload"
                or not attachments_service.is_image_content_type(photo.content_type)
                or not 0 < photo.size_bytes <= attachments_service.MAX_ATTACHMENT_SIZE
            ):
                raise ValueError("Choose an uploaded photo that has finished uploading.")
            fields["avatar_url"] = avatar_url
            await attachments_service.hide_from_gallery(session, photo)
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
    *,
    plan: str = "pro",
) -> User:
    return await users_repo.update(session, user, plan=plan)


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

    await attachments_service.purge_attachments_for_user(session, settings, user.id)
    user_id = user.id
    from app.core.deps import forget_user
    from app.repositories.chats import forget_user_chats

    try:
        # Keyed by reply id, not user id, so only the rows can find them.
        await chats_service.forget_follow_up_questions(session, redis, user_id)
    except Exception:
        logger.warning("Follow-up cache purge failed user_id=%s", user_id, exc_info=True)
    forget_user(user_id)
    forget_user_chats(user_id)
    await users_repo.delete_user(session, user.id)
    # The worker sweeps leftover storage objects and every Redis key that
    # names the user (caches, cards, usage); see purge_user_redis_keys.
    await enqueue(
        redis,
        "storage_sweep",
        {"user_id": str(user_id)},
        dedupe_key=f"storage_sweep:{user_id}",
    )


# Kept after a delete: the cutoff that keeps the deleted account's already
# issued access tokens rejected (it expires with them), and job markers.
_KEEP_AFTER_DELETE_PREFIXES = (REVOKED_SINCE_PREFIX, "jobdone:")
_PURGE_SCAN_COUNT = 1000
_PURGE_BATCH = 500


async def purge_user_redis_keys(redis: Redis, user_id: UUID) -> int:
    """Delete every Redis key that names a deleted user. Returns the count.

    Memory and home caches, reminder and settings cards, web-search and voice
    lookups, usage counters and history-scan state are all keyed by user id.
    One SCAN pass covers them, including key families added later. Runs in
    the worker (``storage_sweep``): a full keyspace scan does not belong on
    the request path.
    """
    needle = str(user_id)
    batch: list[str] = []
    removed = 0
    async for raw in redis.scan_iter(match=f"*{needle}*", count=_PURGE_SCAN_COUNT):
        key = raw.decode() if isinstance(raw, bytes) else str(raw)
        if key.startswith(_KEEP_AFTER_DELETE_PREFIXES) or needle not in key:
            continue
        batch.append(key)
        if len(batch) >= _PURGE_BATCH:
            removed += int(await redis.unlink(*batch) or 0)
            batch = []
    if batch:
        removed += int(await redis.unlink(*batch) or 0)
    if removed:
        logger.info("Account Redis purge user_id=%s removed=%s", user_id, removed)
    return removed


__all__ = [
    "GoogleAuthError",
    "SessionPurgeError",
    "delete_account",
    "logout",
    "purge_user_redis_keys",
    "update_account",
    "upgrade_to_pro_for_dev",
]
