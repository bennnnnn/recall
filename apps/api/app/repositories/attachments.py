from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Attachment


async def create_pending(
    session: AsyncSession,
    *,
    attachment_id: UUID,
    user_id: UUID,
    storage_key: str,
    content_type: str,
    size_bytes: int,
    source: str = "upload",
) -> Attachment:
    row = Attachment(
        id=attachment_id,
        user_id=user_id,
        storage_key=storage_key,
        content_type=content_type,
        size_bytes=size_bytes,
        source=source,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def get_by_id(session: AsyncSession, attachment_id: UUID, user_id: UUID) -> Attachment | None:
    result = await session.execute(
        select(Attachment).where(Attachment.id == attachment_id, Attachment.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def get_by_ids(
    session: AsyncSession, attachment_ids: list[UUID], user_id: UUID
) -> list[Attachment]:
    """Batched ``get_by_id`` — one round-trip instead of one query per id.

    Scoped by ``user_id`` like ``get_by_id``. Order is not guaranteed to match
    ``attachment_ids``; callers that care should re-order by id themselves.
    """
    if not attachment_ids:
        return []
    result = await session.execute(
        select(Attachment).where(Attachment.id.in_(attachment_ids), Attachment.user_id == user_id)
    )
    return list(result.scalars().all())


async def link_message(session: AsyncSession, row: Attachment, message_id: UUID) -> Attachment:
    row.message_id = message_id
    await session.commit()
    await session.refresh(row)
    return row


async def link_to_message(
    session: AsyncSession,
    *,
    user_id: UUID,
    attachment_ids: list[UUID],
    message_id: UUID,
) -> int:
    """Bulk-link a set of attachments to the message just created.

    Only rows owned by ``user_id`` and not already linked are updated, so a
    client can't relink another user's attachment or double-link. Returns the
    number of rows linked. Called from the chat send path right after the user
    message is persisted, so attachments stop being permanent orphans.
    """
    if not attachment_ids:
        return 0
    from sqlalchemy import update as sql_update

    result = cast(
        CursorResult[Any],
        await session.execute(
            sql_update(Attachment)
            .where(
                Attachment.id.in_(attachment_ids),
                Attachment.user_id == user_id,
                Attachment.message_id.is_(None),
            )
            .values(message_id=message_id)
        ),
    )
    await session.commit()
    return result.rowcount or 0


async def list_for_message_ids(session: AsyncSession, message_ids: list[UUID]) -> list[Attachment]:
    if not message_ids:
        return []
    result = await session.execute(select(Attachment).where(Attachment.message_id.in_(message_ids)))
    return list(result.scalars().all())


async def list_for_user(session: AsyncSession, user_id: UUID) -> list[Attachment]:
    """All attachments owned by ``user_id`` (linked and pending) — account delete."""
    result = await session.execute(select(Attachment).where(Attachment.user_id == user_id))
    return list(result.scalars().all())


async def list_orphans(session: AsyncSession, *, older_than_hours: int) -> list[Attachment]:
    """Attachments never linked to a message (message_id IS NULL) past the grace
    window — candidates for the reaper. Pending uploads that were never sent and
    attachments unlinked by a message delete (FK SET NULL) both land here."""
    cutoff = datetime.now(UTC) - timedelta(hours=older_than_hours)
    result = await session.execute(
        select(Attachment).where(
            Attachment.message_id.is_(None),
            Attachment.created_at < cutoff,
        )
    )
    return list(result.scalars().all())


async def delete_rows(
    session: AsyncSession,
    ids: list[UUID],
    *,
    commit: bool = True,
) -> int:
    """Delete attachment rows by id (the reaper deletes bytes first, then this)."""
    if not ids:
        return 0
    from sqlalchemy import delete as sql_delete

    result = cast(
        CursorResult[Any],
        await session.execute(sql_delete(Attachment).where(Attachment.id.in_(ids))),
    )
    if commit:
        await session.commit()
    return result.rowcount or 0


async def delete_unlinked_returning(session: AsyncSession, ids: list[UUID]) -> list[str]:
    """Delete rows still unlinked; return storage keys removed from the DB."""
    if not ids:
        return []
    from sqlalchemy import delete as sql_delete

    result = await session.execute(
        sql_delete(Attachment)
        .where(
            Attachment.id.in_(ids),
            Attachment.message_id.is_(None),
        )
        .returning(Attachment.storage_key)
    )
    await session.commit()
    return [row[0] for row in result.all()]
