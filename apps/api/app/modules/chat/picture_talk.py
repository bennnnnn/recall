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

So once the reply shows one of the server's pictures (``owed_picture``), each sentence that
speaks of the app's pictures, offers to draw a picture of a kind the reply now shows, or says
it cannot draw goes; the rest of its paragraph stays. A reply that shows no picture keeps
them, and gets the line that says the picture was not drawn. Fences, tables and quotes are
never read.
"""

from __future__ import annotations

import re

from app.services.md_fence_scan import iter_fences, line_fences

# A picture by name, and the kinds of picture each names.
_GRAPH_WORDS = r"graphs?|plots?|charts?|curves?"
_DIAGRAM_WORDS = (
    r"diagrams?|pictures?|figures?|scenes?|sketch(?:es)?|drawings?|images?|illustrations?"
)
_PICTURE = rf"(?:{_GRAPH_WORDS}|{_DIAGRAM_WORDS})"
# The app itself, as the prompt names it: "the app", "the app's", "this app".
_THE_APP = re.compile(rf"\b(?:the|this)\s+app(?:'s)?\b[^.!?]{{0,80}}?\b{_PICTURE}\b", re.I)
_APP_AFTER = re.compile(rf"\b{_PICTURE}\b[^.!?]{{0,80}}?\b(?:the|this)\s+app\b", re.I)
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
    r"\b(?:I\s*(?:can|could|'ll|will|'d|would)(?:\s+(?:also|gladly|happily|be\s+happy\s+to))?"
    rf"|happy\s+to)\s+{_DRAWS}[^.!?]*\b(?:if\s+you|on\s+request|just\s+ask|if\s+(?:it|that)\s+helps)",
    re.IGNORECASE,
)
_NAMES_GRAPH = re.compile(rf"\b(?:{_GRAPH_WORDS})\b", re.IGNORECASE)
_NAMES_DIAGRAM = re.compile(rf"\b(?:{_DIAGRAM_WORDS})\b", re.IGNORECASE)
# "I can't draw diagrams here", "I'm unable to render the graphs".
_CANNOT = re.compile(
    r"\bI\s*(?:can(?:'|no)t|can\s+not|could(?:n't|\s+not)|am\s+unable\s+to|'m\s+unable\s+to"
    rf"|am\s+not\s+able\s+to|'m\s+not\s+able\s+to)\s+(?:draw|sketch|plot|render|show|display"
    rf"|produce|create|generate)\b[^.!?]{{0,60}}?\b{_PICTURE}\b",
    re.IGNORECASE,
)
_SENTENCE_BREAK = re.compile(r"(?<=[.!?…]) +")
# A list item's or a numbered line's lead, kept when its sentence goes.
_LEAD = re.compile(r"[ \t]*(?:(?:[-*+]|\d{1,3}[.)])[ \t]+)?")
# Lines no sentence is read in: a table row, a quote, an indented block.
_SKIPPED_STARTS = ("|", ">", "    ", "\t")
_GRAPH_LANGS = frozenset({"graph", "plot", "chart", "vega", "vega-lite"})


def without_picture_talk(text: str) -> str:
    """``text`` without its sentences about drawing pictures, given that it shows one of the
    server's pictures (``owed_picture.shows_a_picture``); ``text`` itself when none speaks
    of one, or when nothing else would be left."""
    langs = {fence.lang for fence in iter_fences(text) if fence.closed}
    graphs = bool(langs & _GRAPH_LANGS)
    diagrams = bool(langs - _GRAPH_LANGS - {"answer", ""})
    owners = line_fences(text)
    out: list[str] = []
    changed = False
    for index, line in enumerate(text.split("\n")):
        if owners[index] is not None or line.startswith(_SKIPPED_STARTS):
            out.append(line)
            continue
        lead_match = _LEAD.match(line)
        lead = lead_match.group(0) if lead_match else ""
        sentences = _SENTENCE_BREAK.split(line[len(lead) :])
        kept = [s for s in sentences if not _speaks_of_drawing(s, graphs, diagrams)]
        if len(kept) == len(sentences):
            out.append(line)
            continue
        changed = True
        if kept:
            out.append(lead + " ".join(kept))
        elif out and not out[-1].strip():
            out.pop()  # the paragraph that went leaves one blank line, not two
    result = "\n".join(out)
    return result if changed and result.strip() else text


def _speaks_of_drawing(sentence: str, graphs: bool, diagrams: bool) -> bool:
    """The sentence speaks of the app's pictures, offers to draw a picture of a kind the
    reply shows, or says it cannot draw one."""
    if _THE_APP.search(sentence) or _APP_AFTER.search(sentence) or _CANNOT.search(sentence):
        return True
    offer = _OFFER_ASKED.search(sentence) or _OFFER_IF.search(sentence)
    if offer is None:
        return False
    rest = sentence[offer.start() :]
    return (graphs and _NAMES_GRAPH.search(rest) is not None) or (
        diagrams and _NAMES_DIAGRAM.search(rest) is not None
    )
