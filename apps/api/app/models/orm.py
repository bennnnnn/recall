import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("plan IN ('free', 'pro')", name="ck_users_plan"),
        CheckConstraint(
            "response_tone IN ('funny', 'professional', 'casual', 'soft')",
            name="ck_users_response_tone",
        ),
        CheckConstraint(
            "age IS NULL OR (age >= 13 AND age <= 120)",
            name="ck_users_age_range",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    google_sub: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    apple_sub: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String)
    avatar_url: Mapped[str | None] = mapped_column(String)
    default_model: Mapped[str] = mapped_column(String, default="auto")
    plan: Mapped[str] = mapped_column(String, default="free", server_default="free")
    enabled_models: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    response_style: Mapped[str] = mapped_column(String, default="balanced")
    response_tone: Mapped[str] = mapped_column(String, default="funny", server_default="funny")
    memory_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    push_notifications_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true"
    )
    email_reminders_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    reminder_lead_minutes: Mapped[int] = mapped_column(Integer, default=10, server_default="10")
    custom_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    locale: Mapped[str] = mapped_column(String(10), default="en", server_default="en")
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", server_default="UTC")
    location: Mapped[str | None] = mapped_column(String(128), nullable=True)
    location_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    country: Mapped[str | None] = mapped_column(String(64), nullable=True)
    job: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    chats: Mapped[list["Chat"]] = relationship(back_populates="user")
    memories: Mapped[list["Memory"]] = relationship(back_populates="user")
    projects: Mapped[list["Project"]] = relationship(back_populates="user")
    calendar_connection: Mapped["UserCalendarConnection | None"] = relationship(
        back_populates="user",
        uselist=False,
    )
    gmail_connection: Mapped["UserGmailConnection | None"] = relationship(
        back_populates="user",
        uselist=False,
    )


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

    user: Mapped["User"] = relationship(back_populates="chats")
    # passive_deletes defers child removal to the DB's ON DELETE CASCADE
    # (messages.chat_id is NOT NULL, so the ORM must NOT try to null it out)
    messages: Mapped[list["Message"]] = relationship(back_populates="chat", passive_deletes=True)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_chat_created", "chat_id", "created_at"),
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

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
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

    chat: Mapped["Chat"] = relationship(back_populates="messages")


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

    user: Mapped["User"] = relationship(back_populates="memories")


class UsageDaily(Base):
    __tablename__ = "usage_daily"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)


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
    sort_order: Mapped[int | None] = mapped_column(nullable=True)
    notification_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    email_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Suggestion(Base):
    __tablename__ = "suggestions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), default="general")
    source: Mapped[str] = mapped_column(String(50), default="model")
    dismissed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        Index("ix_projects_user_updated", "user_id", "updated_at"),
        Index("ix_projects_user_kind", "user_id", "kind"),
        # BUG FIX (was silent): "one language + one trivia project per user"
        # (FEATURES.md) was only checked in-memory in apply_project_actions —
        # two near-concurrent project-sync jobs (at-least-once job
        # redelivery, see core/jobs.py) could both pass that check before
        # either commits. DB-level partial unique index (migration 0055) is
        # the real guard.
        Index(
            "uq_projects_user_kind_active",
            "user_id",
            "kind",
            unique=True,
            postgresql_where=text("kind IN ('language', 'trivia') AND archived = false"),
        ),
        CheckConstraint("kind IN ('language', 'trivia', 'general')", name="ck_projects_kind"),
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
    kind: Mapped[str] = mapped_column(String(50), default="general")
    target_language: Mapped[str] = mapped_column(String(10), default="en", server_default="en")
    native_language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    level: Mapped[str] = mapped_column(String(20), default="level1", server_default="level1")
    daily_goal: Mapped[int | None] = mapped_column(Integer, nullable=True)
    daily_goal_history: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="projects")
    items: Mapped[list["ProjectItem"]] = relationship(
        back_populates="project", passive_deletes=True
    )


class ProjectItem(Base):
    __tablename__ = "project_items"
    __table_args__ = (
        Index("ix_project_items_project_list", "project_id", "list_title"),
        Index("ix_project_items_user_project", "user_id", "project_id"),
        Index("ix_project_items_status_review", "project_id", "status", "last_reviewed_at"),
        Index("ix_project_items_project_due_at", "project_id", "due_at"),
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project: Mapped["Project"] = relationship(back_populates="items")


class QuizMissEvent(Base):
    """Append-only log of wrong-answer events, one row per miss.

    BUG FIX (was silent): day-attribution reads used to key off
    ProjectItem.last_incorrect_at, a single mutable column — a later miss on the
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


class UserCalendarConnection(Base):
    __tablename__ = "user_calendar_connections"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    google_email: Mapped[str] = mapped_column(String(320), nullable=False)
    refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    scopes: Mapped[str] = mapped_column(String(512), nullable=False)
    calendar_id: Mapped[str] = mapped_column(
        String(256), default="primary", server_default="primary"
    )
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="calendar_connection")


class UserGmailConnection(Base):
    __tablename__ = "user_gmail_connections"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    google_email: Mapped[str] = mapped_column(String(320), nullable=False)
    refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    scopes: Mapped[str] = mapped_column(String(512), nullable=False)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="gmail_connection")


class SuggestedReminder(Base):
    __tablename__ = "suggested_reminders"
    __table_args__ = (
        UniqueConstraint("user_id", "gmail_message_id", name="uq_suggested_reminders_user_message"),
        Index("ix_suggested_reminders_user_status", "user_id", "status"),
        Index("ix_suggested_reminders_user_due", "user_id", "due_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    gmail_message_id: Mapped[str] = mapped_column(String(256), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(default=0.5, server_default="0.5")
    source_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    notification_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    todo_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("todo_items.id", ondelete="SET NULL"), nullable=True
    )


class PushToken(Base):
    __tablename__ = "push_tokens"
    __table_args__ = (
        UniqueConstraint("expo_push_token", name="uq_push_tokens_expo_token"),
        Index("ix_push_tokens_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    expo_push_token: Mapped[str] = mapped_column(String(512), nullable=False)
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    device_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Attachment(Base):
    __tablename__ = "attachments"
    __table_args__ = (Index("ix_attachments_user", "user_id"),)

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
