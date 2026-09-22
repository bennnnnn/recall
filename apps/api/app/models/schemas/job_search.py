"""API schemas for the purpose-built My Job assistant."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

JobSearchFrequency = Literal["daily", "weekdays", "weekly", "monthly"]
JobSearchStatus = Literal["active", "paused"]
JobSearchWorkMode = Literal["remote", "hybrid", "onsite"]
JobSearchExperience = Literal["internship", "entry", "mid", "senior"]
JobMatchStatus = Literal[
    "new",
    "saved",
    "applied",
    "interviewing",
    "offer",
    "rejected",
    "hidden",
]
JobSearchListMode = Literal["replace", "add", "remove"]


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


class JobSearchPreferencesPatch(BaseModel):
    """Bounded partial update shared by chat and one-off searches.

    ``model_fields_set`` distinguishes omitted nullable fields from an explicit
    request to clear them. Role/skill/exclusion modes let natural chat requests
    such as "add product manager" avoid replacing the user's whole profile.
    """

    model_config = ConfigDict(title="JobSearchPreferencesPatch", extra="forbid")

    target_roles: list[str] | None = Field(
        default=None,
        max_length=6,
        description="Target job titles as an array, for example ['Product Manager'].",
    )
    target_roles_mode: JobSearchListMode = "replace"
    skills: list[str] | None = Field(
        default=None,
        max_length=30,
        description="Desired skills as an array.",
    )
    skills_mode: JobSearchListMode = "replace"
    location: str | None = Field(default=None, max_length=160)
    work_modes: list[JobSearchWorkMode] | None = Field(
        default=None,
        description="Work modes as an array: remote, hybrid, or onsite.",
    )
    experience_levels: list[JobSearchExperience] | None = Field(
        default=None,
        description="Experience levels as an array: internship, entry, mid, or senior.",
    )
    salary_min: int | None = Field(default=None, ge=0, le=1_000_000)
    requires_sponsorship: bool | None = None
    excluded_companies: list[str] | None = Field(default=None, max_length=20)
    excluded_companies_mode: JobSearchListMode = "replace"
    background: str | None = Field(default=None, max_length=6000)
    result_count: Literal[5, 10, 15] | None = None
    frequency: JobSearchFrequency | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_tool_aliases(cls, value: object) -> object:
        """Accept common singular keys emitted by function-calling models.

        The public schema stays explicit and bounded, while My Job remains
        resilient when a provider emits ``work_mode`` instead of
        ``work_modes`` (or another equivalent singular spelling).
        """
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        aliases = {
            "target_role": "target_roles",
            "roles": "target_roles",
            "role": "target_roles",
            "job_type": "target_roles",
            "skill": "skills",
            "work_mode": "work_modes",
            "experience": "experience_levels",
            "experience_level": "experience_levels",
            "excluded_company": "excluded_companies",
            "locations": "location",
        }
        for raw_key in list(normalized):
            normalized_key = "_".join(raw_key.strip().casefold().replace("-", " ").split())
            canonical = {
                "work_style": "work_modes",
                "work_type": "work_modes",
                "experience_level": "experience_levels",
                "experience_levels": "experience_levels",
                "excluded_companies": "excluded_companies",
            }.get(normalized_key)
            if canonical is not None and canonical not in normalized:
                normalized[canonical] = normalized.pop(raw_key)
        for alias, canonical in aliases.items():
            alias_value = normalized.pop(alias, None)
            if canonical not in normalized and alias_value is not None:
                normalized[canonical] = alias_value
        for field_name in (
            "target_roles",
            "skills",
            "work_modes",
            "experience_levels",
            "excluded_companies",
        ):
            field_value = normalized.get(field_name)
            if isinstance(field_value, str):
                normalized[field_name] = [field_value]
        mode_aliases = {
            "on site": "onsite",
            "on-site": "onsite",
            "onsite work": "onsite",
            "work from home": "remote",
            "remote work": "remote",
            "hybrid work": "hybrid",
            "hybrid work mode": "hybrid",
        }
        if isinstance(normalized.get("work_modes"), list):
            normalized["work_modes"] = [
                mode_aliases.get(str(item).strip().casefold(), str(item).strip().casefold())
                for item in normalized["work_modes"]
            ]
        experience_aliases = {
            "intern": "internship",
            "entry level": "entry",
            "entry-level": "entry",
            "mid level": "mid",
            "mid-level": "mid",
            "experienced": "mid",
            "experienced level": "mid",
            "intermediate": "mid",
            "intermediate level": "mid",
            "2-5 years": "mid",
            "2\u20135 years": "mid",
            "senior level": "senior",
            "senior-level": "senior",
        }
        if isinstance(normalized.get("experience_levels"), list):
            normalized["experience_levels"] = [
                experience_aliases.get(
                    str(item).strip().casefold(),
                    str(item).strip().casefold(),
                )
                for item in normalized["experience_levels"]
            ]
        frequency = normalized.get("frequency")
        if isinstance(frequency, str):
            normalized["frequency"] = frequency.strip().casefold()
        location = normalized.get("location")
        if isinstance(location, str) and location.strip().casefold().replace(".", "") in {
            "us",
            "usa",
            "united states of america",
        }:
            normalized["location"] = "United States"
        return normalized

    @field_validator("target_roles", "skills", "excluded_companies")
    @classmethod
    def normalize_optional_lists(
        cls,
        value: list[str] | None,
        info: ValidationInfo,
    ) -> list[str] | None:
        if value is None:
            return None
        field_name = info.field_name
        if field_name is None:
            raise ValueError("field name is required")
        limit = {"target_roles": 6, "skills": 30, "excluded_companies": 20}[field_name]
        return _clean_list(value, limit=limit)

    @field_validator("location", "background")
    @classmethod
    def normalize_patch_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.strip().split()) if "\n" not in value else value.strip()
        return cleaned or None

    @field_validator("work_modes", "experience_levels")
    @classmethod
    def require_patch_selection(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
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


class ResumeProfile(BaseModel):
    """Structured facts extracted once from an uploaded resume.

    Stored as JSON on the profile so each run can target queries and ranking
    without re-reading the raw resume text.
    """

    model_config = ConfigDict(title="ResumeProfile")

    titles: list[str] = Field(default_factory=list, max_length=8)
    skills: list[str] = Field(default_factory=list, max_length=25)
    years_experience: float | None = None
    domains: list[str] = Field(default_factory=list, max_length=6)
    education: str | None = Field(default=None, max_length=200)
    summary: str | None = Field(default=None, max_length=400)

    @field_validator("titles", "skills", "domains")
    @classmethod
    def clean_items(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        for raw in values:
            value = " ".join(raw.strip().split())[:80]
            if value and value.casefold() not in {item.casefold() for item in result}:
                result.append(value)
        return result


class JobMatchOut(BaseModel):
    model_config = ConfigDict(title="JobMatchOut")

    id: UUID
    title: str
    company: str
    company_logo_url: str | None = None
    location: str | None = None
    work_mode: JobSearchWorkMode | None = None
    salary: str | None = None
    experience: str | None = None
    match_score: int | None = None
    url: str
    source: str | None = None
    posted_at: str | None = None
    summary: str | None = None
    required_skills: list[str] = Field(default_factory=list)
    match_reasons: list[str] = Field(default_factory=list)
    gap: str | None = None
    found_at: datetime
    status: JobMatchStatus = "new"
    notes: str | None = None


class JobSearchDashboardOut(BaseModel):
    model_config = ConfigDict(title="JobSearchDashboardOut")

    profile: JobSearchProfileOut | None = None
    matches: list[JobMatchOut] = Field(default_factory=list)


class JobSearchRunOut(BaseModel):
    model_config = ConfigDict(title="JobSearchRunOut")

    queued: bool = True


class CoverLetterOut(BaseModel):
    """Generated cover letter — also the structured LLM output schema."""

    model_config = ConfigDict(title="CoverLetterOut")

    cover_letter: str = Field(min_length=1, max_length=6000)


class JobMatchStatusUpdate(BaseModel):
    model_config = ConfigDict(title="JobMatchStatusUpdate")

    status: JobMatchStatus
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("notes")
    @classmethod
    def clean_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class JobSearchStateUpdate(BaseModel):
    model_config = ConfigDict(title="JobSearchStateUpdate")

    status: JobSearchStatus
