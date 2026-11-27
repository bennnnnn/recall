"""Working written again outside the laid-out ```worked blocks goes: the layout is the solution.

The contract asks for the whole solution inside a block and nothing outside it, and a model
still wrote it twice: after the layout's last card "Here are the step-by-step solutions for
each part of your problem:" and every part again in $$ lines, or the whole derivation as
prose above **Given**, or after the card a visible re-check ("Let's verify: …" and the sums
once more; Grade 11 physics round, 2026-11-26). A second working is never what the student
needs: one solution, its answer once (owner, worked layout).

Only what says the blocks again goes, never working they do not hold (review of #2602):

- Every block the stream laid out is known (``WorkedFilter.laid_out``), and each stays: two
  blocks, one per part, are two parts, never a repeat of each other. An earlier pass may
  have changed a line of one (an emoji out of a heading), so it is found by its first and
  last lines.
- Text outside them holds a working when its prose works three sums or more as maths
  (``$v = 4 \\times 3$``, ``$$t = \\frac{0.79}{0.1}$$``). A value stated alone is no sum:
  ``$u = 0$``, ``$\\theta = 30^\\circ$``, ``$g = 9.8 m/s^2$``, ``$c = 3 \\times 10^8$``.
- Such a working repeats the blocks piece by piece: a piece whose sums write only numbers
  the blocks or the question hold (a rounding of one too) is the working said again and
  goes, with the words after it up to a sum of their own. A number of its own makes it new
  working, a part the blocks left out, and it stays; so does a part under a label the
  blocks do not letter ("**(c) Time to stop**").
- The words before the first repeat stay (a graph described in words), every fence stays,
  and after the last block so does a closing one-line summary (owner, 2026-11-12), never a
  generic closer in its place. A heading stays only with what it heads. A question that
  asks for a proof or an explanation (``asks_reasoning``) keeps it all.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from app.modules.chat.generic_closer import drop_generic_closer
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
# A sum worked in it: an operation beside the relation. A minus sign before a number
# ("a = -1.2") is no operation.
_OPERATION = re.compile(
    r"[+\u00d7\u00f7*/^]|(?<=[\w)}])\s*[-\u2212]|\\(?:times|cdot|frac|dfrac|sqrt|div)\b"
)
# How a value is written, never a sum (reviews of #2602): a unit group, one level nested,
# and its power after it ("\mathrm{m/s}^2", "\mathrm{m\,s^{-2}}"); a unit written bare after
# a number ("20 m/s", "9.8 m/s^2"); degrees ("30^\circ"); a power of ten ("3 \times 10^8").
_UNIT_GROUP = re.compile(
    r"\\(?:mathrm|text|textrm|operatorname)\s*\{(?:[^{}]|\{[^{}]*\})*\}"
    r"(?:\^\s*(?:\{[^{}]*\}|-?\d))?"
    r"|(?<=\d)\s*(?:\\[,;!: ]|~)?\s*[A-Za-z\u00b5\u03a9]+(?:/[A-Za-z]+)+"
    r"(?:\^\s*(?:\{[^{}]*\}|-?\d))?"
    r"|\^\s*\{?\s*\\circ\s*\}?"
    r"|(?:\\times|\\cdot|\u00d7)\s*10\s*\^\s*(?:\{[^{}]*\}|-?\d+)"
)
# Three sums set as maths are a working; one or two are a sentence's.
_WORKING_RELATIONS = 3
_PARAGRAPH_BREAK = re.compile(r"\n[ \t]*\n")
# A number as written; never a script's ("v_1", "x^2").
_NUMBER = re.compile(r"(?<![\w.^_{])-?\d+(?:\.\d+)?")
# Numbers any working writes: a half, a square, a power of ten.
_EVERYWHERE = frozenset({0.0, 1.0, 2.0, 10.0})
# A part's label at a piece's start: "**a) Initial velocity**", "**(c) Time to stop**",
# "**Part (b): …", "### (c) …".
_PART_LABEL = re.compile(
    r"^\s*(?:#{1,4}\s+)?(?:\*\*)?\s*(?:part\s+)?\(?(?P<letter>[a-h])\)(?=[\s.:*])", re.I
)
# A part's letter in the layout's own headings: "**(a) Initial velocity**", "**Answer (b)**".
_LAYOUT_LETTER = re.compile(r"\*\*(?:Answer\s+)?\((?P<letter>[a-h])\)")
# A piece that only heads or introduces what follows it: "**Part (b): Greatest
# acceleration**", "### Calculation details", "Here are the solutions:". A bold sentence
# ("**The wheel turns at 0.79 rad/s.**") states something, as ``worked_lead`` reads it.
_HEADS = re.compile(r"(?:#{1,4}[ \t][^\n]*|\*\*[^*\n]*[^*.!?\s]\*\*:?|[^\n]*:\**)\s*")


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


def _written(text: str) -> list[str]:
    return _NUMBER.findall(text.replace("\u2212", "-"))


class _Held:
    """The numbers the blocks and the question hold, a rounding of one included: a second
    working rounds them its own way (3.084 for the block's 3.0843)."""

    def __init__(self, texts: list[str]) -> None:
        self._values = sorted({float(number) for text in texts for number in _written(text)})

    def holds(self, written: str) -> bool:
        value = float(written)
        if abs(value) in _EVERYWHERE:
            return True
        step = 0.5 * 10 ** -len(written.partition(".")[2])
        return any(abs(value - held) <= max(step, 0.005 * abs(held)) for held in self._values)


def _repeats(piece: str, held: _Held) -> bool:
    """The piece works sums, and every number in it is one the blocks hold: the working
    said again. One number of its own makes it new working (a part the block left out)."""
    written = _written(piece)
    return bool(written) and all(held.holds(number) for number in written)


_ANCHOR = "x."


def _is_closer(piece: str) -> bool:
    """The piece is a generic closer, as the closer pass reads one: that pass leaves a reply
    that is nothing else, so the piece is read after a line of its own."""
    return drop_generic_closer(f"{_ANCHOR}\n\n{piece}").strip() == _ANCHOR


def _summary(piece: str) -> bool:
    """One short line that works no sum, heads nothing and is no generic closer ("Let me
    know if you have any other questions!", the closer pass's): the summary the owner wants."""
    return (
        is_one_line_summary(piece)
        and not relations_in(piece)
        and not _HEADS.fullmatch(piece)
        and not _is_closer(piece)
    )


def _kept(
    pieces: list[tuple[str, bool]], held: _Held, letters: set[str], *, closing: bool
) -> list[bool]:
    """Which pieces outside the blocks stay (module docstring)."""
    keep: list[bool] = []
    own_part = after_repeat = False
    for piece, prose in pieces:
        label = _PART_LABEL.match(piece) if prose else None
        if label is not None:
            # A part the blocks do not letter is one they left out; a block of one part
            # letters none, and a recap's own "a)" is no part of its own.
            own_part = bool(letters) and label["letter"].lower() not in letters
            after_repeat = False
        if not prose or own_part:
            keep.append(True)
            continue
        if relations_in(piece):
            after_repeat = _repeats(piece, held)
        keep.append(not after_repeat)
    if closing:
        last = next(
            (
                at
                for at in range(len(pieces) - 1, -1, -1)
                if pieces[at][1] and _summary(pieces[at][0])
            ),
            None,
        )
        if last is not None:
            keep[last] = True
    # A heading or an introduction stays only with what it heads.
    for at in range(len(pieces) - 1, -1, -1):
        piece, prose = pieces[at]
        if keep[at] and prose and _HEADS.fullmatch(piece):
            keep[at] = at + 1 < len(pieces) and keep[at + 1]
    return keep


def _without_repeats(text: str, held: _Held, letters: set[str], *, closing: bool) -> str | None:
    """``text`` without the working it says again; None when it holds no working (fewer
    than three sums) or repeats none of it."""
    pieces = _pieces(text)
    if sum(relations_in(piece) for piece, prose in pieces if prose) < _WORKING_RELATIONS:
        return None
    keep = _kept(pieces, held, letters, closing=closing)
    if all(keep):
        return None
    return "\n\n".join(piece for (piece, _prose), kept in zip(pieces, keep, strict=True) if kept)


# How far the block's end may move: an earlier pass changes a line or two of it (an emoji
# out of a heading, a fence the model drew), never the whole block.
_MOST_MOVED = 300


def _occurrences(text: str, line: str, start: int = 0) -> list[int]:
    found: list[int] = []
    at = text.find(line, start)
    while at >= 0:
        found.append(at)
        at = text.find(line, at + 1)
    return found


def _block_span(plain: str, layout: str, start: int) -> tuple[int, int] | None:
    """Where one laid-out block stands in ``plain``, from ``start`` on: the block as laid
    out, else (a pass changed a line of it) the span from a copy of its first line to a
    copy of its last whose length is nearest the block's. None when it cannot be found."""
    block = straighten_apostrophes(layout).strip()
    exact = plain.find(block, start) if block else -1
    if exact >= 0:
        return exact, exact + len(block)
    lines = [line.strip() for line in block.split("\n") if line.strip()]
    if not lines:
        return None
    spans = [
        (first, end + len(lines[-1]))
        for first in _occurrences(plain, lines[0], start)
        for end in _occurrences(plain, lines[-1], first)
    ]
    best = min(spans, key=lambda span: abs(span[1] - span[0] - len(block)), default=None)
    if best is None or abs(best[1] - best[0] - len(block)) > _MOST_MOVED:
        return None
    return best


def _block_spans(text: str, layouts: tuple[str, ...]) -> list[tuple[int, int]] | None:
    """Each laid-out block's span, in order; None when any is not found. Straightening an
    apostrophe keeps every offset: one character for one."""
    plain = straighten_apostrophes(text)
    spans: list[tuple[int, int]] = []
    cursor = 0
    for layout in layouts:
        span = _block_span(plain, layout, cursor)
        if span is None:
            return None
        spans.append(span)
        cursor = span[1]
    return spans


def drop_working_again(text: str, layouts: tuple[str, ...], question: str = "") -> str:
    """``text`` without the working said again around ``layouts``, the ```worked blocks as
    the server laid them out: above, between or after them. As it was when a block is not
    found in it, or when the question asks for reasoning."""
    if not any(layout.strip() for layout in layouts) or asks_reasoning(question):
        return text
    spans = _block_spans(text, layouts)
    if not spans:
        return text
    held = _Held([*layouts, question])
    letters = {found["letter"] for layout in layouts for found in _LAYOUT_LETTER.finditer(layout)}
    bounds = [0, *(at for span in spans for at in span), len(text)]
    pieces: list[str] = []
    changed = False
    for index in range(0, len(bounds), 2):
        outside = text[bounds[index] : bounds[index + 1]]
        kept = _without_repeats(outside, held, letters, closing=index == len(bounds) - 2)
        changed = changed or kept is not None
        pieces.append(outside if kept is None else kept)
        if index + 2 < len(bounds):
            pieces.append(text[bounds[index + 1] : bounds[index + 2]])
    if not changed:
        return text
    joined = "\n\n".join(piece.strip("\n") for piece in pieces if piece.strip())
    return joined + ("\n" if text.endswith("\n") else "")


def drop_working_again_pass(state: FinalizeState) -> str:
    """The finalize pass: a reply with laid-out blocks loses the working said again outside
    them."""
    ctx = state.ctx
    if state.server_text or ctx.worked is None:
        return state.text
    return drop_working_again(state.text, ctx.worked_layouts, ctx.user_message_content or "")
