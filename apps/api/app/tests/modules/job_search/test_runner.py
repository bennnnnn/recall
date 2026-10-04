from dataclasses import replace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.gateways.web_search_gateway import WebSearchHit
from app.modules.job_search import providers
from app.modules.job_search.posting import (
    _dedupe_accepted,
    _extract_company_logo_url,
    _extract_experience,
    _extract_salary,
    _extract_work_mode,
    _is_listing_page,
    _title_and_company,
    _title_company_key,
    canonicalize_job_url,
)
from app.modules.job_search.ranking import (
    _fallback_rank,
    _obvious_mismatch,
    _ranking_messages,
    _salary_ceiling,
    _search_queries,
    _strategic_match_assessment,
)
from app.modules.job_search.records import (
    PostingVerificationError,
    _AcceptedJob,
    _Candidate,
    _ProfileSnapshot,
    _RankedJob,
)
from app.modules.job_search.verification import PostingBatch, PostingFacts
from app.tests.modules.job_search.posting_fixtures import posting
from app.tests.modules.job_search.posting_fixtures import profile as fixture_profile


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


def test_ranked_job_accepts_score_experience_and_unique_skills() -> None:
    job = _RankedJob(
        candidate_id=0,
        match_score=82,
        experience="  3+ years  ",
        required_skills=[" Python ", "python", "FastAPI"],
    )
    assert job.match_score == 82
    assert job.experience == "3+ years"
    assert job.required_skills == ["Python", "FastAPI"]


def test_search_queries_stay_sector_neutral_for_entry_level() -> None:
    profile = _profile(target_roles=["Registered Nurse"], experience_levels=["entry"])
    queries = _search_queries(profile)
    assert queries
    for query in queries:
        assert "software" not in query.casefold()
    assert all("Registered Nurse" in query for query in queries)
    assert len(queries) <= 6


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
    assert accepted[0].experience == "Entry level"
    assert accepted[0].match_reasons
    assert all(
        "title and description" not in reason.casefold() for reason in accepted[0].match_reasons
    )


def test_strategic_match_assessment_compares_user_profile_with_job_requirements() -> None:
    profile = _profile(
        work_modes=["remote"],
        skills=["Python", "FastAPI"],
        years_experience=4,
    )
    reasons, gap = _strategic_match_assessment(
        profile,
        required_skills=["Python", "SQL"],
        experience="3+ years",
        work_mode="remote",
        location="United States",
        salary=None,
    )

    assert any("Python" in reason and "job asks for" in reason for reason in reasons)
    assert any("4 years" in reason and "3+ years" in reason for reason in reasons)
    assert any("remote" in reason for reason in reasons)
    assert gap is not None and "SQL" in gap


def test_posting_fact_fallbacks_extract_salary_and_experience() -> None:
    candidate = _candidate(
        "Backend Engineer",
        "Remote role paying $100,000 - $125,000 per year. Requires 3+ years of experience.",
    )
    assert _extract_salary(candidate) == "$100,000 - $125,000 per year"
    assert _extract_experience(candidate) == "3+ years of experience"


def test_a_named_bonus_does_not_replace_the_salary_range() -> None:
    candidate = _candidate(
        "Backend Engineer",
        "Salary $120,000-$140,000 per year. Signing bonus of 10,000 USD.",
    )
    assert _extract_salary(candidate) == "$120,000-$140,000 per year"


def test_experience_fallback_does_not_treat_manager_title_as_senior() -> None:
    assert _extract_experience(_candidate("Account Manager", "Client services role")) is None


def test_work_mode_fallback_uses_earliest_explicit_posting_metadata() -> None:
    candidate = replace(
        _candidate("Remote Backend Engineer", "Work from anywhere"),
        page_text="Remote Work Full time. Our company also supports hybrid teams.",
    )
    assert _extract_work_mode(candidate) == "remote"


