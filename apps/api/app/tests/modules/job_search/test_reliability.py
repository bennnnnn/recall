"""Durable contracts across preferences, admission, recovery and publication."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select

from app.core.config import Settings
from app.modules.job_search import publishing, service, worker
from app.modules.job_search.chat_commands import parse_command
from app.modules.job_search.models import (
    JobMatch,
    JobNotificationEvent,
    JobSearchProfile,
    JobSearchRun,
)
from app.modules.job_search.providers import SearchResponse
from app.modules.job_search.ranking import _profile_from_rows
from app.modules.job_search.runs import allowance, submit_run
from app.modules.job_search.schemas import JobSearchPreferencesPatch
from app.modules.job_search.verification import assess, grounded
from app.tests.modules.job_search.posting_fixtures import posting


@pytest.mark.parametrize(
    ("text", "field", "expected"),
    [
        (
            "Add DC",
            "included_locations",
            [{"country": "United States", "region": "District of Columbia"}],
        ),
        (
            "I don’t want DC",
            "excluded_locations",
            [{"country": "United States", "region": "District of Columbia"}],
        ),
        ("Check all over the country", "included_locations", [{"country": "United States"}]),
        ("Update my experience to five years", "years_experience", 5),
        ("Minimum salary to 100k", "salary_min", 100000),
    ],
)
async def test_conversation_examples_are_atomic_and_paused_edits_stay_paused(
    account, db_session, text, field, expected
):
    user, profile = account
    profile.status = "paused"
    await db_session.commit()
    command, clarification = parse_command(text, profile)
    assert clarification is None
    assert command["preferences"][field] == expected
    await service.patch_profile(
        db_session,
        user,
        Settings(),
        JobSearchPreferencesPatch.model_validate(command["preferences"]),
    )
    assert profile.status == "paused"
    assert profile.revision == 2
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(JobSearchRun)
            .where(JobSearchRun.profile_id == profile.id)
        )
        == 0
    )


async def test_exclude_dc_and_countrywide_retain_exclusion(account, db_session):
    user, profile = account
    for text in ("Add DC", "I don't want DC", "Check all over the country"):
        command, clarification = parse_command(text, profile)
        assert clarification is None
        await service.patch_profile(
            db_session,
            user,
            Settings(),
            JobSearchPreferencesPatch.model_validate(command["preferences"]),
        )
    assert profile.included_locations == [
        {"country": "United States", "region": None, "city": None}
    ]
    assert profile.excluded_locations == [
        {"country": "United States", "region": "District of Columbia", "city": None}
    ]


async def test_compound_temporary_and_ambiguous_commands(account, db_session):
    _, profile = account
    command, clarification = parse_command(
        "Add DC and update my experience to six years and minimum salary to USD 100k", profile
    )
    assert clarification is None
    assert len(command["preferences"]) == 5
    temporary, _ = parse_command("Add DC just this time", profile)
    assert temporary["action"] == "search_now"
    assert profile.revision == 1
    profile.country, profile.included_locations, profile.location = None, [], None
    assert (
        parse_command("Check all over the country", profile)[1]
        == "Which country should I search across?"
    )
    profile.salary_currency = None
    assert (
        parse_command("Minimum salary to 100k", profile)[1]
        == "Which currency should I use for your minimum salary?"
    )


async def test_revision_conflict_does_not_save_partial_changes(account, db_session):
    user, profile = account
    with pytest.raises(service.JobSearchError, match="Preferences changed"):
        await service.patch_profile(
            db_session,
            user,
            Settings(),
            JobSearchPreferencesPatch(expected_revision=7, years_experience=9),
        )
    assert profile.years_experience == 5
    assert profile.revision == 1


async def test_duplicate_admission_shares_one_run_and_allowance(account, db_session, fake_redis):
    user, profile = account
    settings = Settings(job_search_premium_enabled=True)
    first = await submit_run(db_session, user, settings, fake_redis, request_key="same")
    duplicate = await submit_run(db_session, user, settings, fake_redis, request_key="same")
    other_click = await submit_run(
        db_session, user, settings, fake_redis, request_key="second-click"
    )
    assert first.id == duplicate.id == other_click.id
    assert (await allowance(db_session, profile, user))[0] == 4
    first.state = "completed"
    await db_session.commit()
    with pytest.raises(service.JobSearchError, match="ten minutes"):
        await submit_run(db_session, user, settings, fake_redis)


async def test_local_daily_allowance_excludes_scheduled_runs(account, db_session, fake_redis):
    user, profile = account
    settings = Settings(job_search_premium_enabled=True)
    from app.modules.job_search.runs import local_day

    now = datetime.now(UTC)
    for index in range(5):
        db_session.add(
            JobSearchRun(
                profile_id=profile.id,
                request_key=str(index),
                profile_revision=1,
                state="failed",
                manual=True,
                local_day=local_day(now, user.timezone),
                created_at=now - timedelta(minutes=20 + index),
            )
        )
    await db_session.commit()
    with pytest.raises(service.JobSearchError, match="Five manual"):
        await submit_run(db_session, user, settings, fake_redis)
    scheduled = await submit_run(
        db_session, user, settings, fake_redis, manual=False, request_key="scheduled"
    )
    assert scheduled.manual is False
    assert (await allowance(db_session, profile, user))[0] == 0
    assert local_day(datetime(2026, 10, 4, 1, tzinfo=UTC), user.timezone) == "2026-10-03"


async def test_expired_pro_history_readable_but_edits_and_runs_rejected(
    account, db_session, fake_redis
):
    user, _profile = account
    user.plan = "free"
    await db_session.commit()
    dashboard = await service.get_dashboard(db_session, user, Settings())
    assert dashboard.pro_required and dashboard.profile is not None
    with pytest.raises(service.JobSearchError):
        await service.patch_profile(
            db_session, user, Settings(), JobSearchPreferencesPatch(years_experience=9)
        )
    with pytest.raises(service.JobSearchError):
        await submit_run(db_session, user, Settings(job_search_premium_enabled=True), fake_redis)
    await service.delete_profile(db_session, user, Settings())
    assert await service.get_profile_for_user(db_session, user.id) is None


async def test_worker_empty_success_and_provider_failure_differ(
    account, db_session, fake_redis, durable_session, monkeypatch
):
    user, _profile = account
    settings = Settings(job_search_premium_enabled=True, web_search_enabled=True)
    monkeypatch.setattr(worker.TavilySearch, "search", AsyncMock(return_value=SearchResponse([])))
    first = await submit_run(
        db_session, user, settings, fake_redis, manual=False, request_key="empty"
    )
    await worker.execute_run(settings, fake_redis, first.id)
    assert first.state == "completed" and first.new_match_count == 0 and not first.partial
    monkeypatch.setattr(
        worker.TavilySearch, "search", AsyncMock(side_effect=RuntimeError("provider secret"))
    )
    second = await submit_run(
        db_session, user, settings, fake_redis, manual=False, request_key="outage"
    )
    await worker.execute_run(settings, fake_redis, second.id)
    assert second.state == "failed"
    assert second.failure_reason == "Search provider is unavailable"
    assert "secret" not in second.failure_reason


async def test_edit_during_run_prevents_publication(
    account, db_session, fake_redis, durable_session
):
    user, profile = account
    run = await submit_run(db_session, user, Settings(job_search_premium_enabled=True), fake_redis)
    snapshot = _profile_from_rows(profile, user)
    run.state = "running"
    await db_session.commit()
    candidate, facts = posting()
    verified = grounded(facts, candidate)
    assert verified is not None
    accepted = assess(snapshot, verified, candidate)
    assert accepted is not None
    await service.patch_profile(
        db_session, user, Settings(), JobSearchPreferencesPatch(years_experience=6)
    )
    assert await publishing.publish(run.id, snapshot, [accepted], partial=False, usage={}) == []
    assert run.state == "cancelled"
    assert (
        await db_session.scalar(
            select(func.count()).select_from(JobMatch).where(JobMatch.profile_id == profile.id)
        )
        == 0
    )
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(JobNotificationEvent)
            .where(JobNotificationEvent.user_id == user.id)
        )
        == 0
    )


async def test_requisition_dedup_preserves_saved_history_and_returns_existing_ids(
    account, db_session, fake_redis, durable_session
):
    user, profile = account
    settings = Settings(job_search_premium_enabled=True)
    snapshot = _profile_from_rows(profile, user)
    accepted = []
    for requisition in ("A101", "B202"):
        candidate, facts = posting(requisition=requisition)
        verified = grounded(facts, candidate)
        assert verified is not None
        match = assess(snapshot, verified, candidate)
        assert match is not None
        accepted.append(match)
    first = await submit_run(
        db_session, user, settings, fake_redis, manual=False, request_key="one"
    )
    first.state = "running"
    await db_session.commit()
    ids = await publishing.publish(first.id, snapshot, accepted, partial=False, usage={})
    assert len(ids) == 2 and first.new_match_count == 2
    saved = await db_session.get(JobMatch, ids[0])
    assert saved is not None
    saved.is_saved, saved.status, saved.notes = True, "applied", "Prepare examples"
    await db_session.commit()
    cross_site = replace(
        accepted[0],
        candidate=replace(
            accepted[0].candidate,
            url="https://board.example.com/unique",
            canonical_url="https://board.example.com/unique",
        ),
    )
    second = await submit_run(
        db_session, user, settings, fake_redis, manual=False, request_key="two"
    )
    second.state = "running"
    await db_session.commit()
    assert await publishing.publish(second.id, snapshot, [cross_site], partial=False, usage={}) == [
        ids[0]
    ]
    assert second.new_match_count == 0
    assert saved.is_saved and saved.status == "applied" and saved.notes == "Prepare examples"
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(JobNotificationEvent)
            .where(JobNotificationEvent.user_id == user.id)
        )
        == 1
    )


async def test_restart_reclaims_expired_lease_without_second_allowance(
    account, db_session, fake_redis, durable_session, monkeypatch
):
    user, profile = account
    settings = Settings(job_search_premium_enabled=True, web_search_enabled=True)
    run = await submit_run(db_session, user, settings, fake_redis, request_key="recover")
    run.state = "running"
    run.lease_until = datetime.now(UTC) - timedelta(seconds=1)
    run.attempts = 1
    run.checkpoint = {"candidates": []}
    run.usage = {"search_requests": 6}
    await db_session.commit()
    search = AsyncMock(side_effect=AssertionError("Completed search phase must not repeat"))
    monkeypatch.setattr(worker.TavilySearch, "search", search)
    await worker.execute_run(settings, fake_redis, run.id)
    assert run.state == "completed" and run.attempts == 2
    search.assert_not_called()
    assert (await allowance(db_session, profile, user))[0] == 4


async def test_search_deletion_cannot_reset_user_allowance(account, db_session, fake_redis):
    from app.modules.job_search.models import JobManualAllowance

    user, profile = account
    run = await submit_run(db_session, user, Settings(job_search_premium_enabled=True), fake_redis)
    reserved = await db_session.get(JobManualAllowance, (user.id, run.local_day))
    assert reserved is not None and reserved.reserved_count == 1
    await service.delete_profile(db_session, user, Settings())
    assert await db_session.get(JobSearchProfile, profile.id) is None
    assert await db_session.get(JobManualAllowance, (user.id, run.local_day)) is reserved
    assert reserved.last_requested_at == run.created_at


async def test_chat_status_reads_live_outcome_and_setup_defaults(
    account, db_session, fake_redis, durable_session
):
    from app.modules.job_search.tool import JobSearchAdapter, bind_job_search_context

    user, _profile = account
    settings = Settings(job_search_premium_enabled=True)
    run = await submit_run(db_session, user, settings, fake_redis)
    run.state = "completed"
    run.new_match_count = 3
    run.qualifying_count = 3
    run.possible_count = 2
    run.partial = True
    await db_session.commit()
    with bind_job_search_context(user=user, redis=fake_redis, settings=settings):
        result = await JobSearchAdapter().invoke({"action": "get_profile"})
    assert (
        "3 new" in result.content
        and "5 matches found" in result.content
        and "partial" in result.content
    )
    assert "possible matches" not in result.content
    assert result.data and result.data["dashboard"]["latest_run"]["id"] == str(run.id)
    await service.delete_profile(db_session, user, settings)
    with bind_job_search_context(user=user, redis=fake_redis, settings=settings):
        setup = await JobSearchAdapter().invoke(
            {"action": "setup", "preferences": {"target_roles": ["Teacher"], "country": "Canada"}}
        )
    saved = await service.get_profile_for_user(db_session, user.id)
    assert saved is not None and saved.country == "Canada"
    assert saved.frequency == "weekdays" and saved.result_count == 10
    assert len(saved.work_modes) == 3 and len(saved.experience_levels) == 4
    assert saved.salary_min is None
    assert "set up" in setup.content


async def test_legacy_put_preserves_richer_preferences(account, db_session):
    from app.modules.job_search.schemas import JobSearchUpsert

    user, profile = account
    profile.salary_min = 100000
    profile.salary_period = "month"
    profile.excluded_locations = [{"country": "United States", "region": "District of Columbia"}]
    await db_session.commit()
    await service.upsert_profile(
        db_session,
        user,
        Settings(),
        JobSearchUpsert(
            target_roles=["Backend Engineer"],
            next_run_at=profile.next_run_at,
            location="California",
            salary_min=100000,
        ),
    )
    assert profile.salary_currency == "USD" and profile.salary_period == "month"
    assert profile.years_experience == 5 and profile.excluded_locations
    assert profile.included_locations[0]["region"] == "California"


async def test_uncertain_legacy_preferences_block_spending(account, db_session, fake_redis):
    user, profile = account
    profile.needs_review = True
    await db_session.commit()
    with pytest.raises(service.JobSearchError, match="Review the country"):
        await submit_run(db_session, user, Settings(job_search_premium_enabled=True), fake_redis)
    assert (await allowance(db_session, profile, user))[0] == 5


async def test_expiration_before_worker_prevents_external_calls_and_requires_explicit_resume(
    account, db_session, fake_redis, durable_session, monkeypatch
):
    from app.modules.billing.subscription import apply_plan_for_app_user_id

    user, profile = account
    settings = Settings(job_search_premium_enabled=True, web_search_enabled=True)
    run = await submit_run(db_session, user, settings, fake_redis)
    await apply_plan_for_app_user_id(db_session, str(user.id), plan="free")
    await db_session.refresh(profile)
    assert profile.status == "paused" and profile.suspension_reason == "pro_expired"
    search = AsyncMock()
    monkeypatch.setattr(worker.TavilySearch, "search", search)
    await worker.execute_run(settings, fake_redis, run.id)
    assert run.state in {"cancelled", "limited"}
    search.assert_not_called()
    await apply_plan_for_app_user_id(db_session, str(user.id), plan="pro")
    await db_session.refresh(profile)
    assert profile.status == "paused"
    with pytest.raises(service.JobSearchError, match="Resume"):
        await submit_run(db_session, user, settings, fake_redis)
    await service.set_search_status(db_session, user, settings, "active")
    assert profile.status == "active" and profile.suspension_reason is None


async def test_partial_search_keeps_verified_results_and_records_usage(
    account, db_session, fake_redis, durable_session, monkeypatch
):
    from app.gateways.web_search_gateway import WebSearchHit

    user, profile = account
    profile.target_roles = ["Backend Engineer", "Engineer"]
    await db_session.commit()
    candidate, facts = posting()
    verified = grounded(facts, candidate)
    accepted = assess(_profile_from_rows(profile, user), verified, candidate)
    search = AsyncMock(
        side_effect=[
            SearchResponse(
                [WebSearchHit(candidate.title, candidate.url, candidate.snippet)], {"credits": 1}
            ),
            RuntimeError("provider failure"),
        ]
    )
    monkeypatch.setattr(worker.TavilySearch, "search", search)
    monkeypatch.setattr(
        worker.TavilyExtraction,
        "extract",
        AsyncMock(return_value=({candidate.url: candidate.page_text}, {"credits": 1})),
    )
    monkeypatch.setattr(worker.EvidenceRanker, "rank", AsyncMock(return_value=[accepted]))
    settings = Settings(job_search_premium_enabled=True, web_search_enabled=True)
    run = await submit_run(db_session, user, settings, fake_redis)
    await worker.execute_run(settings, fake_redis, run.id)
    assert run.state == "completed" and run.partial and run.new_match_count == 1
    assert run.usage["search_requests"] == 2 and run.usage["posting_fetches"] == 1
    assert run.usage["search_provider_usage"] == [{"credits": 1}]
    assert run.match_ids


async def test_provider_allowance_limits_worker_before_external_spend(
    account, db_session, fake_redis, durable_session, monkeypatch
):
    user, _ = account
    settings = Settings(
        job_search_premium_enabled=True, web_search_enabled=True, daily_tavily_searches_pro=0
    )
    search = AsyncMock()
    monkeypatch.setattr(worker.TavilySearch, "search", search)
    run = await submit_run(db_session, user, settings, fake_redis)
    await worker.execute_run(settings, fake_redis, run.id)
    assert run.state == "limited" and "allowance" in run.failure_reason
    search.assert_not_called()


async def test_chat_setup_asks_one_country_question_without_partial_save(
    account, db_session, fake_redis, durable_session
):
    from app.modules.job_search.tool import JobSearchAdapter, bind_job_search_context

    user, _ = account
    await service.delete_profile(db_session, user, Settings())
    with bind_job_search_context(user=user, redis=fake_redis, settings=Settings()):
        response = await JobSearchAdapter().invoke(
            {
                "action": "setup",
                "preferences": {"target_roles": ["Teacher"], "location": "Springfield"},
            }
        )
    assert "Which country" in response.content
    assert await service.get_profile_for_user(db_session, user.id) is None


async def test_temporary_location_addition_executes_with_shared_merge_semantics(
    account, db_session, fake_redis, durable_session, monkeypatch
):
    user, profile = account
    command, clarification = parse_command("Add DC just this time", profile)
    assert clarification is None
    settings = Settings(job_search_premium_enabled=True, web_search_enabled=True)
    search = AsyncMock(return_value=SearchResponse([]))
    monkeypatch.setattr(worker.TavilySearch, "search", search)
    run = await submit_run(db_session, user, settings, fake_redis, overrides=command["preferences"])
    await worker.execute_run(settings, fake_redis, run.id)
    assert run.state == "completed"
    queries = [call.args[0] for call in search.await_args_list]
    assert len(queries) == 2
    assert any("California" in query for query in queries)
    assert any("District of Columbia" in query for query in queries)
    assert profile.revision == 1 and len(profile.included_locations) == 1


async def test_blank_temporary_country_rejected_before_allowance(account, db_session, fake_redis):
    user, profile = account
    with pytest.raises(service.JobSearchError, match="temporary"):
        await submit_run(
            db_session,
            user,
            Settings(job_search_premium_enabled=True),
            fake_redis,
            overrides={"included_locations": [{"country": "  "}]},
        )
    assert (await allowance(db_session, profile, user))[0] == 5


async def test_corrupt_persisted_override_is_terminal_not_retried_forever(
    account, db_session, fake_redis, durable_session, monkeypatch
):
    user, _ = account
    settings = Settings(job_search_premium_enabled=True, web_search_enabled=True)
    run = await submit_run(db_session, user, settings, fake_redis)
    run.overrides = {"included_locations": [{"country": "  "}]}
    await db_session.commit()
    search = AsyncMock()
    monkeypatch.setattr(worker.TavilySearch, "search", search)
    await worker.execute_run(settings, fake_redis, run.id)
    assert run.state == "failed" and run.failure_reason == "Temporary preferences need review"
    search.assert_not_called()


async def test_explicit_include_reverses_same_exclusion_without_erasing_other_exclusions(
    account, db_session
):
    user, profile = account
    for text in ("I don't want DC", "Add DC"):
        command, clarification = parse_command(text, profile)
        assert clarification is None
        await service.patch_profile(
            db_session,
            user,
            Settings(),
            JobSearchPreferencesPatch.model_validate(command["preferences"]),
        )
    assert len(profile.included_locations) == 2
    assert profile.excluded_locations == []
    assert any(item.get("region") == "California" for item in profile.included_locations)
    assert any(item.get("region") == "District of Columbia" for item in profile.included_locations)


async def test_transfer_target_downgrade_stays_paused_after_renewal(
    account, db_session, fake_redis, monkeypatch
):
    from app.modules.billing import subscription

    user, profile = account
    monkeypatch.setattr(
        subscription, "resolve_plan_from_revenuecat", AsyncMock(return_value="free")
    )
    assert await subscription.handle_revenuecat_transfer(
        db_session, Settings(), new_app_user_id=str(user.id), transferred_from=[]
    )
    await db_session.refresh(user)
    await db_session.refresh(profile)
    assert user.plan == "free"
    assert profile.status == "paused"
    assert profile.suspension_reason == "pro_expired"
    assert profile.revision == 2
    await subscription.apply_plan_for_app_user_id(db_session, str(user.id), plan="pro")
    await db_session.refresh(profile)
    assert profile.status == "paused"
    settings = Settings(job_search_premium_enabled=True)
    with pytest.raises(service.JobSearchError, match="Resume"):
        await submit_run(db_session, user, settings, fake_redis)
    await service.set_search_status(db_session, user, settings, "active")
    assert profile.status == "active" and profile.suspension_reason is None
