"""Detect when a chat turn needs live web results and inject them into the prompt."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import asdict
from datetime import datetime, timedelta

from app.core.config import Settings
from app.core.redis import get_redis_client
from app.gateways import web_search_gateway
from app.gateways.web_search_gateway import WebSearchHit
from app.services import calendar as calendar_service
from app.services import time_context as time_context_service
from app.services.prompt_safety import wrap_untrusted

logger = logging.getLogger(__name__)

_EXPLICIT_SEARCH = re.compile(
    r"\b("
    r"search(?:\s+the)?\s+web"
    r"|look(?:\s+it|\s+that)?\s+up(?:\s+online)?"
    r"|google(?:\s+for|\s+this|\s+it)?"
    r"|web\s+search"
    r"|find(?:\s+me)?\s+(?:online|on\s+the\s+internet)"
    r")\b",
    re.IGNORECASE,
)

_LOOK_IT_UP = re.compile(
    r"^\s*(?:please\s+)?(?:look(?:\s+it|\s+that)\s+up|search(?:\s+for)?(?:\s+it)?)\s*[.!?]*\s*$",
    re.IGNORECASE,
)

_CLARIFICATION = re.compile(
    r"^\s*(?:"
    r"no[,!.]?\s+(?:i\s+meant|the|not)|"
    r"(?:i\s+meant|not that|the ongoing|the current|that one|this one)|"
    r"yes[,!.]?\s+(?:that|the)\b"
    r")",
    re.IGNORECASE,
)

_ONGOING = re.compile(
    r"\b(ongoing|current(?:ly)?|right now|happening now|this one|that one)\b",
    re.IGNORECASE,
)

_WORLD_CUP = re.compile(r"\b(world\s+cup|fifa|wc\s*2026|2026\s+world\s+cup)\b", re.IGNORECASE)

_SHORT_FOLLOWUP_WORDS = 12

_RECENCY = re.compile(
    r"\b("
    r"latest|breaking|today(?:'s)?|current(?:ly)?|recent(?:ly)?|right\s+now"
    r"|this\s+week|this\s+month|as\s+of|news|headline"
    r"|stock\s+price|share\s+price|market\s+cap"
    r"|who\s+won|what\s+happened|score(?:s)?"
    r"|release\s+date|when\s+did\s+.+\s+(?:happen|release|launch)"
    r"|is\s+.+\s+(?:still|currently)\s+alive"
    r")\b",
    re.IGNORECASE,
)

_NEWS = re.compile(
    r"\b("
    r"what(?:'s| is) (?:happening|going on|new|in the news)"
    r"|top (?:news|stories|headlines)"
    r"|news (?:today|this week|stories)"
    r"|in the world(?: today)?"
    r"|world news|current events"
    r"|what(?:'s| is) cookin(?:'|g)?(?: in the world)?"
    r")\b",
    re.IGNORECASE,
)

_SPORTS = re.compile(
    r"\b("
    r"game|games|match|matches|score|scores|result|results|fixture|standings|highlights|"
    r"soccer|football|nba|nfl|mlb|nhl|premier league|world cup|mls|uefa|champions league"
    r")\b",
    re.IGNORECASE,
)

_YESTERDAY = re.compile(r"\byesterday(?:'?s)?\b", re.IGNORECASE)

_SPORTS_LOOKUP = re.compile(
    r"\b("
    r"yesterday(?:'?s)?\s+(?:games?|match(?:es)?|result|score|scores)"
    r"|(?:games?|match(?:es)?|score|scores|results?)\s+(?:from\s+)?yesterday"
    r"|show me (?:the\s+)?yesterday(?:'?s)?\s+(?:games?|match(?:es)?|result|score|scores)"
    r"|show me (?:the\s+)?(?:games?|match(?:es)?|score|scores|results?)"
    r"|who won (?:the\s+)?(?:games?|match(?:es)?|yesterday|last night)"
    r"|last night(?:'s)?\s+(?:games?|match(?:es)?|score|scores)"
    r")\b",
    re.IGNORECASE,
)

_TEAM_SCORE = re.compile(
    r".{2,60}\b(?:games?|match(?:es)?)\s+score",
    re.IGNORECASE,
)

_TEAM_POSSESSIVE_SCORE = re.compile(
    r".{2,40}(?:'s|s)\s+(?:games?|match(?:es)?|score|scores|result|results)",
    re.IGNORECASE,
)

_SKIP = re.compile(
    r"\b("
    r"rewrite|proofread|debug|refactor|explain\s+this\s+code"
    r"|help\s+me\s+write|draft\s+(?:an?\s+)?(?:email|message|reply)"
    r"|remember\s+that|add\s+to\s+(?:my\s+)?(?:todo|list|memory)"
    r"|translate|summarize\s+this\s+(?:text|email|article)"
    r"|vocabulary\s+quiz|interactive\s+vocabulary|quiz\s+me\s+in\s+chat"
    r"|quick\s+quiz|begin\s+with\s+the\s+first\s+question"
    r")\b",
    re.IGNORECASE,
)

_PERSONAL_PLANNING = re.compile(
    r"\b("
    r"what\s+(?:am\s+I|are\s+we|do\s+I|should\s+I)\s+(?:trying\s+to\s+)?(?:get|have)\s+(?:done|to\s+do)"
    r"|what(?:'s| is)\s+(?:on\s+my\s+(?:plate|list|agenda)|due|still\s+open)"
    r"|what\s+(?:do\s+I|should\s+I)\s+need\s+to\s+(?:do|finish|tackle)"
    r"|(?:my|any)\s+(?:tasks?|todos?|reminders?)\s+(?:for\s+)?(?:today|tonight|this\s+week)"
    r"|how(?:'s| is)\s+my\s+day\s+looking"
    r"|how\s+did\s+my\s+day\s+go"
    r"|help\s+me\s+(?:prioriti[sz]e|plan|wrap\s+up)"
    r"|(?:show|list)\s+(?:me\s+)?(?:my\s+)?(?:tasks?|todos?|reminders?)"
    r"|what\s+(?:should\s+I|can\s+I)\s+(?:tackle|focus\s+on|work\s+on)\s+(?:today|tonight|now)?"
    r"|anything\s+(?:left|open|due)\s+(?:for\s+)?(?:me\s+)?(?:today|tonight)"
    r"|wrap\s+up\s+(?:loose\s+ends|my\s+day)"
    r"|wind\s+down"
    r")\b",
    re.IGNORECASE,
)

# Proximity intent — any "near me / nearest / closest …" ask, not a venue-type list.
_NEARBY_INTENT = re.compile(
    r"\b("
    r"near\s+me|nearby|around\s+here|in\s+(?:this\s+)?town"
    r"|close\s+(?:by|to\s+me)"
    r"|(?:the\s+)?(?:nearest|closest)\b"
    r")\b",
    re.IGNORECASE,
)

# "Nearest" used for abstract/math/social things — not a maps search.
_NON_GEOGRAPHIC_NEAREST = re.compile(
    r"\b(?:nearest|closest)\b.+\b("
    r"number|numbers|integer|prime|multiple|"
    r"match|deadline|"
    r"star|planet|galaxy|sun|moon|"
    r"approach|analogy|synonym|equivalent|"
    r"friend|relative|cousin|neighbor|neighbour|"
    r"guess|approximation|solution|competitor|rival"
    r")\b",
    re.IGNORECASE,
)

_BEST_NEAR = re.compile(
    r"\bbest\b.+\b(?:in|near|around|by)\b",
    re.IGNORECASE,
)

# Implicit nearby intent without saying "near me" (e.g. "where should I eat tonight?").
_IMPLICIT_LOCAL = re.compile(
    r"\b(?:"
    r"where\s+(?:should|can|do)\s+(?:I|we)\s+(?:eat|get|find|go|stay|park)"
    r"|where\s+to\s+(?:eat|go|get|stay|park)"
    r"|what(?:'s| is)\s+(?:good|open)\s+(?:around|near|nearby)"
    r")\b",
    re.IGNORECASE,
)

# Real-estate asks that need sale/rent/address clarified — not generic "places near me".
_AMBIGUOUS_NEARBY_SUBJECT = re.compile(
    r"\b(?:"
    r"house|houses|home|homes|property|properties|building|buildings"
    r"|apartment|apartments|condo|condos|flat|flats|unit|units"
    r")\b",
    re.IGNORECASE,
)

_QUALIFIED_NEARBY = re.compile(
    r"\b(?:"
    r"for\s+sale|to\s+(?:buy|rent|lease)|for\s+rent|rentals?|buying|leasing"
    r"|open\s+(?:now|today)|24\s*hours?"
    r"|near\s+\d|at\s+\d|from\s+\d|\d+\s+\w+\s+(?:st|street|ave|avenue|rd|road|blvd|dr|drive|way|ln|lane)\b"
    r")\b",
    re.IGNORECASE,
)

_PROXIMITY_PHRASES = (
    r"\bnear\s+me\b",
    r"\bnearby\b",
    r"\baround\s+here\b",
    r"\bin(?:\s+this)?\s+town\b",
    r"\bclose\s+(?:by|to\s+me)\b",
    r"\b(?:the\s+)?(?:nearest|closest)\b",
    r"\bbest\b",
)

_QUIZ_ANSWER = re.compile(r"^[A-D]\.?$", re.IGNORECASE)

# Distance / travel from the user's location — venue-agnostic.
_DISTANCE_INTENT = re.compile(
    r"\b("
    r"how\s+far"
    r"|how\s+many\s+(?:miles|kilometers|kilometres|km|minutes|mins)"
    r"|(?:walking|driving|drive|travel|commute)\s+(?:distance|time)"
    r"|distance\s+(?:to|from)"
    r"|how\s+long\s+(?:to\s+get|does\s+it\s+take|is\s+the\s+(?:drive|trip|walk))"
    r"|(?:miles|km|kilometers?|kilometres?|minutes?)\s+(?:away|from\s+(?:me|here))"
    r"|directions?\s+to"
    r")\b",
    re.IGNORECASE,
)

_FROM_USER = re.compile(
    r"\b(?:from\s+(?:me|here|my\s+(?:location|place))|to\s+me|where\s+i\s+am)\b",
    re.IGNORECASE,
)

_DISTANCE_BETWEEN = re.compile(r"\bdistance\b.+\bbetween\b", re.IGNORECASE)


def _subject_without_proximity(cleaned: str) -> str:
    subject = cleaned.strip()
    for pattern in _PROXIMITY_PHRASES:
        subject = re.sub(pattern, " ", subject, flags=re.IGNORECASE)
    return " ".join(subject.split()).strip(" ?.!")


def is_proximity_query(text: str) -> bool:
    """Find something near the user — any category (restaurant, hospital, casino, …)."""
    cleaned = text.strip()
    if not cleaned:
        return False
    if _NON_GEOGRAPHIC_NEAREST.search(cleaned):
        return False
    if _NEARBY_INTENT.search(cleaned):
        return True
    if _IMPLICIT_LOCAL.search(cleaned):
        return True
    return bool(_BEST_NEAR.search(cleaned) and "?" in cleaned)


def is_distance_query(text: str) -> bool:
    """Distance, travel time, or directions from the user's location."""
    cleaned = text.strip()
    if not cleaned or not _DISTANCE_INTENT.search(cleaned):
        return False
    if _DISTANCE_BETWEEN.search(cleaned) and not _FROM_USER.search(cleaned):
        return False
    return True


