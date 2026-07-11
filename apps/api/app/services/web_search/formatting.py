"""Format search hits for prompts and mobile source cards."""

from __future__ import annotations

import json
import re

from app.gateways.web_search_gateway import WebSearchHit
from app.services.web_search.patterns import (
    _ADDRESS_RE,
    _NUMBERED_VENUE_LINE,
    _PRICE_RE,
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
    "Never role-play searching. "
    "If no **Web search results** block is in this prompt, do not claim you searched the "
    "live web — answer from knowledge or say you don't have live results."
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


_SOURCES_FENCE_RE = re.compile(r"```sources\s*\n([\s\S]*?)```", re.IGNORECASE)
_BARE_SOURCES_FENCE_RE = re.compile(r"```\s*\n(\[[\s\S]*?\])\s*```")
_SOURCES_LABEL_RE = re.compile(r"(?:\*\*)?sources(?:\*\*)?\s*:?\s*$", re.IGNORECASE)


def _parse_sources_json(raw: str) -> list[dict[str, str]]:
    text = raw.strip()
    text = re.sub(r"\s*```+\s*$", "", text).strip()
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


def _find_trailing_sources_json(text: str) -> tuple[list[dict[str, str]], int] | None:
    trimmed = text.rstrip()
    index = trimmed.rfind("[")
    while index >= 0:
        candidate = trimmed[index:]
        rows = _parse_sources_json(candidate)
        if rows:
            return rows, index
        index = trimmed.rfind("[", 0, index)
    return None


def strip_sources_from_text(text: str) -> str:
    """Remove ```sources fences and trailing LLM-emitted source JSON from assistant text."""

    def _drop_bare(match: re.Match[str]) -> str:
        return "" if _parse_sources_json(match.group(1)) else match.group(0)

    cleaned = _SOURCES_FENCE_RE.sub("", text)
    cleaned = _BARE_SOURCES_FENCE_RE.sub(_drop_bare, cleaned)
    trailing = _find_trailing_sources_json(cleaned)
    if trailing:
        cleaned = cleaned[: trailing[1]].rstrip()
    cleaned = _SOURCES_LABEL_RE.sub("", cleaned).rstrip()
    return cleaned.rstrip()


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
