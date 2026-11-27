"""The model's own drawing of a physics situation, taken out where the server's picture is.

A box in ASCII art reads as broken rows of symbols on the phone, and a Mermaid "circuit"
above the real schematic is a second, wrong one. Electric fields came as rows of slashes and
arrows in code blocks, and as tables of slashes (live, 2026-11-16). A sketch is a plain block
drawn in slashes, bars and arrows, or a plot in characters (``services.sketches``, the
rule maths uses), or a table whose cells hold no letter and no digit; a data table, a
derivation or a LaTeX block stays. A user who asked for a flowchart or a Mermaid diagram
keeps theirs.
"""

from __future__ import annotations

import re

from app.services.md_fence_scan import iter_fences
from app.services.sketches import (
    PLAIN_FENCE_TAGS,
    asks_for_a_diagram,
    is_arrow_sketch,
    is_text_plot,
)

_MODEL_DIAGRAM_LANGS = frozenset({"mermaid"})


# A border a text table draws: bars, dashes, pluses, equals signs and colons.
_BORDER = frozenset("|+-=: ")


def _drawn_row(row: str) -> bool:
    """A row of ink with no word or number in it, and a stroke no table border makes: "|
    ~~~~  ~~~~ |" is a pipe's flow drawn in tildes."""
    inked = row.strip()
    return bool(inked) and not any(c.isalnum() for c in inked) and not set(inked) <= _BORDER


def _boxed_art(rows: list[str]) -> bool:
    """A picture boxed in bars ("|---- Pipe Wall ----|" over rows of "~~~~"): every row
    starts and ends with a bar or a corner, and two or more are drawn, not written (a pipe in
    text fences on a physics turn, textbook round 2026-11-25). A text table's borders are no
    drawing."""
    inked = [row.strip() for row in rows if row.strip()]
    framed = all(row[0] in "|+" and row[-1] in "|+" for row in inked)
    return len(inked) >= 3 and framed and sum(_drawn_row(row) for row in inked) >= 2


# A table's frame in any characters: plain ("+---+", "|"), light, heavy, rounded or
# double box drawing; and the bars between its cells.
_TABLE_BORDER = frozenset(
    "+-=:|_ ─━│┃┄┅┆┇┈┉┊┋┌┍┎┏┐┑┒┓└┕┖┗┘┙┚┛├┝┞┟┠┡┢┣┤┥┦┧┨┩┪┫┬┭┮┯┰┱┲┳┴┵┶┷┸┹┺┻┼┽┾┿╀╁╂╃╄╅╆╇╈╉╊╋"
    "═║╒╓╔╕╖╗╘╙╚╛╜╝╞╟╠╡╢╣╤╥╦╧╨╩╪╫╬╭╮╯╰"
)
_TABLE_BAR = "|│┃║┆┇┊┋"


def _framed_table(rows: list[str]) -> bool:
    """A data table in characters, whatever its frame ("+-------+--------+" over "| A |
    20 m/s |", "┌───┬───┐" over "│ t │ v │", rounded or heavy): every row a border or cells
    between bars, two or more of them holding a word or a number. A table, never a sketch
    or a plot (review of #2603)."""
    inked = [row.strip() for row in rows if row.strip()]
    cells = [row for row in inked if not set(row) <= _TABLE_BORDER]
    if len(inked) < 2 or not cells:
        return False
    for row in cells:
        if row[0] not in _TABLE_BAR or row[-1] not in _TABLE_BAR:
            return False
        parts = re.split(f"[{re.escape(_TABLE_BAR)}]", row)[1:-1]
        if sum(any(c.isalnum() for c in part) for part in parts) < 2:
            return False
    return True


def _sketch(rows: list[str]) -> bool:
    if _framed_table(rows):
        return False
    inked = [row for row in rows if row.strip()]
    return is_arrow_sketch(rows) or is_text_plot(inked) or _boxed_art(rows)