def is_geo_query(text: str) -> bool:
    """Any query that needs the user's location — places OR distance. Venue-agnostic."""
    return is_proximity_query(text) or is_distance_query(text)


def is_places_list_query(text: str) -> bool:
    """Render the native ```places card (find venues, not mileage-only answers)."""
    if is_ambiguous_local_places_query(text):
        return False
    return is_proximity_query(text)


def is_local_places_query(text: str) -> bool:
    """Backward-compatible alias — prefer is_geo_query / is_places_list_query."""
    return is_proximity_query(text)


def is_ambiguous_local_places_query(text: str) -> bool:
    """Nearby intent but missing sale/rent/address/etc. — ask before web search."""
    cleaned = text.strip()
    if not is_proximity_query(cleaned):
        return False
    if _QUALIFIED_NEARBY.search(cleaned):
        return False
    subject = _subject_without_proximity(cleaned)
    if not subject:
        return False
    return _AMBIGUOUS_NEARBY_SUBJECT.search(subject) is not None


def is_vocab_quiz_answer(text: str) -> bool:
    """Single-letter multiple-choice reply (A–D) in an in-chat vocabulary quiz."""
    return bool(_QUIZ_ANSWER.match(text.strip()))


_QUERY_PREFIX = re.compile(
    r"^\s*(?:"
    r"(?:can\s+you\s+)?(?:please\s+)?"
    r"(?:search(?:\s+the)?\s+web(?:\s+for)?|"
    r"look\s+up(?:\s+online)?(?:\s+for)?|"
    r"google(?:\s+for)?|"
    r"find(?:\s+online)?(?:\s+for)?)"
    r")\s*",
    re.IGNORECASE,
)

