from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

if TYPE_CHECKING:
    from app.models.orm.user import User


class VocabDeck(Base):
    """Curated chapter / SAT bank (not per-user)."""

    __tablename__ = "vocab_decks"
    __table_args__ = (
        UniqueConstraint("target_language", "slug", name="uq_vocab_decks_lang_slug"),
        CheckConstraint("kind IN ('chapter', 'sat')", name="ck_vocab_decks_kind"),
        Index("ix_vocab_decks_language_sort", "target_language", "sort_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    target_language: Mapped[str] = mapped_column(String(10), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    domain: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="chapter")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    entries: Mapped[list[VocabEntry]] = relationship(back_populates="deck", passive_deletes=True)


class VocabEntry(Base):
    """One pre-generated word in a catalog deck."""

    __tablename__ = "vocab_entries"
    __table_args__ = (
        UniqueConstraint("deck_id", "content", name="uq_vocab_entries_deck_content"),
        Index("ix_vocab_entries_deck_sort", "deck_id", "sort_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    deck_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vocab_decks.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    example_sentence: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deck: Mapped[VocabDeck] = relationship(back_populates="entries")


class Learning(Base):
    __tablename__ = "projects"
    __table_args__ = (
        Index("ix_projects_user_updated", "user_id", "updated_at"),
        Index("ix_projects_user_kind", "user_id", "kind"),
        Index(
            "uq_projects_user_language_target_active",
            "user_id",
            "target_language",
            unique=True,
            postgresql_where=text("kind = 'language' AND archived = false"),
        ),
        CheckConstraint("kind IN ('language')", name="ck_projects_kind"),
        CheckConstraint(
            "level IN ('level1', 'level2', 'level3', 'level4', 'level5', 'level6')",
            name="ck_projects_level",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    kind: Mapped[str] = mapped_column(String(50), default="language")
    target_language: Mapped[str] = mapped_column(String(10), default="en", server_default="en")
    native_language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    level: Mapped[str] = mapped_column(String(20), default="level1", server_default="level1")
    daily_goal: Mapped[int | None] = mapped_column(Integer, nullable=True)
    daily_goal_history: Mapped[list[dict[str, object]] | None] = mapped_column(JSONB, nullable=True)
    learning_path: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="projects")
    items: Mapped[list[LearningItem]] = relationship(back_populates="project", passive_deletes=True)


class LearningItem(Base):
    __tablename__ = "project_items"
    __table_args__ = (
        Index("ix_project_items_project_list", "project_id", "list_title"),
        Index("ix_project_items_user_project", "user_id", "project_id"),
        Index("ix_project_items_status_review", "project_id", "status", "last_reviewed_at"),
        Index("ix_project_items_project_due_at", "project_id", "due_at"),
        UniqueConstraint(
            "project_id",
            "list_title",
            "content",
            name="uq_project_items_project_list_content",
        ),
        CheckConstraint(
            "status IN ('new', 'learning', 'mastered')", name="ck_project_items_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    chat_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chats.id", ondelete="SET NULL"), nullable=True
    )
    list_title: Mapped[str] = mapped_column(String(200), nullable=False, default="General")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    definition: Mapped[str | None] = mapped_column(Text, nullable=True)
    example_sentence: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="new", server_default="new")
    mastered: Mapped[bool] = mapped_column(Boolean, default=False)
    mastered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_incorrect_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    review_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    quiz_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    quiz_correct: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    ease_factor: Mapped[float] = mapped_column(
        Float, nullable=False, default=2.5, server_default="2.5"
    )
    interval_days: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pronunciation_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    catalog_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vocab_entries.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project: Mapped[Learning] = relationship(back_populates="items")


class QuizMissEvent(Base):
    """Append-only log of wrong-answer events, one row per miss.

    BUG FIX (was silent): day-attribution reads used to key off
    LearningItem.last_incorrect_at, a single mutable column — a later miss on the
    same item silently overwrote which day an earlier miss was attributed to,
    retroactively changing already-rendered day history. This table lets
    day-attribution reads (see daily_learning.count_missed_by_date) use the full
    miss history instead of just the most recent event.
    """

    __tablename__ = "quiz_miss_events"
    __table_args__ = (
        Index("ix_quiz_miss_events_item_occurred", "item_id", "occurred_at"),
        Index("ix_quiz_miss_events_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project_items.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
