from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.services.job_search.runner import (
    _Candidate,
    _fallback_rank,
    _obvious_mismatch,
    _ProfileSnapshot,
    _RankedJob,
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