_STREET_SUFFIX = (
    r"(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|Way|Pl|Place|"
    r"Ct|Court|Sq|Square|Pkwy|Parkway)"
)
_ADDRESS_RE = re.compile(
    rf"\b(\d+\s+[\w\s.'#-]{{2,40}}{_STREET_SUFFIX}\b(?:,\s*[\w\s.'-]{{2,30}})?)",
    re.IGNORECASE,
)
_PRICE_RE = re.compile(r"(?<![\w$])(\$\$\$|\$\$|\$)(?![\w$])")

_GENERIC_NEWS_QUERY = re.compile(
    r"^(?:"
    r"what(?:'s| is) (?:happening|going on|new)(?: in the world(?: today)?| in the news)?"
    r"|top (?:news|stories|headlines)"
    r"|news (?:today|this week|stories)"
    r"|(?:what(?:'s| is) )?(?:cookin(?:'|g)?(?: in the world)?|in the world(?: today)?)"
    r"|world news|current events"
    r")\s*[.!?]*$",
    re.IGNORECASE,
)


def _extract_address_from_snippet(snippet: str) -> str | None:
    match = _ADDRESS_RE.search(snippet)
    if not match:
        return None
    return match.group(1).strip(" ,.")


def _extract_price_from_snippet(snippet: str) -> str | None:
    match = _PRICE_RE.search(snippet)
    return match.group(1) if match else None


