"""Records shared by My Job search, posting parse, and ranking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.modules.job_search.schemas import ResumeProfile


@dataclass(frozen=True, slots=True)
class _ProfileSnapshot:
    id: UUID
    user_id: UUID
    timezone: str | None
    is_pro: bool
    target_roles: list[str]
    skills: list[str]
    location: str | None
    work_modes: list[str]
    experience_levels: list[str]
    salary_min: int | None
    requires_sponsorship: bool | None
    excluded_companies: list[str]
    background: str | None
    resume_text: str | None
    resume_profile: ResumeProfile | None
    # Titles/companies the user dismissed ("Not interested") — hard filter for
    # companies, ranking signal for titles.
    hidden_companies: list[str]
    hidden_titles: list[str]
    result_count: int
    frequency: str


@dataclass(frozen=True, slots=True)
class JobSearchRunResult:
    """Verified outcome returned to synchronous callers such as chat."""

    status: Literal["completed", "busy", "unavailable"]
    canonical_urls: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _Candidate:
    candidate_id: int
    title: str
    url: str
    canonical_url: str
    snippet: str
    source: str
    # Full posting text when the page-fetch pass succeeded for this URL.
    page_text: str | None = None


class _RankedJob(BaseModel):
    candidate_id: int
    title: str | None = Field(default=None, max_length=240)
    company: str | None = Field(default=None, max_length=180)
    location: str | None = Field(default=None, max_length=180)
    work_mode: Literal["remote", "hybrid", "onsite"] | None = None
    salary: str | None = Field(default=None, max_length=160)
    experience: str | None = Field(default=None, max_length=120)
    match_score: int | None = Field(default=None, ge=0, le=100)
    posted_at: str | None = Field(default=None, max_length=120)
    summary: str | None = Field(default=None, max_length=1000)
    required_skills: list[str] = Field(default_factory=list, max_length=12)
    match_reasons: list[str] = Field(default_factory=list, max_length=5)
    gap: str | None = Field(default=None, max_length=500)

    @field_validator(
        "title",
        "company",
        "location",
        "salary",
        "experience",
        "posted_at",
        "summary",
        "gap",
    )
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.strip().split())
        return cleaned or None

    @field_validator("required_skills")
    @classmethod
    def clean_skills(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for raw in values:
            value = " ".join(raw.strip().split())[:80]
            key = value.casefold()
            if value and key not in seen:
                seen.add(key)
                result.append(value)
            if len(result) == 12:
                break
        return result

    @field_validator("match_reasons")
    @classmethod
    def clean_reasons(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        for raw in values:
            value = " ".join(raw.strip().split())[:240]
            if value and value not in result:
                result.append(value)
            if len(result) == 5:
                break
        return result


class _RankedPayload(BaseModel):
    jobs: list[_RankedJob] = Field(default_factory=list, max_length=15)


@dataclass(frozen=True, slots=True)
class _AcceptedJob:
    candidate: _Candidate
    title: str
    company: str
    company_logo_url: str | None
    location: str | None
    work_mode: str | None
    salary: str | None
    experience: str | None
    match_score: int | None
    posted_at: str | None
    summary: str | None
    required_skills: list[str]
    match_reasons: list[str]
    gap: str | None


class PostingVerificationError(RuntimeError):
    """Candidate pages could not be verified as readable live postings."""