def test_gartner_posting_keeps_employer_place_pay_and_role() -> None:
    """A careers host and a USD range must not become Jobs / Hybrid / no pay."""
    page = (
        "[![Gartner Careers logo](/media/gartner.svg)](/) "
        "# Senior Account Executive * Remote, New York * [Sales](/teams/sales/) "
        "## Description **About this role:** The Senior Account Executive is a field sales "
        "role responsible for client retention and growth. Account Executives build "
        "trust-based relationships with C-Level Executives and their teams. "
        "**What you will need:** * 10+ years' B2B sales experience. "
        "In our hybrid work environment, we provide the flexibility and support "
        "for you to thrive. "
        "A reasonable estimate of the base salary range for this role is "
        "132,000 USD - 170,000 USD. "
        "We also offer a 401k match up to $7,200 per year."
    )
    candidate = replace(
        _candidate(
            "Senior Account Executive ## Description",
            "In our hybrid work environment, we provide the flexibility",
        ),
        url="https://jobs.gartner.com/jobs/job/108710-senior-account-executive",
        canonical_url="https://jobs.gartner.com/jobs/job/108710-senior-account-executive",
        source="jobs.gartner.com",
        page_text=page,
    )
    accepted = _fallback_rank(
        _profile(
            target_roles=["Account Executive"],
            experience_levels=["senior"],
            work_modes=["remote", "hybrid", "onsite"],
        ),
        [candidate],
    )
    assert len(accepted) == 1
    job = accepted[0]
    assert job.title == "Senior Account Executive"
    assert job.company == "Gartner"
    assert job.location == "Remote, New York"
    assert job.work_mode == "remote"
    assert job.salary == "132,000 USD - 170,000 USD"
    assert job.experience == "10+ years"
    assert job.summary is not None
    assert job.summary.startswith("The Senior Account Executive is a field sales role")
    assert "hybrid work environment" not in job.summary


def test_company_logo_must_be_https_and_labelled_with_employer() -> None:
    candidate = replace(
        _candidate("Backend Engineer - Acme"),
        page_text=(
            "[![Image 1: Acme](https://ats-cdn.example.com/acme-logo.png)](company) "
            "![LinkedIn](https://cdn.example.com/linkedin.png)"
        ),
    )
    assert _extract_company_logo_url(candidate, "Acme") == (
        "https://ats-cdn.example.com/acme-logo.png"
    )
    assert _extract_company_logo_url(candidate, "LinkedIn") is None


def test_company_logo_rejects_relative_and_private_urls() -> None:
    relative = replace(
        _candidate("Backend Engineer - Acme"),
        page_text="![Acme](logo.png)",
    )
    private = replace(
        _candidate("Backend Engineer - Acme"),
        page_text="![Acme](https://127.0.0.1/logo.png)",
    )
    assert _extract_company_logo_url(relative, "Acme") is None
    assert _extract_company_logo_url(private, "Acme") is None


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
    from unittest.mock import AsyncMock

    from app.core.config import Settings
    from app.modules.job_search.providers import TavilyExtraction

    candidate, _ = posting()
    response = MagicMock()
    response.json.return_value = {
        "results": [{"url": candidate.url, "raw_content": candidate.page_text}],
        "usage": {"credits": 1},
    }
    client = MagicMock(post=AsyncMock(return_value=response))
    monkeypatch.setattr(providers, "get_pooled_client", lambda timeout: client)
    pages, usage = await TavilyExtraction(Settings()).extract([candidate.url])
    assert pages[candidate.url] == candidate.page_text
    assert usage == {"credits": 1}
    assert client.post.await_args.kwargs["json"]["extract_depth"] == "basic"


async def test_fetch_posting_pages_rejects_unverified_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate, facts = posting()
    candidate = replace(candidate, page_text=None)
    assert await _rank_postings(monkeypatch, fixture_profile(), candidate, facts) == []


