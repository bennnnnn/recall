"""A reply's sentences about drawing its pictures, which come off once the server drew them.

A picture a message asks for is the server's to draw (``figure_turn``, ``drawing_turn``), and
the reply model is told never to speak of it. Two Pro replies (2026-11-27) spoke of it anyway,
in three ways, all false beside the pictures drawn under them:

- the app and its pictures: "The app has no scene for a block sliding down an incline in this
  setup, so here is the picture in words", "The app's picture of the Atwood setup appears
  with this reply";
- an offer to draw what was asked: "I can draw the three graphs for the first 3 seconds if
  you want them as pictures";
- a refusal: "I can't draw diagrams here".

So once the reply shows one of the server's pictures (``owed_picture``), a sentence that
speaks of the app's pictures goes, and so does one that offers to draw, or says it cannot
draw, a kind of picture the reply now shows (a graph, a diagram); what such a sentence goes
on to say after "but" ("…, but v rises from 0 to 16 m/s") stays, and so does the rest of its
paragraph. Words about a kind the reply does not show stay: that picture was not drawn. A
reply that shows no picture keeps them all, and gets the line that says the picture was not
drawn. Fences, tables and quotes are never read.
"""

from __future__ import annotations

import re
from collections.abc import Set as AbstractSet
from typing import Literal

from app.services.md_fence_scan import line_fences

Kind = Literal["graph", "diagram"]

# A picture by name, and the kinds of picture each names.
_GRAPH_WORDS = r"graphs?|plots?|charts?|curves?"
_DIAGRAM_WORDS = (
    r"diagrams?|pictures?|figures?|scenes?|sketch(?:es)?|drawings?|images?|illustrations?"
)
_PICTURE = rf"(?:{_GRAPH_WORDS}|{_DIAGRAM_WORDS})"
# A straight or a curly apostrophe: models write both.
_APOS = r"['\u2019]"
# The app itself speaking of its pictures, as the prompt names it: "The app has no scene for
# this", "the app's picture of the setup appears". Never the app a graph is about ("the graph
# shows the app reaches 6,000 users").
_THE_APP = re.compile(
    rf"\b(?:the|this)\s+app(?:{_APOS}s)?\s+(?:{_PICTURE}\b|(?:has|have|can|cannot"
    rf"|can{_APOS}t|could|couldn{_APOS}t|does|doesn{_APOS}t|will|won{_APOS}t|draws?|shows?"
    rf"|renders?|displays?)\b[^.!?]{{0,80}}?\b{_PICTURE}\b)",
    re.IGNORECASE,
)
_DRAWS = r"(?:draw|sketch|plot|graph|render|show|make|create|generate|produce)\b"
# An offer to draw, asked ("Want me to sketch it?", "Shall I plot the graphs?") or on a
# condition ("I can draw the three graphs ... if you want them as pictures"). A plan the
# reply carries out ("I'll show the working") is no offer.
_OFFER_ASKED = re.compile(
    r"\b(?:(?:do\s+you\s+)?want\s+me\s+to|shall\s+I|should\s+I|would\s+you\s+like\s+me\s+to|"
    rf"let\s+me\s+know\s+if\s+you\s+(?:want|would\s+like|need)\s+me\s+to)\s+(?:also\s+)?{_DRAWS}",
    re.IGNORECASE,
)
_OFFER_IF = re.compile(
    rf"\b(?:I\s*(?:can|could|{_APOS}ll|will|{_APOS}d|would)"
    r"(?:\s+(?:also|gladly|happily|be\s+happy\s+to))?|happy\s+to)"
    rf"\s+{_DRAWS}[^.!?]*\b(?:if\s+you|on\s+request|just\s+ask|if\s+(?:it|that)\s+helps)",
    re.IGNORECASE,
)
_NAMES: dict[Kind, re.Pattern[str]] = {
    "graph": re.compile(rf"\b(?:{_GRAPH_WORDS})\b", re.IGNORECASE),
    "diagram": re.compile(rf"\b(?:{_DIAGRAM_WORDS})\b", re.IGNORECASE),
}
# "I can't draw diagrams here", "I'm unable to render the graphs".
_CANNOT = re.compile(
    rf"\bI\s*(?:can(?:{_APOS}|no)t|can\s+not|could(?:n{_APOS}t|\s+not)|am\s+unable\s+to"
    rf"|{_APOS}m\s+unable\s+to|am\s+not\s+able\s+to|{_APOS}m\s+not\s+able\s+to)\s+"
    rf"(?:draw|sketch|plot|render|show|display|produce|create|generate)\b[^.!?]{{0,60}}?"
    rf"\b{_PICTURE}\b",
    re.IGNORECASE,
)
# What a cut sentence goes on to say of its own: "…, but v rises from 0 to 16 m/s".
_BUT = re.compile(r"[,;]?\s+but\s+", re.IGNORECASE)
_SENTENCE_BREAK = re.compile(r"(?<=[.!?…]) +")
# A list item's or a numbered line's lead, kept when its sentence goes.
_LEAD = re.compile(r"[ \t]*(?:(?:[-*+]|\d{1,3}[.)])[ \t]+)?")
# Lines no sentence is read in: a table row, a quote, an indented block.
_SKIPPED_STARTS = ("|", ">", "    ", "\t")


def without_picture_talk(text: str, drawn: AbstractSet[Kind]) -> str:
    """``text`` without its words about drawing the kinds of picture it shows (``drawn``:
    ``owed_picture.drawn_kinds``); ``text`` itself when none speaks of them, or when nothing
    else would be left."""
    owners = line_fences(text)
    lines = text.split("\n")
    out: list[str] = []
    changed = False
    for index, line in enumerate(lines):
        if owners[index] is not None or line.startswith(_SKIPPED_STARTS) or not line.strip():
            out.append(line)
            continue
        lead_match = _LEAD.match(line)
        lead = lead_match.group(0) if lead_match else ""
        sentences = _SENTENCE_BREAK.split(line[len(lead) :])
        kept = [part for part in (_kept(s, drawn) for s in sentences) if part]
        if kept == sentences:
            out.append(line)
            continue
        changed = True
        if kept:
            out.append(lead + " ".join(kept))
            continue
        # A whole paragraph that went leaves one blank line, not two; a paragraph's first line
        # that went leaves the rest of its paragraph a paragraph of its own.
        after = lines[index + 1] if index + 1 < len(lines) else ""
        if out and not out[-1].strip() and not after.strip():
            out.pop()
    result = "\n".join(out)
    return result if changed and result.strip() else text


def _kept(sentence: str, drawn: AbstractSet[Kind]) -> str:
    """What stays of a sentence: all of it, unless it speaks of the app's pictures, or offers
    to draw or says it cannot draw a kind of picture ``drawn`` holds; then only what it goes
    on to say after "but"."""
    talk = _THE_APP.search(sentence)
    if talk is None:
        cannot = _CANNOT.search(sentence)
        talk = cannot if cannot is not None and _names_drawn(cannot.group(0), drawn) else None
    if talk is None:
        offer = _OFFER_ASKED.search(sentence) or _OFFER_IF.search(sentence)
        offered = offer is not None and _names_drawn(sentence[offer.start() :], drawn)
        return "" if offered else sentence
    rest = _BUT.split(sentence[talk.end() :], maxsplit=1)
    clause = rest[1].strip() if len(rest) == 2 else ""
    return clause[:1].upper() + clause[1:]


def _names_drawn(words: str, drawn: AbstractSet[Kind]) -> bool:
    return any(_NAMES[kind].search(words) is not None for kind in drawn)
