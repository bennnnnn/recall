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

logger = logging.getLogger(__name__)


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
    from app.repositories import attachment_chunks as chunks_repo

    await chunks_repo.delete_for_attachment_ids(session, attachment_ids, commit=False)
    await attachments_repo.delete_rows(session, attachment_ids, commit=commit)
    return storage_keys


async def delete_storage_keys(settings: Settings, storage_keys: list[str]) -> None:
    """Best-effort byte delete after the DB commit that removed the rows."""
    if not storage_keys:
        return
    gateway = get_storage_gateway(settings)
    results = await asyncio.gather(
        *(gateway.delete_bytes(key) for key in storage_keys),
        return_exceptions=True,
    )
    for key, result in zip(storage_keys, results, strict=False):
        if isinstance(result, Exception):
            logger.warning("Failed to delete attachment bytes key=%s", key, exc_info=result)


async def purge_attachments_for_messages(
    session: AsyncSession,
    settings: Settings,
    message_ids: list[UUID],
) -> int:
    """Detach DB rows then delete stored bytes for attachments on ``message_ids``."""
    storage_keys = await detach_attachments_for_messages(session, message_ids, commit=True)
    await delete_storage_keys(settings, storage_keys)
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
    gateway = get_storage_gateway(settings)
    await asyncio.gather(*(gateway.delete_bytes(row.storage_key) for row in rows))
    attachment_ids = [row.id for row in rows]
    from app.repositories import attachment_chunks as chunks_repo

    await chunks_repo.delete_for_attachment_ids(session, attachment_ids)
    return await attachments_repo.delete_rows(session, attachment_ids)


async def reap_orphan_attachments(settings: Settings) -> int:
    """Delete bytes + rows for attachments never linked to a message past the grace window.

    Storage bytes are deleted BEFORE DB rows: if the storage delete fails (or
    the process crashes mid-loop), the DB rows remain and the next reap retries.
    The old order (rows first, then bytes) left orphaned R2 objects with no DB
    row — unrecoverable, since the reaper discovers orphans via the DB.

    Image uploads that are reaped also get their daily image-upload slot
    refunded — without this, an abandoned presign (never sent/confirmed)
    permanently consumes a slot the user can never get back, eventually
    locking them out of image uploads for the day.
    """
    async with SessionLocal() as session:
        orphans = await attachments_repo.list_orphans(
            session, older_than_hours=settings.attachment_orphan_grace_hours
        )
    if not orphans:
        return 0
    gateway = get_storage_gateway(settings)
    for row in orphans:
        await gateway.delete_bytes(row.storage_key)
    async with SessionLocal() as session:
        removed = await attachments_repo.delete_unlinked_returning(
            session, [row.id for row in orphans]
        )
    # Refund the daily image slot for each reaped image. Uploads refund imgup;
    # generated images refund imggen. Map storage_key -> orphan row so we only
    # refund for rows that were actually removed (a row linked between list and
    # delete is NOT reaped and keeps its slot).
    if removed:
        removed_set = set(removed)
        redis = get_redis_client()
        for row in orphans:
            if row.storage_key in removed_set and is_image_content_type(row.content_type):
                try:
                    if getattr(row, "source", "upload") == "generated":
                        await quota_service.refund_image_generation(redis, row.user_id)
                    else:
                        await quota_service.refund_image_upload(redis, row.user_id)
                except Exception:
                    # Best-effort: a Redis hiccup here must not prevent the
                    # reaper from completing -- the slot is daily-scoped and
                    # resets at midnight anyway.
                    logger.debug(
                        "Image quota refund failed for user %s", row.user_id, exc_info=True
                    )
    logger.info("Reaped %d orphan attachment(s)", len(removed))
    return len(removed)
