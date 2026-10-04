"""My Job chat tool: intent routing + adapter behavior."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

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


async def test_adapter_list_without_profile_suggests_setup(
    account, db_session, fake_redis, durable_session
) -> None:
    from app.core.config import Settings

    user, profile = account
    await db_session.delete(profile)
    await db_session.commit()
    with bind_job_search_context(user=user, redis=fake_redis, settings=Settings()):
        result = await JobSearchAdapter().invoke({"action": "list"})
    assert "set up My Job" in result.content and "country" in result.content


async def test_adapter_list_formats_matches(
    account, db_session, fake_redis, durable_session
) -> None:
    from app.core.config import Settings
    from app.modules.job_search.models import JobMatch

    user, profile = account
    match = JobMatch(
        profile_id=profile.id,
        title="Nurse",
        company="Acme Health",
        url="https://jobs.example.com/1",
        canonical_url="https://jobs.example.com/1",
        canonical_url_hash="a" * 64,
        match_reasons=[],
        found_at=datetime.now(UTC),
        match_kind="qualifying",
        assessment={"fit_label": "Potential fit"},
    )
    db_session.add(match)
    await db_session.commit()
    with bind_job_search_context(user=user, redis=fake_redis, settings=Settings()):
        result = await JobSearchAdapter().invoke({"action": "list"})
    assert "job-results" in result.content
    assert result.data and result.data["matches"][0]["id"] == str(match.id)
    assert result.data["matches"][0]["company"] == "Acme Health"
    assert "% fit" not in result.content


async def test_adapter_search_now_returns_only_persisted_verified_matches(
    account, db_session, fake_redis, durable_session
) -> None:
    from app.core.config import Settings
    from app.modules.job_search.models import JobSearchRun

    user, _ = account
    with bind_job_search_context(
        user=user, redis=fake_redis, settings=Settings(job_search_premium_enabled=True)
    ):
        result = await JobSearchAdapter().invoke({"action": "search_now", "result_limit": 2})
    assert "Search queued" in result.content and "close chat" in result.content
    assert result.data and result.data["run_id"]
    from uuid import UUID

    run = await db_session.get(JobSearchRun, UUID(result.data["run_id"]))
    assert run is not None and run.result_limit == 2 and run.state == "queued"


async def test_adapter_search_now_free_user_does_not_run(
    account, db_session, fake_redis, durable_session
) -> None:
    from app.core.config import Settings

    user, _ = account
    user.plan = "free"
    await db_session.commit()
    with bind_job_search_context(
        user=user, redis=fake_redis, settings=Settings(job_search_premium_enabled=True)
    ):
        result = await JobSearchAdapter().invoke({"action": "search_now"})
    assert "Recall Pro" in result.content
    assert result.data and "run_id" not in result.data


async def test_adapter_search_now_explains_paused_profile(
    account, db_session, fake_redis, durable_session
) -> None:
    from app.core.config import Settings

    user, profile = account
    profile.status = "paused"
    await db_session.commit()
    with bind_job_search_context(
        user=user, redis=fake_redis, settings=Settings(job_search_premium_enabled=True)
    ):
        result = await JobSearchAdapter().invoke({"action": "search_now"})
    assert "Resume My Job" in result.content


async def test_adapter_search_now_respects_cooldown(
    account, db_session, fake_redis, durable_session
) -> None:
    from app.core.config import Settings
    from app.modules.job_search.runs import submit_run

    user, _ = account
    settings = Settings(job_search_premium_enabled=True)
    run = await submit_run(db_session, user, settings, fake_redis)
    run.state = "completed"
    await db_session.commit()
    with bind_job_search_context(user=user, redis=fake_redis, settings=settings):
        result = await JobSearchAdapter().invoke({"action": "search_now"})
    assert "ten minutes" in result.content


async def test_adapter_update_profile_uses_structured_patch(
    account, db_session, fake_redis, durable_session
) -> None:
    from app.core.config import Settings

    user, profile = account
    with bind_job_search_context(user=user, redis=fake_redis, settings=Settings()):
        result = await JobSearchAdapter().invoke(
            {
                "action": "update_profile",
                "preferences": {"target_roles": ["Clinic Manager"], "work_modes": ["onsite"]},
            }
        )
    assert profile.target_roles == ["Clinic Manager"] and profile.work_modes == ["onsite"]
    assert profile.revision == 2
    assert result.data and result.data["saved"]["target_roles"] == ["Clinic Manager"]


async def test_adapter_temporary_search_passes_override_without_changing_profile(
    account, db_session, fake_redis, durable_session
) -> None:
    from uuid import UUID

    from app.core.config import Settings
    from app.modules.job_search.models import JobSearchRun

    user, profile = account
    with bind_job_search_context(
        user=user, redis=fake_redis, settings=Settings(job_search_premium_enabled=True)
    ):
        result = await JobSearchAdapter().invoke(
            {
                "action": "search_now",
                "preferences": {"target_roles": ["Clinic Manager"], "work_modes": ["onsite"]},
            }
        )
    assert result.data and result.data["run_id"]
    run = await db_session.get(JobSearchRun, UUID(result.data["run_id"]))
    assert run is not None and run.overrides["target_roles"] == ["Clinic Manager"]
    assert profile.target_roles == ["Backend Engineer"] and profile.revision == 1
    assert "unchanged" in result.content


@pytest.mark.parametrize("text", ["I don't want from DC", "I dont want DC", "Add DC"])
def test_short_location_followups_after_plain_job_search(text):
    from app.modules.job_search.chat_commands import direct_command

    assert direct_command(text) == {"action": "command", "command": text}
    assert wants_job_search_turn(
        [
            {"role": "user", "content": "Search a job"},
            {"role": "assistant", "content": "Wait ten minutes between manual searches"},
            {"role": "user", "content": text},
        ]
    )
    assert not wants_job_search_turn(
        [
            {"role": "user", "content": "Tell me about Washington"},
            {"role": "assistant", "content": "Washington has several meanings."},
            {"role": "user", "content": text},
        ]
    )
