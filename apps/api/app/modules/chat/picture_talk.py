"""A reply's sentences that deny or offer the pictures the server drew beside it.

A picture a message asks for is the server's to draw (``figure_turn``, ``drawing_turn``), and
the reply model is told never to speak of it. Two Pro replies (2026-11-27) spoke of it anyway,
falsely beside the pictures drawn under them: "The app has no scene for a block sliding down an
incline in this setup, so here is the picture in words", "The app's picture of the Atwood setup
appears with this reply", "I can draw the three graphs for the first 3 seconds if you want them
as pictures".

The cut is narrow, because a reply's other sentences about pictures are content. A sentence
goes, whole, only when all of these hold (``owed_picture`` calls this once a picture asked for
is drawn):

- it says the app cannot draw or show a picture ("I can't draw diagrams here", "the app has
  no scene for this"), says the app's picture appears with the reply, or offers to draw one
  on the reader's say-so ("I can draw the graphs if you want them", "Shall I sketch it?");
- the kind of picture it names, a graph or a diagram, is one the reply shows;
- it holds nothing else: no number, no "=", no "but" going on to say something of its own.

Every other sentence stays whole and as written: a sentence about the user's own app, a chart
of their data, teaching ("I'd draw the free-body diagram first if you solve these by hand"),
and words about a kind of picture the reply does not show. A reply that shows no picture keeps
them all, and gets the line that says the picture was not drawn. Fences, tables and quotes are
never read.
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
_NOT = rf"(?:can{_APOS}t|cannot|can\s+not|couldn{_APOS}t|could\s+not|doesn{_APOS}t|won{_APOS}t)"
_SHOWS = r"(?:draw|sketch|plot|render|show|display|animate|produce|create|generate)"
# The app speaking of its own pictures, as the prompt names it: "the app has no scene for
# this", "the app can't draw the graph", "the app's picture of the setup appears".
_THE_APP = re.compile(
    rf"\b(?:the|this)\s+app\s+(?:has|have)\s+no\s+(?:\w+\s+){{0,2}}?{_PICTURE}\b"
    rf"|\b(?:the|this)\s+app\s+{_NOT}\s+{_SHOWS}\b[^.!?]{{0,40}}?\b{_PICTURE}\b"
    rf"|\b(?:the|this)\s+app{_APOS}s\s+{_PICTURE}\b[^.!?]{{0,60}}?\b(?:appears?|is\s+(?:shown"
    r"|drawn|attached|below|above)|comes?\s+with)\b",
    re.IGNORECASE,
)
# The reply saying it cannot draw: "I can't draw diagrams here", "I'm unable to render it".
_CANNOT = re.compile(
    rf"\bI\s*(?:{_NOT}|am\s+unable\s+to|{_APOS}m\s+unable\s+to|am\s+not\s+able\s+to"
    rf"|{_APOS}m\s+not\s+able\s+to)\s+{_SHOWS}\b[^.!?]{{0,60}}?\b{_PICTURE}\b",
    re.IGNORECASE,
)
# An offer to draw, asked ("Want me to sketch it?", "Shall I plot the graphs?") or on the
# reader's say-so ("I can draw the three graphs if you want them as pictures"). A plan the
# reply carries out ("I'll show the working") or teaching ("I'd draw the free-body diagram
# first if you solve these by hand") is no offer.
_OFFER_ASKED = re.compile(
    r"\b(?:(?:do\s+you\s+)?want\s+me\s+to|shall\s+I|should\s+I|would\s+you\s+like\s+me\s+to"
    rf"|let\s+me\s+know\s+if\s+you\s+(?:want|would\s+like|need)\s+me\s+to)\s+(?:also\s+)?{_SHOWS}\b",
    re.IGNORECASE,
)
_OFFER_IF = re.compile(
    rf"\b(?:I\s*(?:can|could|{_APOS}ll|will|{_APOS}d|would)(?:\s+(?:also|gladly|happily))?"
    rf"|happy\s+to)\s+{_SHOWS}\b[^.!?]*\b(?:if\s+you(?:{_APOS}d)?\s+(?:want|like|would\s+like"
    r"|prefer|need)|on\s+request|just\s+ask)\b",
    re.IGNORECASE,
)
_NAMES: dict[Kind, re.Pattern[str]] = {
    "graph": re.compile(rf"\b(?:{_GRAPH_WORDS})\b", re.IGNORECASE),
    "diagram": re.compile(rf"\b(?:{_DIAGRAM_WORDS})\b", re.IGNORECASE),
}
# Content of its own: a number, an equation, or a clause after "but".
_CONTENT = re.compile(r"\d|=|\bbut\b", re.IGNORECASE)
_SENTENCE_BREAK = re.compile(r"(?<=[.!?…]) +")
# A list item's or a numbered line's lead, kept with the rest of its line.
_LEAD = re.compile(r"[ \t]*(?:(?:[-*+]|\d{1,3}[.)])[ \t]+)?")
# Lines no sentence is read in: a table row, a quote, an indented block.
_SKIPPED_STARTS = ("|", ">", "    ", "\t")


def without_picture_talk(text: str, drawn: AbstractSet[Kind]) -> str:
    """``text`` without the sentences that deny or offer a kind of picture it shows
    (``drawn``: ``owed_picture.drawn_kinds``); ``text`` itself when none does, or when
    nothing else would be left."""
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
        kept = [sentence for sentence in sentences if not _denies_or_offers(sentence, drawn)]
        if len(kept) == len(sentences):
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


def _denies_or_offers(sentence: str, drawn: AbstractSet[Kind]) -> bool:
    """The sentence only denies or offers a kind of picture ``drawn`` holds."""
    if _CONTENT.search(sentence) is not None:
        return False
    found = (
        _THE_APP.search(sentence)
        or _CANNOT.search(sentence)
        or _OFFER_ASKED.search(sentence)
        or _OFFER_IF.search(sentence)
    )
    if found is None:
        return False
    words = sentence[found.start() :]
    return any(_NAMES[kind].search(words) is not None for kind in drawn)
