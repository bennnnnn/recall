import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
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


class Attachment(Base):
    __tablename__ = "attachments"
    __table_args__ = (
        Index("ix_attachments_user", "user_id"),
        CheckConstraint("source IN ('upload', 'generated')", name="ck_attachments_source"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="upload", default="upload"
    )
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Set once bytes have been verified against the declared type/size.
    # Subsequent /file and /url reads skip the full-object download.
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # False for send-clones of a Library item (same file, new chat). Gallery
    # lists only the original so reuse does not duplicate the archive.
    library_visible: Mapped[bool] = mapped_column(
        Boolean(),
        nullable=False,
        default=True,
        server_default="true",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AttachmentChunk(Base):
    __tablename__ = "attachment_chunks"
    __table_args__ = (
        Index("ix_attachment_chunks_user_chat", "user_id", "chat_id"),
        Index("ix_attachment_chunks_attachment", "attachment_id"),
        # DB index (migration 0047) is actually:
        #   CREATE INDEX ix_attachment_chunks_embedding ON attachment_chunks
        #   USING hnsw (embedding vector_cosine_ops)
        # Plain Index() can't express the hnsw method/vector_cosine_ops opclass; declared
        # on `embedding` so autogenerate knows an index with this name exists here and
        # won't propose dropping it.
        Index("ix_attachment_chunks_embedding", "embedding"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    attachment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attachments.id", ondelete="CASCADE"), nullable=False
    )
    chat_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chats.id", ondelete="CASCADE"), nullable=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


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