# A drawing in characters the user asked for ("show laminar flow as ASCII art"): theirs, as
# the physics pack allows (``reply_policy.PHYSICS_NO_SKETCH``, "unless the user asks").
_ASKS_TEXT_ART = re.compile(
    r"\bascii\b|\btext[\s-]?(?:art|diagram|drawing|sketch|picture)s?\b"
    r"|\b(?:in|with|using)\s+(?:keyboard\s+|plain[\s-]text\s+)?characters\b",
    re.IGNORECASE,
)


def asks_for_text_art(user_text: str) -> bool:
    return _ASKS_TEXT_ART.search(user_text or "") is not None


def without_sketches(text: str) -> str:
    """``text`` without its sketches in plain blocks: a physics reply's picture drawn in
    characters, which the physics pack forbids and the phone shows as broken rows (u8-17 of
    a textbook round drew laminar flow as rows of tildes in ```text blocks)."""
    drawings = [
        (fence.start, fence.end)
        for fence in iter_fences(text)
        if fence.closed
        and fence.lang in PLAIN_FENCE_TAGS
        and _sketch(text[fence.body_start : fence.body_end].split("\n"))
    ]
    if not drawings:
        return text
    for start, end in reversed(drawings):
        # A heading over nothing but the sketch ("### Streamline Flow") goes with it.
        heading = _HEADING_BEFORE.search(text, 0, start)
        rest = text[end:].lstrip()
        if heading is not None and (not rest or rest.startswith("#")):
            start = heading.start()
        text = text[:start] + text[end:]
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


# A markdown heading line just before a fence, with only blank lines between them.
_HEADING_BEFORE = re.compile(r"(?m)^#{1,6}[ \t][^\n]*\n\s*\Z")


def without_model_drawings(text: str, user_text: str = "") -> str:
    """``text`` without the model's own pictures: sketches in plain blocks or in tables, and
    a Mermaid diagram the user did not ask for."""
    keep_diagrams = asks_for_a_diagram(user_text)
    drawings = [
        (fence.start, fence.end)
        for fence in iter_fences(text)
        if (fence.lang in _MODEL_DIAGRAM_LANGS and not keep_diagrams)
        or (
            fence.lang in PLAIN_FENCE_TAGS
            and _sketch(text[fence.body_start : fence.body_end].split("\n"))
        )
    ]
    original = text
    for start, end in reversed(drawings):
        text = text[:start] + text[end:]
    text = _without_drawn_tables(text)
    return re.sub(r"\n{3,}", "\n\n", text).strip() if text != original else text


def _without_drawn_tables(text: str) -> str:
    """A table whose cells hold no letter and no digit is a drawing: ``| \\ | | / |``."""
    lines = text.split("\n")
    fenced = _fenced_lines(text)
    kept: list[str] = []
    index = 0
    changed = False
    while index < len(lines):
        end = index
        while end < len(lines) and end not in fenced and _table_row(lines[end]):
            end += 1
        table = lines[index:end]
        if len(table) >= 3 and _table_rule(table[1]) and _drawn_table(table):
            index, changed = end, True
            continue
        kept.extend(table or [lines[index]])
        index = max(end, index + 1)
    return "\n".join(kept) if changed else text


def _table_row(line: str) -> bool:
    row = line.strip()
    return len(row) > 1 and row.startswith("|") and row.endswith("|")


def _table_rule(line: str) -> bool:
    """The rule under a table's header: bars, dashes, colons and spaces, "---" in it."""
    return "--" in line and set(line.strip()) <= set("|-: ")


def _drawn_table(table: list[str]) -> bool:
    cells = [
        cell.strip() for row in (table[0], *table[2:]) for cell in row.strip().strip("|").split("|")
    ]
    inked = [cell for cell in cells if cell]
    return len(inked) >= 3 and not any(char.isalnum() for cell in inked for char in cell)


def _fenced_lines(text: str) -> set[int]:
    """The line numbers inside fences: a table in a code block is the code's."""
    inside: set[int] = set()
    for fence in iter_fences(text):
        first = text.count("\n", 0, fence.start)
        last = text.count("\n", 0, fence.end)
        inside.update(range(first, last + 1))
    return inside