WEB_SEARCH_HINT = (
    "Live web search may be injected immediately before the user's latest message. "
    "When a **Web search results** block is present, you MUST answer from those results "
    "(scores, dates, headlines, facts). Never say search failed, came up dry, or that you "
    "cannot browse when results were provided. "
    "When the user asks about a specific team or country, only report that entity's results "
    "from the snippets — do NOT attach unrelated tournament results (e.g. World Cup group "
    "stage) to a team unless that team appears in the results. If results show the team "
    "did not qualify or has no match in that tournament, say so clearly. "
    "Do NOT offer fictional results, tournament-schedule guesses, or 'probably Matchday X' "
    "speculation. "
    "When the user asks for anything nearby or at a distance (venues, directions, "
    "how far, travel time), give a one-sentence intro then a ```places fence with JSON "
    "when listing findable places (see format hint). For mileage-only answers, state "
    "distance and time in prose — no ```places fence. "
    "The app renders places blocks natively — do NOT also hand-format a markdown list. "
    "If you must use markdown links instead, use [Name](https://url) with parentheses "
    "around the URL — never $url$ delimiters."
    "When search returned no hits, say so in one sentence — do NOT guess why or fill in "
    "from training data. "
    "Do NOT add a separate Sources section — the app renders source cards. "
    "Never role-play searching."
)


def _prior_user_messages(
    prompt_messages: list[dict[str, str]],
    current: str,
) -> list[str]:
    user_msgs = [str(m.get("content") or "") for m in prompt_messages if m.get("role") == "user"]
    if user_msgs and user_msgs[-1].strip() == current.strip():
        user_msgs = user_msgs[:-1]
    return [msg for msg in user_msgs if msg.strip()]


def _topic_needs_search(text: str) -> bool:
    return needs_web_search(text, prior_user_messages=None)


def _prior_searchable_topic(prior_user_messages: list[str] | None) -> str | None:
    if not prior_user_messages:
        return None
    for msg in reversed(prior_user_messages):
        cleaned = msg.strip()
        if not cleaned or _LOOK_IT_UP.match(cleaned):
            continue
        if (
            _topic_needs_search(cleaned)
            or _SPORTS.search(cleaned)
            or _WORLD_CUP.search(cleaned)
            or _NEWS.search(cleaned)
        ):
            return cleaned
    return None


def resolve_search_subject(
    user_content: str,
    *,
    prior_user_messages: list[str] | None = None,
) -> str:
    cleaned = user_content.strip()
    if _LOOK_IT_UP.match(cleaned) and prior_user_messages:
        for msg in reversed(prior_user_messages):
            if msg.strip() and not _LOOK_IT_UP.match(msg.strip()):
                return msg.strip()
    if prior_user_messages and (
        len(cleaned.split()) <= _SHORT_FOLLOWUP_WORDS or _CLARIFICATION.search(cleaned)
    ):
        prior_topic = _prior_searchable_topic(prior_user_messages)
        if prior_topic:
            return prior_topic
    return cleaned


def needs_web_search(
    text: str,
    *,
    prior_user_messages: list[str] | None = None,
) -> bool:
    cleaned = text.strip()
    if not cleaned or len(cleaned) < 4:
        return False
    if _QUIZ_ANSWER.match(cleaned):
        return False
    if time_context_service.is_time_question(cleaned):
        return False
    if time_context_service.is_location_question(cleaned):
        return False
    if _SKIP.search(cleaned):
        return False
    if _PERSONAL_PLANNING.search(cleaned):
        return False
    if calendar_service.is_external_calendar_question(cleaned):
        return False
    if _LOOK_IT_UP.match(cleaned):
        return bool(prior_user_messages)
    if _CLARIFICATION.search(cleaned) and prior_user_messages:
        return _prior_searchable_topic(prior_user_messages) is not None
    if _EXPLICIT_SEARCH.search(cleaned):
        return True
    if _NEWS.search(cleaned):
        return True
    if _SPORTS_LOOKUP.search(cleaned):
        return True
    if _TEAM_SCORE.search(cleaned) or _TEAM_POSSESSIVE_SCORE.search(cleaned):
        return True
    if _YESTERDAY.search(cleaned) and _SPORTS.search(cleaned):
        return True
    if _WORLD_CUP.search(cleaned) and (_ONGOING.search(cleaned) or _SPORTS.search(cleaned)):
        return True
    if prior_user_messages and len(cleaned.split()) <= _SHORT_FOLLOWUP_WORDS:
        if _prior_searchable_topic(prior_user_messages) is not None:
            return True
    subject = resolve_search_subject(cleaned, prior_user_messages=prior_user_messages)
    if _SPORTS_LOOKUP.search(subject):
        return True
    if _YESTERDAY.search(subject) and _SPORTS.search(subject):
        return True
    if _WORLD_CUP.search(subject) and (_ONGOING.search(cleaned) or _SPORTS.search(subject)):
        return True
    if _RECENCY.search(cleaned) and "?" in cleaned:
        return True
    if _RECENCY.search(cleaned) and len(cleaned.split()) >= 6:
        return True
    if is_geo_query(cleaned):
        return True
    return False


