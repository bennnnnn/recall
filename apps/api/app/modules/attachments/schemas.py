from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.attachment_limits import MAX_ATTACHMENT_SIZE
from app.models.schemas.text import UserText
from app.modules.attachments.models import ORIGINAL_FILENAME_MAX_CHARS

UploadPurpose = Literal["chat", "paste", "avatar", "reference"]


class AttachmentPresignIn(BaseModel):
    content_type: str = Field(min_length=3, max_length=128)
    size_bytes: int = Field(gt=0, le=MAX_ATTACHMENT_SIZE)
    filename: UserText | None = Field(default=None, max_length=ORIGINAL_FILENAME_MAX_CHARS)
    # What the file is for. A chat upload goes out with a message, so on a plan whose
    # uploads follow messages it needs one left; a profile photo or an AI picture's
    # reference photo never does (``upload.create_presigned_upload``). A paste is a chat
    # file holding text the user pasted into the composer: the one upload read as their
    # own words (``pasted_text.py``).
    purpose: UploadPurpose = "chat"


class AttachmentPresignOut(BaseModel):
    attachment_id: UUID
    upload_url: str
    headers: dict[str, str] = Field(default_factory=dict)
    api_upload: bool = False


class LibraryStorageOut(BaseModel):
    """What the account keeps in its Library against its plan's total (Settings shows it)."""

    used_bytes: int
    limit_bytes: int


class AttachmentOut(BaseModel):
    id: UUID
    content_type: str
    size_bytes: int
    download_url: str
    created_at: datetime
    indexed: bool = True
    # The name it was uploaded with; the stored message only links the file.
    original_filename: str | None = None


class AttachmentListItemOut(BaseModel):
    id: UUID
    content_type: str
    size_bytes: int
    download_url: str
    source: str
    created_at: datetime
    chat_id: UUID | None = None
    message_id: UUID | None = None
    original_filename: str | None = None
    chat_title: str | None = None
    # Text the user pasted (``pasted_text.py``): a resend from Library is a paste again.
    pasted: bool = False
