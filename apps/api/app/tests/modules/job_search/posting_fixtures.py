"""Realistic, locally authored posting fixtures; no live provider spending in tests."""

from dataclasses import replace
from uuid import uuid4

from app.modules.job_search.records import _Candidate, _ProfileSnapshot
from app.modules.job_search.verification import PostingFacts


def profile(**changes) -> _ProfileSnapshot:
    base = _ProfileSnapshot(
        id=uuid4(),
        user_id=uuid4(),
        timezone="America/Los_Angeles",
        is_pro=True,
        target_roles=["Backend Engineer"],
        skills=["Python", "SQL"],
        location="California, United States",
        work_modes=["remote", "hybrid", "onsite"],
        experience_levels=["internship", "entry", "mid", "senior"],
        salary_min=None,
        requires_sponsorship=None,
        excluded_companies=[],
        background=None,
        resume_text=None,
        resume_profile=None,
        hidden_companies=[],
        hidden_titles=[],
        result_count=10,
        frequency="weekdays",
        included_locations=[{"country": "United States", "region": "California"}],
        excluded_locations=[],
        country="United States",
        salary_currency="USD",
        years_experience=5,
    )
    return replace(base, **changes)


def posting(
    *,
    title="Backend Engineer",
    company="Acme",
    country="United States",
    region="California",
    city="San Francisco",
    mode="onsite",
    salary="USD 100,000-120,000 per year",
    lower=100000,
    upper=120000,
    currency="USD",
    period="year",
    years=3,
    requisition="ENG-101",
    remote_countries=None,
    worldwide=False,
    skills=None,
    availability="open",
):
    skills = ["Python", "SQL"] if skills is None else skills
    place = ", ".join(value for value in (city, region, country) if value)
    experience = (
        f"{years:g}+ years of experience" if years is not None else "Experience not specified"
    )
    apply = (
        "Apply now. Applications are open."
        if availability == "open"
        else "This position is closed."
    )
    remote = "Remote hiring countries: " + ", ".join(remote_countries or [])
    if worldwide:
        remote += " Worldwide hiring in any country."
    text = f"{title}\n{company}\nLocation: {place}\nWork arrangement: {mode}\nSalary: {salary or 'Not disclosed'}\nRequirements: {experience}; {', '.join(skills)}.\nRequisition {requisition or 'Not disclosed'}\n{remote}\nResponsibilities: Build and maintain reliable systems for customers.\n{apply}"
    evidence = {
        "title": title,
        "company": company,
        "document_kind": "Responsibilities: Build and maintain reliable systems for customers.",
        "availability": apply,
        "location": place,
        "countries": country,
        "work_mode": mode,
        "required_skills": ", ".join(skills),
    }
    if region:
        evidence["region"] = region
    if city:
        evidence["city"] = city
    if salary:
        evidence["salary"] = salary
    if years is not None:
        evidence["minimum_years"] = experience
    if requisition:
        evidence["requisition"] = requisition
    if remote_countries:
        evidence["remote_countries"] = remote
    if worldwide:
        evidence["remote_worldwide"] = remote
    facts = PostingFacts(
        candidate_id=0,
        document_kind="posting",
        availability=availability,
        title=title,
        company=company,
        location=place,
        countries=[country],
        region=region,
        city=city,
        work_mode=mode,
        salary_text=salary,
        salary_lower=lower if salary else None,
        salary_upper=upper if salary else None,
        salary_currency=currency if salary else None,
        salary_period=period if salary else None,
        minimum_years=years,
        requisition=requisition,
        required_skills=skills,
        remote_countries=remote_countries or [],
        remote_worldwide=worldwide,
        evidence=evidence,
    )
    candidate = _Candidate(
        0,
        title,
        f"https://careers.example.com/jobs/{requisition or 'role'}",
        f"https://careers.example.com/jobs/{requisition or 'role'}",
        title,
        "careers.example.com",
        text,
    )
    return candidate, facts
