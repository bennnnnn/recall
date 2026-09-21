from dataclasses import replace
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.gateways.web_search_gateway import WebSearchHit
from app.models.schemas.job_search import ResumeProfile
from app.services.job_search import runner
from app.services.job_search.runner import (
    PostingVerificationError,
    _Candidate,
    _dedupe_accepted,
    _fallback_rank,
    _fetch_posting_pages,
    _find_candidates,
    _is_listing_page,
    _obvious_mismatch,
    _ProfileSnapshot,
    _rank_candidates,
    _RankedJob,
    _RankedPayload,
    _ranking_messages,
    _salary_ceiling,
    _search_queries,
    _title_and_company,
    _title_company_key,
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
        "work_modes": ["remote", "hybrid", "onsite"],
        "experience_levels": ["entry", "mid", "senior"],
        "salary_min": None,
        "requires_sponsorship": False,
        "excluded_companies": [],
        "background": None,
        "resume_text": None,
        "resume_profile": None,
        "hidden_companies": [],
        "hidden_titles": [],
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
        _profile(experience_levels=["entry"]),
        _candidate("Principal Backend Engineer"),
    )


def test_entry_profile_does_not_treat_requested_manager_title_as_seniority() -> None:
    profile = _profile(target_roles=["Account Manager"], experience_levels=["entry"])
    assert not _obvious_mismatch(profile, _candidate("Account Manager"))
    assert _obvious_mismatch(profile, _candidate("Senior Account Manager"))


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
        _candidate("Entry-Level Backend Engineer", "Python FastAPI remote"),
        _candidate("Junior Backend Engineer", "Python"),
    ]
    accepted = _fallback_rank(profile, candidates)
    assert len(accepted) == 2
    scores = [job.match_score for job in accepted]
    assert all(score is not None and 0 <= score <= 100 for score in scores)
    # More keyword hits must not rank below fewer hits.
    assert scores[0] is not None and scores[1] is not None
    assert scores[0] >= scores[1]
    assert accepted[0].experience is None


@pytest.mark.parametrize(
    ("salary", "expected"),
    [
        ("$100,000-$125,000 per year", 125_000),
        ("€75.5k–€92k", 92_000),
        ("£80k", 80_000),
        ("$45 per hour", None),
    ],
)
def test_salary_ceiling_parses_annual_ranges(salary: str, expected: int | None) -> None:
    assert _salary_ceiling(salary) == expected


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


async def test_fetch_posting_pages_rejects_unverified_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = MagicMock(job_search_page_fetch_enabled=True, job_search_page_fetch_max=1)
    candidates = [_candidate("Backend Engineer", "Python"), _candidate("Other", "none")]

    async def fake_extract(_settings: Any, _urls: list[str]) -> dict[str, str]:
        return {}

    monkeypatch.setattr(runner.web_search_gateway, "extract_pages", fake_extract)
    with pytest.raises(PostingVerificationError):
        await _fetch_posting_pages(settings, _profile(), candidates)


async def test_fetch_posting_pages_disabled_flag_is_passthrough() -> None:
    settings = MagicMock(job_search_page_fetch_enabled=False)
    candidates = [_candidate("Backend Engineer", "Python")]
    result = await _fetch_posting_pages(settings, _profile(), candidates)
    assert result == candidates


def test_search_queries_use_resume_skills_and_alt_title() -> None:
    resume = ResumeProfile(
        titles=["Platform Engineer"],
        skills=["Kubernetes", "Terraform"],
    )
    profile = _profile(resume_profile=resume)
    queries = _search_queries(profile)
    assert any("Kubernetes" in query for query in queries)
    assert any('"Platform Engineer"' in query for query in queries)


def test_search_queries_skip_resume_title_already_targeted() -> None:
    resume = ResumeProfile(titles=["Backend Engineer"], skills=[])
    queries = _search_queries(_profile(resume_profile=resume))
    assert sum('"Backend Engineer"' in query for query in queries) == 2


def test_ranking_messages_include_structured_resume_profile() -> None:
    resume = ResumeProfile(titles=["Backend Engineer"], skills=["Python"], years_experience=4)
    messages = _ranking_messages(
        _profile(resume_profile=resume, resume_text="raw resume text"),
        [_candidate("Backend Engineer", "Python")],
    )
    payload = messages[1]["content"]
    assert '"resume_profile"' in payload
    assert '"years_experience": 4' in payload
    assert "raw resume text" in payload


