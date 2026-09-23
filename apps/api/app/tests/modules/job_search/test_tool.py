"""My Job chat tool: intent routing + adapter behavior."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.job_search import tool as job_search_adapter
from app.modules.job_search.chat_intent import wants_job_search, wants_job_search_turn
from app.modules.job_search.tool import JobSearchAdapter, bind_job_search_context


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


def test_job_intent_recognizes_terse_search_follow_up_from_context() -> None:
    messages: list[dict[str, object]] = [
        {
            "role": "assistant",
            "content": "Your My Job preferences are saved. I can start searching for roles.",
        },
        {"role": "user", "content": "search 2"},
    ]
    assert wants_job_search_turn(messages)


def test_job_intent_does_not_guess_standalone_terse_search() -> None:
    assert not wants_job_search_turn([{"role": "user", "content": "search 2"}])


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
    match.canonical_url = "https://jobs.example.com/1"
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


async def test_adapter_search_now_returns_only_persisted_verified_matches() -> None:
    adapter = JobSearchAdapter()
    user = MagicMock()
    profile = _profile()
    run_search = AsyncMock(
        return_value=job_search_adapter.job_search_runner.JobSearchRunResult(
            status="completed",
            canonical_urls=("https://jobs.example.com/1",),
        )
    )
    with (
        bind_job_search_context(user=user, redis=MagicMock(), settings=MagicMock()),
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
        patch.object(
            job_search_adapter.job_search_runner,
            "run_job_search",
            new=run_search,
        ),
        patch.object(
            job_search_adapter.job_search_service,
            "can_request_manual_run",
            return_value=True,
        ),
    ):
        result = await adapter.invoke({"action": "search_now", "result_limit": 2})
    run_search.assert_awaited_once()
    run_args = run_search.await_args
    assert run_args is not None
    assert run_args.kwargs["result_limit"] == 2
    assert "found and saved 1 verified job" in result.content
    assert "[Nurse at Acme Health](https://jobs.example.com/1)" in result.content
    assert result.data is not None and "direct_reply" in result.data


async def test_adapter_search_now_free_user_does_not_run() -> None:
    adapter = JobSearchAdapter()
    user = MagicMock()
    profile = _profile(
        last_run_at=datetime.now(UTC) - timedelta(days=1),
        last_run_status="ok",
    )
    run_search = AsyncMock()
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
            job_search_adapter.job_search_runner,
            "run_job_search",
            new=run_search,
        ),
        patch.object(
            job_search_adapter.job_search_service,
            "can_request_manual_run",
            return_value=False,
        ),
    ):
        result = await adapter.invoke({"action": "search_now"})
    run_search.assert_not_awaited()
    assert "Recall Pro" in result.content
    assert "No matches yet" in result.content


async def test_adapter_search_now_explains_paused_profile() -> None:
    adapter = JobSearchAdapter()
    user = MagicMock()
    profile = _profile(status="paused")
    run_search = AsyncMock()
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
            job_search_adapter.job_search_runner,
            "run_job_search",
            new=run_search,
        ),
    ):
        result = await adapter.invoke({"action": "search_now"})

    run_search.assert_not_awaited()
    assert "My Job is paused" in result.content
    assert "Resume My Job" in result.content
    assert "Recall Pro" not in result.content


async def test_adapter_search_now_respects_cooldown() -> None:
    adapter = JobSearchAdapter()
    user = MagicMock()
    profile = _profile(
        last_run_at=datetime.now(UTC),
        last_run_status="ok",
        updated_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    run_search = AsyncMock()
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
            job_search_adapter.job_search_runner,
            "run_job_search",
            new=run_search,
        ),
        patch.object(
            job_search_adapter.job_search_service,
            "can_request_manual_run",
            return_value=True,
        ),
    ):
        result = await adapter.invoke({"action": "search_now"})
    run_search.assert_not_awaited()
    assert "finished a few minutes ago" in result.content


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
    patch_args = patch_profile.await_args
    assert patch_args is not None
    patch_arg = patch_args.args[3]
    assert patch_arg.target_roles_mode == "add"
    assert patch_arg.experience_levels == ["senior"]
    assert "Clinical Educator" in result.content


async def test_adapter_temporary_search_passes_override_without_changing_profile() -> None:
    adapter = JobSearchAdapter()
    user = MagicMock()
    profile = _profile()
    run_search = AsyncMock(
        return_value=job_search_adapter.job_search_runner.JobSearchRunResult(status="completed")
    )
    with (
        bind_job_search_context(user=user, redis=MagicMock(), settings=MagicMock()),
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
        patch.object(
            job_search_adapter.job_search_runner,
            "run_job_search",
            new=run_search,
        ),
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
    run_args = run_search.await_args
    assert run_args is not None
    overrides = run_args.kwargs["overrides"]
    assert overrides["target_roles"] == ["Clinic Manager"]
    assert overrides["work_modes"] == ["onsite"]
    assert "no verified jobs" in result.content
