from uuid import uuid4

from app.services.job_search_runner import (
    _Candidate,
    _ProfileSnapshot,
    _obvious_mismatch,
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
