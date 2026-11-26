"""How a reply is laid out, read from its Markdown, and whether that is the shape its kind wants.

The owner's shape for every informational reply (2026-11-26): a short intro, a title, the
main items numbered or bulleted with a **bold** name and a short explanation, each item's
members as a nested list under it, subtitles for sections, the key words bold. A one-line
fact stays a line or two; a conversation stays a few plain lines; a maths or physics
workout keeps its own worked layout with its answer card. ``format_eval`` sends
``format_corpus.json`` through the real chat stream and judges each reply here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Kinds an informational reply answers, laid out to be scanned.
STRUCTURED = frozenset({"overview", "explain", "howto", "tips", "compare", "picks"})

_FENCE = re.compile(r"^```.*?^```[^\n]*$", re.MULTILINE | re.DOTALL)
_HEADING = re.compile(r"^(#{1,6})\s+\S")
_ITEM = re.compile(r"^(\s*)(?:[-*+]|\d+[.)])\s+(.*)$")
_NUMBERED = re.compile(r"^\d+[.)]\s")
_BOLD = re.compile(r"\*\*[^*\n]+\*\*")
_EMOJI = re.compile("[\U0001f300-\U0001faff☀-➿]")
_LEAD = re.compile("^(?:[\U0001f300-\U0001faff☀-➿️]\\s*)*")
_SENTENCE = re.compile(r"[.!?](?:\s|$)")


@dataclass(frozen=True)
class Shape:
    """What a reply's Markdown holds, outside code and card fences."""

    intro: bool
    intro_sentences: int
    title: bool
    subtitles: int
    items: int
    numbered: int
    bold_labels: int
    nested: int
    bold: int
    emoji: int
    lines: int
    answer_card: bool
    steps_card: bool


def shape_of(reply: str) -> Shape:
    """The layout of ``reply``: its intro, headings, lists and emphasis."""
    answer_card = "```answer" in reply
    steps_card = "```steps" in reply
    text = _FENCE.sub("", reply)
    lines = [line for line in text.splitlines() if line.strip()]
    first = lines[0] if lines else ""
    intro = bool(first) and not _HEADING.match(first) and not _ITEM.match(first)
    headings = [len(m.group(1)) for line in lines if (m := _HEADING.match(line))]
    top = [m for line in lines if (m := _ITEM.match(line)) and not m.group(1)]
    nested = [m for line in lines if (m := _ITEM.match(line)) and m.group(1)]
    return Shape(
        intro=intro,
        intro_sentences=len(_SENTENCE.findall(first)) or (1 if intro else 0),
        title=any(level <= 2 for level in headings),
        subtitles=sum(1 for level in headings if level >= 3),
        items=len(top),
        numbered=sum(1 for line in lines if _NUMBERED.match(line)),
        bold_labels=sum(1 for m in top if _LEAD.sub("", m.group(2)).startswith("**")),
        nested=len(nested),
        bold=len(_BOLD.findall(text)),
        emoji=len(_EMOJI.findall(text)),
        lines=len(lines),
        answer_card=answer_card,
        steps_card=steps_card,
    )


def misses(kind: str, shape: Shape) -> list[str]:
    """What the reply's layout lacks for its kind; empty when it is the shape wanted."""
    found: list[str] = []
    if kind in STRUCTURED and shape.steps_card:
        # The app's step card is its own laid-out list: numbered, each step a bold name.
        if not shape.intro:
            found.append("no intro")
    elif kind in STRUCTURED:
        if not shape.intro:
            found.append("no intro")
        elif shape.intro_sentences > 3:
            found.append("long intro")
        if not shape.title:
            found.append("no title")
        if shape.items < 2 and shape.subtitles < 2:
            found.append("no main items")
        if shape.items >= 2 and shape.bold_labels * 5 < shape.items * 4:
            found.append("items without bold names")
        if kind == "overview" and shape.nested < 2:
            found.append("no nested members")
    elif kind == "fact":
        if shape.title or shape.subtitles:
            found.append("heading on a fact")
        if shape.lines > 4:
            found.append("fact too long")
        if not shape.bold:
            found.append("fact not bold")
    elif kind == "casual":
        if shape.title or shape.subtitles:
            found.append("heading in conversation")
        if shape.items or shape.nested:
            found.append("list in conversation")
    elif kind == "maths" and not shape.answer_card:
        found.append("no answer card")
    return found
