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

Facts are carried the same way (2026-11-07). A 100-turn chat's summary held only the
newest fold's facts ("User requested a reminder to call the Honda shop"): each fold let
the model restate the old ones, and it did not, so "what laptop do I have" got "I don't
have any record" though the user named a 2017 Dell Inspiron in their first message. Every
fact sentence is kept, oldest first, once each; a changed fact is written again and read
as the newer one. Over the facts' share the earlier facts go, longest first: a durable fact
is short ("User drives a 2011 Honda Civic"), a narration long ("User asked about renting
vs buying; …"). The fold's new facts never go, so a changed rent is never lost the fold it
arrives (review, 2026-11-07). On the 100-turn chat's recorded folds this kept 8 of 10
checked details; oldest-first kept 5 or 6.
"""

from __future__ import annotations

import re

_SECTION = re.compile(r"^(?P<name>Facts|Topics|Open):[ \t]*(?P<rest>.*)$", re.IGNORECASE)
_SECTIONS = ("Facts", "Topics", "Open")
# An old topic line shortened to make room keeps this much, then only its subject.
_SHORT_TOPIC = 90
_BARE_TOPIC = 40
# A sentence ends at . ! ? or the Ethiopic full stop, before a capital (Latin or Cyrillic),
# an Ethiopic letter, a digit or a quote; "Dr. Smith" and "e.g. Python" go on.
_FACT_SENTENCE = re.compile(
    r"(?<!\bDr\.)(?<!\bMr\.)(?<!\bMs\.)(?<!\bMrs\.)(?<!\bSt\.)(?<!\bvs\.)(?<!\be\.g\.)(?<!\bi\.e\.)"
    r"(?<=[.!?።])\s+(?=[A-Z0-9\"'(\u0401\u0410-\u042F\u1200-\u137F])"
)
# Facts and Open written by the model are held to these shares of the cap. Facts come
# first: an old topic line shortens to its subject, a fact is gone when it goes.
_FACTS_SHARE = 2
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
    """Every fact sentence and every topic line, the earlier ones as they were, then the new
    ones, and the fresh summary's Open. Over ``max_chars``, the oldest lines are shortened first, then
    cut to their subject, then the oldest subjects go; the result always fits."""
    old, new = sections(prior), sections(fresh)
    topics = list(dict.fromkeys([*old["Topics"], *new["Topics"]]))
    facts = [" ".join(_carried_facts(old["Facts"], new["Facts"], max_chars // _FACTS_SHARE))]
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


def _carried_facts(old: list[str], new: list[str], width: int) -> list[str]:
    """The earlier fact sentences, then the new ones, each once. Over ``width`` the earlier
    ones go, longest first (the oldest of equals); a new fact stays. A fact is never
    judged restated by its words: "User earns $3,200" and "User's wife earns $2,800" share
    most of them (review, 2026-11-07)."""

    def key(fact: str) -> str:
        return " ".join(fact.lower().rstrip(".").split())

    fresh = list({key(fact): fact for fact in _fact_sentences(new)}.values())
    # A fact said again moves to the end, where the later value holds: rent $1,100, then
    # $1,250, then $1,100 again is $1,100 (review of #2337).
    said_again = {key(fact) for fact in fresh}
    earlier = list({key(fact): fact for fact in _fact_sentences(old)}.values())
    earlier = [fact for fact in earlier if key(fact) not in said_again]
    while earlier and len(" ".join([*earlier, *fresh])) > width:
        earlier.pop(max(range(len(earlier)), key=lambda i: (len(earlier[i]), -i)))
    facts = [*earlier, *fresh]
    return [_clipped(" ".join(facts), width)] if facts else []


def _fact_sentences(lines: list[str]) -> list[str]:
    return [part.strip() for line in lines for part in _FACT_SENTENCE.split(line) if part.strip()]


def _clipped(line: str, width: int) -> str:
    return line if len(line) <= width else f"{line[:width].rstrip()}…"


def _compose(facts: list[str], topics: list[str], still_open: list[str]) -> str:
    return (
        f"Facts: {' '.join(facts)}\n\nTopics:\n"
        + "\n".join(topics)
        + f"\n\nOpen: {' '.join(still_open)}"
    )
