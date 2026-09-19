from dataclasses import replace
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.services.job_search import runner
from app.services.job_search.runner import (
    _Candidate,
    _fallback_rank,
    _fetch_posting_pages,
    _obvious_mismatch,
    _ProfileSnapshot,
    _RankedJob,
    _ranking_messages,
    _search_queries,
    canonicalize_job_url,
)


def _profile(**overrides: object) -> _ProfileSnapshot:
    values: dict[str, object] = {
        "id": uuid4(),
        "user_id": uuid4(),
        "timezone": "America/Los_Angeles",
        "is_pro": True,
        "target_roles": ["Backend Engineer"],
        "skills": ["Python", "FastAPI"],
        "location": "United States",
        "work_modes": ["remote"],
        "experience_levels": ["entry"],
        "salary_min": 100_000,
        "requires_sponsorship": False,
        "excluded_companies": [],
        "background": None,
        "resume_text": None,
        "result_count": 10,
        "frequency": "weekdays",
    }
    values.update(overrides)
    return _ProfileSnapshot(**values)  # type: ignore[arg-type]


def _candidate(title: str, snippet: str = "") -> _Candidate:
    return _Candidate(
        candidate_id=0,
        title=title,
        url="https://jobs.example.com/roles/123",
        canonical_url="https://jobs.example.com/roles/123",
        snippet=snippet,
        source="jobs.example.com",
    )


def test_canonicalize_job_url_removes_tracking_but_keeps_job_identifier() -> None:
    result = canonicalize_job_url(
        "HTTPS://Jobs.Example.com/roles/123/?utm_source=mail&job_id=123#apply"
    )
    assert result == "https://jobs.example.com/roles/123?job_id=123"


def test_entry_profile_rejects_obviously_senior_role() -> None:
    assert _obvious_mismatch(
        _profile(),
        _candidate("Principal Backend Engineer"),
    )


def test_profile_rejects_excluded_company() -> None:
    assert _obvious_mismatch(
        _profile(excluded_companies=["Acme"]),
        _candidate("Backend Engineer at Acme"),
    )


def test_ranked_job_rejects_out_of_range_match_score() -> None:
    with pytest.raises(ValidationError):
        _RankedJob(candidate_id=0, match_score=150)


def test_ranked_job_accepts_score_and_experience() -> None:
    job = _RankedJob(candidate_id=0, match_score=82, experience="  3+ years  ")
    assert job.match_score == 82
    assert job.experience == "3+ years"


def test_search_queries_stay_sector_neutral_for_entry_level() -> None:
    profile = _profile(target_roles=["Registered Nurse"], experience_levels=["entry"])
    queries = _search_queries(profile)
    assert queries
    for query in queries:
        assert "software" not in query.casefold()
    assert any("entry level" in query for query in queries)


def test_fallback_rank_assigns_bounded_heuristic_scores() -> None:
    profile = _profile()
    candidates = [
        _candidate("Backend Engineer", "Python FastAPI remote"),
        _candidate("Backend Engineer", "Python"),
    ]
    accepted = _fallback_rank(profile, candidates)
    assert len(accepted) == 2
    scores = [job.match_score for job in accepted]
    assert all(score is not None and 0 <= score <= 100 for score in scores)
    # More keyword hits must not rank below fewer hits.
    assert scores[0] is not None and scores[1] is not None
    assert scores[0] >= scores[1]
    assert accepted[0].experience is None


def test_ranking_messages_prefer_page_text_over_snippet() -> None:
    candidate = _candidate("Backend Engineer", "short snippet")
    with_page = _ranking_messages(_profile(), [replace(candidate, page_text="full posting text")])
    assert "full posting text" in with_page[1]["content"]
    assert "short snippet" not in with_page[1]["content"]
    without_page = _ranking_messages(_profile(), [candidate])
    assert "short snippet" in without_page[1]["content"]


async def test_fetch_posting_pages_shortlists_and_attaches_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = MagicMock(job_search_page_fetch_enabled=True, job_search_page_fetch_max=1)
    weak = _candidate("Unrelated role", "nothing here")
    strong = replace(_candidate("Backend Engineer", "Python FastAPI remote"), candidate_id=1)

    async def fake_extract(_settings: Any, urls: list[str]) -> dict[str, str]:
        return {urls[0]: "full page text"}

    monkeypatch.setattr(runner.web_search_gateway, "extract_pages", fake_extract)
    result = await _fetch_posting_pages(settings, _profile(), [weak, strong])
    assert [item.candidate_id for item in result] == [1]
    assert result[0].page_text == "full page text"


async def test_fetch_posting_pages_keeps_full_list_when_extract_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = MagicMock(job_search_page_fetch_enabled=True, job_search_page_fetch_max=1)
    candidates = [_candidate("Backend Engineer", "Python"), _candidate("Other", "none")]

    async def fake_extract(_settings: Any, _urls: list[str]) -> dict[str, str]:
        return {}

    monkeypatch.setattr(runner.web_search_gateway, "extract_pages", fake_extract)
    result = await _fetch_posting_pages(settings, _profile(), candidates)
    assert result == candidates


async def test_fetch_posting_pages_disabled_flag_is_passthrough() -> None:
    settings = MagicMock(job_search_page_fetch_enabled=False)
    candidates = [_candidate("Backend Engineer", "Python")]
    result = await _fetch_posting_pages(settings, _profile(), candidates)
    assert result == candidates