async def test_fetch_posting_pages_disabled_flag_is_passthrough(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Legacy flags cannot allow snippet-only matches through the premium verifier.
    candidate, facts = posting()
    candidate = replace(candidate, page_text=None, snippet=candidate.page_text or "")
    assert await _rank_postings(monkeypatch, fixture_profile(), candidate, facts) == []


def test_search_queries_use_explicit_titles() -> None:
    queries = _search_queries(_profile())
    assert all('"Backend Engineer"' in query for query in queries)


def test_ranking_messages_use_only_user_supplied_candidate_facts() -> None:
    messages = _ranking_messages(
        _profile(skills=["Python"], years_experience=4),
        [_candidate("Backend Engineer", "Python")],
    )
    payload = messages[1]["content"]
    assert '"years_experience": 4' in payload
    assert '"Python"' in payload
    assert '"resume_profile"' not in payload
    assert '"resume_excerpt"' not in payload


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
    def accepted(title: str, company: str, url: str) -> _AcceptedJob:
        return _AcceptedJob(
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
            company_logo_url=None,
            location=None,
            work_mode=None,
            salary=None,
            experience=None,
            match_score=None,
            posted_at=None,
            summary=None,
            required_skills=[],
            match_reasons=[],
            gap=None,
        )

    batch = [
        accepted("Backend Engineer", "Acme Inc", "https://linkedin.example.com/1"),
        accepted("Backend Engineer", "Acme", "https://indeed.example.com/2"),
        accepted("Backend Engineer", "Other Co", "https://indeed.example.com/3"),
    ]
    unique = _dedupe_accepted(batch)
    assert [item.company for item in unique] == ["Acme Inc", "Acme", "Other Co"]


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
    from app.modules.job_search.discovery import collect_candidates
    from app.modules.job_search.providers import SearchResponse

    hits = [
        WebSearchHit(
            title="Registered Nurse Jobs",
            url="https://de.indeed.com/jobs?q=nurse",
            snippet="Browse jobs",
        ),
        WebSearchHit(
            title="Intensivpfleger",
            url="https://www.charite.de/karriere/stellenangebote/12345",
            snippet="One opening",
        ),
    ]
    candidates = collect_candidates([SearchResponse(hits)])
    assert [item.url for item in candidates] == [hits[1].url]


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
    # job-boards.greenhouse.io is the ATS, not an employer named Job Boards.
    _, company = _title_and_company("Backend Engineer", "job-boards.greenhouse.io")
    assert company == "Unknown employer"


def _rank_settings() -> MagicMock:
    return MagicMock(job_search_page_fetch_enabled=False)


async def test_rank_keeps_exact_grounded_posting_title(monkeypatch: pytest.MonkeyPatch) -> None:
    title = "Intensivpfleger (m/w/d) Intensivstation"
    candidate, facts = posting(
        title=title,
        company="Charité",
        country="Germany",
        region="Berlin",
        city="Berlin",
        currency="EUR",
        salary="EUR 50000-60000 per year",
        lower=50000,
        upper=60000,
    )
    accepted = await _rank_postings(
        monkeypatch,
        fixture_profile(target_roles=[title], included_locations=[{"country": "Germany"}]),
        candidate,
        facts,
    )
    assert len(accepted) == 1
    assert accepted[0].title == title and accepted[0].company == "Charité"


async def test_rank_keeps_grounded_title_pay_and_employer_without_a_heading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate, facts = posting(salary="USD 120000-140000 per year", lower=120000, upper=140000)
    accepted = await _rank_postings(monkeypatch, fixture_profile(), candidate, facts)
    assert len(accepted) == 1
    assert accepted[0].title == "Backend Engineer" and accepted[0].company == "Acme"
    assert accepted[0].salary == "USD 120000-140000 per year"


async def test_rank_rejects_composed_title_in_favor_of_page_headline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate, facts = posting()
    facts.title = "Registered Nurse (ICU) Berlin"
    # An invented title is rejected rather than repaired using a search snippet.
    assert await _rank_postings(monkeypatch, fixture_profile(), candidate, facts) == []


async def test_rank_drops_listing_titled_results(monkeypatch: pytest.MonkeyPatch) -> None:
    candidate, facts = posting()
    facts.document_kind = "listing"
    assert await _rank_postings(monkeypatch, fixture_profile(), candidate, facts) == []


async def test_rank_rejects_board_name_as_company(monkeypatch: pytest.MonkeyPatch) -> None:
    candidate, facts = posting()
    facts.company = "LinkedIn"
    assert await _rank_postings(monkeypatch, fixture_profile(), candidate, facts) == []


def test_ranking_prompt_requires_exact_posting_title() -> None:
    system = _ranking_messages(_profile(), [_candidate("Backend Engineer")])[0]["content"]
    assert "Copy title exactly" in system
    assert "never the job board" in system
    assert "required_skills" in system
    assert "Every reason must compare" in system
    assert "Never use a matching job title" in system


async def test_rank_replaces_weak_reason_with_evidence_based_comparison(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate, facts = posting(skills=["Python", "SQL"], years=3)
    accepted = await _rank_postings(
        monkeypatch, fixture_profile(skills=["Python"], years_experience=4), candidate, facts
    )
    assert len(accepted) == 1
    assert any("Python" in reason for reason in accepted[0].match_reasons)
    assert any("4 years" in reason for reason in accepted[0].match_reasons)
    assert all(
        "title and description" not in reason.casefold() for reason in accepted[0].match_reasons
    )


def test_fallback_rejects_result_without_required_salary_evidence() -> None:
    accepted = _fallback_rank(
        _profile(salary_min=100_000),
        [_candidate("Backend Engineer", "Python remote role")],
    )
    assert accepted == []


def test_entry_fallback_requires_entry_level_evidence() -> None:
    assert (
        _fallback_rank(
            _profile(target_roles=["Account Manager"], experience_levels=["entry"]),
            [_candidate("Technical Account Manager", "Remote customer success role")],
        )
        == []
    )


async def test_rank_falls_back_to_verified_page_when_structured_result_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from unittest.mock import AsyncMock

    from app.core.config import Settings

    candidate, _ = posting()
    monkeypatch.setattr(
        providers.litellm_gateway,
        "complete_structured",
        AsyncMock(return_value=PostingBatch(postings=[])),
    )
    # Empty model output is a provider failure, never an invented fallback match.
    with pytest.raises(PostingVerificationError):
        await providers.EvidenceRanker(Settings()).rank(fixture_profile(), [candidate], {})


async def test_rank_rejects_salary_below_minimum(monkeypatch: pytest.MonkeyPatch) -> None:
    candidate, facts = posting(salary="USD 80000-90000 per year", lower=80000, upper=90000)
    assert (
        await _rank_postings(monkeypatch, fixture_profile(salary_min=100000), candidate, facts)
        == []
    )


async def test_rank_requires_positive_sponsorship_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    candidate, facts = posting()
    accepted = await _rank_postings(
        monkeypatch, fixture_profile(requires_sponsorship=True), candidate, facts
    )
    assert len(accepted) == 1 and accepted[0].match_kind == "possible"
    assert accepted[0].gap and "sponsorship" in accepted[0].gap.lower()


async def test_rank_requires_entry_level_evidence_for_entry_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate, facts = posting(title="Account Manager")
    accepted = await _rank_postings(
        monkeypatch,
        fixture_profile(target_roles=["Account Manager"], experience_levels=["entry"]),
        candidate,
        facts,
    )
    assert len(accepted) == 1 and accepted[0].match_kind == "possible"
    assert accepted[0].gap and "seniority" in accepted[0].gap.lower()


async def _rank_postings(
    monkeypatch: pytest.MonkeyPatch,
    profile: _ProfileSnapshot,
    candidate: _Candidate,
    facts: PostingFacts,
) -> list[_AcceptedJob]:
    from unittest.mock import AsyncMock

    from app.core.config import Settings

    monkeypatch.setattr(
        providers.litellm_gateway,
        "complete_structured",
        AsyncMock(return_value=PostingBatch(postings=[facts])),
    )
    return await providers.EvidenceRanker(Settings()).rank(profile, [candidate], {})


@pytest.mark.parametrize(
    ("premium_enabled", "web_enabled"), [(False, True), (True, False), (False, False)]
)
async def test_analysis_flags_block_provider_calls_and_spending(
    monkeypatch: pytest.MonkeyPatch, fake_redis, premium_enabled: bool, web_enabled: bool
) -> None:
    from unittest.mock import AsyncMock

    from app.core.config import Settings
    from app.modules.job_search import runner, spending
    from app.modules.job_search.service import JobSearchError
    from app.services import quota

    load = AsyncMock()
    extract = AsyncMock()
    rank = AsyncMock()
    spend = AsyncMock()
    tokens = AsyncMock()
    monkeypatch.setattr(runner, "_load_snapshot", load)
    monkeypatch.setattr(providers.TavilyExtraction, "extract", extract)
    monkeypatch.setattr(providers.EvidenceRanker, "rank", rank)
    monkeypatch.setattr(quota, "record_global_spend", spend)
    monkeypatch.setattr(spending, "record_tokens", tokens)
    with pytest.raises(JobSearchError, match="unavailable") as error:
        await runner.analyze_job_url(
            Settings(job_search_premium_enabled=premium_enabled, web_search_enabled=web_enabled),
            profile_id=uuid4(),
            url="https://jobs.example.com/roles/123",
            redis=fake_redis,
        )
    assert error.value.status_code == 503
    for blocked in (load, extract, rank, spend, tokens):
        blocked.assert_not_awaited()
