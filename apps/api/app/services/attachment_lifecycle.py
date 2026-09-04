"""Attachment storage cleanup — message deletes and orphan reaping."""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import SessionLocal
from app.core.redis import get_redis_client
from app.gateways.storage_gateway import get_storage_gateway
from app.repositories import attachments as attachments_repo
from app.services import quota as quota_service
from app.services.attachment_content import is_image_content_type
from app.services.attachment_quota import has_current_upload_reservation

logger = logging.getLogger(__name__)

PENDING_STORAGE_DELETE_KEY = "recall:storage:pending_delete"


async def detach_attachments_for_messages(
    session: AsyncSession,
    message_ids: list[UUID],
    *,
    commit: bool = True,
) -> list[str]:
    """Remove attachment DB rows/chunks; return storage keys for deferred byte delete.

    Callers that need transactional safety with a parent commit should pass
    ``commit=False``, commit the parent session, then ``delete_storage_keys``.
    """
    if not message_ids:
        return []
    rows = await attachments_repo.list_for_message_ids(session, message_ids)
    if not rows:
        return []
    attachment_ids = [row.id for row in rows]
    storage_keys = [row.storage_key for row in rows if row.storage_key]
    # The FK cascade deletes chunks after locking their attachment parent,
    # matching the index worker's lock order.
    await attachments_repo.delete_rows(session, attachment_ids, commit=commit)
    return storage_keys


async def delete_storage_keys(settings: Settings, storage_keys: list[str]) -> list[str]:
    """Best-effort byte delete. Returns keys whose delete failed (keep those rows)."""
    if not storage_keys:
        return []
    gateway = get_storage_gateway(settings)
    results = await asyncio.gather(
        *(gateway.delete_bytes(key) for key in storage_keys),
        return_exceptions=True,
    )
    failed: list[str] = []
    for key, result in zip(storage_keys, results, strict=False):
        if isinstance(result, Exception):
            logger.warning("Failed to delete attachment bytes key=%s", key, exc_info=result)
            failed.append(key)
    return failed


async def enqueue_failed_storage_deletes(keys: list[str]) -> None:
    """Keep failed R2 deletes so the orphan reaper can retry after rows are gone."""
    if not keys:
        return
    try:
        redis = get_redis_client()
        await redis.sadd(PENDING_STORAGE_DELETE_KEY, *keys)
    except Exception:
        logger.warning("Could not enqueue failed storage deletes", exc_info=True)


async def retry_pending_storage_deletes(settings: Settings) -> int:
    try:
        redis = get_redis_client()
        raw = await redis.smembers(PENDING_STORAGE_DELETE_KEY)
    except Exception:
        logger.debug("Pending storage-delete retry skipped", exc_info=True)
        return 0
    if not isinstance(raw, set | list | tuple):
        return 0
    keys = [
        item.decode() if isinstance(item, bytes) else item
        for item in raw
        if isinstance(item, bytes | str)
    ]
    if not keys:
        return 0
    still_failed = set(await delete_storage_keys(settings, keys))
    succeeded = [key for key in keys if key not in still_failed]
    if succeeded:
        try:
            await redis.srem(PENDING_STORAGE_DELETE_KEY, *succeeded)
        except Exception:
            logger.debug("Could not clear pending storage deletes", exc_info=True)
    return len(succeeded)


async def purge_attachments_for_messages(
    session: AsyncSession,
    settings: Settings,
    message_ids: list[UUID],
) -> int:
    """Detach DB rows then delete stored bytes for attachments on ``message_ids``."""
    storage_keys = await detach_attachments_for_messages(session, message_ids, commit=True)
    failed = await delete_storage_keys(settings, storage_keys)
    await enqueue_failed_storage_deletes(failed)
    return len(storage_keys)


