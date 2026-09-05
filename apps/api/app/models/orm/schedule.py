import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class TodoItem(Base):
    __tablename__ = "todo_items"
    __table_args__ = (
        Index("ix_todo_user_created", "user_id", "created_at"),
        Index("ix_todo_user_topic", "user_id", "topic"),
        Index("ix_todo_user_topic_sort", "user_id", "topic", "sort_order"),
        Index("ix_todo_items_user_project", "user_id", "project_id"),
        # DB index (migration 0021) is actually a partial index:
        #   CREATE INDEX ix_todo_user_open_due ON todo_items (user_id, due_at)
        #   WHERE checked = false AND due_at IS NOT NULL
        Index(
            "ix_todo_user_open_due",
            "user_id",
            "due_at",
            postgresql_where=text("checked = false AND due_at IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    chat_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chats.id", ondelete="SET NULL"), nullable=True
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    topic: Mapped[str] = mapped_column(String(200), nullable=False, default="General")
    checked: Mapped[bool] = mapped_column(Boolean, default=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recurrence_rule: Mapped[str | None] = mapped_column(String(16), nullable=True)
    sort_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notification_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    email_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
