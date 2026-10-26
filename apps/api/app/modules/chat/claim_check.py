"""Finalize pass: on a searched turn, a claim the sources never made is cut.

The search hint tells the model to ground its answer in the results, and a model can
still add what no result says. In one study chat (2026-10-26) a reply told a user a
broker "has been reinstated and is fully operational, so you can use them safely" under
five sources that were its own research pages, and a fee table carried a "CSTA levy"
credited to the regulator that no source named.

A cheap model lists the claims the evidence does not support: a figure, a legal or
regulatory status, a named organisation or product said to do something, an attribution
to a source. The evidence is this turn's search results and the user's own messages;
an earlier reply of the assistant is not evidence, it is where an invention starts.
Each listed quote must be in the reply word for word, or it is ignored. The pass then
removes the table row or sentence that holds it, outside fences, and adds one line
saying what was left out. A check that fails, times out or flags most of the reply
changes nothing: it never costs the user an answer.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from app.gateways.structured_completion import complete_structured
from app.models.routing_lanes import ROUTING
from app.modules.chat.markdown_regions import map_prose_outside_fences
from app.modules.chat.stream_status import announced_if_slow
from app.services.text_normalize import collapse_ws

if TYPE_CHECKING:
    from app.modules.chat.finalize_passes import FinalizeState

logger = logging.getLogger(__name__)

# A reply shorter than this holds no table of figures or status claims worth a model call.
_MIN_REPLY_CHARS = 120
_MAX_HITS = 8
_HIT_CHARS = 700
_EARLIER_USER_MESSAGES = 4
_USER_CHARS = 600
_REPLY_CHARS = 7000
# More than this share of the reply flagged: the check is wrong or the reply is not worth
# editing; either way the user keeps what they were sent.
_MAX_CUT_SHARE = 0.5
_MAX_CLAIMS = 12
_SEARCH_BLOCK_MARK = "Web search results"

_SYSTEM = (
    "You check an assistant reply against the evidence it had, and list every claim the "
    "evidence does not support.\n\n"
    "A claim is: a figure (rate, fee, price, percentage, date, count); a legal or "
    "regulatory status (licensed, banned, approved, reinstated, safe to use); a named "
    "organisation, product or person said to offer or do something; or an attribution "
    "to a named source or authority.\n\n"
    "Evidence is ONLY the web results (each one's title, address and text all count; a "
    "headline that states a fact supports it) and the user's own messages. Earlier "
    "assistant replies are NOT evidence. A figure within rounding of one in the evidence is "
    "supported, and so is arithmetic done on supported or user-given figures.\n\n"
    "Not a claim to list: advice, opinions, definitions, general explanations of how "
    "something works, steps for doing something, hedged estimates the reply calls "
    "estimates, and what the reply says it could not find.\n\n"
    'Return JSON: {"unsupported": [{"quote": ..., "topic": ...}], "note": ...}. '
    "quote is the shortest span copied exactly from the reply that holds the claim. "
    "topic is 2 to 8 words naming what was claimed. note is one short sentence, in the "
    "language of the reply, saying you could not confirm those details from the sources "
    "found and left them out. Use an empty list and an empty note when every claim is "
    "supported."
)


class _Claim(BaseModel):
    quote: str = Field(min_length=3, max_length=300)
    topic: str = Field(default="", max_length=100)


class _Verdict(BaseModel):
    unsupported: list[_Claim] = Field(default_factory=list, max_length=_MAX_CLAIMS)
    note: str = Field(default="", max_length=240)


def _evidence(state: FinalizeState) -> str:
    ctx = state.ctx
    hits = [
        f"[{n}] {hit.title}\n{hit.url}\n{hit.snippet[:_HIT_CHARS]}"
        for n, hit in enumerate(ctx.search_sources[:_MAX_HITS], 1)
    ]
    earlier = [
        m["content"][:_USER_CHARS]
        for m in ctx.prompt_messages[:-1]
        if m.get("role") == "user"
        and isinstance(m.get("content"), str)
        and _SEARCH_BLOCK_MARK not in m["content"]
    ][-_EARLIER_USER_MESSAGES:]
    said = [*earlier, (ctx.user_message_content or "")[:_USER_CHARS]]
    return (
        "WEB RESULTS:\n"
        + "\n\n".join(hits)
        + "\n\nTHE USER'S MESSAGES (oldest first):\n"
        + "\n".join(f"- {message}" for message in said)
    )


_TABLE_ROW = re.compile(r"^\s*\|")
_TABLE_RULE = re.compile(r"^\s*\|?[\s:|-]+\|[\s:|-]*$")
_SENTENCE_GAP = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9*_\[(\"'])")
_ONLY_MARKUP = re.compile(r"^[\s>*_\-•\d.)#]*$")


_MARKUP = re.compile(r"[*_`~|]+")
_WORD = re.compile(r"[\w.%]+")
# A quote the model re-typed, not copied: it still names the line when this much of its
# words are the line's own.
_MIN_OVERLAP = 0.8


def _plain(text: str) -> str:
    """Words only: emphasis, code ticks, tildes and pipes do not tell two lines apart."""
    return collapse_ws(_MARKUP.sub(" ", text)).casefold()


def _find_line(lines: list[str], quote: str) -> int | None:
    needle = _plain(quote)
    if not needle:
        return None
    for index, line in enumerate(lines):
        if needle in _plain(line):
            return index
    words = set(_WORD.findall(needle))
    best: tuple[float, int] | None = None
    for index, line in enumerate(lines):
        have = set(_WORD.findall(_plain(line)))
        if not have or len(words) < 3:
            continue
        overlap = len(words & have) / len(words)
        if overlap >= _MIN_OVERLAP and (best is None or overlap > best[0]):
            best = (overlap, index)
    return None if best is None else best[1]


def _cut_from_line(line: str, quote: str) -> str | None:
    """The line without the sentence holding ``quote``; None when nothing is left."""
    if _TABLE_ROW.match(line):
        return None
    needle = _plain(quote)
    sentences = _SENTENCE_GAP.split(line)
    kept = [s for s in sentences if needle not in _plain(s)]
    if len(kept) == len(sentences):
        # Named by its words, not copied: one sentence has nothing else to keep, and with
        # several there is no telling which one it meant.
        return None if len(sentences) == 1 else line
    rest = " ".join(kept).rstrip()
    return None if _ONLY_MARKUP.match(rest) else rest


_TOTAL_ROW = re.compile(r"^\s*\|[\s*_]*(?:grand\s+)?(?:total|sum)\b", re.IGNORECASE)


def _tidy_tables(lines: list[str | None]) -> list[str]:
    """A table that lost rows: its total no longer adds up, so that goes too; a table whose
    rows are all gone leaves nothing to show, so its header goes with them."""
    out: list[str] = []
    run: list[str] = []
    cut = False

    def flush() -> None:
        nonlocal cut
        rows = [row for row in run if not _TABLE_RULE.match(row)]
        if cut:
            rows = [row for row in rows if not _TOTAL_ROW.match(row)]
        if len(rows) > 1:
            out.extend(row for row in run if _TABLE_RULE.match(row) or row in rows)
        run.clear()
        cut = False

    for line in lines:
        if line is None:
            cut = cut or bool(run)
            continue
        if _TABLE_ROW.match(line):
            run.append(line)
            continue
        flush()
        out.append(line)
    flush()
    return out


def cut_claims(text: str, quotes: list[str]) -> tuple[str, int]:
    """``text`` without the sentence or table row of each quote found in its prose,
    and how many quotes it found."""
    found = 0

    def rewrite(prose: str) -> str:
        nonlocal found
        lines: list[str | None] = prose.split("\n")  # type: ignore[assignment]
        for quote in quotes:
            index = _find_line([line or "" for line in lines], quote)
            if index is None:
                continue
            found += 1
            lines[index] = _cut_from_line(lines[index] or "", quote)
        return "\n".join(_tidy_tables(lines))

    return map_prose_outside_fences(text, rewrite), found


async def _verdict(state: FinalizeState) -> _Verdict | None:
    settings = state.settings
    messages = [
        {"role": "system", "content": _SYSTEM},
        {
            "role": "user",
            "content": f"{_evidence(state)}\n\nASSISTANT REPLY TO CHECK:\n{state.text[:_REPLY_CHARS]}",
        },
    ]
    return await announced_if_slow(
        complete_structured(
            settings=settings,
            model_alias=ROUTING.background,
            messages=messages,
            schema=_Verdict,
            max_tokens=600,
            timeout_seconds=settings.claim_check_timeout_seconds,
            usage=state.usage,
            allow_fallback=False,
        ),
        state.on_status,
        "checking",
        then="finishing",
    )


def _prose_chars(text: str) -> int:
    total = 0

    def count(prose: str) -> str:
        nonlocal total
        total += len(prose)
        return prose

    map_prose_outside_fences(text, count)
    return total


async def cut_unsupported_claims(state: FinalizeState) -> str:
    """Pass entry: a searched reply keeps only what its sources or the user said."""
    ctx = state.ctx
    text = state.text
    if (
        not state.settings.claim_check_enabled
        or not ctx.search_sources
        or state.server_text
        or state.was_cancelled
        or ctx.verified_subject is not None
        or ctx.money is not None
        or len(text) < _MIN_REPLY_CHARS
    ):
        return text
    verdict = await _verdict(state)
    if verdict is None or not verdict.unsupported:
        return text
    quotes = [claim.quote for claim in verdict.unsupported]
    cut, found = cut_claims(text, quotes)
    if not found:
        return text
    before = _prose_chars(text)
    if before and (before - _prose_chars(cut)) / before > _MAX_CUT_SHARE:
        logger.warning("claim_check flagged most of a reply; left it as written")
        return text
    topics = "; ".join(dict.fromkeys(c.topic.strip() for c in verdict.unsupported if c.topic))
    logger.info("claim_check cut %d unsupported claim(s): %s", found, topics)
    note = verdict.note.strip() or (
        f"I couldn't confirm these from the sources I found, so I left them out: {topics}."
        if topics
        else "I left out details the sources I found did not confirm."
    )
    return f"{cut.rstrip()}\n\n*{note.strip('*_ ')}*"
