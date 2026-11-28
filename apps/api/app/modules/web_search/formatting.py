"""Format search hits for prompts and mobile source cards."""

from __future__ import annotations

import json
import re
from typing import TypedDict

from app.gateways.web_search_gateway import WebSearchHit
from app.modules.web_search.source_dates import (
    local_today,
    mark_dates,
    published_note,
    stale_note,
)
from app.modules.web_search.source_tables import flowed_snippet
from app.services.md_fence_scan import (
    iter_fences,
    strip_closed_fences,
)

WEB_SEARCH_HINT = (
    "Live web search results come as a **Web search results** block just before the "
    "user's latest message, or as the web_search tool's result. "
    "When either is present, ground your answer in those results "
    "(scores, dates, headlines, facts). If none of them answers the question, say so "
    'plainly ("I couldn\'t find a source that covers that") instead of stretching an '
    "off-topic result or filling in from memory. "
    "State the retrieved facts themselves: the app shows the sources under the reply, so "
    'never write which outlet said what ("ESPN lists", "according to Reuters", "per '
    'Experian") or "the search results", unless sources disagree. Keep your own '
    "explanation or background apart from what the sources say. "
    "Never say search failed or that you cannot browse when results were provided. "
    "For today/current/latest news, use the current local date in the time context and only "
    "call an event today's when a result explicitly supports that date. Older, future, or "
    "undated snippets are not today's news; say when fewer requested items can be verified. "
    "When the user asks about a specific team or country, only report that entity's results "
    "from the snippets — do NOT attach unrelated tournament results (e.g. World Cup group "
    "stage) to a team unless that team appears in the results. If results show the team "
    "did not qualify or has no match in that tournament, say so clearly. "
    "Do NOT offer fictional results, tournament-schedule guesses, or 'probably Matchday X' "
    "speculation. "
    "Write a link to a page as [Name](https://url), with parentheses around the URL, never "
    "$url$ delimiters, and link only pages from the results. "
    "When search returned no hits, say you could not verify that live right now — "
    "do NOT guess why or fill in from training data. When the block says the search "
    "failed, say the search didn't work just now, not that nothing exists. "
    "Do NOT add a separate Sources section — the app renders source cards. "
    "Never role-play searching. "
    "If neither is in this prompt, do not claim you searched the live web: call the "
    "web_search tool when it is offered, else answer from knowledge or say you don't have "
    "live results. "
    "Recall does search the web when the user asks: never say you can't browse, can't "
    "search or have no internet access. If the user asked for a search and no results "
    "came with this turn, say you couldn't find it this time and ask them to name the "
    "person, place or thing in full, in one short sentence."
)


# Pages saved at different times disagree about what changes: "who is top of the Premier
# League" read TNT's table after 6 games (City first) beside ESPN's after 9 (Arsenal first),
# and the reply named City (2026-11-05). Said with the results, on both search paths. The
# user never sees this list, so "the most recent price in these results" told them nothing.
NEWEST_SOURCE_RULE = (
    "When these pages disagree about something that changes (a table or standings, a "
    "price or rate, a count or toll, the latest version), go by the most recent one, by "
    "its date or by how far along it is; do not blend them or give the older figure. "
    'Name the page\'s source, since this list is never shown ("Coinbase shows …"), never '
    '"these results" or "these pages".'
)


def format_search_block(
    hits: list[WebSearchHit],
    *,
    team: str | None = None,
    user_timezone: str | None = None,
) -> str:
    lines = [
        "Web search results (retrieved just now — ground your answer in these):",
        NEWEST_SOURCE_RULE,
    ]
    if team:
        lines.append(
            f"Report scores or tournament status only for **{team}**, the team asked about: "
            "do not attribute other teams' World Cup results to them."
        )
    # Each dated day says how long ago it was, and a page that calls a time already past
    # still to come says it is a forecast.
    today = local_today(user_timezone)
    for index, hit in enumerate(hits, start=1):
        snippet = flowed_snippet(mark_dates(hit.snippet, today), indent="   ")
        note = published_note(hit.published, today, user_timezone) + stale_note(hit.snippet, today)
        lines.append(f"{index}. {hit.title} ({hit.url}) — {note}{snippet}")
    if team:
        lines.append(
            f"Required: answer using the results above for **{team}** only. "
            "Include concrete scores and dates when snippets mention them. "
            f"If none of them gives {team}'s result, say so; do not guess one. "
            "Do not paste this list — the app shows source cards."
        )
    else:
        lines.append(
            "Required: answer the user's question from the results above, saying which "
            "site a fact comes from. If none of them answers it, say you couldn't find a "
            "source that covers it — do not fill the gap from memory or stretch an unrelated "
            "result. "
            "If they named a team or country, only use snippets about that entity — never "
            "attribute generic tournament results to them unless they appear in the snippet. "
            "If snippets show they did not qualify for a tournament, say so. "
            "Include concrete scores, teams, and dates when the snippets mention them. "
            "Do not paste this list — the app shows source cards."
        )
    return "\n".join(lines)


