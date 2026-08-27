from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

if TYPE_CHECKING:
    from app.models.orm.chat import Chat
    from app.models.orm.integrations import UserCalendarConnection, UserGmailConnection
    from app.models.orm.learning import Learning
    from app.models.orm.memory import Memory


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
    # Last processed RevenueCat webhook event_timestamp_ms — ignore older events.
    rc_last_event_at_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
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

    chats: Mapped[list[Chat]] = relationship(back_populates="user")
    memories: Mapped[list[Memory]] = relationship(back_populates="user")
    projects: Mapped[list[Learning]] = relationship(back_populates="user")
    calendar_connection: Mapped[UserCalendarConnection | None] = relationship(
        back_populates="user",
        uselist=False,
    )
    gmail_connection: Mapped[UserGmailConnection | None] = relationship(
        back_populates="user",
        uselist=False,
    )
