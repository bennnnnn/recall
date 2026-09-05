"""Copy a Library attachment so a new chat can link it without stealing the original."""

from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.exceptions import AttachmentValidationError
from app.gateways.storage_gateway import get_storage_gateway
from app.models.orm import Attachment
from app.repositories import attachments as attachments_repo


async def ensure_unlinked_copies(
    session: AsyncSession,
    settings: Settings,
    rows: list[Attachment],
) -> list[Attachment]:
    """Keep already-unlinked rows; copy bytes + insert a hidden clone for linked ones.

    ``link_to_message`` only updates ``message_id IS NULL``. Reusing a Library
    item that is still attached to yesterday's chat needs a new row so today's
    send can link, and so deleting one chat cannot drop the other's file.
    """
    if not rows:
        return []
    out: list[Attachment] = []
    gateway = None
    created_keys: list[str] = []
    try:
        for row in rows:
            if row.message_id is None:
                out.append(row)
                continue
            if row.verified_at is None:
                raise AttachmentValidationError("The attached file has not finished uploading.")
            if gateway is None:
                gateway = get_storage_gateway(settings)
            data = await gateway.read_bytes(row.storage_key)
            if not data:
                raise AttachmentValidationError("Could not read the attached file.")
            new_id = uuid4()
            storage_key = f"{row.user_id}/{new_id}"
            created_keys.append(storage_key)
            await gateway.write_bytes(storage_key, data)
            out.append(
                await attachments_repo.insert_verified_clone(
                    session,
                    src=row,
                    new_id=new_id,
                    storage_key=storage_key,
                )
            )
        if created_keys:
            await session.commit()
    except BaseException:
        try:
            await session.rollback()
        finally:
            from app.services.attachment_lifecycle import (
                delete_storage_keys,
                enqueue_failed_storage_deletes,
            )

            failed = await delete_storage_keys(settings, created_keys)
            await enqueue_failed_storage_deletes(failed)
        raise
    return out
