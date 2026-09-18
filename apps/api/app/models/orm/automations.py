import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

# Same 4 fixed rules as Schedule's recurrence_rule, plus "once" (no recurrence —
# the automation runs a single time then flips to status="completed").
AUTOMATION_FREQUENCIES = ("once", "daily", "weekdays", "weekly", "monthly")
AUTOMATION_STATUSES = ("active", "paused", "completed")
AUTOMATION_RUN_STATUSES = ("ok", "skipped_quota", "error")


class Automation(Base):
    """A recurring prompt the worker runs unattended through the chat turn
    engine (read-only tools only — see services/automations/run.py), posting
    into its own dedicated `chat_id` thread. Not a Schedule reminder: nothing
    here just re-fires static text, every run is a real LLM+tool turn.
    """

    __tablename__ = "automations"
    __table_args__ = (
        Index("ix_automations_user_id", "user_id"),
        # Serves the scheduler's list_due() query: status='active' AND next_run_at <= now.
        Index("ix_automations_status_next_run", "status", "next_run_at"),
        CheckConstraint(
            "frequency IN ('once', 'daily', 'weekdays', 'weekly', 'monthly')",
            name="ck_automations_frequency",
        ),
        CheckConstraint(
            "status IN ('active', 'paused', 'completed')",
            name="ck_automations_status",
        ),
        CheckConstraint(
            "last_run_status IS NULL OR last_run_status IN ('ok', 'skipped_quota', 'error')",
            name="ck_automations_last_run_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # One dedicated Chat per automation (its run history); the automation row
    # is cascade-deleted when that chat is deleted through the normal chat
    # delete path (services/chats.py delete_chat), so DELETE /automations/{id}
    # and a bulk "delete all chats" GDPR wipe both clean up correctly.
    chat_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    frequency: Mapped[str] = mapped_column(String(16), nullable=False)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
