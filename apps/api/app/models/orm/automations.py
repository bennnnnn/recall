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
AUTOMATION_KINDS = ("generic", "job_search")


class Automation(Base):
    """A scheduled headless chat turn.

    ``generic`` rows are the original open-ended automation primitive.
    ``job_search`` rows power the purpose-built My Job product and keep their
    structured preferences/status map in ``config_json``. Both use the same
    durable scheduler and hidden result chat.
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
        CheckConstraint(
            "kind IN ('generic', 'job_search')",
            name="ck_automations_kind",
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
    kind: Mapped[str] = mapped_column(
        String(24), nullable=False, default="generic", server_default="generic"
    )
    # Versioned JSON owned by the feature named in ``kind``. My Job stores its
    # search profile, extracted resume text, and per-match Saved/Applied state.
    config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
