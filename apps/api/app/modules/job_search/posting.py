"""Read one job posting: title, employer, place, pay, and the role itself."""

from __future__ import annotations

import hashlib
import html
import ipaddress
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.modules.job_search.records import _AcceptedJob, _Candidate, _ProfileSnapshot

# Pay and the role body sit past the nav and the culture copy. 4k cuts them off.
_POSTING_EXTRACT_CHARS = 12_000
_TRACKING_KEYS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "referrer",
    "source",
}
_SENIOR_TERMS = re.compile(
    r"\b(senior|staff|principal|lead|manager|director|architect|head of|vp)\b",
    re.IGNORECASE,
)
_JUNIOR_TERMS = re.compile(
    r"\b(intern(?:ship)?|entry[ -]?level|junior|graduate|new grad)\b",
    re.IGNORECASE,
)
_EXPLICIT_SENIOR_LEVEL = re.compile(
    r"\b(senior|staff|principal|director|head of|vp|vice president)\b",
    re.IGNORECASE,
)
_NO_SPONSORSHIP = re.compile(
    r"\b(no|without|unable to provide)\s+(visa\s+)?sponsorship\b",
    re.IGNORECASE,
)
_SPONSORSHIP_AVAILABLE = re.compile(
    r"\b(visa sponsorship|sponsorship (is )?(available|provided|offered)|"
    r"will sponsor|sponsor eligible)\b",
    re.IGNORECASE,
)
_SALARY_NUMBER = re.compile(
    r"(?<!\w)(\d{2,3}(?:[,.]\d{3})+|\d{1,3}(?:[,.]\d{1,2})(?=\s*[kK]\b)|"
    r"\d{4,7}|\d{2,3})(\s*[kK])?"
)
_COMPANY_SUFFIXES = re.compile(
    r"\b(inc|llc|ltd|gmbh|corp|corporation|co|company|sarl|sas|ag)\b\.?",
    re.IGNORECASE,
)

# --- Listing-page detection -------------------------------------------------
# A card must always be one specific opening on its own page. Search-result and
# category pages ("500+ Nurse Jobs in Berlin | Indeed") carry no single salary,
# experience, or employer, so they are rejected at intake and again after ranking.
_AGGREGATOR_HOST_MARKERS = (
    "indeed.",
    "stepstone.",
    "linkedin.",
    "glassdoor.",
    "ziprecruiter.",
    "monster.",
    "careerjet.",
    "jooble.",
    "simplyhired.",
    "xing.",
    "totaljobs.",
    "reed.co",
    "stellenanzeigen.",
    "kimeta.",
    "jobware.",
    "arbeitnow.",
)
_BOARD_NAMES = {marker.removesuffix(".").split(".")[0] for marker in _AGGREGATOR_HOST_MARKERS} | {
    "reed"
}
# "500+ Registered Nurse Jobs", "12,000+ jobs" — only list pages headline counts.
_LISTING_TITLE_COUNT = re.compile(r"\b\d[\d,.]*\s*\+\s+[^|]{0,60}\bjobs?\b", re.IGNORECASE)
_LISTING_TITLE_PLACE = re.compile(
    r"\bjobs\s+(in|near|bei|im|für|for)\b|\bstellenangebote\b|\boffene\s+stellen\b|"
    r"\bjobbörse\b|\bstellenmarkt\b|\bjob\s+listings\b|\bjobs\s+found\b|"
    r"\bjob\s+search\b|\bvacancies\s+in\b",
    re.IGNORECASE,
)
_LISTING_TITLE_GENERIC = re.compile(
    r"\bjobs?(?:\s*\((?:now hiring|hiring)\)|\s+(?:now hiring|hiring))?"
    r"(?:\s+\d{4})?\s*$",
    re.IGNORECASE,
)
_LISTING_QUERY_KEYS = {"q", "query", "search", "keyword", "keywords", "what", "where"}
_LISTING_PATH_MARKERS = ("/jobs/search", "/jobsearch", "srch_", "/jobs-by-")
_LISTING_PATH_ROOTS = ("/jobs", "/careers", "/stellenangebote", "/offene-stellen", "/jobboerse")
# Board suffix glued onto page titles: "Nurse at Acme | Indeed.com".
_BOARD_SUFFIX = re.compile(
    r"\s*[|\u2013\u2014-]\s*(indeed|stepstone|linkedin|glassdoor|ziprecruiter|monster|"
    r"careerjet|jooble|simplyhired|xing|totaljobs|reed|stellenanzeigen|kimeta|"
    r"jobware|arbeitnow|jobs\.ch|jobup\.ch)(\.[a-z]{2,})?\s*$",
    re.IGNORECASE,
)


