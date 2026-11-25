"""An upload's daily slot: which counter it takes, the record that it took one, and its
refund, which skips completed uploads, reuse copies and uploads that took no slot."""

from datetime import UTC, date, datetime
from uuid import UUID

from redis.asyncio import Redis

from app.models.orm import Attachment
from app.modules.attachments.content_types import IMAGE_CONTENT_TYPES, normalize_content_type
from app.services.quota import counters
from app.services.quota.counters import CounterName


def upload_counter(content_type: str) -> CounterName:
    """The daily slot an upload of this type takes: images and documents count apart."""
    if normalize_content_type(content_type) in IMAGE_CONTENT_TYPES:
        return "image_upload"
    return "document_upload"


def has_current_upload_reservation(row: Attachment) -> bool:
    """Only original, unfinished uploads reserved an upload slot today.

    Hidden reuse clones never reserve quota. Completed Library files may have
    already been used, and deleting them must not replenish the daily allowance.
    """
    return (
        row.source == "upload"
        and row.library_visible is True
        and row.verified_at is None
        and isinstance(row.created_at, datetime)
        and row.created_at.replace(tzinfo=row.created_at.tzinfo or UTC).astimezone(UTC).date()
        == datetime.now(UTC).date()
    )


def _slot_key(attachment_id: UUID) -> str:
    return f"recall:upload_slot:{attachment_id}"


async def record_upload_slot(redis: Redis, attachment_id: UUID, day: date) -> None:
    """Note that this upload's presign took a slot on *day*. An upload on a plan whose
    uploads follow its messages took none and has no record, so its refund gives back
    nothing: it once lowered a counter another plan's uploads had raised."""
    await redis.set(_slot_key(attachment_id), day.isoformat(), ex=counters.DAILY_TTL)


async def refund_upload(redis: Redis, row: Attachment) -> None:
    """Give back the slot *row*'s presign took, when it took one, once (the record is
    deleted as it is read). Callers ask ``has_current_upload_reservation`` first."""
    key = _slot_key(row.id)
    raw = await redis.get(key)
    if raw is None or not await redis.delete(key):
        return
    text = raw.decode() if isinstance(raw, bytes) else str(raw)
    await counters.refund(
        upload_counter(row.content_type), redis, row.user_id, day=date.fromisoformat(text)
    )
