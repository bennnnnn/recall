"""Authenticated account update, logout, and deletion workflows."""

import logging
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import user_cache
from app.core.access_tokens import REVOKED_SINCE_PREFIX
from app.core.config import Settings
from app.core.jobs import enqueue
from app.core.validation import normalize_avatar_url
from app.exceptions import AuthenticationError
from app.gateways import apple_revoke
from app.models.orm import User
from app.modules import memory as memory_service
from app.modules.account import quota_carryover
from app.modules.account import tokens as tokens_service
from app.modules.attachments import service as attachments_service
from app.modules.billing import plan as plan_service
from app.modules.chat import service as chats_service
from app.modules.memory import crud as memory_crud
from app.modules.suggestions import service as suggestions_service
from app.modules.todos import service as todos_service
from app.repositories import push_tokens as push_tokens_repo
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
    # An older app still sends default_model: it chooses through the same rule.
    chosen = fields.pop("default_model", None)
    if chosen is not None and "enabled_models" not in fields:
        fields["enabled_models"] = plan_service.models_choosing(user, settings, chosen)
    if "enabled_models" in fields:
        fields["enabled_models"] = plan_service.validate_enabled_models_for_update(
            user,
            fields["enabled_models"],
            settings,
        )
    # A rename changes which saved name facts the memory block keeps (memory.user_name).
    memory_changed = (
        "memory_enabled" in fields and fields["memory_enabled"] != user.memory_enabled
    ) or ("name" in fields and fields["name"] != user.name)
    if fields.get("avatar_url"):
        try:
            avatar_url = normalize_avatar_url(fields["avatar_url"])
            if avatar_url is None:
                raise ValueError("Choose an uploaded photo that has finished uploading.")
            attachment_id = UUID(avatar_url.split("/")[2])
            if not await attachments_service.claim_profile_photo(session, attachment_id, user.id):
                raise ValueError("Choose an uploaded photo that has finished uploading.")
            fields["avatar_url"] = avatar_url
            updated = await users_repo.update(session, user, commit=False, **fields)
            user_id = updated.id
            await session.commit()
            await user_cache.publish_change(user_id)
            await session.refresh(updated)
        except BaseException:
            await session.rollback()
            raise
    else:
        updated = await users_repo.update(session, user, **fields)
    if memory_changed:
        await memory_service.invalidate_memory_block(user.id)
    return updated


async def upgrade_to_pro_for_dev(
    session: AsyncSession,
    user: User,
    *,
    plan: str = "pro",
) -> User:
    return await users_repo.update(session, user, plan=plan)


async def logout(
    session: AsyncSession,
    redis: Redis,
    settings: Settings,
    *,
    access_token: str | None,
    refresh_token: str | None,
    expo_push_token: str | None = None,
) -> None:
    """End this device's session; with ``expo_push_token``, this device stops getting the
    account's reminders too. Signed out, a phone kept showing them on its lock screen.
    """
    if expo_push_token:
        # Before the revokes: the live session proves whose token this is, so a token
        # string alone never silences another account's device.
        user_id = await _session_user(redis, settings, access_token, refresh_token)
        if user_id is not None:
            await push_tokens_repo.delete_token(session, user_id, expo_push_token)
    if access_token and refresh_token:
        await tokens_service.revoke_access_token(redis, access_token, settings)
        await tokens_service.revoke_refresh_token(redis, refresh_token)
    elif refresh_token:
        await tokens_service.revoke_refresh_token(redis, refresh_token)
    elif access_token:
        # No refresh token (the phone could not read it): this device's session only.
        user_id = await tokens_service.verify_access_token(redis, access_token, settings)
        session_id = tokens_service.session_id_from_access_token(access_token, settings)
        if session_id:
            await tokens_service.end_session(redis, user_id, session_id, settings=settings)
        await tokens_service.revoke_access_token(redis, access_token, settings)


