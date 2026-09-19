"""Resume profile extraction for My Job (save-time, best-effort)."""

from unittest.mock import AsyncMock, MagicMock, patch

from app.models.schemas.job_search import ResumeProfile
from app.services import job_search as job_search_service


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
