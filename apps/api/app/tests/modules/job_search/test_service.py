"""Resume profile extraction for My Job (save-time, best-effort)."""

from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.orm import JobMatch
from app.models.schemas.tools import JobSearchToolInput
from app.modules.job_search import service as job_search_service
from app.modules.job_search.schemas import (
    JobMatchStatusUpdate,
    JobSearchPreferencesPatch,
    ResumeProfile,
)


def test_match_status_update_accepts_stages_and_notes() -> None:
    body = JobMatchStatusUpdate(status="interviewing", notes="  Call Friday  ")
    assert body.status == "interviewing"
    assert body.notes == "Call Friday"
    assert JobMatchStatusUpdate(status="offer").notes is None
    assert JobMatchStatusUpdate(status="rejected", notes="   ").notes is None
    assert JobMatchStatusUpdate(is_saved=True).is_saved is True


def test_match_status_update_requires_stage_or_bookmark() -> None:
    with pytest.raises(ValidationError):
        JobMatchStatusUpdate()


def test_match_status_update_rejects_unknown_status() -> None:
    with pytest.raises(ValidationError):
        JobMatchStatusUpdate(status="ghosted")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_bookmarking_preserves_applied_stage() -> None:
    match = MagicMock(status="applied", is_saved=False)
    session = AsyncMock()
    session.scalar.return_value = match
    dashboard = MagicMock()

    with patch.object(job_search_service, "get_dashboard", AsyncMock(return_value=dashboard)):
        output = await job_search_service.set_match_status(
            session,
            MagicMock(id=uuid4()),
            MagicMock(),
            uuid4(),
            None,
            is_saved=True,
        )

    assert match.status == "applied"
    assert match.is_saved is True
    session.commit.assert_awaited_once()
    assert output is dashboard


@pytest.mark.asyncio
async def test_legacy_saved_command_bookmarks_without_replacing_stage() -> None:
    match = MagicMock(status="interviewing", is_saved=False)
    session = AsyncMock()
    session.scalar.return_value = match

    with patch.object(job_search_service, "get_dashboard", AsyncMock(return_value=MagicMock())):
        await job_search_service.set_match_status(
            session,
            MagicMock(id=uuid4()),
            MagicMock(),
            uuid4(),
            "saved",
        )

    assert match.status == "interviewing"
    assert match.is_saved is True


def test_preference_patch_adds_and_removes_without_replacing_profile() -> None:
    profile = MagicMock(
        target_roles=["Registered Nurse"],
        skills=["Triage", "CPR"],
        excluded_companies=["Acme"],
    )
    values = job_search_service.preference_values(
        profile,
        JobSearchPreferencesPatch(
            target_roles=["Clinical Educator"],
            target_roles_mode="add",
            skills=["CPR"],
            skills_mode="remove",
            location="Hamburg, Germany",
        ),
    )
    assert values["target_roles"] == ["Registered Nurse", "Clinical Educator"]
    assert values["skills"] == ["Triage"]
    assert values["location"] == "Hamburg, Germany"
    assert "salary_min" not in values


def test_preference_patch_rejects_removing_every_target_role() -> None:
    profile = MagicMock(
        target_roles=["Registered Nurse"],
        skills=[],
        excluded_companies=[],
    )
    with pytest.raises(job_search_service.JobSearchError) as excinfo:
        job_search_service.preference_values(
            profile,
            JobSearchPreferencesPatch(
                target_roles=["Registered Nurse"],
                target_roles_mode="remove",
            ),
        )
    assert excinfo.value.status_code == 422


def test_preference_patch_normalizes_common_tool_aliases() -> None:
    patch = JobSearchPreferencesPatch.model_validate(
        {
            "role": "Product Manager",
            "skill": "Roadmapping",
            "work_mode": "Hybrid",
            "experience_level": "Senior Level",
            "excluded_company": "Acme",
            "location": "USA",
        }
    )
    assert patch.target_roles == ["Product Manager"]
    assert patch.skills == ["Roadmapping"]
    assert patch.work_modes == ["hybrid"]
    assert patch.experience_levels == ["senior"]
    assert patch.excluded_companies == ["Acme"]
    assert patch.location == "United States"


def test_preference_patch_accepts_natural_experience_and_work_phrases() -> None:
    patch = JobSearchPreferencesPatch.model_validate(
        {
            "location": "Seattle, Washington",
            "work_mode": "Hybrid work",
            "experience_level": "Experienced level",
        }
    )

    assert patch.location == "Seattle, Washington"
    assert patch.work_modes == ["hybrid"]
    assert patch.experience_levels == ["mid"]


