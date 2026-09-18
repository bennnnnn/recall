"""Purpose-built My Job profile, scheduled prompt, and structured match feed.

The durable scheduler remains the existing Automation engine, but this module
owns the product contract: one search profile per user, strict job-only prompt,
resume extraction, match parsing, and Saved/Applied state.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, cast
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.gateways.storage_gateway import get_storage_gateway
from app.models.orm import Automation, User
from app.models.schemas.job_search import (
    JobMatchOut,
    JobMatchStatus,
    JobSearchDashboardOut,
    JobSearchExperience,
    JobSearchFrequency,
    JobSearchProfileOut,
    JobSearchUpsert,
    JobSearchWorkMode,
)
from app.repositories import attachments as attachments_repo
from app.repositories import automations as automations_repo
from app.repositories import chats as chats_repo
from app.repositories import messages as messages_repo
from app.services import chats as chats_service
from app.services import plan as plan_service
from app.services.attachments import content as attachment_content_service
from app.services.prompt_safety import wrap_untrusted
from app.services.time_context import normalize_due_at

_CONFIG_VERSION = 1
_MAX_RESUME_CHARS = 10_000
_MATCH_FENCE_RE = re.compile(r"```job_matches\s*\n([\s\S]*?)```", re.IGNORECASE)
_ALLOWED_TRACKING_QUERY_KEYS = {
    "ashby_jid",
    "gh_jid",
    "job_id",
    "jobid",
    "lever-origin",
}
_VALID_WORK_MODES = {"remote", "hybrid", "onsite"}
_VALID_EXPERIENCE_LEVELS = {"internship", "entry", "mid", "senior"}
_VALID_FREQUENCIES = {"daily", "weekdays", "weekly", "monthly"}
_VALID_AUTOMATION_STATUSES = {"active", "paused", "completed"}
_VALID_RUN_STATUSES = {"ok", "skipped_quota", "error"}


class JobSearchError(Exception):
    def __init__(self, detail: str, *, status_code: int) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


class _JobPayloadItem(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    company: str = Field(min_length=1, max_length=180)
    location: str | None = Field(default=None, max_length=180)
    work_mode: Literal["remote", "hybrid", "onsite"] | None = None
    salary: str | None = Field(default=None, max_length=160)
    url: str = Field(min_length=8, max_length=2000)
    source: str | None = Field(default=None, max_length=120)
    posted_at: str | None = Field(default=None, max_length=120)
    summary: str | None = Field(default=None, max_length=1000)
    match_reasons: list[str] = Field(default_factory=list, max_length=5)
    gap: str | None = Field(default=None, max_length=500)

    @field_validator(
        "title",
        "company",
        "location",
        "salary",
        "source",
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

    @field_validator("url")
    @classmethod
    def direct_http_url(cls, value: str) -> str:
        cleaned = value.strip()
        parsed = urlsplit(cleaned)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("job URL must be http(s)")
        return cleaned

    @field_validator("match_reasons")
    @classmethod
    def clean_reasons(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        for raw in values:
            value = " ".join(str(raw).strip().split())
            if value and value not in result:
                result.append(value[:240])
            if len(result) >= 5:
                break
        return result


class _JobPayload(BaseModel):
    jobs: list[_JobPayloadItem] = Field(default_factory=list, max_length=15)


def _require_enabled(settings: Settings) -> None:
    if not settings.automations_enabled:
        raise JobSearchError("My Job is not available", status_code=404)


def _load_config(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _dump_config(value: dict[str, Any]) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _string_list(
    config: dict[str, Any],
    key: str,
    default: list[str] | None = None,
) -> list[str]:
    raw = config.get(key)
    if not isinstance(raw, list):
        return list(default or [])
    return [str(item) for item in raw if isinstance(item, str) and item.strip()]


def _work_modes(config: dict[str, Any]) -> list[JobSearchWorkMode]:
    result: list[JobSearchWorkMode] = []
    for value in _string_list(config, "work_modes", ["remote"]):
        if value in _VALID_WORK_MODES:
            result.append(cast(JobSearchWorkMode, value))
    return result or ["remote"]


def _experience_levels(config: dict[str, Any]) -> list[JobSearchExperience]:
    result: list[JobSearchExperience] = []
    for value in _string_list(config, "experience_levels", ["entry"]):
        if value in _VALID_EXPERIENCE_LEVELS:
            result.append(cast(JobSearchExperience, value))
    return result or ["entry"]


def _frequency(value: str) -> JobSearchFrequency:
    if value in _VALID_FREQUENCIES:
        return cast(JobSearchFrequency, value)
    return "weekly"


def _uuid_or_none(value: object) -> UUID | None:
    if value in (None, ""):
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _normalize_job_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    query = [
        (key, val)
        for key, val in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() in _ALLOWED_TRACKING_QUERY_KEYS
    ]
    path = re.sub(r"/{2,}", "/", parsed.path).rstrip("/") or "/"
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            urlencode(query),
            "",
        )
    )


def _job_id(item: _JobPayloadItem) -> str:
    stable = _normalize_job_url(item.url)
    if not stable:
        stable = f"{item.company}|{item.title}|{item.location or ''}".casefold()
    return str(uuid5(NAMESPACE_URL, stable))


def _prompt_example() -> str:
    example = {
        "jobs": [
            {
                "title": "Software Engineer I",
                "company": "Example",
                "location": "Remote - US",
                "work_mode": "remote",
                "salary": "$110k-$140k",
                "url": "https://company.example/jobs/123",
                "source": "Company careers",
                "posted_at": "2 days ago",
                "summary": "Build production APIs.",
                "match_reasons": [
                    "Python API work",
                    "Accepts 0-2 years",
                ],
                "gap": "Kubernetes is preferred",
            }
        ]
    }
    return json.dumps(example, ensure_ascii=True, separators=(",", ":"))


def _build_prompt(config: dict[str, Any]) -> str:
    roles = ", ".join(_string_list(config, "target_roles"))
    skills = ", ".join(_string_list(config, "skills"))
    work_modes = ", ".join(_string_list(config, "work_modes", ["remote"]))
    levels = ", ".join(_string_list(config, "experience_levels", ["entry"]))
    excluded = ", ".join(_string_list(config, "excluded_companies")) or "None"
    location = str(config.get("location") or "Any location")
    salary_min = config.get("salary_min")
    if isinstance(salary_min, int):
        salary = f"At least ${salary_min:,} when salary is disclosed"
    else:
        salary = "No minimum"
    sponsorship = config.get("requires_sponsorship")
    if sponsorship is True:
        sponsorship_text = "Sponsorship required"
    elif sponsorship is False:
        sponsorship_text = "No sponsorship required"
    else:
        sponsorship_text = "Not specified"
    background = str(config.get("background") or "").strip()
    resume_text = str(config.get("resume_text") or "").strip()
    result_count = int(config.get("result_count") or 5)

    profile_lines = [
        f"Target roles: {roles}",
        f"Experience levels: {levels}",
        f"Skills: {skills or 'No required skills specified'}",
        f"Location: {location}",
        f"Work modes: {work_modes}",
        f"Salary: {salary}",
        f"Work authorization: {sponsorship_text}",
        f"Exclude companies: {excluded}",
    ]
    if background:
        profile_lines.append(f"Candidate background: {background}")

    profile_block = wrap_untrusted(
        "candidate profile",
        "\n".join(profile_lines),
        first_party=True,
    )
    resume_block = wrap_untrusted("resume", resume_text) if resume_text else ""

    lines = [
        "Run the user's dedicated My Job search now.",
        "",
        "CANDIDATE PROFILE",
        profile_block,
    ]
    if resume_block:
        lines.extend(["", "RESUME", resume_block])
    lines.extend(
        [
            "",
            "SEARCH RULES",
            "- Search the public web for fresh, real, currently open jobs.",
            f"- Return up to {result_count} strong matches.",
            "- Never add weak jobs merely to reach the selected count.",
            "- Treat stated location, work mode, experience, sponsorship,",
            "  exclusions, and salary minimum as hard filters.",
            "- Prefer jobs posted in the last 14 days and direct employer or",
            "  applicant-tracking-system application pages.",
            "- Exclude duplicate URLs, expired listings, staffing spam, scraped",
            "  copies, and roles whose seniority clearly conflicts with the profile.",
            "- Do not apply, email, or take any write action.",
            "- Explain the strongest match reasons and one meaningful gap.",
            "- Every URL must point to the specific job listing you verified.",
            "",
            "RESPONSE FORMAT",
            "First write a brief human-readable summary.",
            "Then emit exactly one fenced JSON block with no comments:",
            "```job_matches",
            _prompt_example(),
            "```",
            "Use null for unknown optional fields.",
            'If no strong verified matches exist, return {"jobs":[]}.',
        ]
    )
    return "\n".join(lines)


async def _resume_details(
    session: AsyncSession,
    user: User,
    settings: Settings,
    attachment_id: UUID | None,
    previous: dict[str, Any],
) -> tuple[str | None, str | None]:
    if attachment_id is None:
        return None, None
    if str(previous.get("resume_attachment_id") or "") == str(attachment_id):
        cached = previous.get("resume_text")
        if isinstance(cached, str) and cached.strip():
            filename = previous.get("resume_filename")
            return cached[:_MAX_RESUME_CHARS], str(filename) if filename else None

    row = await attachments_repo.get_by_id(session, attachment_id, user.id)
    if row is None or row.verified_at is None:
        raise JobSearchError(
            "Resume file was not found or is still uploading",
            status_code=422,
        )
    if row.content_type not in attachment_content_service.EXTRACTABLE_CONTENT_TYPES:
        raise JobSearchError(
            "Upload a PDF, DOCX, or text resume",
            status_code=422,
        )

    gateway = get_storage_gateway(settings)
    data = await attachment_content_service.read_attachment_bytes(
        gateway,
        row.storage_key,
    )
    if not data:
        raise JobSearchError("Could not read the resume file", status_code=422)
    details = await attachment_content_service.extract_text_details_async(
        row.content_type,
        data,
        settings,
        max_chars=_MAX_RESUME_CHARS,
        ocr_max_pages=min(settings.attachment_ocr_index_max_pages, 20),
    )
    if details is None or not details.text.strip():
        raise JobSearchError(
            "Could not extract readable text from the resume",
            status_code=422,
        )
    return details.text.strip()[:_MAX_RESUME_CHARS], row.original_filename


def _enforce_plan(user: User, body: JobSearchUpsert) -> None:
    if plan_service.is_pro(user):
        return
    if body.result_count != 5 or body.frequency != "weekly":
        raise JobSearchError(
            "Free My Job searches deliver up to 5 matches weekly. "
            "Upgrade for more jobs or faster delivery.",
            status_code=403,
        )


def _profile_out(
    automation: Automation,
    config: dict[str, Any],
) -> JobSearchProfileOut:
    count = int(config.get("result_count") or 5)
    if count not in {5, 10, 15}:
        count = 5
    raw_salary_min = config.get("salary_min")
    salary_min = raw_salary_min if isinstance(raw_salary_min, int) else None
    raw_status = automation.status
    status = raw_status if raw_status in _VALID_AUTOMATION_STATUSES else "paused"
    raw_run_status = automation.last_run_status
    last_run_status = raw_run_status if raw_run_status in _VALID_RUN_STATUSES else None
    return JobSearchProfileOut(
        id=automation.id,
        target_roles=_string_list(config, "target_roles"),
        skills=_string_list(config, "skills"),
        location=str(config["location"]) if config.get("location") else None,
        work_modes=_work_modes(config),
        experience_levels=_experience_levels(config),
        salary_min=salary_min,
        requires_sponsorship=(
            config.get("requires_sponsorship")
            if isinstance(config.get("requires_sponsorship"), bool)
            else None
        ),
        excluded_companies=_string_list(config, "excluded_companies"),
        background=(str(config["background"]) if config.get("background") else None),
        resume_attachment_id=_uuid_or_none(config.get("resume_attachment_id")),
        resume_filename=(str(config["resume_filename"]) if config.get("resume_filename") else None),
        result_count=cast(Literal[5, 10, 15], count),
        frequency=_frequency(automation.frequency),
        next_run_at=automation.next_run_at,
        status=cast(Literal["active", "paused", "completed"], status),
        last_run_at=automation.last_run_at,
        last_run_status=cast(
            Literal["ok", "skipped_quota", "error"] | None,
            last_run_status,
        ),
        created_at=automation.created_at,
        updated_at=automation.updated_at,
    )


def _parse_message_jobs(content: str) -> list[_JobPayloadItem]:
    jobs: list[_JobPayloadItem] = []
    for raw in _MATCH_FENCE_RE.findall(content):
        try:
            payload = _JobPayload.model_validate_json(raw.strip())
        except ValidationError:
            continue
        jobs.extend(payload.jobs)
    return jobs


async def _collect_matches(
    session: AsyncSession,
    automation: Automation,
    config: dict[str, Any],
    *,
    include_hidden: bool = False,
) -> list[JobMatchOut]:
    messages = await messages_repo.list_recent(
        session,
        automation.chat_id,
        limit=120,
    )
    raw_statuses = config.get("match_statuses")
    statuses = raw_statuses if isinstance(raw_statuses, dict) else {}
    seen: set[str] = set()
    matches: list[JobMatchOut] = []

    for message in reversed(messages):
        if message.role != "assistant":
            continue
        for item in _parse_message_jobs(message.content):
            match_id = _job_id(item)
            if match_id in seen:
                continue
            seen.add(match_id)
            raw_status = statuses.get(match_id, "new")
            status: JobMatchStatus = (
                raw_status if raw_status in {"new", "saved", "applied", "hidden"} else "new"
            )
            if status == "hidden" and not include_hidden:
                continue
            matches.append(
                JobMatchOut(
                    id=match_id,
                    title=item.title,
                    company=item.company,
                    location=item.location,
                    work_mode=item.work_mode,
                    salary=item.salary,
                    url=item.url,
                    source=item.source,
                    posted_at=item.posted_at,
                    summary=item.summary,
                    match_reasons=item.match_reasons,
                    gap=item.gap,
                    found_at=message.created_at,
                    status=status,
                )
            )
    return matches[:200]


async def get_dashboard(
    session: AsyncSession,
    user: User,
    settings: Settings,
) -> JobSearchDashboardOut:
    _require_enabled(settings)
    automation = await automations_repo.get_job_search_for_user(session, user.id)
    if automation is None:
        return JobSearchDashboardOut()
    config = _load_config(automation.config_json)
    matches = await _collect_matches(session, automation, config)
    return JobSearchDashboardOut(
        profile=_profile_out(automation, config),
        matches=matches,
    )


async def upsert_profile(
    session: AsyncSession,
    user: User,
    settings: Settings,
    body: JobSearchUpsert,
) -> JobSearchDashboardOut:
    _require_enabled(settings)
    _enforce_plan(user, body)
    next_run_at = normalize_due_at(body.next_run_at, user.timezone)
    if next_run_at is None:
        raise JobSearchError("Delivery time is required", status_code=422)

    existing = await automations_repo.get_job_search_for_user(session, user.id)
    previous = _load_config(existing.config_json if existing else None)
    resume_text, resume_filename = await _resume_details(
        session,
        user,
        settings,
        body.resume_attachment_id,
        previous,
    )
    raw_statuses = previous.get("match_statuses")
    statuses = raw_statuses if isinstance(raw_statuses, dict) else {}
    resume_attachment_id = (
        str(body.resume_attachment_id) if body.resume_attachment_id else None
    )

    config: dict[str, Any] = {
        "version": _CONFIG_VERSION,
        "target_roles": body.target_roles,
        "skills": body.skills,
        "location": body.location,
        "work_modes": body.work_modes,
        "experience_levels": body.experience_levels,
        "salary_min": body.salary_min,
        "requires_sponsorship": body.requires_sponsorship,
        "excluded_companies": body.excluded_companies,
        "background": body.background,
        "resume_attachment_id": resume_attachment_id,
        "resume_filename": resume_filename,
        "resume_text": resume_text,
        "result_count": body.result_count,
        "match_statuses": statuses,
    }
    prompt = _build_prompt(config)
    encoded = _dump_config(config)

    if existing is None:
        chat = await chats_repo.create(
            session,
            user_id=user.id,
            model="smart-chat",
            commit=False,
        )
        automation = await automations_repo.create(
            session,
            user_id=user.id,
            chat_id=chat.id,
            prompt=prompt,
            frequency=body.frequency,
            next_run_at=next_run_at,
            kind="job_search",
            config_json=encoded,
            commit=False,
        )
        await session.commit()
        await session.refresh(automation)
    else:
        automation = await automations_repo.update(
            session,
            existing,
            prompt=prompt,
            frequency=body.frequency,
            next_run_at=next_run_at,
            status="active",
            config_json=encoded,
        )

    matches = await _collect_matches(session, automation, config)
    return JobSearchDashboardOut(
        profile=_profile_out(automation, config),
        matches=matches,
    )


async def set_search_status(
    session: AsyncSession,
    user: User,
    settings: Settings,
    status: Literal["active", "paused"],
) -> JobSearchDashboardOut:
    _require_enabled(settings)
    automation = await automations_repo.get_job_search_for_user(session, user.id)
    if automation is None:
        raise JobSearchError("Job search not found", status_code=404)
    await automations_repo.update(session, automation, status=status)
    return await get_dashboard(session, user, settings)


async def set_match_status(
    session: AsyncSession,
    user: User,
    settings: Settings,
    match_id: str,
    status: JobMatchStatus,
) -> JobSearchDashboardOut:
    _require_enabled(settings)
    automation = await automations_repo.get_job_search_for_user(session, user.id)
    if automation is None:
        raise JobSearchError("Job search not found", status_code=404)
    config = _load_config(automation.config_json)
    existing_matches = await _collect_matches(
        session,
        automation,
        config,
        include_hidden=True,
    )
    known = {match.id for match in existing_matches}
    if match_id not in known:
        raise JobSearchError("Job match not found", status_code=404)
    raw_statuses = config.get("match_statuses")
    statuses = dict(raw_statuses) if isinstance(raw_statuses, dict) else {}
    if status == "new":
        statuses.pop(match_id, None)
    else:
        statuses[match_id] = status
    config["match_statuses"] = statuses
    await automations_repo.update(
        session,
        automation,
        config_json=_dump_config(config),
    )
    return await get_dashboard(session, user, settings)


async def run_now(
    session: AsyncSession,
    user: User,
    settings: Settings,
) -> JobSearchDashboardOut:
    _require_enabled(settings)
    if not plan_service.is_pro(user):
        raise JobSearchError("Run now requires Recall Pro", status_code=403)
    automation = await automations_repo.get_job_search_for_user(session, user.id)
    if automation is None:
        raise JobSearchError("Set up your job search first", status_code=404)
    now = datetime.now(UTC)
    ran_recently = automation.last_run_at is not None and now - automation.last_run_at < timedelta(
        minutes=10
    )
    if ran_recently:
        raise JobSearchError(
            "A job search ran recently. Try again in a few minutes.",
            status_code=429,
        )
    await automations_repo.update(
        session,
        automation,
        status="active",
        next_run_at=now,
    )
    return await get_dashboard(session, user, settings)


async def delete_profile(
    session: AsyncSession,
    user: User,
    settings: Settings,
) -> None:
    _require_enabled(settings)
    automation = await automations_repo.get_job_search_for_user(session, user.id)
    if automation is None:
        return
    try:
        await chats_service.delete_chat(
            session,
            user,
            automation.chat_id,
            settings=settings,
        )
    except chats_service.ChatsError as exc:
        raise JobSearchError(exc.detail, status_code=exc.status_code) from exc