def _is_listing_title(title: str) -> bool:
    return bool(
        _LISTING_TITLE_COUNT.search(title)
        or _LISTING_TITLE_PLACE.search(title)
        or _LISTING_TITLE_GENERIC.search(title.strip(" ()"))
    )


def _is_listing_page(url: str, title: str) -> bool:
    """Search-result / category pages can never yield one specific posting."""
    if _is_listing_title(title):
        return True
    parsed = urlsplit(url)
    path = parsed.path.casefold().rstrip("/")
    if path.endswith("-jobs") or path.endswith("/jobs"):
        return True
    if path.endswith(_LISTING_PATH_ROOTS):
        return True
    if any(marker in path for marker in _LISTING_PATH_MARKERS):
        return True
    query_keys = {key.casefold() for key, _ in parse_qsl(parsed.query, keep_blank_values=True)}
    return bool(query_keys & _LISTING_QUERY_KEYS)


def _is_board_name(company: str) -> bool:
    return _normalize_key_part(company) in _BOARD_NAMES


def _content_words(text: str) -> set[str]:
    return set(re.findall(r"[a-zäöüß0-9]{3,}", text.casefold()))


def _grounded_title(title: str, candidate: _Candidate) -> bool:
    """A ranked title is only trusted when its words appear in the fetched
    posting (or, without a page fetch, in the search title/snippet). Anything
    else is a composed label like 'Registered Nurse (ICU) — Berlin'."""
    words = _content_words(title)
    if not words:
        return False
    haystack = (candidate.page_text or f"{candidate.title} {candidate.snippet}").casefold()
    hits = sum(1 for word in words if word in haystack)
    return hits / len(words) >= 0.6


def _normalize_key_part(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", value.casefold()).split())


def _title_company_key(title: str, company: str) -> str:
    """Cross-source identity: the same opening posted on several boards shares
    a title+company pair even though every URL differs."""
    normalized_company = _normalize_key_part(_COMPANY_SUFFIXES.sub("", company))
    return f"{_normalize_key_part(title)}|{normalized_company}"


def _dedupe_accepted(accepted: list[_AcceptedJob]) -> list[_AcceptedJob]:
    """Drop same-job repeats inside one batch (different boards, same opening)."""
    seen: set[str] = set()
    unique: list[_AcceptedJob] = []
    for item in accepted:
        key = _title_company_key(item.title, item.company)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def canonicalize_job_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return ""
    query = [
        (key, val)
        for key, val in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in _TRACKING_KEYS
    ]
    path = re.sub(r"/{2,}", "/", parsed.path).rstrip("/") or "/"
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            urlencode(sorted(query)),
            "",
        )
    )


