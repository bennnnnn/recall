"""Resume profile extraction for My Job (save-time, best-effort)."""

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from app.models.schemas.job_search import JobMatchStatusUpdate, ResumeProfile
from app.services import job_search as job_search_service


def test_match_status_update_accepts_stages_and_notes() -> None:
    body = JobMatchStatusUpdate(status="interviewing", notes="  Call Friday  ")
    assert body.status == "interviewing"
    assert body.notes == "Call Friday"
    assert JobMatchStatusUpdate(status="offer").notes is None
    assert JobMatchStatusUpdate(status="rejected", notes="   ").notes is None


def test_match_status_update_rejects_unknown_status() -> None:
    with pytest.raises(ValidationError):
        JobMatchStatusUpdate(status="ghosted")  # type: ignore[arg-type]


async def test_extract_resume_profile_returns_parsed_model() -> None:
    extracted = ResumeProfile(
        titles=["Nurse", "Charge Nurse"],
        skills=["Triage", "ACLS"],
        years_experience=6,
        domains=["Healthcare"],
        education="BSN",
        summary="Experienced nurse.",
    )
    with patch.object(
        job_search_service.litellm_gateway,
        "complete_structured",
        new=AsyncMock(return_value=extracted),
    ):
        result = await job_search_service.extract_resume_profile(MagicMock(), "resume text")
    assert result is not None
    assert result.titles == ["Nurse", "Charge Nurse"]
    assert result.years_experience == 6


async def test_extract_resume_profile_none_when_gateway_returns_none() -> None:
    with patch.object(
        job_search_service.litellm_gateway,
        "complete_structured",
        new=AsyncMock(return_value=None),
    ):
        assert await job_search_service.extract_resume_profile(MagicMock(), "text") is None


async def test_extract_resume_profile_swallows_provider_errors() -> None:
    with patch.object(
        job_search_service.litellm_gateway,
        "complete_structured",
        new=AsyncMock(side_effect=RuntimeError("provider down")),
    ):
        assert await job_search_service.extract_resume_profile(MagicMock(), "text") is None


async def test_extract_resume_profile_skips_empty_text() -> None:
    with patch.object(
        job_search_service.litellm_gateway,
        "complete_structured",
        new=AsyncMock(side_effect=AssertionError("must not be called")),
    ):
        assert await job_search_service.extract_resume_profile(MagicMock(), "   ") is None


# --- Cover letters ---------------------------------------------------------

from uuid import uuid4

from app.models.schemas.job_search import CoverLetterOut


@dataclass
class _CoverEnv:
    session: AsyncMock
    redis: AsyncMock
    match: MagicMock
    llm: AsyncMock
    extract: AsyncMock


def _cover_letter_setup(
    *,
    incr_total: int = 1,
    llm_result: CoverLetterOut | None = None,
    pages: dict[str, str] | None = None,
) -> _CoverEnv:
    match = MagicMock()
    match.id = uuid4()
    match.profile_id = uuid4()
    match.title = "Registered Nurse"
    match.company = "Acme Health"
    match.location = "Berlin"
    match.work_mode = "onsite"
    match.match_reasons = ["ICU experience"]
    match.gap = None
    match.summary = "snippet summary"
    match.url = "https://jobs.example.com/1"

    profile = MagicMock()
    profile.target_roles = ["Registered Nurse"]
    profile.skills = ["Triage"]
    profile.experience_levels = ["mid"]
    profile.resume_profile = {"titles": ["Nurse"], "skills": ["Triage"]}
    profile.resume_text = "raw resume"

    session = AsyncMock()
    session.scalar.return_value = match
    session.get.return_value = profile

    redis = AsyncMock()
    redis.incrby.return_value = incr_total

    return _CoverEnv(
        session=session,
        redis=redis,
        match=match,
        llm=AsyncMock(return_value=llm_result),
        extract=AsyncMock(return_value=pages or {}),
    )


async def test_cover_letter_requires_pro() -> None:
    env = _cover_letter_setup()
    with (
        patch.object(job_search_service.plan_service, "is_pro", return_value=False),
        patch.object(job_search_service.web_search_gateway, "extract_pages", new=env.extract),
        patch.object(job_search_service.litellm_gateway, "complete_structured", new=env.llm),
    ):
        with pytest.raises(job_search_service.JobSearchError) as excinfo:
            await job_search_service.generate_cover_letter(
                env.session, MagicMock(id=uuid4()), MagicMock(), env.redis, uuid4()
            )
    assert excinfo.value.status_code == 403


async def test_cover_letter_daily_cap() -> None:
    env = _cover_letter_setup(incr_total=11)
    with (
        patch.object(job_search_service.plan_service, "is_pro", return_value=True),
        patch.object(job_search_service.web_search_gateway, "extract_pages", new=env.extract),
        patch.object(job_search_service.litellm_gateway, "complete_structured", new=env.llm),
    ):
        with pytest.raises(job_search_service.JobSearchError) as excinfo:
            await job_search_service.generate_cover_letter(
                env.session, MagicMock(id=uuid4()), MagicMock(), env.redis, uuid4()
            )
    assert excinfo.value.status_code == 429


async def test_cover_letter_happy_path_includes_posting_text() -> None:
    env = _cover_letter_setup(
        llm_result=CoverLetterOut(cover_letter="Dear Acme Health team, ..."),
        pages={"https://jobs.example.com/1": "We seek an ICU nurse with ACLS."},
    )
    with (
        patch.object(job_search_service.plan_service, "is_pro", return_value=True),
        patch.object(job_search_service.web_search_gateway, "extract_pages", new=env.extract),
        patch.object(job_search_service.litellm_gateway, "complete_structured", new=env.llm),
    ):
        result = await job_search_service.generate_cover_letter(
            env.session, MagicMock(id=uuid4()), MagicMock(), env.redis, uuid4()
        )
    assert result.cover_letter.startswith("Dear Acme")
    await_args = env.llm.await_args
    assert await_args is not None
    payload = await_args.kwargs["messages"][1]["content"]
    assert "ICU nurse with ACLS" in payload
    assert "Registered Nurse" in payload


async def test_cover_letter_llm_failure_is_502() -> None:
    env = _cover_letter_setup(llm_result=None)
    with (
        patch.object(job_search_service.plan_service, "is_pro", return_value=True),
        patch.object(job_search_service.web_search_gateway, "extract_pages", new=env.extract),
        patch.object(job_search_service.litellm_gateway, "complete_structured", new=env.llm),
    ):
        with pytest.raises(job_search_service.JobSearchError) as excinfo:
            await job_search_service.generate_cover_letter(
                env.session, MagicMock(id=uuid4()), MagicMock(), env.redis, uuid4()
            )
    assert excinfo.value.status_code == 502
