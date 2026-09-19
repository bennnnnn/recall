"""Dedicated persistence for the My Job search product."""

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
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

JOB_SEARCH_FREQUENCIES = ("daily", "weekdays", "weekly", "monthly")
JOB_SEARCH_STATUSES = ("active", "paused")
JOB_SEARCH_RUN_STATUSES = ("ok", "error", "skipped_quota")
JOB_MATCH_STATUSES = ("new", "saved", "applied", "hidden")
JOB_WORK_MODES = ("remote", "hybrid", "onsite")


class JobSearchProfile(Base):
    """One structured, scheduled job search per user."""

    __tablename__ = "job_search_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_job_search_profiles_user"),
        Index("ix_job_search_profiles_due", "status", "next_run_at"),
        CheckConstraint(
            "result_count IN (5, 10, 15)",
            name="ck_job_search_profiles_result_count",
        ),
        CheckConstraint(
            "frequency IN ('daily', 'weekdays', 'weekly', 'monthly')",
            name="ck_job_search_profiles_frequency",
        ),
        CheckConstraint(
            "status IN ('active', 'paused')",
            name="ck_job_search_profiles_status",
        ),
        CheckConstraint(
            "last_run_status IS NULL OR last_run_status IN ('ok', 'error', 'skipped_quota')",
            name="ck_job_search_profiles_last_run_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    target_roles: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    skills: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    location: Mapped[str | None] = mapped_column(String(160), nullable=True)
    work_modes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    experience_levels: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requires_sponsorship: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    excluded_companies: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    background: Mapped[str | None] = mapped_column(Text, nullable=True)
    resume_attachment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("attachments.id", ondelete="SET NULL"),
        nullable=True,
    )
    resume_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resume_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    frequency: Mapped[str] = mapped_column(String(16), nullable=False)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class JobMatch(Base):
    """A de-duplicated opening found for one My Job profile."""

    __tablename__ = "job_matches"
    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "canonical_url_hash",
            name="uq_job_matches_profile_url_hash",
        ),
        Index(
            "ix_job_matches_profile_status_found",
            "profile_id",
            "status",
            "found_at",
        ),
        CheckConstraint(
            "work_mode IS NULL OR work_mode IN ('remote', 'hybrid', 'onsite')",
            name="ck_job_matches_work_mode",
        ),
        CheckConstraint(
            "status IN ('new', 'saved', 'applied', 'hidden')",
            name="ck_job_matches_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_search_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    canonical_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    canonical_url_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    company: Mapped[str] = mapped_column(String(180), nullable=False)
    location: Mapped[str | None] = mapped_column(String(180), nullable=True)
    work_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    salary: Mapped[str | None] = mapped_column(String(160), nullable=True)
    experience: Mapped[str | None] = mapped_column(String(120), nullable=True)
    match_score: Mapped[int | None] = mapped_column(nullable=True)
    source: Mapped[str | None] = mapped_column(String(120), nullable=True)
    posted_at: Mapped[str | None] = mapped_column(String(120), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    match_reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    gap: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="new")
    found_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
