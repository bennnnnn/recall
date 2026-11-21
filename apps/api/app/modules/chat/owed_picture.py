# ruff: noqa: RUF001 - the lines are written in the app's languages (Turkish dotless i, Cyrillic)
"""A picture the turn's read asked for: drawn by the app, or said in one line not to be.

Every picture path (a solve's scene, a described ```draw block, a maths figure, a chart, a
molecule) asks the same read (``drawn_picture``) whether the message asks to see one, and
each may come back empty: a description that does not check, a chart whose numbers are not
the chat's, a setup no renderer draws. Seven of seven picture requests in a Grade 8 physics
round (2026-11-18) got nothing, with nothing said: a sentence claiming a graph, a Mermaid
flowchart of a hydraulic press, "I can't draw the rays myself". So, last of the picture
passes, the reply is held to what was asked:

- A Mermaid card stands in for no picture. Kept only when the message asks for a flowchart
  or another boxes-and-arrows diagram (``is_mermaid_question``), or when the read asks to
  see nothing: a request to draw, show or animate a thing or a motion is never answered as
  boxes (owner, 2026-11-18).
- A maths, physics or chemistry message whose read asks for a graph, a diagram or a molecule,
  and whose reply carries none of the app's pictures, gets one short line saying so, in the
  reply's language. The reply's text stays; an empty reply is the line alone.

The saved reply then says what was drawn; the chat's summary reads the pictures it shows
from their fences (``compaction``).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Literal

from app.modules.chat.decider_read import READ_SUBJECTS
from app.modules.chat.drawn_picture import DRAWN_PICTURES, answered_read
from app.modules.chat.finalize_subjects import fallback_text
from app.modules.chat.reply_language import line_language
from app.modules.chat.turn_decision import TurnDecision
from app.modules.turn_reading.diagrams import is_mermaid_question
from app.services.md_fence_scan import iter_fences

if TYPE_CHECKING:
    from app.modules.chat.finalize_passes import FinalizeState
    from app.modules.chat.turn_prep.context import StreamContext

Kind = Literal["graph", "diagram", "molecule"]

# The fences the app draws a picture from: a curve, a figure, a scene or schematic, a chart,
# a molecule (the phone's fence registry, ``lib/fence/registry.ts``).
APP_PICTURES = frozenset(
    {"graph", "geometry", "simulation", "chart", "vega", "vega-lite", "plot", "smiles",
     "chemistry", "chem_scene", "molecule", "molecule3d", "mol3d", "3dmol"}
)  # fmt: skip
_MERMAID = "mermaid"

_NOT_DRAWN: dict[str, dict[Kind, str]] = {
    "en": {
        "graph": "I couldn't draw this graph.",
        "diagram": "I couldn't draw this diagram.",
        "molecule": "I couldn't draw this molecule.",
    },
    "es": {
        "graph": "No pude dibujar este gráfico.",
        "diagram": "No pude dibujar este diagrama.",
        "molecule": "No pude dibujar esta molécula.",
    },
    "fr": {
        "graph": "Je n'ai pas pu dessiner ce graphique.",
        "diagram": "Je n'ai pas pu dessiner ce schéma.",
        "molecule": "Je n'ai pas pu dessiner cette molécule.",
    },
    "pt": {
        "graph": "Não consegui desenhar este gráfico.",
        "diagram": "Não consegui desenhar este diagrama.",
        "molecule": "Não consegui desenhar esta molécula.",
    },
    "tr": {
        "graph": "Bu grafiği çizemedim.",
        "diagram": "Bu diyagramı çizemedim.",
        "molecule": "Bu molekülü çizemedim.",
    },
    "ru": {
        "graph": "Не удалось нарисовать этот график.",
        "diagram": "Не удалось нарисовать эту схему.",
        "molecule": "Не удалось нарисовать эту молекулу.",
    },
    "am": {
        "graph": "ይህን ግራፍ መሳል አልቻልኩም።",
        "diagram": "ይህን ሥዕላዊ መግለጫ መሳል አልቻልኩም።",
        "molecule": "ይህን ሞለኪውል መሳል አልቻልኩም።",
    },
    "hi": {
        "graph": "मैं यह ग्राफ़ नहीं बना पाया।",
        "diagram": "मैं यह आरेख नहीं बना पाया।",
        "molecule": "मैं यह अणु नहीं बना पाया।",
    },
}


def not_drawn_line(kind: Kind, language: str) -> str:
    """The line in ``language`` (English for one the app lacks)."""
    return _NOT_DRAWN.get(language, _NOT_DRAWN["en"])[kind]


def mermaid_stands_in(decision: TurnDecision | None, line: str) -> bool:
    """The read says the message asks to see a picture that is no boxes-and-arrows diagram:
    a maths, physics or chemistry picture, or anyone's photo or painting of a thing. A
    Mermaid card is then no answer to it. An everyday or code diagram or graph (an
    architecture, a process, a dependency graph) stays the model's to draw as one, and a
    message that names a flowchart, a flow or tree diagram, a mind map or another such
    diagram keeps it whatever its subject."""
    if decision is None or decision.picture in (None, "none") or is_mermaid_question(line):
        return False
    return decision.subject in READ_SUBJECTS or decision.picture in ("photo", "image")


def owed_kind(decision: TurnDecision | None, ctx: StreamContext) -> Kind | None:
    """The picture the app owes the turn: what the read says a maths, physics or chemistry
    message asks to see; or, with no read in, a picture the reply was asked to describe on
    the message's words (``drawing_turn``)."""
    if decision is None:
        return "diagram" if ctx.drawing is not None and ctx.drawing.asked == "words" else None
    if decision.subject not in READ_SUBJECTS or decision.picture not in DRAWN_PICTURES:
        return None
    picture = decision.picture
    return picture if picture in ("graph", "diagram", "molecule") else None


