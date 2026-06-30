from uuid import UUID

from sqlalchemy import select
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
) -> Attachment:
    row = Attachment(
        id=attachment_id,
        user_id=user_id,
        storage_key=storage_key,
        content_type=content_type,
        size_bytes=size_bytes,
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


async def link_message(session: AsyncSession, row: Attachment, message_id: UUID) -> Attachment:
    row.message_id = message_id
    await session.commit()
    await session.refresh(row)
    return row