def _yesterday_label(user_timezone: str | None) -> str:
    tz = time_context_service.resolve_timezone(user_timezone)
    yesterday = datetime.now(tz) - timedelta(days=1)
    return yesterday.strftime("%B %d %Y")


def _yesterday_iso(user_timezone: str | None) -> str:
    tz = time_context_service.resolve_timezone(user_timezone)
    yesterday = datetime.now(tz) - timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d")


def _today_label(user_timezone: str | None) -> str:
    tz = time_context_service.resolve_timezone(user_timezone)
    return datetime.now(tz).strftime("%B %d %Y")


def _today_iso(user_timezone: str | None) -> str:
    tz = time_context_service.resolve_timezone(user_timezone)
    return datetime.now(tz).strftime("%Y-%m-%d")


def _world_cup_queries(
    *, today: str, yesterday: str, yesterday_iso: str, today_iso: str
) -> list[str]:
    return [
        f"FIFA World Cup 2026 live scores results {today}",
        f"FIFA World Cup 2026 match results scores {yesterday}",
        f"World Cup 2026 group stage results {yesterday_iso}",
        f"World Cup 2026 scores {today_iso}",
    ]


def _normalize_team_label(raw: str) -> str:
    label = raw.strip().strip("?.!")
    label = re.sub(r"\s+(?:game|match|scores?|results?|fixture)s?\s*$", "", label, flags=re.I)
    label = re.sub(r"(?:'s|s)$", "", label, flags=re.I)
    return label.strip()


def _extract_team_subject(cleaned: str) -> str | None:
    if not (_TEAM_SCORE.search(cleaned) or _TEAM_POSSESSIVE_SCORE.search(cleaned)):
        return None
    for pattern in (
        r"^(?P<team>.+?)\s+(?:game|match|scores?|results?|fixture)s?\s*[?.!]*$",
        r"^(?P<team>.+?)\s+(?:game|match)\s+score\s*[?.!]*$",
    ):
        match = re.match(pattern, cleaned, flags=re.I)
        if match:
            team = _normalize_team_label(match.group("team"))
            if team and len(team.split()) <= 6:
                return team
    return _normalize_team_label(cleaned) or None


def _team_score_queries(team: str) -> list[str]:
    return [
        f"{team} national team football latest match score result",
        f"{team} football latest match score result",
        f"{team} World Cup 2026 qualified teams list",
    ]


def _hit_mentions_team(hit: WebSearchHit, team: str) -> bool:
    needle = team.strip().lower()
    if not needle:
        return False
    blob = f"{hit.title} {hit.snippet}".lower()
    return needle in blob


def _prioritize_team_hits(hits: list[WebSearchHit], team: str) -> list[WebSearchHit]:
    if not hits or not team.strip():
        return hits
    matched = [hit for hit in hits if _hit_mentions_team(hit, team)]
    if not matched:
        return hits
    rest = [hit for hit in hits if hit not in matched]
    return matched + rest


def _is_team_specific_sports_query(cleaned: str) -> bool:
    if _WORLD_CUP.search(cleaned):
        return False
    return (
        _TEAM_SCORE.search(cleaned) is not None
        or _TEAM_POSSESSIVE_SCORE.search(cleaned) is not None
    )


def _geo_located_queries(
    cleaned: str,
    user_location: str | None,
    *,
    latitude: float | None = None,
    longitude: float | None = None,
) -> list[str]:
    query = _QUERY_PREFIX.sub("", cleaned.strip()).strip(" ?.!")
    loc = (user_location or "").strip()
    coord = (
        f"{latitude:.5f},{longitude:.5f}"
        if latitude is not None and longitude is not None
        else None
    )
    anchor = coord or loc
    if anchor:
        for pattern, repl in (
            (r"\bnear me\b", f"near {anchor}"),
            (r"\bnearby\b", f"near {anchor}"),
            (r"\baround here\b", f"near {anchor}"),
            (r"\bin(?:\s+this)?\s+town\b", f"in {loc or anchor}"),
            (r"\bclose to me\b", f"near {anchor}"),
            (r"\bfrom me\b", f"from {anchor}"),
            (r"\bfrom here\b", f"from {anchor}"),
        ):
            query = re.sub(pattern, repl, query, flags=re.I)
        if anchor.lower() not in query.lower():
            query = f"{query} {anchor}"
        if loc and loc.lower() not in query.lower():
            query = f"{query} {loc}"
    primary = query or cleaned
    return [primary, f"{primary} official website address"]