def test_hidden_company_is_filtered_like_an_excluded_company() -> None:
    profile = _profile(hidden_companies=["Acme Health"])
    assert _obvious_mismatch(profile, _candidate("Nurse", "Acme Health is hiring")) is True
    assert _obvious_mismatch(profile, _candidate("Nurse", "Other Hospital hiring")) is False


def test_ranking_messages_include_user_rejected_block() -> None:
    profile = _profile(hidden_titles=["Sales Manager"], hidden_companies=["Acme"])
    messages = _ranking_messages(profile, [_candidate("Backend Engineer", "Python")])
    payload = messages[1]["content"]
    assert '"user_rejected"' in payload
    assert "Sales Manager" in payload
    assert "Acme" in payload
    assert "never select them or close variants" in messages[0]["content"]
    # No rejections → no block at all.
    clean = _ranking_messages(_profile(), [_candidate("Backend Engineer", "Python")])
    assert "user_rejected" not in clean[1]["content"]


def test_title_company_key_ignores_case_punctuation_and_suffixes() -> None:
    assert _title_company_key("Backend Engineer", "Acme, Inc.") == _title_company_key(
        "backend engineer", "Acme"
    )
    assert _title_company_key("Backend Engineer", "Acme") != _title_company_key(
        "Frontend Engineer", "Acme"
    )


def test_dedupe_accepted_drops_cross_source_repeats() -> None:
    def accepted(title: str, company: str, url: str) -> runner._AcceptedJob:
        return runner._AcceptedJob(
            candidate=_Candidate(
                candidate_id=0,
                title=title,
                url=url,
                canonical_url=url,
                snippet="",
                source="board.example.com",
            ),
            title=title,
            company=company,
            location=None,
            work_mode=None,
            salary=None,
            experience=None,
            match_score=None,
            posted_at=None,
            summary=None,
            match_reasons=[],
            gap=None,
        )

    batch = [
        accepted("Backend Engineer", "Acme Inc", "https://linkedin.example.com/1"),
        accepted("Backend Engineer", "Acme", "https://indeed.example.com/2"),
        accepted("Backend Engineer", "Other Co", "https://indeed.example.com/3"),
    ]
    unique = _dedupe_accepted(batch)
    assert [item.company for item in unique] == ["Acme Inc", "Other Co"]


@pytest.mark.parametrize(
    ("url", "title"),
    [
        # Search-result / category pages — never one specific opening.
        ("https://de.indeed.com/jobs?q=registered+nurse&l=Berlin", "Registered Nurse Jobs"),
        ("https://www.linkedin.com/jobs/search/?keywords=nurse", "Nurse openings"),
        ("https://www.stepstone.de/jobs/intensivpfleger", "500+ Intensivpfleger Jobs"),
        ("https://www.glassdoor.com/Job/berlin-nurse-jobs-SRCH_IL.0,6_IC2622109.htm", "Nurse"),
        ("https://boards.example.com/careers", "Careers"),
        ("https://jobs.example.com/page", "Registered Nurse jobs in Berlin"),
        ("https://workingnomads.com/remote", "Remote Entry Level Account Manager Jobs"),
        ("https://builtin.com/jobs/remote", "Best Remote Account Manager Jobs 2026"),
        ("https://jobs.example.com/page", "1,200+ Pflege Jobs bei Kliniken"),
        ("https://jobs.example.com/page", "Alle Stellenangebote im Landkreis"),
        (
            "https://www.workingnomads.com/remote-entry-level-software-engineer-jobs",
            "Remote Entry Level Software Engineer Jobs Explore",
        ),
        ("https://arc.dev/remote-jr-jobs", "Remote Junior Developer Jobs & Internships"),
    ],
)
def test_listing_pages_are_detected(url: str, title: str) -> None:
    assert _is_listing_page(url, title)


@pytest.mark.parametrize(
    ("url", "title"),
    [
        # Specific postings — one opening on its own page.
        ("https://boards.greenhouse.io/acme/jobs/12345", "Registered Nurse, ICU - Acme"),
        ("https://www.linkedin.com/jobs/view/3981234567", "Charité hiring Intensivpfleger"),
        ("https://de.indeed.com/viewjob?jk=abc123def", "Intensivpfleger (m/w/d)"),
        ("https://www.charite.de/karriere/stellenangebote/12345", "Pflegefachkraft"),
        ("https://jobs.lever.co/acme/9f0e2a", "Backend Engineer"),
    ],
)
def test_specific_posting_pages_pass(url: str, title: str) -> None:
    assert not _is_listing_page(url, title)


