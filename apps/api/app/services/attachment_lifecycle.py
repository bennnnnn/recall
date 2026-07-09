"""Attachment storage cleanup — message deletes and orphan reaping."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import SessionLocal
from app.gateways.storage_gateway import get_storage_gateway
from app.repositories import attachments as attachments_repo

logger = logging.getLogger(__name__)


async def purge_attachments_for_messages(
    session: AsyncSession,
    settings: Settings,
    message_ids: list[UUID],
) -> int:
    """Delete stored bytes and DB rows for attachments linked to ``message_ids``."""
    if not message_ids:
        return 0
    rows = await attachments_repo.list_for_message_ids(session, message_ids)
    if not rows:
        return 0
    attachment_ids = [row.id for row in rows]
    from app.repositories import attachment_chunks as chunks_repo

    await chunks_repo.delete_for_attachment_ids(session, attachment_ids)
    gateway = get_storage_gateway(settings)
    for row in rows:
        await gateway.delete_bytes(row.storage_key)
    return await attachments_repo.delete_rows(session, attachment_ids)


async def reap_orphan_attachments(settings: Settings) -> int:
    """Delete bytes + rows for attachments never linked to a message past the grace window.

    Storage bytes are deleted BEFORE DB rows: if the storage delete fails (or
    the process crashes mid-loop), the DB rows remain and the next reap retries.
    The old order (rows first, then bytes) left orphaned R2 objects with no DB
    row — unrecoverable, since the reaper discovers orphans via the DB.
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
    logger.info("Reaped %d orphan attachment(s)", len(removed))
    return len(removed)
