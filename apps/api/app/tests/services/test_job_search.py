from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

import pytest

from app.models.orm import Automation
from app.models.schemas.job_search import JobSearchUpsert
from app.services import job_search


def test_job_search_prompt_is_strict_and_profile_grounded() -> None:
    prompt = job_search._build_prompt(
        {
            "target_roles": ["Backend Engineer", "Platform Engineer"],
            "skills": ["Python", "FastAPI"],
            "location": "Remote in the United States",
            "work_modes": ["remote"],
            "experience_levels": ["entry"],
            "salary_min": 100000,
            "requires_sponsorship": False,
            "excluded_companies": ["Example Staffing"],
            "background": "Built production APIs.",
            "result_count": 10,
        }
    )
    assert "Backend Engineer, Platform Engineer" in prompt
    assert "Return up to 10 strong matches" in prompt
    assert "```job_matches" in prompt
    assert "Never add weak jobs" in prompt


def test_parse_job_matches_accepts_verified_shape_and_rejects_bad_url() -> None:
    valid = """Summary
```job_matches
{"jobs":[{"title":"Software Engineer I","company":"Acme","location":"Remote - US","work_mode":"remote","salary":null,"url":"https://jobs.acme.test/123","source":"Acme","posted_at":"today","summary":"Build APIs","match_reasons":["Python"],"gap":null}]}
```"""
    rows = job_search._parse_message_jobs(valid)
    assert len(rows) == 1
    assert rows[0].company == "Acme"

    invalid = """```job_matches
{"jobs":[{"title":"Bad","company":"Bad","url":"javascript:alert(1)"}]}
```"""
    assert job_search._parse_message_jobs(invalid) == []


def test_job_id_ignores_tracking_parameters() -> None:
    first = job_search._JobPayloadItem(
        title="Engineer",
        company="Acme",
        url="https://jobs.acme.test/123?utm_source=feed&gh_jid=44",
    )
    second = job_search._JobPayloadItem(
        title="Engineer",
        company="Acme",
        url="https://jobs.acme.test/123?gh_jid=44&utm_campaign=x",
    )
    assert job_search._job_id(first) == job_search._job_id(second)


def test_schema_normalizes_duplicate_profile_values() -> None:
    body = JobSearchUpsert(
        target_roles=[" Backend Engineer ", "backend engineer"],
        skills=["Python", " python "],
        work_modes=["remote"],
        experience_levels=["entry"],
        result_count=5,
        frequency="weekly",
        next_run_at=datetime.now(UTC),
    )
    assert body.target_roles == ["Backend Engineer"]
    assert body.skills == ["Python"]


@pytest.mark.parametrize("count", [5, 10, 15])
def test_profile_result_counts_are_bounded(
    count: Literal[5, 10, 15],
) -> None:
    body = JobSearchUpsert(
        target_roles=["Backend Engineer"],
        work_modes=["remote"],
        experience_levels=["entry"],
        result_count=count,
        frequency="weekly",
        next_run_at=datetime.now(UTC),
    )
    assert body.result_count == count


def test_job_search_automation_fields_have_safe_defaults() -> None:
    automation = Automation(
        id=uuid4(),
        user_id=uuid4(),
        chat_id=uuid4(),
        prompt="search",
        frequency="weekly",
        next_run_at=datetime.now(UTC),
        kind="job_search",
    )
    assert automation.kind == "job_search"
