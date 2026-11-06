"""The running summary's topics are kept by code, never rewritten away.

A 31-turn chat (2026-11-06) talked about a Zanzibar trip for four turns; ten turns later the
summary said "Trip is in December" and named no Zanzibar, and "u forgot the zanzibar stuff"
got "I don't have anything about Zanzibar from our chats". The summary model was told to
"never drop a topic", yet each fold rewrote the whole summary and the oldest topics fell
out (dinner and a fight with a manager went too). So the model writes the topic lines of
the new messages only, and the earlier lines are carried over as they were. Over the size
cap, the oldest lines are shortened, never removed.
"""

from __future__ import annotations

import re

_SECTION = re.compile(r"^(?P<name>Facts|Topics|Open):[ \t]*(?P<rest>.*)$", re.IGNORECASE)
_SECTIONS = ("Facts", "Topics", "Open")
# An old topic line shortened to make room keeps this much.
_SHORT_TOPIC = 90


def sections(summary: str | None) -> dict[str, list[str]]:
    """``summary`` read as its Facts, Topics and Open lines; a line before any heading is a
    fact."""
    found: dict[str, list[str]] = {name: [] for name in _SECTIONS}
    current = "Facts"
    for line in (summary or "").splitlines():
        heading = _SECTION.match(line.strip())
        if heading is not None:
            current = heading["name"].capitalize()
            line = heading["rest"]
        if line.strip():
            found[current].append(line.strip())
    return found


def merged(prior: str | None, fresh: str, max_chars: int) -> str:
    """The fresh summary's Facts and Open, and every topic line: the earlier ones as they
    were, then the new ones. Over ``max_chars``, the oldest lines are shortened first."""
    old, new = sections(prior), sections(fresh)
    topics = list(dict.fromkeys([*old["Topics"], *new["Topics"]]))
    facts = new["Facts"] or old["Facts"]
    still_open = new["Open"] or ["None"]
    text = _compose(facts, topics, still_open)
    for index in range(len(topics)):
        if len(text) <= max_chars:
            break
        if len(topics[index]) > _SHORT_TOPIC:
            topics[index] = f"{topics[index][:_SHORT_TOPIC].rstrip()}…"
            text = _compose(facts, topics, still_open)
    return text


def _compose(facts: list[str], topics: list[str], still_open: list[str]) -> str:
    return (
        f"Facts: {' '.join(facts)}\n\nTopics:\n"
        + "\n".join(topics)
        + f"\n\nOpen: {' '.join(still_open)}"
    )