def test_preference_patch_canonical_fields_win_over_tool_aliases() -> None:
    patch = JobSearchPreferencesPatch.model_validate(
        {
            "target_roles": ["Nurse"],
            "role": "Product Manager",
            "work_modes": ["remote"],
            "work_mode": "hybrid",
        }
    )
    assert patch.target_roles == ["Nurse"]
    assert patch.work_modes == ["remote"]


def test_job_tool_decodes_provider_stringified_preference_aliases() -> None:
    tool_input = JobSearchToolInput.model_validate(
        {
            "action": "update_profile",
            "preferences": (
                '{"roles":"Software Engineer","experience":"entry level","locations":"USA"}'
            ),
        }
    )
    assert tool_input.preferences is not None
    assert tool_input.preferences.target_roles == ["Software Engineer"]
    assert tool_input.preferences.experience_levels == ["entry"]
    assert tool_input.preferences.location == "United States"


def test_job_tool_decodes_provider_compact_preference_string() -> None:
    tool_input = JobSearchToolInput.model_validate(
        {
            "action": "update_profile",
            "preferences": (
                "location: Seattle, Washington; experience level: experienced; work_mode: hybrid"
            ),
        }
    )

    assert tool_input.preferences is not None
    assert tool_input.preferences.location == "Seattle, Washington"
    assert tool_input.preferences.experience_levels == ["mid"]
    assert tool_input.preferences.work_modes == ["hybrid"]


def test_job_tool_decodes_comma_delimited_provider_preference_string() -> None:
    tool_input = JobSearchToolInput.model_validate(
        {
            "action": "update_profile",
            "preferences": ("Location: Portland, Oregon, Experience: senior, Work mode: onsite"),
        }
    )

    assert tool_input.preferences is not None
    assert tool_input.preferences.location == "Portland, Oregon"
    assert tool_input.preferences.experience_levels == ["senior"]
    assert tool_input.preferences.work_modes == ["onsite"]


def test_job_tool_decodes_equals_delimited_provider_preference_string() -> None:
    tool_input = JobSearchToolInput.model_validate(
        {
            "action": "update_profile",
            "preferences": ("location=Portland, Oregon; experience=senior; work_modes=onsite"),
        }
    )

    assert tool_input.preferences is not None
    assert tool_input.preferences.location == "Portland, Oregon"
    assert tool_input.preferences.experience_levels == ["senior"]
    assert tool_input.preferences.work_modes == ["onsite"]


def test_preference_patch_accepts_provider_labels_with_spaces() -> None:
    patch = JobSearchPreferencesPatch.model_validate(
        {
            "location": "Portland, Oregon",
            "experience level": "Senior",
            "work style": "On site",
        }
    )

    assert patch.location == "Portland, Oregon"
    assert patch.experience_levels == ["senior"]
    assert patch.work_modes == ["onsite"]


def test_job_tool_rejects_unknown_compact_preference_labels() -> None:
    with pytest.raises(ValidationError):
        JobSearchToolInput.model_validate(
            {
                "action": "update_profile",
                "preferences": "location: Seattle; favorite color: blue",
            }
        )


@pytest.mark.parametrize(
    ("status", "last_run_at", "last_run_status", "is_pro", "expected"),
    [
        ("active", None, None, False, True),
        ("active", MagicMock(), "error", False, True),
        ("active", MagicMock(), "ok", True, True),
        ("active", MagicMock(), "ok", False, False),
        ("paused", None, None, True, False),
        ("paused", MagicMock(), "error", True, False),
    ],
)
def test_manual_run_policy(
    status: str,
    last_run_at: object | None,
    last_run_status: str | None,
    is_pro: bool,
    expected: bool,
) -> None:
    user = MagicMock()
    profile = MagicMock(
        status=status,
        last_run_at=last_run_at,
        last_run_status=last_run_status,
    )
    with patch.object(job_search_service, "is_pro", return_value=is_pro):
        assert job_search_service.can_request_manual_run(user, profile) is expected


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


