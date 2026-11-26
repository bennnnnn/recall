"""Working written outside the laid-out ```worked block goes: the layout is the solution.

The contract asks for the whole solution inside the block and nothing outside it, and a model
still wrote it twice: after the layout's last card "Here are the step-by-step solutions for
each part of your problem:" and every part again in $$ lines, or the whole derivation as
prose above **Given**, or after the card a visible re-check ("Let's verify: …" and the sums
once more, with numbers of its own; Grade 11 physics round, 2026-11-26). A second working
is never what the student needs: one solution, its answer once (owner, worked layout).

The block's own text is known (``WorkedFilter`` keeps the last one it laid out), so what
lies outside it is read by where it stands, never by what it says; an earlier pass may have
changed a line of it (an emoji out of a heading), so it is found by its first and last
lines. Text there whose prose works three sums or more as maths (``$v = 4 \\times 3$``,
``$$t = \\frac{0.79}{0.1}$$``) holds a second working; a value stated alone (``$u = 0$``, an
assumption) is no sum, and a sentence with one sum in it (a caveat, a direction) is no
working, so that text stays whole. Above the block such a working goes, but for its fences.
After it, the words before the first sum stay (a graph described in words that the block
left out), and so do every fence and a closing one-line summary (owner, 2026-11-12); from
the first sum on, the prose goes, with a heading left over it. A question that asks for a
proof or an explanation (``asks_reasoning``) keeps it all: the words may be what was asked.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from app.modules.turn_reading.question_kinds import asks_reasoning
from app.services.closing_summary import is_one_line_summary
from app.services.md_fence_scan import iter_fences
from app.services.text_normalize import straighten_apostrophes

if TYPE_CHECKING:
    from app.modules.chat.finalize_passes import FinalizeState

# Maths in a reply: a display, or inline maths on one line.
_MATHS = re.compile(r"\$\$(?P<display>.+?)\$\$|(?<![\\$])\$(?P<inline>[^$\n]+?)\$", re.DOTALL)
# A relation in it, with a number: "v = 4", "t \approx 7.85"; never "\le" alone or "<=".
_RELATION = re.compile(r"(?<![<>!\\])=|\\approx\b")
_DIGIT = re.compile(r"\d")
# A sum worked in it: an operation beside the relation. "$u = 0$" (an assumption) states a
# value and works nothing.
# A unit's letters ("m/s^2") and a minus sign before a number ("a = -1.2") are no operation.
_OPERATION = re.compile(
    r"[+\u00d7\u00f7*/^]|(?<=[\w)}])\s*[-\u2212]|\\(?:times|cdot|frac|dfrac|sqrt|div)\b"
)
_UNIT_GROUP = re.compile(r"\\(?:mathrm|text|textrm|operatorname)\s*\{[^{}]*\}")
# Three equations set as maths are a working; one or two are a sentence's sum.
_WORKING_RELATIONS = 3
_PARAGRAPH_BREAK = re.compile(r"\n[ \t]*\n")


def relations_in(prose: str) -> int:
    """How many pieces of maths in ``prose`` work a sum: a relation, a number, an operation."""
    count = 0
    for found in _MATHS.finditer(prose):
        body = _UNIT_GROUP.sub(" ", found["display"] or found["inline"] or "")
        count += bool(_RELATION.search(body) and _DIGIT.search(body) and _OPERATION.search(body))
    return count


def _pieces(text: str) -> list[tuple[str, bool]]:
    """``text`` in pieces, each with whether it is prose: a fence is one piece, and the
    prose between fences a piece per paragraph."""
    pieces: list[tuple[str, bool]] = []
    cursor = 0
    for fence in [*iter_fences(text), None]:
        stop = len(text) if fence is None else fence.start
        pieces += [
            (paragraph.strip("\n"), True)
            for paragraph in _PARAGRAPH_BREAK.split(text[cursor:stop])
            if paragraph.strip()
        ]
        if fence is not None:
            pieces.append((text[fence.start : fence.end].strip("\n"), False))
            cursor = fence.end
    return pieces


# A piece that only heads or introduces what follows it: "**Part (b): Greatest
# acceleration**", "### Calculation details", "Here are the solutions:".
_HEADS = re.compile(r"(?:#{1,4}[ \t][^\n]*|\*\*[^*\n]+\*\*:?|[^\n]*:\**)\s*")


def _summary(piece: str) -> bool:
    """One short line that works no sum and heads nothing: the summary the owner wants."""
    return is_one_line_summary(piece) and not relations_in(piece) and not _HEADS.fullmatch(piece)


def _kept_tail(pieces: list[tuple[str, bool]]) -> list[bool]:
    """Which pieces after the block stay: the words before the working starts again (a
    description the block did not give: "To draw the graph, plot time …"), every fence,
    and a closing one-line summary; from the first piece that works a sum, the prose goes."""
    again = next(at for at, (piece, prose) in enumerate(pieces) if prose and relations_in(piece))
    keep = [at < again or not prose for at, (_piece, prose) in enumerate(pieces)]
    last = max((at for at, (_piece, prose) in enumerate(pieces) if prose), default=-1)
    if last >= again and _summary(pieces[last][0]):
        keep[last] = True
    # A heading or an introduction stays only with what it heads.
    for at in range(len(pieces) - 1, -1, -1):
        piece, prose = pieces[at]
        if keep[at] and prose and _HEADS.fullmatch(piece):
            keep[at] = at + 1 < len(pieces) and keep[at + 1]
    return keep


def _without_working(text: str, *, closing: bool) -> str | None:
    """``text`` without its working when its prose holds one, None when it holds none: above
    the block only its fences stay, after it ``_kept_tail``."""
    pieces = _pieces(text)
    if sum(relations_in(piece) for piece, prose in pieces if prose) < _WORKING_RELATIONS:
        return None
    keep = _kept_tail(pieces) if closing else [not prose for _piece, prose in pieces]
    return "\n\n".join(piece for (piece, _prose), kept in zip(pieces, keep, strict=True) if kept)


# How far the block's end may move: an earlier pass changes a line or two of it (an emoji
# out of a heading, a fence the model drew), never the whole block.
_MOST_MOVED = 300


def _block_span(text: str, layout: str) -> tuple[int, int] | None:
    """Where the laid-out block stands in ``text``: from its first line to its last, the
    occurrence of the last nearest where the block as laid out would end (the working said
    again may repeat that line). None when it cannot be found."""
    lines = [line.strip() for line in straighten_apostrophes(layout).split("\n") if line.strip()]
    plain = straighten_apostrophes(text)
    if not lines or len(plain) != len(text):
        return None
    start = plain.find(lines[0])
    if start < 0:
        return None
    expected = start + len(layout.strip())
    ends: list[int] = []
    at = plain.find(lines[-1], start)
    while at >= 0:
        ends.append(at + len(lines[-1]))
        at = plain.find(lines[-1], at + 1)
    end = min(ends, key=lambda end: abs(end - expected), default=None)
    if end is None or abs(end - expected) > _MOST_MOVED:
        return None
    return start, end


def drop_working_again(text: str, layout: str, question: str = "") -> str:
    """``text`` without the working written again around ``layout``, the ```worked block as
    the server laid it out: above it or after it. As it was when the block is not found in
    it, or when the question asks for reasoning."""
    span = _block_span(text, layout) if layout.strip() else None
    if span is None or asks_reasoning(question):
        return text
    start, end = span
    lead, tail = text[:start], text[end:]
    kept_lead = _without_working(lead, closing=False)
    kept_tail = _without_working(tail, closing=True)
    if kept_lead is None and kept_tail is None:
        return text
    pieces = (
        lead if kept_lead is None else kept_lead,
        text[start:end],
        tail if kept_tail is None else kept_tail,
    )
    joined = "\n\n".join(piece.strip("\n") for piece in pieces if piece.strip())
    return joined + ("\n" if text.endswith("\n") else "")


def drop_working_again_pass(state: FinalizeState) -> str:
    """The finalize pass: a reply with a laid-out block loses the working outside it."""
    ctx = state.ctx
    if state.server_text or ctx.worked is None:
        return state.text
    return drop_working_again(state.text, ctx.worked_layout, ctx.user_message_content or "")