async def test_find_candidates_drops_listing_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    hits = [
        WebSearchHit(
            title="Registered Nurse Jobs in Berlin",
            url="https://de.indeed.com/jobs?q=registered+nurse&l=Berlin",
            snippet="Browse 500+ openings",
        ),
        WebSearchHit(
            title="Intensivpfleger (m/w/d) - Charité",
            url="https://www.charite.de/karriere/stellenangebote/12345",
            snippet="Zum nächstmöglichen Zeitpunkt",
        ),
    ]

    async def fake_search(
        _settings: object, _query: str, *, max_results: int
    ) -> list[WebSearchHit]:
        return hits

    monkeypatch.setattr(runner.web_search_gateway, "search_web", fake_search)
    candidates = await _find_candidates(MagicMock(), _profile())
    assert [item.url for item in candidates] == [
        "https://www.charite.de/karriere/stellenangebote/12345"
    ]


def test_title_and_company_strips_board_suffix() -> None:
    assert _title_and_company("Registered Nurse at Acme | Indeed.com", "indeed.com") == (
        "Registered Nurse",
        "Acme",
    )
    assert _title_and_company("Intensivpfleger (m/w/d) - StepStone", "stepstone.de") == (
        "Intensivpfleger (m/w/d)",
        "Unknown employer",
    )


def test_title_and_company_never_names_the_board_as_employer() -> None:
    title, company = _title_and_company("Registered Nurse ICU", "de.indeed.com")
    assert title == "Registered Nurse ICU"
    assert company == "Unknown employer"
    # A company's own career site still derives a readable name.
    _, company = _title_and_company("Registered Nurse ICU", "charite.de")
    assert company == "Charite"


def _rank_settings() -> MagicMock:
    return MagicMock(job_search_page_fetch_enabled=False)


async def test_rank_keeps_exact_grounded_posting_title(monkeypatch: pytest.MonkeyPatch) -> None:
    candidate = _candidate("Intensivpfleger (m/w/d) Intensivstation - Charité", "snippet")

    async def fake_structured(**kwargs: object) -> _RankedPayload:
        return _RankedPayload(
            jobs=[
                _RankedJob(
                    candidate_id=0,
                    title="Intensivpfleger (m/w/d) Intensivstation",
                    company="Charité",
                )
            ]
        )

    monkeypatch.setattr(runner.litellm_gateway, "complete_structured", fake_structured)
    accepted = await _rank_candidates(_rank_settings(), _profile(), [candidate])
    assert len(accepted) == 1
    assert accepted[0].title == "Intensivpfleger (m/w/d) Intensivstation"
    assert accepted[0].company == "Charité"


async def test_rank_rejects_composed_title_in_favor_of_page_headline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate("Intensivpfleger (m/w/d) Intensivstation - Charité", "snippet")

    async def fake_structured(**kwargs: object) -> _RankedPayload:
        return _RankedPayload(
            jobs=[_RankedJob(candidate_id=0, title="Registered Nurse (ICU) — Berlin")]
        )

    monkeypatch.setattr(runner.litellm_gateway, "complete_structured", fake_structured)
    accepted = await _rank_candidates(_rank_settings(), _profile(), [candidate])
    assert len(accepted) == 1
    # The composed label is ungrounded — the real page headline wins.
    assert accepted[0].title == "Intensivpfleger (m/w/d) Intensivstation"
    assert accepted[0].company == "Charité"


async def test_rank_drops_listing_titled_results(monkeypatch: pytest.MonkeyPatch) -> None:
    candidate = _candidate("Registered Nurse jobs in Berlin", "browse openings")

    async def fake_structured(**kwargs: object) -> _RankedPayload:
        return _RankedPayload(jobs=[_RankedJob(candidate_id=0)])

    monkeypatch.setattr(runner.litellm_gateway, "complete_structured", fake_structured)
    accepted = await _rank_candidates(_rank_settings(), _profile(), [candidate])
    assert accepted == []


async def test_rank_rejects_board_name_as_company(monkeypatch: pytest.MonkeyPatch) -> None:
    candidate = _candidate("Backend Engineer - Acme", "Python APIs")

    async def fake_structured(**kwargs: object) -> _RankedPayload:
        return _RankedPayload(
            jobs=[_RankedJob(candidate_id=0, title="Backend Engineer", company="LinkedIn")]
        )

    monkeypatch.setattr(runner.litellm_gateway, "complete_structured", fake_structured)
    accepted = await _rank_candidates(_rank_settings(), _profile(), [candidate])
    assert len(accepted) == 1
    assert accepted[0].company == "Acme"


