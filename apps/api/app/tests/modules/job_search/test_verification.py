from dataclasses import replace

import pytest

from app.gateways.web_search_gateway import WebSearchHit
from app.modules.job_search.discovery import collect_candidates
from app.modules.job_search.providers import SearchResponse
from app.modules.job_search.schemas import JobLocation
from app.modules.job_search.verification import assess, grounded
from app.tests.modules.job_search.posting_fixtures import posting, profile


@pytest.mark.parametrize(
    "country,region,city,title,currency,pay",
    [
        (
            "United States",
            "California",
            "Oakland",
            "Registered Nurse",
            "USD",
            "USD 100,000-120,000 per year",
        ),
        ("Canada", "Ontario", "Toronto", "Teacher", "CAD", "CAD 100,000-120,000 per year"),
        ("Germany", "Berlin", "Berlin", "Intensivpfleger", "EUR", "EUR 100,000-120,000 per year"),
        (
            "United Kingdom",
            "England",
            "London",
            "Account Executive",
            "GBP",
            "GBP 100,000-120,000 per year",
        ),
        (
            "India",
            "Karnataka",
            "Bengaluru",
            "Backend Engineer",
            "INR",
            "INR 100,000-120,000 per year",
        ),
        ("Ethiopia", None, "Addis Ababa", "Civil Engineer", "ETB", "ETB 100,000-120,000 per year"),
        (
            "Australia",
            "Victoria",
            "Melbourne",
            "Electrician",
            "AUD",
            "AUD 100,000-120,000 per year",
        ),
    ],
)
def test_verified_worldwide_postings(country, region, city, title, currency, pay):
    candidate, facts = posting(
        country=country, region=region, city=city, title=title, currency=currency, salary=pay
    )
    verified = grounded(facts, candidate)
    assert verified is not None
    match = assess(
        profile(
            target_roles=[title],
            included_locations=[{"country": country}],
            salary_currency=currency,
            salary_min=100000,
        ),
        verified,
        candidate,
    )
    assert match and match.match_kind == "qualifying"
    assert match.assessment["fit_label"] == "Strong fit"


@pytest.mark.parametrize(
    "lower,upper,currency,period,salary,expected",
    [
        (100000, 120000, "USD", "year", "USD 100,000-120,000 per year", "qualifying"),
        (90000, 120000, "USD", "year", "USD 90,000-120,000 per year", "possible"),
        (80000, 90000, "USD", "year", "USD 80,000-90,000 per year", None),
        (100000, 120000, "EUR", "year", "EUR 100,000-120,000 per year", "possible"),
        (100000, 120000, "USD", "month", "USD 100,000-120,000 per month", "possible"),
        (50, 60, "USD", "hour", "USD 50-60 per hour", "possible"),
        (100000, 120000, "USD", "year", "$100,000-120,000 per year", "possible"),
        (None, None, None, None, None, "possible"),
    ],
)
def test_salary_requires_compatible_verified_lower_bound(
    lower, upper, currency, period, salary, expected
):
    candidate, facts = posting(
        lower=lower, upper=upper, currency=currency, period=period, salary=salary
    )
    verified = grounded(facts, candidate)
    assert verified
    match = assess(profile(salary_min=100000), verified, candidate)
    assert (match.match_kind if match else None) == expected


@pytest.mark.parametrize(
    "region,expected", [("California", True), ("Texas", False), ("District of Columbia", False)]
)
def test_state_scope_and_exclusions(region, expected):
    candidate, facts = posting(region=region)
    verified = grounded(facts, candidate)
    scope = profile(
        excluded_locations=[{"country": "United States", "region": "District of Columbia"}]
    )
    assert bool(assess(scope, verified, candidate)) == expected


@pytest.mark.parametrize(
    "countries,worldwide,expected",
    [
        (["Canada"], False, None),
        (["United States"], False, "qualifying"),
        ([], False, "possible"),
        ([], True, "qualifying"),
    ],
)
def test_remote_hiring_restrictions(countries, worldwide, expected):
    candidate, facts = posting(mode="remote", remote_countries=countries, worldwide=worldwide)
    verified = grounded(facts, candidate)
    match = assess(profile(), verified, candidate)
    assert (match.match_kind if match else None) == expected


