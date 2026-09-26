"""Chat-history message chunks.

Attachment rows live in the attachments module and are re-exported here so older
imports keep working.
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.modules.attachments.models import Attachment as Attachment
from app.modules.attachments.models import AttachmentChunk as AttachmentChunk


class MessageChunk(Base):
    __tablename__ = "message_chunks"
    __table_args__ = (
        UniqueConstraint("message_id", "chunk_index", name="uq_message_chunks_message_index"),
        Index("ix_message_chunks_user", "user_id"),
        Index("ix_message_chunks_user_chat", "user_id", "chat_id"),
        Index("ix_message_chunks_message", "message_id"),
        # DB index (migration 0064) is actually:
        #   CREATE INDEX ix_message_chunks_embedding ON message_chunks
        #   USING hnsw (embedding vector_cosine_ops)
        Index("ix_message_chunks_embedding", "embedding"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    chat_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chats.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