def test_ranking_prompt_requires_exact_posting_title() -> None:
    system = _ranking_messages(_profile(), [_candidate("Backend Engineer")])[0]["content"]
    assert "Copy title exactly" in system
    assert "never the job board" in system


def test_fallback_rejects_result_without_required_salary_evidence() -> None:
    accepted = _fallback_rank(
        _profile(salary_min=100_000),
        [_candidate("Backend Engineer", "Python remote role")],
    )
    assert accepted == []


def test_entry_fallback_requires_entry_level_evidence() -> None:
    assert _fallback_rank(
        _profile(target_roles=["Account Manager"], experience_levels=["entry"]),
        [_candidate("Technical Account Manager", "Remote customer success role")],
    ) == []


async def test_rank_falls_back_to_verified_page_when_structured_result_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request: dict[str, object] = {}
    candidate = _Candidate(
        candidate_id=0,
        title="(Remote) - Entry-Level Account Manager (20 - 27 per hour)",
        url="https://apply.workable.com/nogigiddy/j/123",
        canonical_url="https://apply.workable.com/nogigiddy/j/123",
        snippet="Remote entry-level account manager",
        source="apply.workable.com",
        page_text=(
            "[![Image 1: NoGigiddy](logo)](company) "
            "# (Remote) - Entry-Level Account Manager (20 - 27 per hour) "
            "**Remote** Remote Work Full time ## Description "
            "NoGigiddy is seeking an entry-level account manager."
        ),
    )

    async def empty_structured(**kwargs: object) -> _RankedPayload:
        request.update(kwargs)
        return _RankedPayload(jobs=[])

    monkeypatch.setattr(runner.litellm_gateway, "complete_structured", empty_structured)
    accepted = await _rank_candidates(
        _rank_settings(),
        _profile(
            target_roles=["Account Manager"],
            experience_levels=["entry"],
            work_modes=["remote"],
            result_count=2,
        ),
        [candidate],
    )

    assert len(accepted) == 1
    assert accepted[0].title == "Entry-Level Account Manager (20 - 27 per hour)"
    assert accepted[0].company == "NoGigiddy"
    assert accepted[0].candidate.url == candidate.url
    assert request["model_alias"] == "gemini-flash"
    assert request["timeout_seconds"] == 20.0


async def test_rank_rejects_salary_below_minimum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate("Backend Engineer - Acme", "Python remote $80,000-$90,000")

    async def fake_structured(**kwargs: object) -> _RankedPayload:
        return _RankedPayload(
            jobs=[
                _RankedJob(
                    candidate_id=0,
                    work_mode="remote",
                    salary="$80,000-$90,000",
                )
            ]
        )

    monkeypatch.setattr(runner.litellm_gateway, "complete_structured", fake_structured)
    accepted = await _rank_candidates(
        _rank_settings(),
        _profile(salary_min=100_000, work_modes=["remote"]),
        [candidate],
    )
    assert accepted == []


async def test_rank_requires_positive_sponsorship_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate("Backend Engineer - Acme", "Python remote role")

    async def fake_structured(**kwargs: object) -> _RankedPayload:
        return _RankedPayload(
            jobs=[_RankedJob(candidate_id=0, work_mode="remote")]
        )

    monkeypatch.setattr(runner.litellm_gateway, "complete_structured", fake_structured)
    accepted = await _rank_candidates(
        _rank_settings(),
        _profile(requires_sponsorship=True, work_modes=["remote"]),
        [candidate],
    )
    assert accepted == []


async def test_rank_requires_entry_level_evidence_for_entry_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate(
        "Technical Account Manager - Smile Digital Health",
        "Remote customer success and technical enablement role",
    )

    async def fake_structured(**kwargs: object) -> _RankedPayload:
        return _RankedPayload(
            jobs=[
                _RankedJob(
                    candidate_id=0,
                    company="Smile Digital Health",
                    work_mode="remote",
                )
            ]
        )

    monkeypatch.setattr(runner.litellm_gateway, "complete_structured", fake_structured)
    accepted = await _rank_candidates(
        _rank_settings(),
        _profile(
            target_roles=["Account Manager"],
            experience_levels=["entry"],
            work_modes=["remote"],
        ),
        [candidate],
    )
    assert accepted == []