def test_match_out_upgrades_legacy_weak_reason_with_profile_evidence() -> None:
    match = SimpleNamespace(
        id=uuid4(),
        title="Backend Engineer",
        company="Acme",
        company_logo_url=None,
        location="United States",
        work_mode="remote",
        salary=None,
        experience="3+ years",
        match_score=86,
        url="https://jobs.example.com/1",
        source="jobs.example.com",
        posted_at=None,
        summary="Remote role requiring Python and SQL.",
        required_skills=["Python", "SQL"],
        match_reasons=["The title and description align with your target role."],
        gap=None,
        found_at=datetime.now(UTC),
        status="new",
        notes=None,
    )
    profile = SimpleNamespace(
        skills=["Python"],
        resume_profile=ResumeProfile(skills=["Python"], years_experience=4),
        experience_levels=["mid"],
        work_modes=["remote"],
        location="United States",
        salary_min=None,
    )

    output = job_search_service.match_out(cast(JobMatch, match), profile_snapshot=profile)

    assert any("Python" in reason for reason in output.match_reasons)
    assert any("4 years" in reason for reason in output.match_reasons)
    assert all("title and description" not in reason.casefold() for reason in output.match_reasons)
    assert output.gap is not None and "SQL" in output.gap


def test_match_out_versions_legacy_bookmark_status() -> None:
    match = SimpleNamespace(
        id=uuid4(),
        title="Backend Engineer",
        company="Acme",
        company_logo_url=None,
        location=None,
        work_mode=None,
        salary=None,
        experience=None,
        match_score=80,
        url="https://jobs.example.com/1",
        source="jobs.example.com",
        posted_at=None,
        summary=None,
        required_skills=[],
        match_reasons=[],
        gap=None,
        found_at=datetime.now(UTC),
        status="saved",
        is_saved=True,
        notes=None,
    )

    modern = job_search_service.match_out(cast(JobMatch, match))
    legacy = job_search_service.match_out(
        cast(JobMatch, match),
        separate_bookmarks=False,
    )

    assert modern.status == "new"
    assert modern.is_saved is True
    assert legacy.status == "saved"
    assert legacy.is_saved is True


@pytest.mark.asyncio
async def test_legacy_unsave_preserves_newer_application_stage() -> None:
    match = MagicMock(status="interviewing", is_saved=True)
    session = AsyncMock()
    session.scalar.return_value = match

    with patch.object(job_search_service, "get_dashboard", AsyncMock(return_value=MagicMock())):
        await job_search_service.set_match_status(
            session,
            MagicMock(id=uuid4()),
            MagicMock(),
            uuid4(),
            "new",
            separate_bookmarks=False,
        )

    assert match.status == "interviewing"
    assert match.is_saved is False


def test_match_out_drops_stale_preference_reasons_after_profile_change() -> None:
    match = SimpleNamespace(
        id=uuid4(),
        title="Backend Engineer",
        company="Acme",
        company_logo_url=None,
        location="Portland, Oregon",
        work_mode="remote",
        salary=None,
        experience="entry level",
        match_score=86,
        url="https://jobs.example.com/1",
        source="jobs.example.com",
        posted_at=None,
        summary="Remote entry-level role.",
        required_skills=[],
        match_reasons=[
            "The Portland, Oregon location matches your Portland, Oregon preference.",
            ("The posting mentions Portland, aligning with your preferred work mode and location."),
        ],
        gap=None,
        found_at=datetime.now(UTC),
        status="new",
        is_saved=True,
        notes=None,
    )
    current_profile = SimpleNamespace(
        skills=[],
        resume_profile=None,
        experience_levels=["entry"],
        work_modes=["remote"],
        location="United States",
        salary_min=None,
    )

    output = job_search_service.match_out(cast(JobMatch, match), profile_snapshot=current_profile)

    assert all("Portland, Oregon preference" not in reason for reason in output.match_reasons)
    assert all("aligning with your" not in reason for reason in output.match_reasons)
    assert any("work-mode preference" in reason for reason in output.match_reasons)
    assert any("selected experience level" in reason for reason in output.match_reasons)


# --- Cover letters ---------------------------------------------------------

from app.modules.job_search.schemas import CoverLetterOut


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
        patch.object(job_search_service, "is_pro", return_value=False),
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
        patch.object(job_search_service, "is_pro", return_value=True),
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
        patch.object(job_search_service, "is_pro", return_value=True),
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
        patch.object(job_search_service, "is_pro", return_value=True),
        patch.object(job_search_service.web_search_gateway, "extract_pages", new=env.extract),
        patch.object(job_search_service.litellm_gateway, "complete_structured", new=env.llm),
    ):
        with pytest.raises(job_search_service.JobSearchError) as excinfo:
            await job_search_service.generate_cover_letter(
                env.session, MagicMock(id=uuid4()), MagicMock(), env.redis, uuid4()
            )
    assert excinfo.value.status_code == 502
