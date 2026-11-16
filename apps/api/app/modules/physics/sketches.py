"""The model's own drawing of a physics situation, taken out where the server's picture is.

A box in ASCII art reads as broken rows of symbols on the phone, and a Mermaid "circuit"
above the real schematic is a second, wrong one. Electric fields came as rows of slashes and
arrows in code blocks, and as tables of slashes (live, 2026-11-16): a sketch is any plain
block or table drawn in symbols, not one shape of it. A user who asked for a flowchart or a
Mermaid diagram keeps theirs.
"""

from __future__ import annotations

import re

from app.services.md_fence_scan import iter_fences

# A plain block may hold a sketch; a tagged one (python, math) never does.
_PLAIN_FENCE_LANGS = frozenset({"", "text", "txt", "plaintext", "ascii"})
_MODEL_DIAGRAM_LANGS = frozenset({"mermaid"})
_ASKED_FOR_DIAGRAM = re.compile(
    r"\b(?:flow[\s-]?charts?|mermaid|sequence diagram|mind[\s-]?maps?|state diagram)\b",
    re.IGNORECASE,
)
# Box-drawing lines, arrows and blocks, or a run of slashes, bars and dashes.
_DRAWN = re.compile(r"[←-⇿─-╿■-◿]|[-_|/\\]{3,}|[/\\]\s*$")
# Most of a drawn row is symbols: "\  |  /", "->  ^  <-", "( + )", "+ + + +".
_DRAWN_SHARE = 0.6


def asks_for_a_diagram(user_text: str) -> bool:
    """The user asked for a flowchart or a Mermaid diagram of their own."""
    return _ASKED_FOR_DIAGRAM.search(user_text) is not None


def _drawn_row(row: str) -> bool:
    ink = [char for char in row if not char.isspace()]
    if not ink:
        return False
    if _DRAWN.search(row):
        return True
    symbols = sum(not char.isalnum() for char in ink)
    return len(ink) >= 3 and symbols / len(ink) >= _DRAWN_SHARE


def _sketch_rows(rows: list[str]) -> bool:
    """Two rows or more drawn in symbols, and more of them drawn than written."""
    inked = [row for row in rows if row.strip()]
    drawn = sum(_drawn_row(row) for row in inked)
    return drawn >= 2 and drawn * 2 >= len(inked)


def without_model_drawings(text: str, user_text: str = "") -> str:
    """``text`` without the model's own pictures: sketches in plain blocks or in tables, and
    a Mermaid diagram the user did not ask for."""
    keep_diagrams = asks_for_a_diagram(user_text)
    drawings = [
        (fence.start, fence.end)
        for fence in iter_fences(text)
        if (fence.lang in _MODEL_DIAGRAM_LANGS and not keep_diagrams)
        or (
            fence.lang in _PLAIN_FENCE_LANGS
            and _sketch_rows(text[fence.body_start : fence.body_end].split("\n"))
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
