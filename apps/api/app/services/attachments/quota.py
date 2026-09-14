"""Identify abandoned reservations without refunding completed uploads or reuse copies."""

from datetime import UTC, datetime

from app.models.orm import Attachment


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
