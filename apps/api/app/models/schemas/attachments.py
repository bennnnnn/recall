from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AttachmentPresignIn(BaseModel):
    content_type: str = Field(min_length=3, max_length=128)
    size_bytes: int = Field(gt=0, le=10_485_760)


class AttachmentPresignOut(BaseModel):
    attachment_id: UUID
    upload_url: str
    storage_key: str
    headers: dict[str, str] = Field(default_factory=dict)
    api_upload: bool = False


class AttachmentOut(BaseModel):
    id: UUID
    content_type: str
    size_bytes: int
    download_url: str
    created_at: datetime
