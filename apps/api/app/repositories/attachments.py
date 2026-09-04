from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.orm import Attachment, Chat, Message


def _contains(column: Any, query: str) -> Any:
    """Case-insensitive substring match with LIKE wildcards escaped."""
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return column.ilike(f"%{escaped}%", escape="\\")


async def create_pending(
    session: AsyncSession,
    *,
    attachment_id: UUID,
    user_id: UUID,
    storage_key: str,
    content_type: str,
    size_bytes: int,
    source: str = "upload",
    original_filename: str | None = None,
    commit: bool = True,
) -> Attachment:
    row = Attachment(
        id=attachment_id,
        user_id=user_id,
        storage_key=storage_key,
        content_type=content_type,
        size_bytes=size_bytes,
        source=source,
        original_filename=original_filename,
    )
    session.add(row)
    if commit:
        await session.commit()
        await session.refresh(row)
    else:
        await session.flush()
    return row


async def insert_verified_clone(
    session: AsyncSession,
    *,
    src: Attachment,
    new_id: UUID,
    storage_key: str,
) -> Attachment:
    """Unlinked copy of a Library item for a new chat send. Hidden from gallery."""
    row = Attachment(
        id=new_id,
        user_id=src.user_id,
        storage_key=storage_key,
        content_type=src.content_type,
        size_bytes=src.size_bytes,
        source=src.source,
        original_filename=src.original_filename,
        verified_at=src.verified_at or datetime.now(UTC),
        library_visible=False,
        message_id=None,
    )
    session.add(row)
    await session.flush()
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
    commit: bool = True,
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
    if commit:
        await session.commit()
    return result.rowcount or 0


async def list_for_message_ids(session: AsyncSession, message_ids: list[UUID]) -> list[Attachment]:
    if not message_ids:
        return []
    result = await session.execute(select(Attachment).where(Attachment.message_id.in_(message_ids)))
    return list(result.scalars().all())


async def list_for_user(
    session: AsyncSession,
    user_id: UUID,
    *,
    limit: int | None = None,
) -> list[Attachment]:
    """Attachments owned by ``user_id`` (linked and pending) — account delete / export."""
    stmt = (
        select(Attachment)
        .where(Attachment.user_id == user_id)
        .order_by(Attachment.created_at.asc(), Attachment.id.asc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_for_gallery(
    session: AsyncSession,
    user_id: UUID,
    *,
    category: str | None = None,
    source: str | None = None,
    q: str | None = None,
    limit: int = 30,
    offset: int = 0,
) -> tuple[list[Attachment], bool]:
    """Paginated attachments for the gallery.

    Returns ``(rows, has_more)``. ``category`` narrows by content family:

    * ``"images"`` — ``content_type LIKE 'image/%'``
    * ``"files"``  — ``content_type NOT LIKE 'image/%'``
    * ``None``     — all attachments

    Optional ``source`` filter narrows to ``'upload'`` or ``'generated'``.
    Verified items stay listed after their chat is deleted (``message_id``
    SET NULL); Open chat is omitted when no chat remains. Optional ``q``
    matches original filename, content type, the linked message body, or
    the previous user message in that chat (the draw prompt for generated
    images, which are linked to the assistant ``[Image: …]`` marker rather
    than the user prompt).
    """
    stmt = select(Attachment).where(
        Attachment.user_id == user_id,
        Attachment.verified_at.is_not(None),
        Attachment.library_visible.is_(True),
    )
    if category == "images":
        stmt = stmt.where(Attachment.content_type.like("image/%"))
    elif category == "files":
        stmt = stmt.where(Attachment.content_type.notlike("image/%"))
    if source in ("upload", "generated"):
        stmt = stmt.where(Attachment.source == source)
    if q:
        linked = aliased(Message)
        prev_user_content = (
            select(Message.content)
            .where(
                Message.chat_id == linked.chat_id,
                Message.role == "user",
                Message.created_at < linked.created_at,
            )
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(1)
            .correlate(linked)
            .scalar_subquery()
        )
        stmt = stmt.outerjoin(linked, Attachment.message_id == linked.id)
        stmt = stmt.where(
            or_(
                _contains(Attachment.original_filename, q),
                _contains(Attachment.content_type, q),
                _contains(linked.content, q),
                _contains(prev_user_content, q),
            )
        )
    stmt = stmt.order_by(Attachment.created_at.desc(), Attachment.id.desc())
    page_size = max(limit, 1)
    stmt = stmt.offset(max(offset, 0)).limit(page_size + 1)
    result = await session.execute(stmt)
    rows = list(result.scalars().all())
    has_more = len(rows) > page_size
    return rows[:page_size], has_more


async def chat_meta_for_message_ids(
    session: AsyncSession,
    message_ids: list[UUID],
) -> dict[UUID, tuple[UUID, str | None]]:
    """Map message id → (chat id, chat title) for gallery rows."""
    if not message_ids:
        return {}
    result = await session.execute(
        select(Message.id, Message.chat_id, Chat.title)
        .join(Chat, Chat.id == Message.chat_id)
        .where(Message.id.in_(message_ids))
    )
    return {row[0]: (row[1], row[2]) for row in result.all()}


async def chat_ids_for_message_ids(
    session: AsyncSession,
    message_ids: list[UUID],
) -> dict[UUID, UUID]:
    """Map message id → chat id for gallery 'open chat'. Empty input skips IO."""
    meta = await chat_meta_for_message_ids(session, message_ids)
    return {message_id: chat_id for message_id, (chat_id, _title) in meta.items()}


async def list_orphans(
    session: AsyncSession,
    *,
    older_than_hours: int,
    limit: int = 100,
) -> list[Attachment]:
    """Pending uploads and hidden send-clones never linked to a message.

    Verified Library items that lost their chat (``message_id`` SET NULL,
    ``library_visible`` still true) are not orphans — they stay until the
    user deletes them from Library. Hidden copies created for a later chat
    are reaped once that chat is gone.

    Bounded so one reap cannot load every orphan in the system; the scheduler
    re-runs and drains remaining rows over time.
    """
    cutoff = datetime.now(UTC) - timedelta(hours=older_than_hours)
    result = await session.execute(
        select(Attachment)
        .where(
            Attachment.message_id.is_(None),
            Attachment.created_at < cutoff,
            or_(
                Attachment.verified_at.is_(None),
                Attachment.library_visible.is_(False),
            ),
        )
        .order_by(Attachment.created_at.asc(), Attachment.id.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def mark_verified(session: AsyncSession, attachment_id: UUID, *, commit: bool = True) -> None:
    """Record that stored bytes matched the declared type/size."""
    from sqlalchemy import update as sql_update

    await session.execute(
        sql_update(Attachment)
        .where(Attachment.id == attachment_id)
        .values(verified_at=datetime.now(UTC))
    )
    if commit:
        await session.commit()


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
