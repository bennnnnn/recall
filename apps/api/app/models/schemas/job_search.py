"""API schemas for the purpose-built My Job assistant."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

JobSearchFrequency = Literal["daily", "weekdays", "weekly", "monthly"]
JobSearchStatus = Literal["active", "paused"]
JobSearchWorkMode = Literal["remote", "hybrid", "onsite"]
JobSearchExperience = Literal["internship", "entry", "mid", "senior"]
JobMatchStatus = Literal["new", "saved", "applied", "hidden"]


def _default_work_modes() -> list[JobSearchWorkMode]:
    return ["remote"]


def _default_experience_levels() -> list[JobSearchExperience]:
    return ["entry"]


def _clean_list(values: list[str], *, limit: int) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = " ".join(str(raw).strip().split())
        if not value:
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(value[:120])
        if len(result) >= limit:
            break
    return result


class JobSearchUpsert(BaseModel):
    model_config = ConfigDict(title="JobSearchUpsert")

    target_roles: list[str] = Field(min_length=1, max_length=6)
    skills: list[str] = Field(default_factory=list, max_length=30)
    location: str | None = Field(default=None, max_length=160)
    work_modes: list[JobSearchWorkMode] = Field(default_factory=_default_work_modes)
    experience_levels: list[JobSearchExperience] = Field(default_factory=_default_experience_levels)
    salary_min: int | None = Field(default=None, ge=0, le=1_000_000)
    requires_sponsorship: bool | None = None
    excluded_companies: list[str] = Field(default_factory=list, max_length=20)
    background: str | None = Field(default=None, max_length=6000)
    resume_attachment_id: UUID | None = None
    result_count: Literal[5, 10, 15] = 10
    frequency: JobSearchFrequency = "weekdays"
    next_run_at: datetime

    @field_validator("target_roles", "skills", "excluded_companies")
    @classmethod
    def normalize_lists(cls, value: list[str], info: ValidationInfo) -> list[str]:
        field_name = info.field_name
        if field_name is None:
            raise ValueError("field name is required")
        limit = {"target_roles": 6, "skills": 30, "excluded_companies": 20}[field_name]
        cleaned = _clean_list(value, limit=limit)
        if field_name == "target_roles" and not cleaned:
            raise ValueError("at least one target role is required")
        return cleaned

    @field_validator("location", "background")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.strip().split()) if "\n" not in value else value.strip()
        return cleaned or None

    @field_validator("work_modes", "experience_levels")
    @classmethod
    def require_selection(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("at least one option is required")
        return list(dict.fromkeys(value))


class JobSearchProfileOut(BaseModel):
    model_config = ConfigDict(title="JobSearchProfileOut")

    id: UUID
    target_roles: list[str]
    skills: list[str]
    location: str | None = None
    work_modes: list[JobSearchWorkMode]
    experience_levels: list[JobSearchExperience]
    salary_min: int | None = None
    requires_sponsorship: bool | None = None
    excluded_companies: list[str]
    background: str | None = None
    resume_attachment_id: UUID | None = None
    resume_filename: str | None = None
    result_count: Literal[5, 10, 15]
    frequency: JobSearchFrequency
    next_run_at: datetime
    status: JobSearchStatus
    last_run_at: datetime | None = None
    last_run_status: Literal["ok", "error", "skipped_quota"] | None = None
    created_at: datetime
    updated_at: datetime


class JobMatchOut(BaseModel):
    model_config = ConfigDict(title="JobMatchOut")

    id: UUID
    title: str
    company: str
    location: str | None = None
    work_mode: JobSearchWorkMode | None = None
    salary: str | None = None
    experience: str | None = None
    match_score: int | None = None
    url: str
    source: str | None = None
    posted_at: str | None = None
    summary: str | None = None
    match_reasons: list[str] = Field(default_factory=list)
    gap: str | None = None
    found_at: datetime
    status: JobMatchStatus = "new"


class JobSearchDashboardOut(BaseModel):
    model_config = ConfigDict(title="JobSearchDashboardOut")

    profile: JobSearchProfileOut | None = None
    matches: list[JobMatchOut] = Field(default_factory=list)


class JobMatchStatusUpdate(BaseModel):
    model_config = ConfigDict(title="JobMatchStatusUpdate")

    status: JobMatchStatus


class JobSearchStateUpdate(BaseModel):
    model_config = ConfigDict(title="JobSearchStateUpdate")

    status: JobSearchStatus