def build_search_queries(
    text: str,
    *,
    user_timezone: str | None = None,
    user_location: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    prior_user_messages: list[str] | None = None,
) -> list[str]:
    subject = resolve_search_subject(text, prior_user_messages=prior_user_messages)
    query = _QUERY_PREFIX.sub("", subject.strip())
    cleaned = query.strip(" ?.!")
    current = text.strip()
    yesterday = _yesterday_label(user_timezone)
    yesterday_iso = _yesterday_iso(user_timezone)
    today = _today_label(user_timezone)
    today_iso = _today_iso(user_timezone)

    if _GENERIC_NEWS_QUERY.match(cleaned):
        return ["top news today"]

    if _WORLD_CUP.search(current) or (
        _WORLD_CUP.search(subject) and (_ONGOING.search(current) or _CLARIFICATION.search(current))
    ):
        return _world_cup_queries(
            today=today,
            yesterday=yesterday,
            yesterday_iso=yesterday_iso,
            today_iso=today_iso,
        )

    if _YESTERDAY.search(cleaned) and _SPORTS.search(cleaned):
        return _world_cup_queries(
            today=today,
            yesterday=yesterday,
            yesterday_iso=yesterday_iso,
            today_iso=today_iso,
        )

    team = _extract_team_subject(cleaned)
    if team and _is_team_specific_sports_query(cleaned):
        return _team_score_queries(team)

    if _SPORTS.search(cleaned):
        return [
            f"{cleaned} scores results {yesterday}",
            f"{cleaned} latest match result",
        ]

    if _LOOK_IT_UP.match(current) and prior_user_messages:
        return build_search_queries(
            subject,
            user_timezone=user_timezone,
            user_location=user_location,
            prior_user_messages=None,
        )

    if _CLARIFICATION.search(current) and prior_user_messages:
        return build_search_queries(
            subject,
            user_timezone=user_timezone,
            user_location=user_location,
            prior_user_messages=None,
        )

    if is_geo_query(subject) or is_geo_query(current):
        return _geo_located_queries(
            cleaned or current,
            user_location,
            latitude=latitude,
            longitude=longitude,
        )

    fallback = cleaned or current
    return [fallback] if fallback else []


def build_search_query(
    text: str,
    *,
    user_timezone: str | None = None,
    user_location: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    prior_user_messages: list[str] | None = None,
) -> str:
    queries = build_search_queries(
        text,
        user_timezone=user_timezone,
        user_location=user_location,
        latitude=latitude,
        longitude=longitude,
        prior_user_messages=prior_user_messages,
    )
    return queries[0] if queries else text.strip()


def _geo_is_active(*texts: str) -> bool:
    return any(is_geo_query(t.strip()) for t in texts if t and t.strip())


def _places_list_is_active(*texts: str) -> bool:
    return any(is_places_list_query(t.strip()) for t in texts if t and t.strip())


def format_location_not_set_answer() -> str:
    """No user location for a geo query — ask to enable location instead of guessing."""
    return (
        "I don't have your location yet, so I can't answer nearby or distance questions "
        "accurately.\n\n"
        "Turn on **Location** in **Settings** (or allow location when prompted), then ask again."
    )


def format_search_block(
    hits: list[WebSearchHit],
    *,
    team: str | None = None,
    local_places: bool = False,
    user_location: str | None = None,
) -> str:
    lines = [
        "Web search results (retrieved just now — ground your answer in these):",
    ]
    if local_places and not (user_location or "").strip():
        lines.append(
            "User location is not set — nearby results may be less precise. "
            "If they asked for 'near me', briefly suggest Settings → Location."
        )
    if team:
        lines.append(
            f"The user asked about **{team}**. Only report scores or tournament status for "
            f"{team} — do not attribute other teams' World Cup results to them."
        )
    for index, hit in enumerate(hits, start=1):
        snippet = hit.snippet.replace("\n", " ").strip()
        lines.append(f"{index}. {hit.title} ({hit.url}) — {snippet}")
    if local_places:
        seed = places_payload_from_hits(hits)
        seed_block = ""
        if seed:
            seed_block = (
                "\nStarter JSON (refine name/url/note from snippets; include every real venue):\n"
                f"```places\n{json.dumps(seed, ensure_ascii=False)}\n```\n"
            )
        lines.append(
            "Required: one-sentence intro, then a ```places fence with JSON array "
            '[{"name":"Venue","url":"https://www.google.com/maps/search/?api=1&query=...",'
            '"note":"optional","address":"street when known","price":"$$"}]. '
            "url must be a Google Maps link to the venue address — never a generic search page. "
            "Do NOT also output a markdown numbered list of venues."
            f"{seed_block}"
        )
    elif team:
        lines.append(
            f"Required: answer using the results above for **{team}** only. "
            "Include concrete scores and dates when snippets mention them. "
            "Do NOT say search failed. Do not paste this list — the app shows source cards."
        )
    else:
        lines.append(
            "Required: answer the user's question using the results above. "
            "If they named a team or country, only use snippets about that entity — never "
            "attribute generic tournament results to them unless they appear in the snippet. "
            "If snippets show they did not qualify for a tournament, say so. "
            "Include concrete scores, teams, and dates when the snippets mention them. "
            "Do NOT say search failed or came up dry. "
            "Do not paste this list — the app shows source cards."
        )
    return "\n".join(lines)


