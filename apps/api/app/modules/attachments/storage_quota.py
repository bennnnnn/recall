"""How much an account keeps in its Library, against its plan's total.

Daily upload counts cap how fast files arrive, not how many stay: a free
account could keep about 4.5 GB more every month, forever. Every attachment row
is real stored bytes (a resend copies the object, ``reuse.py``), generated
pictures included, so the total is one SUM over the user's rows
(``ix_attachments_user``). A web lookup's reference photos are part of their
message, not the Library, and are left out. A pending upload counts from its
presign. Two presigns that race the read can both pass, which costs at most a
few files' size past the cap (each is capped by size and by the daily counts).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.orm import Attachment, User
from app.modules.billing.entitlements import allowance
from app.services.quota.messages import plan_message

STORAGE_FULL_MESSAGE_FREE = (
    "Your Library is full. Delete files you no longer need, or upgrade for more room."
)
STORAGE_FULL_MESSAGE_PAID = "Your Library is full. Delete files you no longer need to make room."


# A reference photo a web lookup found (``search``) is part of its message, never a Library
# item: it is not counted against the plan's total (owner, 2026-11-24).
_NOT_STORED_SOURCES = ("search",)


async def stored_bytes(session: AsyncSession, user_id: UUID) -> int:
    """Bytes in the user's attachment rows, pending uploads included, lookup photos not."""
    total = await session.scalar(
        select(func.coalesce(func.sum(Attachment.size_bytes), 0)).where(
            Attachment.user_id == user_id,
            Attachment.source.not_in(_NOT_STORED_SOURCES),
        )
    )
    return int(total or 0)


async def has_room_for(
    session: AsyncSession, settings: Settings, user: User, size_bytes: int
) -> bool:
    """True when *size_bytes* more still fits in the user's plan's Library total."""
    cap = allowance(user, "library_storage_bytes", settings)
    return await stored_bytes(session, user.id) + size_bytes <= cap


async def library_storage(session: AsyncSession, settings: Settings, user: User) -> tuple[int, int]:
    """(bytes kept, the plan's total): the same sum and total the presign checks."""
    cap = allowance(user, "library_storage_bytes", settings)
    return await stored_bytes(session, user.id), cap


def storage_full_message(user: User) -> str:
    return plan_message(user, free=STORAGE_FULL_MESSAGE_FREE, paid=STORAGE_FULL_MESSAGE_PAID)
