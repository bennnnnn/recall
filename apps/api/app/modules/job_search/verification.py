"""Ground extracted posting facts in quotes; enforce preferences without inventing facts."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.job_search.locations import canonical_country, contains_place
from app.modules.job_search.posting import (
    _extract_company_logo_url,
    _is_board_name,
    _is_generic_employer,
    _is_listing_title,
)
from app.modules.job_search.records import _AcceptedJob, _Candidate, _ProfileSnapshot
from app.modules.job_search.schemas import JobLocation

_CLOSED = re.compile(
    (
        "(?:position|job|vacancy|posting) (?:has been |is )?(?:c"
        "losed|filled|expired)|no longer accepting applications|"
        "applications? (?:are )?closed"
    ),
    re.I,
)


class PostingFacts(BaseModel):
    candidate_id: int
    document_kind: Literal["posting", "listing", "unknown"] = "unknown"
    availability: Literal["open", "closed", "unknown"] = "unknown"
    title: str | None = Field(default=None, max_length=240)
    company: str | None = Field(default=None, max_length=180)
    location: str | None = Field(default=None, max_length=180)
    countries: list[str] = Field(default_factory=list, max_length=20)
    region: str | None = Field(default=None, max_length=100)
    city: str | None = Field(default=None, max_length=100)
    work_mode: Literal["remote", "hybrid", "onsite"] | None = None
    remote_countries: list[str] = Field(default_factory=list, max_length=50)
    remote_worldwide: bool = False
    remote_locations: list[JobLocation] = Field(default_factory=list, max_length=30)
    remote_excluded_locations: list[JobLocation] = Field(default_factory=list, max_length=30)
    salary_lower: float | None = Field(default=None, ge=0)
    salary_upper: float | None = Field(default=None, ge=0)
    salary_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    salary_period: Literal["year", "month", "week", "hour"] | None = None
    salary_text: str | None = Field(default=None, max_length=160)
    minimum_years: float | None = Field(default=None, ge=0, le=80)
    seniority: Literal["internship", "entry", "mid", "senior"] | None = None
    sponsorship: bool | None = None
    requisition: str | None = Field(default=None, max_length=120)
    required_skills: list[str] = Field(default_factory=list, max_length=12)
    posted_at: str | None = Field(default=None, max_length=120)
    summary: str | None = Field(default=None, max_length=600)
    # Every populated factual field needs an exact quote from this page.
    evidence: dict[str, str] = Field(default_factory=dict)


class PostingBatch(BaseModel):
    postings: list[PostingFacts] = Field(default_factory=list, max_length=6)


def _fold(text: str) -> str:
    return " ".join(text.casefold().split())


def grounded(facts: PostingFacts, candidate: _Candidate) -> PostingFacts | None:
    text = candidate.page_text or ""
    if len(text.strip()) < 80 or _CLOSED.search(text):
        return None
    values = facts.model_dump()
    evidence = {
        key: quote
        for key, quote in facts.evidence.items()
        if quote.strip() and _fold(quote) in _fold(text)
    }
    for key, default in (
        ("title", None),
        ("company", None),
        ("location", None),
        ("countries", []),
        ("region", None),
        ("city", None),
        ("work_mode", None),
        ("remote_countries", []),
        ("remote_worldwide", False),
        ("remote_locations", []),
        ("remote_excluded_locations", []),
        ("minimum_years", None),
        ("seniority", None),
        ("sponsorship", None),
        ("requisition", None),
        ("required_skills", []),
        ("posted_at", None),
        ("summary", None),
    ):
        if key not in evidence:
            values[key] = default
    # String facts and skill names must themselves appear on the page.
    for key in ("title", "company", "region", "city", "requisition", "posted_at"):
        value = values[key]
        if value and _fold(value) not in _fold(evidence.get(key, "")):
            values[key] = None
    values["required_skills"] = [
        skill
        for skill in values["required_skills"]
        if _fold(skill) in _fold(evidence.get("required_skills", ""))
    ]
    # A country quoted only in a prohibition cannot establish hiring eligibility.
    prohibition = r"\b(?:not|cannot|can't|unable|excluding|except|ineligible|no hires?)\b"
    for key in ("countries", "remote_countries"):
        values[key] = [
            canonical_country(country)
            for country in values[key]
            if contains_place({"country": canonical_country(country)}, evidence.get(key, ""))
            and (
                key != "remote_countries" or not re.search(prohibition, evidence.get(key, ""), re.I)
            )
        ]
    for key in ("remote_locations", "remote_excluded_locations"):
        values[key] = [
            place
            for place in values[key]
            if contains_place(place, evidence.get(key, ""))
            and (
                bool(re.search(prohibition, evidence.get(key, ""), re.I))
                if key == "remote_excluded_locations"
                else not re.search(prohibition, evidence.get(key, ""), re.I)
            )
        ]
    mode = values["work_mode"]
    mode_quote = evidence.get("work_mode", "")
    patterns = {
        "remote": r"remote|work from home|telecommut",
        "hybrid": r"hybrid",
        "onsite": r"on[ -]?site|in[ -]?person",
    }
    if mode and (
        not re.search(patterns[mode], mode_quote, re.I)
        or re.search(r"not remote|no remote", mode_quote, re.I)
    ):
        values["work_mode"] = None
    if values["remote_worldwide"] and (
        not re.search(r"worldwide|globally|any country", evidence.get("remote_worldwide", ""), re.I)
        or re.search(r"not|except|excluding", evidence.get("remote_worldwide", ""), re.I)
    ):
        values["remote_worldwide"] = False
    years_quote = evidence.get("minimum_years", "")
    if values["minimum_years"] is not None and not re.search(
        rf"(?<!\d){values['minimum_years']:g}(?:\+|\s|[-\u2013])*\s*(?:years?|yrs?)\b",
        years_quote,
        re.I,
    ):
        values["minimum_years"] = None
    if values["availability"] == "open" and not re.search(
        r"apply|accepting applications|applications open", evidence.get("availability", ""), re.I
    ):
        values["availability"] = "unknown"
    level_patterns = {
        "entry": r"entry[ -]?level|junior",
        "mid": r"mid[ -]?level|intermediate",
        "senior": r"senior|principal|staff",
        "internship": r"intern",
    }
    if values["seniority"] and not re.search(
        level_patterns[values["seniority"]], evidence.get("seniority", ""), re.I
    ):
        values["seniority"] = None
    sponsorship_quote = evidence.get("sponsorship", "")
    if values["sponsorship"] is not None:
        if not re.search(r"sponsor|visa", sponsorship_quote, re.I):
            values["sponsorship"] = None
        elif re.search(r"no |not |without |unavailable", sponsorship_quote, re.I):
            values["sponsorship"] = False
    values["summary"] = evidence.get("summary", "")[:600] or None
    salary_quote = evidence.get("salary", "")
    for key in ("salary_lower", "salary_upper", "salary_currency", "salary_period", "salary_text"):
        if not salary_quote:
            values[key] = None
    if salary_quote:
        # Currency symbols alone are ambiguous; never infer USD from '$'.
        currency = values["salary_currency"]
        symbols = {"USD": "US$", "CAD": "CA$", "AUD": "AU$", "EUR": "€", "GBP": "£"}
        if (
            currency
            and currency.casefold() not in salary_quote.casefold()
            and symbols.get(currency, "\x00") not in salary_quote
        ):
            values["salary_currency"] = None
        period = values["salary_period"]
        period_words = {
            "year": r"year|annual|annum",
            "month": r"month",
            "week": r"week",
            "hour": r"hour|/hr",
        }
        if period and not re.search(period_words[period], salary_quote, re.I):
            values["salary_period"] = None
        normalized_numbers = [
            float(number.replace(",", "")) * (1000 if suffix else 1)
            for number, suffix in re.findall(r"(\d[\d,]*(?:\.\d+)?)\s*([kK]?)", salary_quote)
        ]
        # Derive range boundaries ourselves: quoting the range cannot justify
        # presenting its upper endpoint as the minimum.
        if len(normalized_numbers) == 2:
            if normalized_numbers[0] < 1000 <= normalized_numbers[1] and re.search(
                r"[kK]", salary_quote
            ):
                normalized_numbers[0] *= 1000
            values["salary_lower"], values["salary_upper"] = sorted(normalized_numbers)
        elif len(normalized_numbers) == 1:
            number = normalized_numbers[0]
            values["salary_lower"] = (
                None if re.search(r"up to|maximum|at most", salary_quote, re.I) else number
            )
            values["salary_upper"] = (
                None if re.search(r"from|minimum|at least|\+", salary_quote, re.I) else number
            )
        else:
            values["salary_lower"] = values["salary_upper"] = None
        values["salary_text"] = salary_quote[:160]
    if "document_kind" not in evidence or facts.document_kind != "posting":
        return None
    if "availability" not in evidence:
        values["availability"] = "unknown"
    if (
        values["availability"] == "closed"
        or not values["title"]
        or not values["company"]
        or _is_board_name(values["company"])
        or _is_generic_employer(values["company"])
        or _is_listing_title(values["title"])
    ):
        return None
    values["evidence"] = evidence
    return PostingFacts.model_validate(values)


def assess(
    profile: _ProfileSnapshot, facts: PostingFacts, candidate: _Candidate
) -> _AcceptedJob | None:
    if any(
        re.search(
            r"(?<!\w)" + re.escape(company.casefold()) + r"(?!\w)", (facts.company or "").casefold()
        )
        for company in profile.excluded_companies
    ):
        return None
    unresolved: list[str] = []
    reasons: list[str] = []
    disclosed = {
        "country": facts.countries[0] if len(facts.countries) == 1 else None,
        "region": facts.region,
        "city": facts.city,
    }
    place_text = ", ".join(str(v) for v in disclosed.values() if v)
    includes = profile.included_locations or (
        [{"country": profile.country}] if profile.country else []
    )
    excludes = profile.excluded_locations or []
    # Exclusions apply to a stated posting location, including remote roles.
    for place in excludes:
        if contains_place(place, place_text):
            return None
    if facts.work_mode == "remote":
        desired_countries = {canonical_country(place["country"]).casefold() for place in includes}
        eligible = {canonical_country(country).casefold() for country in facts.remote_countries}
        if desired_countries and eligible and not desired_countries.intersection(eligible):
            return None
        if not facts.remote_worldwide and not eligible:
            unresolved.append("Remote hiring eligibility is not disclosed")
        elif desired_countries and (
            facts.remote_worldwide or desired_countries.intersection(eligible)
        ):
            reasons.append("Remote hiring includes your search country")
        eligible_places = [place.model_dump() for place in facts.remote_locations]
        if eligible_places:

            def overlaps(left: dict, right: dict) -> bool:
                return all(
                    not left.get(key)
                    or not right.get(key)
                    or str(left[key]).casefold() == str(right[key]).casefold()
                    for key in ("country", "region", "city")
                )

            if includes and not any(
                overlaps(desired, eligible_place)
                for desired in includes
                for eligible_place in eligible_places
            ):
                return None
            if all(
                any(
                    contains_place(
                        excluded,
                        ", ".join(str(value) for value in eligible_place.values() if value),
                    )
                    for excluded in excludes
                )
                for eligible_place in eligible_places
            ):
                return None
        for remote_excluded in facts.remote_excluded_locations:
            if includes and all(
                contains_place(
                    remote_excluded.model_dump(), ", ".join(str(v) for v in desired.values() if v)
                )
                for desired in includes
            ):
                return None
    elif includes:
        if any(contains_place(place, place_text) for place in includes):
            reasons.append("The posting location matches your search scope")
        elif facts.countries and (
            not any(
                canonical_country(place["country"]).casefold()
                in {country.casefold() for country in facts.countries}
                for place in includes
            )
            or (facts.region and any(place.get("region") for place in includes))
            or (facts.city and any(place.get("city") for place in includes))
        ):
            return None
        else:
            unresolved.append("The posting location needs confirmation")
    if facts.work_mode is not None and facts.work_mode not in profile.work_modes:
        return None
    if facts.work_mode is None and set(profile.work_modes) != {"remote", "hybrid", "onsite"}:
        unresolved.append("The work arrangement is not disclosed")
    elif facts.work_mode and len(profile.work_modes) < 3:
        reasons.append(f"The {facts.work_mode} arrangement matches your preference")
    if profile.salary_min is not None:
        compatible = (
            facts.salary_currency is not None
            and facts.salary_currency == profile.salary_currency
            and facts.salary_period == profile.salary_period
        )
        if (
            compatible
            and facts.salary_upper is not None
            and facts.salary_upper < profile.salary_min
        ):
            return None
        if (
            compatible
            and facts.salary_lower is not None
            and facts.salary_lower >= profile.salary_min
        ):
            reasons.append(
                f"Disclosed minimum pay meets {profile.salary_currency} "
                f"{profile.salary_min:,}/{profile.salary_period}"
            )
        else:
            unresolved.append("Pay does not confirm your minimum in the same currency and period")
    actual_years = profile.years_experience
    if facts.minimum_years is not None and actual_years is not None:
        if facts.minimum_years > actual_years:
            return None
        reasons.append(
            f"Your {actual_years:g} years meet the {facts.minimum_years:g}-year requirement"
        )
    if facts.seniority and facts.seniority not in profile.experience_levels:
        return None
    if facts.seniority is None and len(profile.experience_levels) < 4:
        unresolved.append("Desired job seniority needs confirmation")
    if profile.requires_sponsorship is True:
        if facts.sponsorship is False:
            return None
        if facts.sponsorship is None:
            unresolved.append("Sponsorship availability is not disclosed")
        else:
            reasons.append("The posting offers sponsorship")
    if facts.availability != "open":
        unresolved.append("Current application availability needs confirmation")
    skills = profile.skills
    overlap = [
        skill
        for skill in facts.required_skills
        if any(_fold(skill) == _fold(item) for item in skills)
    ]
    if overlap:
        reasons.append(f"Your {', '.join(overlap[:3])} matches the posting requirements")
    if not any(
        _fold(role) in _fold(facts.title or "") or _fold(facts.title or "") in _fold(role)
        for role in profile.target_roles
    ):
        # Related titles remain reviewable, never a strong verified role match.
        unresolved.append("The job title differs from your target roles")
    kind = "possible" if unresolved else "qualifying"
    label = (
        "Strong fit"
        if kind == "qualifying" and len(reasons) >= 2
        else "Potential fit"
        if kind == "qualifying"
        else "Needs review"
    )
    identity = (
        f"{_fold(facts.company or '')}:{facts.requisition.casefold()}"
        if facts.requisition
        else None
    )
    return _AcceptedJob(
        candidate=candidate,
        title=facts.title or "",
        company=facts.company or "",
        company_logo_url=_extract_company_logo_url(candidate, facts.company or ""),
        location=facts.location or place_text or None,
        work_mode=facts.work_mode,
        salary=facts.salary_text,
        experience=f"{facts.minimum_years:g}+ years"
        if facts.minimum_years is not None
        else facts.seniority,
        match_score=None,
        posted_at=facts.posted_at,
        summary=facts.summary,
        required_skills=facts.required_skills,
        match_reasons=reasons[:5],
        gap="; ".join(unresolved) or None,
        assessment=facts.model_dump() | {"unresolved": unresolved, "fit_label": label},
        match_kind=kind,
        posting_identity=identity,
    )
