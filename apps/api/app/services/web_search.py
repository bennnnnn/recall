"""Detect when a chat turn needs live web results and inject them into the prompt."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta

from app.core.config import Settings
from app.gateways import web_search_gateway
from app.gateways.web_search_gateway import WebSearchHit
from app.services import calendar as calendar_service
from app.services import time_context as time_context_service

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

_QUIZ_ANSWER = re.compile(r"^[A-D]\.?$", re.IGNORECASE)


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
    "When search returned no hits, say so in one sentence — do NOT guess why or fill in "
    "from training data. "
    "Do NOT include inline source links or a Sources section — the app renders source cards. "
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


def _world_cup_queries(*, today: str, yesterday: str, yesterday_iso: str, today_iso: str) -> list[str]:
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
    return _TEAM_SCORE.search(cleaned) is not None or _TEAM_POSSESSIVE_SCORE.search(cleaned) is not None


def build_search_queries(
    text: str,
    *,
    user_timezone: str | None = None,
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
            prior_user_messages=None,
        )

    if _CLARIFICATION.search(current) and prior_user_messages:
        return build_search_queries(
            subject,
            user_timezone=user_timezone,
            prior_user_messages=None,
        )

    fallback = cleaned or current
    return [fallback] if fallback else []


def build_search_query(
    text: str,
    *,
    user_timezone: str | None = None,
    prior_user_messages: list[str] | None = None,
) -> str:
    queries = build_search_queries(
        text,
        user_timezone=user_timezone,
        prior_user_messages=prior_user_messages,
    )
    return queries[0] if queries else text.strip()


def format_search_block(hits: list[WebSearchHit], *, team: str | None = None) -> str:
    lines = [
        "Web search results (retrieved just now — USE THESE for your answer):",
    ]
    if team:
        lines.append(
            f"The user asked about **{team}**. Only report scores or tournament status for "
            f"{team} — do not attribute other teams' World Cup results to them."
        )
    for index, hit in enumerate(hits, start=1):
        snippet = hit.snippet.replace("\n", " ").strip()
        lines.append(f"{index}. {hit.title} ({hit.url}) — {snippet}")
    lines.append(
        "Required: answer the user's question using the results above. "
        "If they named a team or country, only use snippets about that entity — never "
        "attribute generic tournament results to them unless they appear in the snippet. "
        "If snippets show they did not qualify for a tournament, say so. "
        "Include concrete scores, teams, and dates when the snippets mention them. "
        "Do NOT say search failed or came up dry. "
        "Do not paste this list or add links — the app shows source cards."
    )
    return "\n".join(lines)


def format_sources_fence(hits: list[WebSearchHit]) -> str:
    if not hits:
        return ""
    return f"\n\n```sources\n{json.dumps(sources_payload(hits), ensure_ascii=False)}\n```"


def sources_payload(hits: list[WebSearchHit]) -> list[dict[str, str]]:
    return [
        {"title": hit.title, "url": hit.url, "snippet": hit.snippet[:280]}
        for hit in hits
    ]


def format_search_empty_block(queries: list[str]) -> str:
    tried = ", ".join(f'"{q}"' for q in queries[:3])
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
        hits = await web_search_gateway.search_web(settings, query, max_results=limit)
        for hit in hits:
            key = hit.url.strip().lower() or hit.title.strip().lower()
            if key in seen_urls:
                continue
            seen_urls.add(key)
            merged.append(hit)
            if len(merged) >= limit:
                return merged, tried

    return merged, tried


async def augment_prompt_messages(
    messages: list[dict[str, str]],
    user_content: str,
    settings: Settings,
    *,
    user_timezone: str | None = None,
    prior_user_messages: list[str] | None = None,
) -> tuple[list[dict[str, str]], list[WebSearchHit]]:
    prior_user = prior_user_messages or _prior_user_messages(messages, user_content)
    if not needs_web_search(user_content, prior_user_messages=prior_user):
        return messages, []

    queries = build_search_queries(
        user_content,
        user_timezone=user_timezone,
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
    block = (
        format_search_block(hits, team=team)
        if hits
        else format_search_empty_block(tried)
    )
    return _inject_before_last_user(messages, block), hits