def shows_a_picture(text: str) -> bool:
    """The reply carries one of the app's pictures."""
    return any(fence.closed and fence.lang in APP_PICTURES for fence in iter_fences(text))


# A picture by name: a diagram, a chart, a graph, a figure, a sketch, a setup.
_NAMES_A_PICTURE = re.compile(
    r"\b(?:diagrams?|flow\s*charts?|charts?|graphs?|plots?|pictures?|figures?|sketch|setup)\b",
    re.IGNORECASE,
)
# A short paragraph beside a flowchart that speaks of it ("That diagram is the simplest way
# to see it", "Here's the setup:"): it goes with the flowchart.
_SPEAKS_OF_IT = re.compile(
    rf"{_NAMES_A_PICTURE.pattern}|\b(?:above|below|shown)\b|:\s*$", re.IGNORECASE
)
# What a colon may still lead into once the picture is gone: a list, maths, a table (or a fence).
_LEADS_INTO = re.compile(r"[-*+]\s|\d+[.)]\s|\$\$|\\\[|\|")
_SHORT = 240


def without_flowcharts(text: str) -> str:
    """The reply with its Mermaid cards out, and the one short paragraph just before or
    after each that speaks of it."""
    spans: list[tuple[int, int]] = []
    for fence in iter_fences(text):
        if not fence.closed or fence.lang != _MERMAID:
            continue
        start, end = fence.start, fence.end
        head = text[:start].rstrip()
        cut = head.rfind("\n\n") + 2 if "\n\n" in head else 0
        lead = head[cut:].strip()
        if lead and len(lead) < _SHORT and _SPEAKS_OF_IT.search(lead):
            start = cut
        else:
            rest = text[end:]
            gap = len(rest) - len(rest.lstrip())
            stop = rest.find("\n\n", gap)
            tail = rest[gap : stop if stop >= 0 else len(rest)].strip()
            if not lead and tail and len(tail) < _SHORT and _SPEAKS_OF_IT.search(tail):
                end += stop if stop >= 0 else len(rest)
        spans.append((start, end))
    for start, end in reversed(_merged(spans)):
        text = text[:start] + text[end:]
    return re.sub(r"\n{3,}", "\n\n", text) if spans else text


def _merged(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Spans that overlap as one: two flowcharts may each take the paragraph between them,
    and cut one after the other the second cut's end would run past the text (review)."""
    merged: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def held_to_the_ask(text: str, ctx: StreamContext, language: str) -> str:
    """The reply with no stand-in for the picture asked, and the line when none was drawn."""
    decision = answered_read(ctx.live_read)
    line = ctx.user_message_content or ""
    out = text
    if mermaid_stands_in(decision, line) and (dropped := without_flowcharts(out)) != out:
        out = dropped.strip()
    # A reply that was only a flowchart taken out, or only its picture's description,
    # dropped, says the picture was not drawn: never an empty reply. A photo or a painting
    # asked for is no drawing the app owes: its reply keeps its words with no line (review).
    emptied = not out.strip() and (out != text or ctx.drawing is not None)
    kind = owed_kind(decision, ctx) or ("diagram" if emptied else None)
    if kind is None or shows_a_picture(out):
        return out
    return with_the_line(out, not_drawn_line(kind, language))


def _leads_into(following: str) -> bool:
    """The paragraph after a lead is something it leads into: a list, maths, a table, a fence."""
    fence = next(iter_fences(following), None)
    return _LEADS_INTO.match(following) is not None or (fence is not None and fence.start == 0)


def with_the_line(text: str, note: str) -> str:
    """``text`` with ``note`` in place of the paragraph that presented the picture not drawn
    (a picture pass took the fence it led into, and its "Here is the graph:" would say one is
    shown just above the line saying none is), else after the text (review)."""
    parts = re.split(r"(\n[ \t]*\n)", text.strip())
    for at in range(0, len(parts), 2):
        lead = parts[at].strip()
        following = parts[at + 2].lstrip() if at + 2 < len(parts) else ""
        # A paragraph that presents a picture ("Here is the v-t graph of the motion:"): it
        # names one and ends on a colon, leading into what is no longer there.
        presents = lead.endswith(":") and _NAMES_A_PICTURE.search(lead) is not None
        if len(lead) < _SHORT and presents and not _leads_into(following):
            parts[at] = note
            return "".join(parts).strip() + "\n"
    return f"{text.rstrip()}\n\n{note}\n" if text.strip() else f"{note}\n"


async def settle_owed_picture(state: FinalizeState) -> str:
    """Finalize's pass: ``held_to_the_ask`` on the reply, committed when it changed."""
    ctx = state.ctx
    # A reply cut off owes no picture: the phone says it was cut off and offers Continue,
    # and the picture may come with the rest (a length cut is no cancel, ``cut_off``).
    if state.cut_off:
        return state.text
    locale = ctx.user.locale if ctx.user is not None else None
    text = held_to_the_ask(state.text, ctx, line_language(ctx.user_message_content or "", locale))
    if text != state.text:
        # Committed, so a later pass that falls back keeps the line.
        state.committed = fallback_text(text, server_text=state.server_text)
    return text