LOCAL_PLACES_FORMAT_HINT = (
    "Local places output (any nearby venue the user asked for):\n"
    "- One short intro sentence, then ONLY a ```places JSON fence — no duplicate markdown list.\n"
    '- Schema: [{"name":"Venue","url":"https://www.google.com/maps/search/?api=1&query=...",'
    '"note":"rating/cuisine","address":"street, city","price":"$$"}]\n'
    "- url MUST open the venue on Google Maps (use address in the query). "
    "Never use generic Yelp/Google search pages.\n"
    "- address is required when the snippet mentions a street or neighborhood.\n"
    "- price is optional plain text like $, $$, or $$$ — never inside the url field."
)

AMBIGUOUS_NEARBY_HINT = (
    "The user's nearby request is underspecified (e.g. 'nearest house' without sale vs rent "
    "vs a specific address). Do NOT web-search or guess listings yet. Ask 1-3 concise "
    "clarifying questions — e.g. homes for sale near their location, rentals, or nearest to "
    "a specific address. No ```places fence and no listing links until they clarify."
)

GEO_DISTANCE_HINT = (
    "Distance / travel query: use the user's location and search results. Give concrete "
    "miles or km and drive/walk time when available. Do NOT use a ```places fence unless "
    "they also asked to find venues."
)

GEO_ACTIVE_LOCATION_HINT = (
    "The user's current device location for this nearby/distance query is shown above. "
    "Use that location in your answer — do not substitute another city from memory or profile."
)


def _is_generic_search_url(url: str) -> bool:
    lowered = url.strip().lower()
    if not lowered:
        return True
    if "yelp.com/search" in lowered:
        return True
    if "google.com/search" in lowered:
        return True
    if "bing.com/search" in lowered:
        return True
    return False


def _maps_url_for_place(name: str, address: str | None = None) -> str:
    query = name.strip()
    if address and address.strip():
        addr = address.strip()
        if query.lower() not in addr.lower():
            query = f"{query}, {addr}"
        else:
            query = addr
    from urllib.parse import quote

    return f"https://www.google.com/maps/search/?api=1&query={quote(query)}"