async def logout_everywhere(
    session: AsyncSession,
    redis: Redis,
    settings: Settings,
    user_id: UUID,
    *,
    access_token: str | None,
) -> None:
    """End every session, and forget every device's push token: no signed-out phone keeps
    getting this account's reminders."""
    await tokens_service.purge_user_sessions(redis, user_id, settings)
    if access_token:
        await tokens_service.revoke_access_token(redis, access_token, settings)
    await push_tokens_repo.delete_for_user(session, user_id)


async def _session_user(
    redis: Redis, settings: Settings, access_token: str | None, refresh_token: str | None
) -> UUID | None:
    """The account a live access or refresh token of this device belongs to."""
    if access_token:
        try:
            return await tokens_service.verify_access_token(redis, access_token, settings)
        except AuthenticationError:
            pass  # expired: the refresh token still proves the session
    return await tokens_service.refresh_token_user(redis, refresh_token) if refresh_token else None


async def delete_account(
    session: AsyncSession,
    redis: Redis,
    settings: Settings,
    user: User,
    *,
    apple_authorization_code: str | None = None,
) -> None:
    """Delete the account and everything stored for it.

    *apple_authorization_code* is a fresh Sign in with Apple code the phone
    asked for; with it, the user's Apple grant is revoked last, best effort
    (``gateways/apple_revoke.py``), so Apple being down never blocks the delete.
    """
    apple_sub = user.apple_sub
    # First, while nothing is undone: a new account for the same Google/Apple login must
    # not start today's limits from zero. Redis failing here refuses the delete (503
    # unavailable) with the account still signed in, so the phone's retry needs no sign-in.
    await quota_carryover.save_on_delete(redis, settings, user)
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
    from app.core.user_cache import forget_user
    from app.modules.chat.history import forget_user_chats

    try:
        # Keyed by reply id, not user id, so only the rows can find them.
        await chats_service.forget_follow_up_questions(session, redis, user_id)
    except Exception:
        logger.warning("Follow-up cache purge failed user_id=%s", user_id, exc_info=True)
    forget_user(user_id)
    forget_user_chats(user_id)
    await erase_user_rows(session, user_id)
    # The worker sweeps leftover storage objects and every Redis key that
    # names the user (caches, cards, usage); see purge_user_redis_keys.
    await enqueue(
        redis,
        "storage_sweep",
        {"user_id": str(user_id)},
        dedupe_key=f"storage_sweep:{user_id}",
    )
    if apple_sub and apple_authorization_code:
        await apple_revoke.revoke_authorization_code(
            settings, apple_authorization_code, expected_sub=apple_sub
        )
    elif apple_sub:
        logger.info("Apple-linked account deleted without an Apple code; grant not revoked")


# Kept after a delete: the cutoff that keeps the deleted account's already
# issued access tokens rejected (it expires with them), and job markers.
_KEEP_AFTER_DELETE_PREFIXES = (REVOKED_SINCE_PREFIX, "jobdone:")
_PURGE_SCAN_COUNT = 1000
_PURGE_BATCH = 500


async def erase_user_rows(session: AsyncSession, user_id: UUID) -> None:
    """Every row of the account, the user's own last, and commit.

    Under the user's row lock (memory writers take it first) each module deletes its
    rows, children before the chats and the user they hang from; ``users_repo`` then
    deletes the core rows and the user.
    """
    await users_repo.lock_for_delete(session, user_id)
    for delete_rows in (
        memory_crud.delete_user_rows,
        todos_service.delete_user_rows,
        suggestions_service.delete_user_rows,
        attachments_service.delete_user_rows,
    ):
        await delete_rows(session, user_id)
    await users_repo.delete_user(session, user_id)


async def purge_user_redis_keys(redis: Redis, user_id: UUID) -> int:
    """Delete every Redis key that names a deleted user. Returns the count.

    Memory caches, reminder and settings cards, web-search and voice
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
    "SessionPurgeError",
    "delete_account",
    "logout",
    "purge_user_redis_keys",
    "update_account",
    "upgrade_to_pro_for_dev",
]