AMBIGUOUS_NEARBY_HINT = (
    "Before answering a nearby request that leaves its kind open ('nearest house' without "
    "sale vs rent vs a specific address), do NOT web-search or guess listings. Ask 1-3 concise "
    "clarifying questions — e.g. homes for sale near their location, rentals, or nearest to "
    "a specific address. No listings and no listing links until they clarify."
)

# "Can i wolk?" to the nearest Apple Store got "1.5 miles, about 30 minutes" to a store
# across the bay (2026-11-09): the model has no route to measure. Maps does, from the phone.
DIRECTIONS_LINK_RULE = (
    "Asked about getting somewhere (can they walk there, how long to drive, how far, which "
    "train), give a Google Maps directions link, such as [Walking directions to <place>]"
    "(https://www.google.com/maps/dir/?api=1&destination=<the place and its address, "
    "URL-encoded>&travelmode=walking), with travelmode walking, driving, transit or bicycling. "
    "Leave the origin out when they start from where they are: Maps starts from the phone. "
    "Write no travel time and no distance (no minutes, hours, miles or km) unless a search "
    "result in this turn states that number for this route: the link shows the real one, and "
    "a guess is often wrong. Say whether it is walkable only when that is plain (across a bay, "
    "between cities); otherwise let the link answer."
)

GEO_DISTANCE_HINT = (
    f"Distance / travel query: use the user's location and search results. {DIRECTIONS_LINK_RULE}"
)

GEO_ACTIVE_LOCATION_HINT = (
    "Use the location shown above for this nearby or distance question (the phone's, or "
    "the place it last reported when marked so) in your answer — do not "
    "substitute another city from memory or profile. When it is the phone's last report, "
    "say which place the answer is for."
)


_SOURCES_LABEL_RE = re.compile(r"(?:\*\*)?sources(?:\*\*)?\s*:?\s*$", re.IGNORECASE)


def _sanitize_fence_json_text(value: str) -> str:
    """Backticks inside a fenced JSON body would terminate the fence on reload."""
    return value.replace("```", "'''").replace("`", "'")


def _parse_sources_json(raw: str) -> list[dict[str, str]]:
    # A closer the model left glued to the JSON.
    text = raw.strip().rstrip("`").strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    rows: list[dict[str, str]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        if not title and not url:
            continue
        row = {"title": title or url, "url": url}
        snippet = str(item.get("snippet") or "").strip()
        if snippet:
            row["snippet"] = snippet
        rows.append(row)
    return rows


def _strip_bare_source_array_fences(text: str) -> str:
    """Drop unlabeled ``` fences whose body is a sources JSON array."""
    pieces: list[str] = []
    index = 0
    for fence in iter_fences(text):
        body = text[fence.body_start : fence.body_end]
        if fence.closed and not fence.opener.info and _parse_sources_json(body):
            pieces.append(text[index : fence.start])
            index = fence.end
    pieces.append(text[index:])
    return "".join(pieces)


def strip_sources_from_text(text: str) -> str:
    """Remove ```sources fences and unlabeled source-JSON fences from assistant text."""
    cleaned = strip_closed_fences(text, "sources")
    cleaned = _strip_bare_source_array_fences(cleaned)
    cleaned = _SOURCES_LABEL_RE.sub("", cleaned).rstrip()
    return cleaned.rstrip()


def format_sources_fence(hits: list[WebSearchHit]) -> str:
    if not hits:
        return ""
    return f"\n\n```sources\n{json.dumps(sources_payload(hits), ensure_ascii=False)}\n```"


class SearchSource(TypedDict):
    """One source chip under a searched reply."""

    title: str
    url: str
    snippet: str


def sources_payload(hits: list[WebSearchHit]) -> list[SearchSource]:
    rows: list[SearchSource] = []
    for hit in hits:
        snippet = _sanitize_fence_json_text(hit.snippet[:280])
        rows.append({"title": hit.title, "url": hit.url, "snippet": snippet})
    return rows


def format_search_empty_block(queries: list[str], *, failed: bool = False) -> str:
    """The block for a search that came back with nothing, or that failed (``failed``)."""
    tried = ", ".join(f'"{q}"' for q in queries[:3])
    if failed:
        return (
            f"Web search was attempted ({tried}) but the search service failed, so "
            "nothing was retrieved.\n"
            "Tell the user in one sentence that the search didn't work just now and to try "
            "again shortly. Do not say nothing exists, and do not present an answer from "
            "memory as checked or current."
        )
    return (
        f"Web search was run ({tried}) but returned no usable results.\n"
        "Reply in one sentence that you could not verify that live right now. "
        "Do NOT invent tournament schedules, Matchday guesses, off-season explanations, "
        "or scores from memory. Do not fill in from training data."
    )
