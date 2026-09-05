"""Immutable question outcomes from the Learning lesson screen."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class LearningPracticeEvent(Base):
    __tablename__ = "learning_practice_events"
    __table_args__ = (
        UniqueConstraint("user_id", "attempt_id", name="uq_learning_practice_user_attempt"),
        CheckConstraint(
            "NOT completes_word OR was_correct", name="ck_learning_practice_completion"
        ),
        CheckConstraint(
            "NOT newly_mastered OR completes_word", name="ck_learning_practice_new_mastery"
        ),
        Index("ix_learning_practice_user_time", "user_id", "occurred_at", "id"),
        Index("ix_learning_practice_project_time", "project_id", "occurred_at"),
        Index("ix_learning_practice_item_time", "item_id", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project_items.id", ondelete="CASCADE"), nullable=False
    )
    was_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    completes_word: Mapped[bool] = mapped_column(Boolean, nullable=False)
    newly_mastered: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
