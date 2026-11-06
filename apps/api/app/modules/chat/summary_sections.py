"""The running summary's topics are kept by code, never rewritten away.

A 31-turn chat (2026-11-06) talked about a Zanzibar trip for four turns; ten turns later the
summary said "Trip is in December" and named no Zanzibar, and "u forgot the zanzibar stuff"
got "I don't have anything about Zanzibar from our chats". The summary model was told to
"never drop a topic", yet each fold rewrote the whole summary and the oldest topics fell
out (dinner and a fight with a manager went too). So the model writes the topic lines of
the new messages only, and the earlier lines are carried over as they were. Over the size
cap, the oldest lines are shortened first, then cut to their subject; only a chat with
more subjects than the cap holds loses its oldest ones, so the newest topics and the Open
line always fit.
"""

from __future__ import annotations

import re

_SECTION = re.compile(r"^(?P<name>Facts|Topics|Open):[ \t]*(?P<rest>.*)$", re.IGNORECASE)
_SECTIONS = ("Facts", "Topics", "Open")
# An old topic line shortened to make room keeps this much, then only its subject.
_SHORT_TOPIC = 90
_BARE_TOPIC = 40
# Facts and Open written by the model are held to these shares of the cap.
_FACTS_SHARE = 4
_OPEN_SHARE = 8


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
    were, then the new ones. Over ``max_chars``, the oldest lines are shortened first, then
    cut to their subject, then the oldest subjects go; the result always fits."""
    old, new = sections(prior), sections(fresh)
    topics = list(dict.fromkeys([*old["Topics"], *new["Topics"]]))
    facts = [_clipped(" ".join(new["Facts"] or old["Facts"]), max_chars // _FACTS_SHARE)]
    still_open = [_clipped(" ".join(new["Open"]) or "None", max_chars // _OPEN_SHARE)]
    # Each change is counted as it is made, so a long chat is not recomposed per line.
    size = len(_compose(facts, topics, still_open))
    for width in (_SHORT_TOPIC, _BARE_TOPIC):
        for index, line in enumerate(topics):
            if size <= max_chars:
                break
            topics[index] = _clipped(line, width)
            size += len(topics[index]) - len(line)
    while topics and size > max_chars:
        size -= len(topics.pop(0)) + 1
    return _compose(facts, topics, still_open)


def _clipped(line: str, width: int) -> str:
    return line if len(line) <= width else f"{line[:width].rstrip()}…"


def _compose(facts: list[str], topics: list[str], still_open: list[str]) -> str:
    return (
        f"Facts: {' '.join(facts)}\n\nTopics:\n"
        + "\n".join(topics)
        + f"\n\nOpen: {' '.join(still_open)}"
    )