async def purge_attachments_for_user(
    session: AsyncSession,
    settings: Settings,
    user_id: UUID,
) -> int:
    """Delete storage bytes then DB rows for every attachment owned by ``user_id``.

    Bytes are removed before rows (same ordering as the orphan reaper): if storage
    delete fails or the process dies mid-loop, rows remain so a retry can finish.
    Call this before ``users_repo.delete_user``, which only clears attachment rows.
    """
    rows = await attachments_repo.list_for_user(session, user_id)
    if not rows:
        return 0
    # Per-object best-effort: one R2 failure must not abort GDPR account wipe.
    # Failed keys may leave storage orphans; the orphan reaper / bucket lifecycle
    # covers those — failing the whole delete would leave the user logged out
    # with their account still intact.
    keys = [row.storage_key for row in rows if row.storage_key]
    failed = set(await delete_storage_keys(settings, keys))
    await enqueue_failed_storage_deletes(list(failed))
    attachment_ids = [
        row.id for row in rows if not row.storage_key or row.storage_key not in failed
    ]
    if not attachment_ids:
        return 0
    return await attachments_repo.delete_rows(session, attachment_ids)


async def reap_orphan_attachments(settings: Settings) -> int:
    """Delete bytes + rows for unlinked pending uploads and hidden send-clones.

    Uses a DB-first-then-storage order: the DB unlink check
    (``delete_unlinked_returning``) runs BEFORE storage deletion, so an
    attachment linked between list and delete time is NOT reaped (its row
    survives, its bytes are not touched). Previously storage was deleted
    first, which could leave a linked attachment with missing file content.

    Verified Library items that outlive their chat are not listed.

    Image uploads that are reaped also get their daily image-upload slot
    refunded — without this, an abandoned presign (never sent/confirmed)
    permanently consumes a slot the user can never get back, eventually
    locking them out of image uploads for the day.
    """
    await retry_pending_storage_deletes(settings)
    async with SessionLocal() as session:
        orphans = await attachments_repo.list_orphans(
            session,
            older_than_hours=settings.attachment_orphan_grace_hours,
            limit=settings.attachment_orphan_reap_limit,
        )
    if not orphans:
        return 0

    # DB-first: delete rows that are still unlinked. This returns the storage
    # keys of rows actually removed — a row linked between list and delete
    # is NOT removed and its bytes are preserved.
    ids_to_delete = [row.id for row in orphans]
    async with SessionLocal() as session:
        removed_keys = await attachments_repo.delete_unlinked_returning(
            session, ids_to_delete, orphan_only=True
        )
    if not removed_keys:
        return 0

    # Storage cleanup for confirmed-removed rows only.
    removed_set = set(removed_keys)
    rows_to_refund = [row for row in orphans if row.storage_key in removed_set]
    failed = await delete_storage_keys(settings, removed_keys)
    await enqueue_failed_storage_deletes(failed)

    # Refund the daily image slot for each reaped image.
    if rows_to_refund:
        redis = get_redis_client()
        for row in rows_to_refund:
            if is_image_content_type(row.content_type) and has_current_upload_reservation(row):
                try:
                    await quota_service.refund_image_upload(redis, row.user_id)
                except Exception:
                    logger.debug(
                        "Image quota refund failed for user %s", row.user_id, exc_info=True
                    )
    logger.info("Reaped %d orphan attachment(s)", len(removed_keys))
    return len(removed_keys)


async def sweep_user_storage(settings: Settings, user_id: UUID) -> int:
    """Delete leftover objects under ``{user_id}/`` after account wipe.

    Complements ``purge_attachments_for_user`` when Redis pending-delete never
    ran. Prefix is the user UUID only — never ``/`` or ``..``.
    """
    prefix = f"{user_id}/"
    if ".." in prefix or prefix.startswith("/"):
        return 0
    gateway = get_storage_gateway(settings)
    deleted = await gateway.delete_prefix(prefix)
    if deleted:
        logger.info("storage_sweep user_id=%s deleted=%s", user_id, deleted)
    return deleted