def _canonical_url_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _source_for_url(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return host.removeprefix("www.")[:120]


def _strip_board_suffix(title: str) -> str:
    cleaned = title
    for _ in range(3):
        stripped = _BOARD_SUFFIX.sub("", cleaned).strip()
        if stripped == cleaned:
            break
        cleaned = stripped
    return cleaned


def _title_and_company(raw: str, source: str) -> tuple[str, str]:
    title = _strip_board_suffix(" ".join(raw.strip().split())) or "Job opening"
    for separator in (" at ", " | ", " — ", " - "):
        if separator in title:
            left, right = title.split(separator, 1)
            if left.strip() and right.strip():
                return left.strip()[:240], right.strip()[:180]
    # A board/aggregator domain is not an employer — stay honest instead of
    # stamping "Indeed" as the company.
    if any(marker in source for marker in _AGGREGATOR_HOST_MARKERS):
        return title[:240], "Unknown employer"
    return title[:240], _employer_from_host(source)


_CAREER_HOST_LABELS = frozenset(
    {"jobs", "job", "careers", "career", "apply", "boards", "recruiting", "talent", "www"}
)
_ATS_HOST_LABELS = frozenset(
    {
        "greenhouse",
        "lever",
        "ashbyhq",
        "ashby",
        "workable",
        "myworkdayjobs",
        "workday",
        "smartrecruiters",
        "icims",
        "taleo",
    }
)
_HOST_SUFFIXES = frozenset(
    {"com", "io", "co", "de", "org", "net", "uk", "jobs", "ai", "app", "dev"}
)


def _is_career_host_label(label: str) -> bool:
    """A careers token, including a compound such as ``job-boards``."""
    if label in _CAREER_HOST_LABELS:
        return True
    parts = [part for part in label.split("-") if part]
    return len(parts) > 1 and all(part in _CAREER_HOST_LABELS for part in parts)


def _employer_from_host(source: str) -> str:
    """Employer from a career hostname, skipping the jobs/careers label.

    ``jobs.gartner.com`` is Gartner. ``apply.workable.com`` is an ATS, not the
    employer, so it stays unknown until the page names a company.
    """
    labels = [part for part in source.casefold().split(".") if part and part not in _HOST_SUFFIXES]
    while labels and _is_career_host_label(labels[0]):
        del labels[0]
    if not labels or labels[0] in _ATS_HOST_LABELS or labels[0] in _BOARD_NAMES:
        return "Unknown employer"
    return labels[0].replace("-", " ").title()[:180]


def _verified_fallback_identity(candidate: _Candidate) -> tuple[str | None, str]:
    """Extract an honest title/employer from a fetched posting page.

    The title is only a real ``#`` heading. A page with no heading returns
    ``None`` so a grounded ranker title is not replaced by the search result.
    ATS search titles are inconsistent. The page heading and logo alt text are
    stronger evidence than deriving an employer from a hostname like
    ``apply.workable.com``.
    """
    page = " ".join((candidate.page_text or "").split())
    # A single '#' heading. Stop at the next '##' so "Senior Account Executive
    # ## Description Remote, New York" does not keep the section label.
    heading_match = re.search(
        r"(?:^|\s)#(?!#)\s+(.{2,240}?)(?=\s+\*|\s+##|\s+\*\*|\s+Remote\b|\s+Full[ -]?time\b|$)",
        page,
        re.IGNORECASE,
    )
    title = heading_match.group(1).strip() if heading_match else None
    if title is not None:
        title = re.sub(r"\s+#+\s*$", "", title).strip()
        title = re.sub(
            r"^\(remote\)\s*[-\u2013\u2014:]\s*",
            "",
            title,
            flags=re.IGNORECASE,
        )
        title = _clean_posting_title(title) or None

    company_match = re.search(
        r"Image\s+\d+\s*:\s*([^\]]{2,100})\]",
        page,
        re.IGNORECASE,
    )
    if company_match is None:
        company_match = re.search(
            r"!\[([A-Z][^\]|]{1,40}?)\s+(?:Careers\s+)?logo\]",
            page,
        )
    if company_match is None:
        company_match = re.search(
            r"(?:Description|About)\s+([A-Z][A-Za-z0-9&.'\u2019+ -]{1,80}?)\s+"
            r"(?:is|are)\s+(?:seeking|looking|hiring)",
            page,
        )
    if company_match:
        company = company_match.group(1).strip()
    else:
        _, company = _title_and_company(candidate.title, candidate.source)
    shown = title[:240] if title else None
    return shown or None, company[:180]


def _clean_posting_title(title: str) -> str:
    """Drop a markdown section label glued onto the heading."""
    if "##" in title:
        title = title.split("##", 1)[0]
    return title.strip().strip("*").strip()[:240]


def _is_generic_employer(name: str) -> bool:
    """A careers-host label such as Jobs is not the hiring company."""
    return _normalize_key_part(name) in _CAREER_HOST_LABELS


def _safe_logo_url(value: str) -> str | None:
    """Accept only public HTTPS image URLs before a mobile client fetches them."""
    url = html.unescape(value.strip())
    parsed = urlsplit(url)
    host = (parsed.hostname or "").casefold()
    if parsed.scheme != "https" or not host or host == "localhost" or host.endswith(".local"):
        return None
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if not address.is_global:
            return None
    return url[:2000]


def _extract_company_logo_url(candidate: _Candidate, company: str) -> str | None:
    """Find an image explicitly labelled with the hiring company.

    The image may be hosted by an ATS CDN, but its alt text must name the
    employer. This deliberately rejects a board's own logo and never guesses a
    logo from the posting hostname.
    """
    page = candidate.page_text or ""
    company_key = _normalize_key_part(_COMPANY_SUFFIXES.sub("", company))
    if not company_key or company == "Unknown employer":
        return None

    images: list[tuple[str, str]] = []
    images.extend(
        (alt, url)
        for alt, url in re.findall(
            r"!\[([^\]]*)\]\((https://[^\s)]+)",
            page,
            flags=re.IGNORECASE,
        )
    )
    images.extend(
        (alt, url)
        for url, alt in re.findall(
            r"<img\b[^>]*\bsrc=[\"'](https://[^\"']+)[\"'][^>]*\balt=[\"']([^\"']*)[\"'][^>]*>",
            page,
            flags=re.IGNORECASE,
        )
    )
    images.extend(
        (alt, url)
        for alt, url in re.findall(
            r"<img\b[^>]*\balt=[\"']([^\"']*)[\"'][^>]*\bsrc=[\"'](https://[^\"']+)[\"'][^>]*>",
            page,
            flags=re.IGNORECASE,
        )
    )
    for alt, raw_url in images:
        alt_key = _normalize_key_part(alt)
        if company_key not in alt_key or _is_board_name(company):
            continue
        logo_url = _safe_logo_url(raw_url)
        if logo_url is not None:
            return logo_url
    return None


_PAY_TEXT = re.compile(
    r"(?P<pay>(?:[$€£]\s*)?\d[\d,.]*(?:\s*[kK])?\s*"
    r"(?:(?:-|\u2013|\u2014|to)\s*(?:[$€£]\s*)?\d[\d,.]*(?:\s*[kK])?)?"
    r"\s*(?:(?:per|/)\s*(?:hour|hr|year|yr|month|annum|week))?)",
    re.IGNORECASE,
)
# "132,000 USD - 170,000 USD" names the currency in words, with no $ sign.
_NAMED_CURRENCY_PAY = re.compile(
    r"(?P<pay>\d{1,3}(?:,\d{3})+(?:\.\d+)?(?:\s*[kK])?\s*(?:USD|EUR|GBP)"
    r"(?:\s*(?:-|\u2013|\u2014|to)\s*"
    r"\d{1,3}(?:,\d{3})+(?:\.\d+)?(?:\s*[kK])?\s*(?:USD|EUR|GBP))?)",
    re.IGNORECASE,
)
_PLACE_LINE = re.compile(
    r"\b(?P<mode>Remote|Hybrid|On-?site)\s*,\s*"
    r"(?P<place>[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,1}(?:,\s*[A-Z]{2})?)\b"
)
_ATS_PLACE_MODE = re.compile(
    r"\b(?P<mode>remote|hybrid|on[ -]?site)\s+work\s+(?:full|part)[ -]?time\b",
    re.IGNORECASE,
)
_ROLE_SUMMARY = re.compile(
    r"\*{0,2}About this role\*{0,2}\s*:\s*\**\s*(?P<body>.+?)"
    r"(?=\s+\*{0,2}What you will|\s+##\s|$)",
    re.IGNORECASE,
)
_EXPERIENCE_TEXT = re.compile(
    r"\b(?P<years>\d+(?:\.\d+)?\+?(?:\s*(?:-|to)\s*\d+(?:\.\d+)?\+?)?\s+"
    r"years?(?:\s+of\s+(?:relevant\s+)?experience)?)\b",
    re.IGNORECASE,
)


_SALARY_CONTEXT = re.compile(
    r"\b(?:salary|compensation|wage|base pay|pay range)\b",
    re.IGNORECASE,
)
_PAY_RANGE = re.compile(r"(?:-|\u2013|\u2014|\bto\b)", re.IGNORECASE)


def _currency_salary(text: str) -> str | None:
    """A ``$`` amount or a pay cadence. A bare number is not pay."""
    for match in _PAY_TEXT.finditer(text):
        value = " ".join(match.group("pay").split()).strip(" ,.;:()")
        has_currency_or_cadence = re.search(
            r"[$€£]|\b(?:per|/)\s*(?:hour|hr|year|yr|month|annum|week)\b",
            value,
            re.IGNORECASE,
        )
        if has_currency_or_cadence:
            return value[:160]
    return None


def _named_salary(text: str) -> str | None:
    """A named-currency amount that is the salary, not a bonus or benefit.

    ``132,000 USD - 170,000 USD`` is a range. ``10,000 USD`` does not replace
    a ``$120,000`` salary, and it counts only when the nearby words call it pay.
    """
    for match in _NAMED_CURRENCY_PAY.finditer(text):
        pay = match.group("pay")
        if _PAY_RANGE.search(pay):
            return " ".join(pay.split())[:160]
    if _currency_salary(text) is not None:
        return None
    for match in _NAMED_CURRENCY_PAY.finditer(text):
        pay = match.group("pay")
        window = text[max(0, match.start() - 40) : match.end() + 20]
        if _SALARY_CONTEXT.search(window):
            return " ".join(pay.split())[:160]
    return None


def _extract_salary(candidate: _Candidate) -> str | None:
    text = f"{candidate.title} {candidate.snippet} {candidate.page_text or ''}"
    # A named base range ("132,000 USD - 170,000 USD") is the salary. A later
    # "$7,200" 401k match, or a bare "10,000 USD" bonus, must not win instead.
    named = _named_salary(text)
    if named is not None:
        return named
    return _currency_salary(text)


def _extract_experience(candidate: _Candidate) -> str | None:
    text = f"{candidate.title} {candidate.snippet} {candidate.page_text or ''}"
    years = _EXPERIENCE_TEXT.search(text)
    if years:
        return " ".join(years.group("years").split())[:120]
    if _JUNIOR_TERMS.search(text):
        return "Entry level"
    if _EXPLICIT_SENIOR_LEVEL.search(text):
        return "Senior level"
    return None


def _normalize_place_mode(raw: str) -> str:
    value = re.sub(r"[\s-]+", "", raw.casefold())
    if value == "onsite":
        return "onsite"
    return value


def _explicit_place_mode(text: str) -> str | None:
    """Work mode from the posting's place line, not a later culture sentence.

    ``Remote, New York`` and ``Remote Work Full time`` are the job site.
    ``hybrid work environment`` is how the office flexes, and it does not win.
    """
    ats = _ATS_PLACE_MODE.search(text)
    if ats is not None:
        return _normalize_place_mode(ats.group("mode"))
    place = _PLACE_LINE.search(text)
    if place is not None:
        return _normalize_place_mode(place.group("mode"))
    return None


def _extract_work_mode(candidate: _Candidate) -> str | None:
    # When the page was fetched, the search snippet is a random passage and
    # must not outrank the place line. "In our hybrid work environment" in the
    # snippet was marking a Remote, New York role as hybrid.
    page = " ".join((candidate.page_text or "").split())
    scoped = page or f"{candidate.title} {candidate.snippet}"
    explicit = _explicit_place_mode(scoped)
    if explicit is not None:
        return explicit
    text = scoped[:1200].casefold()
    matches: list[tuple[int, str]] = []
    for mode, pattern in (
        ("remote", r"\b(remote|telecommut(?:e|ing)|work from home)\b"),
        ("hybrid", r"\bhybrid\b"),
        ("onsite", r"\b(on[ -]?site|in[ -]?person)\b"),
    ):
        match = re.search(pattern, text)
        if match is not None:
            matches.append((match.start(), mode))
    return min(matches)[1] if matches else None


def _extract_location(candidate: _Candidate) -> str | None:
    """Extract the posting's place line without guessing from profile data."""
    page = " ".join((candidate.page_text or "").split())
    match = re.search(
        r"(?:Remote Work|Hybrid|On[ -]?site)\s+"
        r"(?:Full[ -]?time|Part[ -]?time|Contract|Temporary)\s+"
        r"(?P<location>.{2,120}?)(?=\s+\[Overview\]|\s+Overview\b|\s+##)",
        page,
        re.IGNORECASE,
    )
    if match is not None:
        location = " ".join(match.group("location").strip(" ,.;:-").split())
        return location[:180] or None
    place = _PLACE_LINE.search(page)
    if place is None:
        return None
    location = f"{place.group('mode')}, {place.group('place')}"
    return " ".join(location.split())[:180] or None


def _extract_role_summary(candidate: _Candidate) -> str | None:
    """First sentences of "About this role", not a later culture snippet."""
    page = " ".join((candidate.page_text or "").split())
    match = _ROLE_SUMMARY.search(page)
    if match is None:
        return None
    body = " ".join(match.group("body").strip().split())
    sentences = re.split(r"(?<=[.!?])\s+", body)
    text = " ".join(sentence for sentence in sentences[:2] if sentence).strip()
    if len(text) < 40:
        return None
    if len(text) > 320:
        text = text[:317].rstrip() + "…"
    return text


def _fallback_required_skills(
    profile: _ProfileSnapshot,
    candidate: _Candidate,
) -> list[str]:
    """Conservative fallback when structured ranking is unavailable.

    A profile skill is shown only when the posting itself names it, so these
    chips remain posting requirements rather than unsupported guesses.
    """
    text = f"{candidate.snippet} {candidate.page_text or ''}".casefold()
    known = list(profile.skills)
    if profile.resume_profile is not None:
        known.extend(profile.resume_profile.skills)
    result: list[str] = []
    seen: set[str] = set()
    for skill in known:
        key = skill.casefold()
        if key in text and key not in seen:
            seen.add(key)
            result.append(skill)
        if len(result) == 8:
            break

    page = " ".join((candidate.page_text or "").split())
    section = re.search(
        r"(?:\*\*)?(?:skills? and qualifications|qualifications|requirements|"
        r"what you(?:'|\u2019)ll need)\s*(?:\*\*)?\s*:?\s*(?:\*\*)?\s*"
        r"(?P<body>.+?)(?=(?:\*\*|##)\s*(?:benefits|about|apply|what we offer)\b|$)",
        page,
        re.IGNORECASE,
    )
    if section is not None:
        non_skill_labels = {
            "benefits",
            "compensation",
            "location",
            "remote work",
            "salary",
            "work environment",
            "work schedule",
        }
        for raw in re.findall(r"\*\s+([^:*]{2,60})\s*:", section.group("body")):
            skill = " ".join(raw.strip(" -*").split())
            key = skill.casefold()
            if 1 <= len(skill.split()) <= 6 and key not in seen and key not in non_skill_labels:
                seen.add(key)
                result.append(skill[:80])
            if len(result) == 8:
                break
    return result