def test_remote_state_restriction_rejects_california():
    candidate, facts = posting(mode="remote", remote_countries=["United States"])
    restriction = "Remote hiring only in Texas, United States"
    candidate = replace(candidate, page_text=candidate.page_text + "\n" + restriction)
    facts.remote_locations = [JobLocation(country="United States", region="Texas")]
    facts.evidence["remote_locations"] = restriction
    verified = grounded(facts, candidate)
    assert verified
    assert assess(profile(), verified, candidate) is None


@pytest.mark.parametrize(
    "change",
    [
        {"company": "Imaginary Corp"},
        {"title": "Invented title"},
        {"document_kind": "listing"},
        {"availability": "closed"},
    ],
)
def test_unverified_identity_listing_and_closed_pages_never_become_matches(change):
    candidate, facts = posting()
    modified = facts.model_copy(update=change)
    assert grounded(modified, candidate) is None


def test_unreadable_closed_and_ungrounded_salary():
    candidate, facts = posting()
    assert grounded(facts, replace(candidate, page_text="unreadable")) is None
    assert (
        grounded(facts, replace(candidate, page_text=candidate.page_text + " This job is expired."))
        is None
    )
    facts.salary_lower = 999999
    verified = grounded(facts, candidate)
    assert verified and verified.salary_lower == 100000


def test_numeric_experience_uses_explicit_user_value():
    candidate, facts = posting(years=6)
    verified = grounded(facts, candidate)
    assert assess(profile(years_experience=5), verified, candidate) is None
    assert assess(profile(years_experience=7), verified, candidate).match_kind == "qualifying"


def test_candidate_intake_is_fair_and_bounded():
    responses = [
        SearchResponse(
            [
                WebSearchHit(
                    f"Engineer {group}-{i}", f"https://careers.example.com/{group}/{i}", "Posting"
                )
                for i in range(10)
            ]
        )
        for group in range(6)
    ]
    candidates = collect_candidates(responses)
    assert len(candidates) == 30
    assert {item.url.split("/")[-2] for item in candidates} == set(map(str, range(6)))


def test_negated_remote_country_is_not_positive_eligibility():
    candidate, facts = posting(mode="remote", remote_countries=["United States"])
    prohibition = "We cannot hire in United States."
    candidate = replace(candidate, page_text=candidate.page_text + "\n" + prohibition)
    facts.evidence["remote_countries"] = prohibition
    verified = grounded(facts, candidate)
    assert verified and verified.remote_countries == []
    assert assess(profile(), verified, candidate).match_kind == "possible"


def test_salary_number_cannot_ground_years_of_experience():
    candidate, facts = posting(
        years=None, salary="USD 50 per hour", lower=50, upper=None, period="hour"
    )
    facts.minimum_years = 50
    facts.evidence["minimum_years"] = "USD 50 per hour"
    verified = grounded(facts, candidate)
    assert verified and verified.minimum_years is None


def test_remote_country_comparison_is_case_insensitive():
    candidate, facts = posting(mode="remote", remote_countries=["United States"])
    verified = grounded(facts, candidate)
    assert (
        assess(
            profile(included_locations=[{"country": "united states"}]), verified, candidate
        ).match_kind
        == "qualifying"
    )


async def test_zai_comparison_requires_explicit_opt_in(monkeypatch):
    from unittest.mock import Mock

    from app.core.config import Settings
    from app.modules.job_search import providers
    from app.modules.job_search.records import PostingVerificationError

    client = Mock()
    monkeypatch.setattr(providers, "get_pooled_client", client)
    with pytest.raises(PostingVerificationError, match="disabled"):
        await providers.ZaiComparisonSearch(Settings()).search("Teacher Canada")
    client.assert_not_called()


def test_ambiguous_reference_query_keeps_distinct_posting_identifiers():
    from app.modules.job_search.posting import canonicalize_job_url

    first = canonicalize_job_url("https://careers.example.com/opening?ref=REQ-1&utm_source=mail")
    second = canonicalize_job_url("https://careers.example.com/opening?ref=REQ-2&utm_source=mail")
    assert first != second and "utm_source" not in first