def places_payload_from_hits(hits: list[WebSearchHit]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for hit in hits[:8]:
        name = hit.title.strip()
        if not name:
            continue
        url = hit.url.strip()
        snippet = hit.snippet.replace("\n", " ").strip()
        address = _extract_address_from_snippet(snippet)
        price = _extract_price_from_snippet(snippet)
        row: dict[str, str] = {"name": name}
        note = snippet
        if price:
            row["price"] = price
            note = note.replace(price, "").strip(" ,-\u2013\u2014()")
        if address:
            row["address"] = address
        if note:
            row["note"] = note[:160]
        if url and not _is_generic_search_url(url):
            row["url"] = url
        else:
            row["url"] = _maps_url_for_place(name, address or (snippet[:120] if snippet else None))
        rows.append(row)
    return rows


def format_places_fence(hits: list[WebSearchHit]) -> str:
    payload = places_payload_from_hits(hits)
    if not payload:
        return ""
    return f"\n\n```places\n{json.dumps(payload, ensure_ascii=False)}\n```"


_NUMBERED_VENUE_LINE = re.compile(r"^\s*\d+\.\s+")


def strip_duplicate_venue_list(text: str) -> str:
    """Drop model-numbered venue lists when the app renders a ```places block."""
    lines = text.split("\n")
    out: list[str] = []
    index = 0
    while index < len(lines):
        if _NUMBERED_VENUE_LINE.match(lines[index]):
            run_end = index
            count = 0
            while run_end < len(lines):
                line = lines[run_end]
                if _NUMBERED_VENUE_LINE.match(line):
                    count += 1
                    run_end += 1
                elif not line.strip():
                    run_end += 1
                else:
                    break
            if count >= 2:
                index = run_end
                continue
        out.append(lines[index])
        index += 1
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def format_sources_fence(hits: list[WebSearchHit]) -> str:
    if not hits:
        return ""
    return f"\n\n```sources\n{json.dumps(sources_payload(hits), ensure_ascii=False)}\n```"


def sources_payload(hits: list[WebSearchHit]) -> list[dict[str, str]]:
    return [{"title": hit.title, "url": hit.url, "snippet": hit.snippet[:280]} for hit in hits]


def format_search_empty_block(queries: list[str], *, local_places: bool = False) -> str:
    tried = ", ".join(f'"{q}"' for q in queries[:3])
    if local_places:
        return (
            f"Web search was run ({tried}) but returned no usable results.\n"
            "Tell the user live search found nothing useful — one short sentence only. "
            "Do NOT invent restaurant names, addresses, or ratings from memory."
        )
    return (
        f"Web search was run ({tried}) but returned no usable results.\n"
        "Tell the user live search found nothing useful — one short sentence only. "
        "Do NOT invent tournament schedules, Matchday guesses, off-season explanations, "
        "or scores from memory. Ask for a specific league, team, or date to retry."
    )


def _inject_before_last_user(messages: list[dict[str, str]], block: str) -> list[dict[str, str]]:
    augmented = list(messages)
    insert_at = len(augmented)
    for index in range(len(augmented) - 1, -1, -1):
        if augmented[index].get("role") == "user":
            insert_at = index
            break
    augmented.insert(insert_at, {"role": "system", "content": block})
    return augmented


async def _run_search(
    settings: Settings,
    queries: list[str],
) -> tuple[list[WebSearchHit], list[str]]:
    limit = max(1, min(settings.web_search_max_results, 10))
    seen_urls: set[str] = set()
    merged: list[WebSearchHit] = []
    tried: list[str] = []

    for query in queries:
        tried.append(query)
        hits = await _search_with_cache(settings, query, max_results=limit)
        for hit in hits:
            key = hit.url.strip().lower() or hit.title.strip().lower()
            if key in seen_urls:
                continue
            seen_urls.add(key)
            merged.append(hit)
            if len(merged) >= limit:
                return merged, tried

    return merged, tried


def _search_cache_key(query: str) -> str:
    digest = hashlib.sha256(query.strip().lower().encode()).hexdigest()[:32]
    return f"websearch:{digest}"


async def _search_with_cache(
    settings: Settings,
    query: str,
    *,
    max_results: int,
) -> list[WebSearchHit]:
    cleaned = query.strip()
    if not cleaned:
        return []

    cache_key = _search_cache_key(cleaned)
    redis = get_redis_client()
    try:
        cached = await redis.get(cache_key)
        if cached:
            payload = json.loads(cached)
            if isinstance(payload, list):
                return [
                    WebSearchHit(
                        title=str(item.get("title") or ""),
                        url=str(item.get("url") or ""),
                        snippet=str(item.get("snippet") or ""),
                    )
                    for item in payload
                    if isinstance(item, dict)
                ]
    except Exception:
        logger.debug("Web search cache read failed", exc_info=True)

    hits = await web_search_gateway.search_web(settings, cleaned, max_results=max_results)
    if hits:
        try:
            await redis.set(
                cache_key,
                json.dumps([asdict(hit) for hit in hits]),
                ex=max(60, settings.web_search_cache_ttl),
            )
        except Exception:
            logger.debug("Web search cache write failed", exc_info=True)
    return hits


async def augment_prompt_messages(
    messages: list[dict[str, str]],
    user_content: str,
    settings: Settings,
    *,
    user_timezone: str | None = None,
    user_location: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    prior_user_messages: list[str] | None = None,
) -> tuple[list[dict[str, str]], list[WebSearchHit]]:
    prior_user = prior_user_messages or _prior_user_messages(messages, user_content)
    if not needs_web_search(user_content, prior_user_messages=prior_user):
        return messages, []

    subject = resolve_search_subject(user_content, prior_user_messages=prior_user)
    queries = build_search_queries(
        user_content,
        user_timezone=user_timezone,
        user_location=user_location,
        latitude=latitude,
        longitude=longitude,
        prior_user_messages=prior_user,
    )
    hits, tried = await _run_search(settings, queries)
    team = _extract_team_subject(user_content.strip())
    if not team and prior_user:
        for prior in reversed(prior_user):
            team = _extract_team_subject(prior.strip())
            if team:
                break
    hits = _prioritize_team_hits(hits, team) if team else hits
    local_places = _places_list_is_active(user_content, subject)
    geo_query = _geo_is_active(user_content, subject)
    if hits:
        block = format_search_block(
            hits, team=team, local_places=local_places, user_location=user_location
        )
        if geo_query and not local_places:
            block = f"{block}\n\n{GEO_DISTANCE_HINT}"
        block = wrap_untrusted("web search", block)
    else:
        block = format_search_empty_block(tried, local_places=local_places)
    return _inject_before_last_user(messages, block), hits
