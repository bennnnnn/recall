from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

if TYPE_CHECKING:
    from app.models.orm.user import User


class Memory(Base):
    __tablename__ = "memories"
    __table_args__ = (
        Index("ix_memories_user_updated", "user_id", "updated_at"),
        UniqueConstraint("user_id", "type", name="uq_memories_user_type"),
        # DB index (migration 0033) is actually:
        #   CREATE INDEX ix_memories_embedding ON memories USING hnsw (embedding vector_cosine_ops)
        # Plain Index() can't express the hnsw method/vector_cosine_ops opclass; declared
        # on `embedding` so autogenerate knows an index with this name exists here and
        # won't propose dropping it.
        Index("ix_memories_embedding", "embedding"),
        CheckConstraint(
            "type IN ('profile', 'preference', 'project', 'fact', 'focus')",
            name="ck_memories_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Numeric(3, 2))
    embedding_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    # Hash of the text this embedding was actually computed from — lets
    # extraction/consolidation detect "embedding is stale relative to text"
    # reliably across passes, not just within one call. See migration 0057.
    embedding_text_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_chat_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chats.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="memories")
