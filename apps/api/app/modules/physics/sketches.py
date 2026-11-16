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


def _sketch(rows: list[str]) -> bool:
    return is_arrow_sketch(rows) or is_text_plot([row for row in rows if row.strip()])


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
