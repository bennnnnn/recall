from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.ids import uuid7

if TYPE_CHECKING:
    from app.models.orm.user import User


class Chat(Base):
    __tablename__ = "chats"
    __table_args__ = (
        Index("ix_chats_user_updated", "user_id", "updated_at"),
        Index("ix_chats_user_project", "user_id", "project_id"),
        Index("ix_chats_user_archived", "user_id", "archived"),
        # DB index (migration 0021) is actually:
        #   CREATE INDEX ix_chats_title_trgm ON chats USING gin (title gin_trgm_ops)
        #   WHERE title IS NOT NULL AND title <> ''
        # Plain Index() can't express the gin/trgm opclass or the partial predicate;
        # declared on `title` so autogenerate knows an index with this name exists
        # here and won't propose dropping it.
        Index("ix_chats_title_trgm", "title"),
        CheckConstraint(
            "quiz_mode IS NULL OR quiz_mode IN ('exam', 'chat')",
            name="ck_chats_quiz_mode",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    quiz_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    title: Mapped[str | None] = mapped_column(String)
    model: Mapped[str] = mapped_column(String, default="free-chat")
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Rolling summary of messages older than the recent window (history compression)
    summary: Mapped[str | None] = mapped_column(Text)
    summary_message_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="chats")
    # passive_deletes defers child removal to the DB's ON DELETE CASCADE
    # (messages.chat_id is NOT NULL, so the ORM must NOT try to null it out)
    messages: Mapped[list[Message]] = relationship(back_populates="chat", passive_deletes=True)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_chat_created", "chat_id", "created_at"),
        # Composite (chat_id, created_at, id) serves the tuple-cursor
        # pagination queries in repositories/messages.py, which order by
        # (created_at DESC, id DESC) and filter on (created_at, id) — the
        # id tiebreaker makes the sort stable when two messages share a
        # millisecond timestamp. See migration 0063.
        Index("ix_messages_chat_created_id", "chat_id", "created_at", "id"),
        Index("ix_messages_chat_role", "chat_id", "role"),
        Index("ix_messages_user_id", "user_id"),
        # DB index (migration 0009) is actually:
        #   CREATE INDEX ix_messages_content_trgm ON messages USING gin (content gin_trgm_ops)
        # Plain Index() can't express the gin/trgm opclass; declared on `content` so
        # autogenerate knows an index with this name exists here and won't propose
        # dropping it.
        Index("ix_messages_content_trgm", "content"),
        CheckConstraint("role IN ('user', 'assistant', 'system')", name="ck_messages_role"),
        CheckConstraint(
            "feedback IS NULL OR feedback IN ('up', 'down')", name="ck_messages_feedback"
        ),
    )

    # uuid7 so (created_at, id) cursors stay time-stable when created_at ties.
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    chat_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chats.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str | None] = mapped_column(String)
    feedback: Mapped[str | None] = mapped_column(String)  # 'up' | 'down' | None
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    chat: Mapped[Chat] = relationship(back_populates="messages")
