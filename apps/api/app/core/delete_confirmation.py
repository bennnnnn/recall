"""A delete of everything says it means it, as ``DELETE /auth/me`` does.

``DELETE /chats`` and ``DELETE /memories`` emptied the account on a bearer token alone, so a
crafted chat link whose id the phone pasted into a path (``/chats/../chats``, resolved by
Android's HTTP stack) reached them (pre-launch review B1, 2026-11-27). Each asks for
``{"confirm": "delete"}`` and refuses 400 ``confirm_required`` without it.
"""

from __future__ import annotations

from fastapi import status
from pydantic import BaseModel, Field

from app.exceptions import DomainError

DELETE_CONFIRMATION = "delete"


class DeleteConfirmation(BaseModel):
    # ``DELETE_CONFIRMATION``, or the delete is refused 400 ``confirm_required``.
    confirm: str | None = Field(default=None, max_length=32)


def require_delete_confirmation(body: DeleteConfirmation | None, message: str) -> None:
    """Refuse a bulk delete whose body does not confirm it; ``message`` names what it deletes."""
    if body is None or body.confirm != DELETE_CONFIRMATION:
        raise DomainError(message, status_code=status.HTTP_400_BAD_REQUEST, code="confirm_required")
