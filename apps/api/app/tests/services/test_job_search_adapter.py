"""My Job chat tool: intent routing + adapter behavior."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.job_search.chat_intent import wants_job_search
from app.services.mcp import job_search_adapter
from app.services.mcp.job_search_adapter import JobSearchAdapter, bind_job_search_context


@pytest.mark.parametrize(
    "text",
    [
        "find me jobs",
        "Find me a new role",
        "search for job openings",
        "looking for work",
        "show my job matches",
        "any new matches?",
        "jobs near me",
        "Find me senior product manager jobs in Seattle and use hybrid work.",
        "Change my job search to senior experience and hybrid work.",
        "Check this job posting against my background",
        "Would I be a good fit for this job?",
        "I only want remote roles now",
        "Make it hybrid from now on",
    ],
)
def test_job_intent_triggers(text: str) -> None:
    assert wants_job_search(text)


@pytest.mark.parametrize(
    "text",
    [
        "I got a job offer!",
        "job satisfaction matters to me",
        "what is my job title in my profile",
        "help me write a resignation letter",
        "find me a recipe",
    ],
)
def test_job_intent_ignores_career_talk(text: str) -> None:
    assert not wants_job_search(text)


class _SessionCM:
    def __init__(self, session: MagicMock) -> None:
        self.session = session

    async def __aenter__(self) -> MagicMock:
        return self.session

    async def __aexit__(self, *args: object) -> bool:
        return False


def _session_with_matches(matches: list[MagicMock]) -> MagicMock:
    result = MagicMock()
    result.all.return_value = matches
    session = AsyncMock()
    session.scalars.return_value = result
    return session


def _match(title: str = "Nurse", company: str = "Acme Health", score: int | None = 88) -> MagicMock:
    match = MagicMock()
    match.title = title
    match.company = company
    match.match_score = score
    match.url = "https://jobs.example.com/1"
    match.status = "new"
    match.id = uuid4()
    return match


def _profile(**overrides: object) -> MagicMock:
    values: dict[str, object] = {
        "id": uuid4(),
        "target_roles": ["Nurse"],
        "skills": ["CPR"],
        "location": "Berlin, Germany",
        "work_modes": ["hybrid"],
        "experience_levels": ["mid"],
        "salary_min": None,
        "requires_sponsorship": None,
        "excluded_companies": [],
        "result_count": 5,
        "frequency": "weekly",
        "status": "active",
        "last_run_at": None,
        "last_run_status": None,
        "updated_at": None,
    }
    values.update(overrides)
    return MagicMock(**values)


async def test_adapter_list_without_profile_suggests_setup() -> None:
    adapter = JobSearchAdapter()
    user = MagicMock()
    with (
        bind_job_search_context(user=user, redis=None),
        patch.object(job_search_adapter, "SessionLocal", return_value=_SessionCM(AsyncMock())),
        patch.object(
            job_search_adapter.job_search_service,
            "get_profile_for_user",
            new=AsyncMock(return_value=None),
        ),
    ):
        result = await adapter.invoke({"action": "list"})
    assert "not set up My Job" in result.content


async def test_adapter_list_formats_matches() -> None:
    adapter = JobSearchAdapter()
    user = MagicMock()
    profile = _profile()
    with (
        bind_job_search_context(user=user, redis=None),
        patch.object(
            job_search_adapter,
            "SessionLocal",
            return_value=_SessionCM(_session_with_matches([_match()])),
        ),
        patch.object(
            job_search_adapter.job_search_service,
            "get_profile_for_user",
            new=AsyncMock(return_value=profile),
        ),
    ):
        result = await adapter.invoke({"action": "list"})
    assert "Nurse at Acme Health" in result.content
    assert "88% fit" in result.content
    assert "https://jobs.example.com/1" in result.content


async def test_adapter_search_now_enqueues_for_pro() -> None:
    adapter = JobSearchAdapter()
    user = MagicMock()
    profile = _profile()
    enqueue = AsyncMock()
    with (
        bind_job_search_context(user=user, redis=MagicMock()),
        patch.object(
            job_search_adapter,
            "SessionLocal",
            return_value=_SessionCM(_session_with_matches([_match()])),
        ),
        patch.object(
            job_search_adapter.job_search_service,
            "get_profile_for_user",
            new=AsyncMock(return_value=profile),
        ),
        patch.object(job_search_adapter, "enqueue", new=enqueue),
        patch.object(
            job_search_adapter.job_search_service,
            "can_request_manual_run",
            return_value=True,
        ),
    ):
        result = await adapter.invoke({"action": "search_now"})
    enqueue.assert_awaited_once()
    await_args = enqueue.await_args
    assert await_args is not None and await_args.args[1] == "job_search_run"
    assert "fresh job search" in result.content


async def test_adapter_search_now_free_user_does_not_enqueue() -> None:
    adapter = JobSearchAdapter()
    user = MagicMock()
    profile = _profile(
        last_run_at=datetime.now(UTC) - timedelta(days=1),
        last_run_status="ok",
    )
    enqueue = AsyncMock()
    with (
        bind_job_search_context(user=user, redis=MagicMock()),
        patch.object(
            job_search_adapter,
            "SessionLocal",
            return_value=_SessionCM(_session_with_matches([])),
        ),
        patch.object(
            job_search_adapter.job_search_service,
            "get_profile_for_user",
            new=AsyncMock(return_value=profile),
        ),
        patch.object(job_search_adapter, "enqueue", new=enqueue),
        patch.object(
            job_search_adapter.job_search_service,
            "can_request_manual_run",
            return_value=False,
        ),
    ):
        result = await adapter.invoke({"action": "search_now"})
    enqueue.assert_not_awaited()
    assert "Recall Pro" in result.content
    assert "No matches yet" in result.content


async def test_adapter_search_now_respects_cooldown() -> None:
    adapter = JobSearchAdapter()
    user = MagicMock()
    profile = _profile(
        last_run_at=datetime.now(UTC),
        last_run_status="ok",
        updated_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    enqueue = AsyncMock()
    with (
        bind_job_search_context(user=user, redis=MagicMock()),
        patch.object(
            job_search_adapter,
            "SessionLocal",
            return_value=_SessionCM(_session_with_matches([])),
        ),
        patch.object(
            job_search_adapter.job_search_service,
            "get_profile_for_user",
            new=AsyncMock(return_value=profile),
        ),
        patch.object(job_search_adapter, "enqueue", new=enqueue),
        patch.object(
            job_search_adapter.job_search_service,
            "can_request_manual_run",
            return_value=True,
        ),
    ):
        result = await adapter.invoke({"action": "search_now"})
    enqueue.assert_not_awaited()
    assert "ran a few minutes ago" in result.content


async def test_adapter_update_profile_uses_structured_patch() -> None:
    adapter = JobSearchAdapter()
    user = MagicMock()
    profile = _profile()
    updated = _profile(
        target_roles=["Nurse", "Clinical Educator"],
        experience_levels=["senior"],
    )
    patch_profile = AsyncMock(return_value=MagicMock(profile=updated))
    with (
        bind_job_search_context(user=user, settings=MagicMock()),
        patch.object(
            job_search_adapter,
            "SessionLocal",
            return_value=_SessionCM(_session_with_matches([])),
        ),
        patch.object(
            job_search_adapter.job_search_service,
            "get_profile_for_user",
            new=AsyncMock(return_value=profile),
        ),
        patch.object(
            job_search_adapter.job_search_service,
            "patch_profile",
            new=patch_profile,
        ),
    ):
        result = await adapter.invoke(
            {
                "action": "update_profile",
                "preferences": {
                    "target_roles": ["Clinical Educator"],
                    "target_roles_mode": "add",
                    "experience_levels": ["senior"],
                },
            }
        )
    patch_profile.assert_awaited_once()
    patch_arg = patch_profile.await_args.args[3]
    assert patch_arg.target_roles_mode == "add"
    assert patch_arg.experience_levels == ["senior"]
    assert "Clinical Educator" in result.content


async def test_adapter_temporary_search_keeps_override_in_job_payload() -> None:
    adapter = JobSearchAdapter()
    user = MagicMock()
    profile = _profile()
    enqueue = AsyncMock()
    with (
        bind_job_search_context(user=user, redis=MagicMock()),
        patch.object(
            job_search_adapter,
            "SessionLocal",
            return_value=_SessionCM(_session_with_matches([])),
        ),
        patch.object(
            job_search_adapter.job_search_service,
            "get_profile_for_user",
            new=AsyncMock(return_value=profile),
        ),
        patch.object(
            job_search_adapter.job_search_service,
            "can_request_manual_run",
            return_value=True,
        ),
        patch.object(job_search_adapter, "enqueue", new=enqueue),
    ):
        result = await adapter.invoke(
            {
                "action": "search_now",
                "preferences": {
                    "target_roles": ["Clinic Manager"],
                    "work_modes": ["onsite"],
                },
            }
        )
    payload = enqueue.await_args.args[2]
    assert payload["overrides"]["target_roles"] == ["Clinic Manager"]
    assert payload["overrides"]["work_modes"] == ["onsite"]
    assert "saved My Job profile was not changed" in result.content
