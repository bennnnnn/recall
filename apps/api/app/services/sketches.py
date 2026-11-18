"""A picture drawn in text characters: the one rule for what a sketch is.

A model told not to draw still sketches a graph with ``*``, ``|`` and ``_``, a number line
with dots on a dash rule, or a field, a circuit or forces with slashes and arrows; the
phone wraps every such row into broken text. Maths takes out its plots
(``math.text_plot``), physics its situations (``physics.sketches``), both by these rules.
A plain block may hold a sketch; a tagged one (graph, math, python) never does.
"""

from __future__ import annotations

import re

PLAIN_FENCE_TAGS = frozenset({"", "text", "txt", "plaintext", "ascii"})
_WORD = re.compile(r"[A-Za-z]{3,}")
# ``12|``, ``  |``, ``0+--``: the y-axis at the start of a row.
_Y_AXIS = re.compile(r"^\s*[-+]?\d*(?:\.\d+)?\s*[|+](?:\s|$|[-_*•●o/\\])")
_X_AXIS = re.compile(r"[-_]{5,}")
_MARK = re.compile(r"(?<![\w*])[*•●](?![\w*])|(?<![\w])o(?![\w])|[/\\]")
_TABLE_RULE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")
# A number line in characters: one row of line (``─``, ``═``, ``-``) carrying a dot or an
# arrowhead, and rows of numbers under or over it ("-1.2  -3/4  0.5", "9").
_LINE_CHARS = re.compile(r"[─━═=\-_]")
_LINE_MARK = re.compile(r"[●○•◦*oO|<>←→↔]")
_NUMBER_ROW = re.compile("^[\\s\\d.,/+\\-\u2212x]*\\d[\\s\\d.,/+\\-\u2212x]*$")
_LINE_ROW_CHARS = 8


def could_be_plot_row(line: str) -> bool:
    """Axis rows, point rows and tick labels: no math, at most a couple of words."""
    return bool(line.strip()) and "$" not in line and len(_WORD.findall(line)) <= 2


def _is_number_line_sketch(rows: list[str]) -> bool:
    if len(rows) < 2 or len(rows) > 4:
        return False
    lines = [
        row
        for row in rows
        if len(_LINE_CHARS.findall(row)) >= _LINE_ROW_CHARS
        and _LINE_MARK.search(row)
        and not _WORD.search(row)
    ]
    others = [row for row in rows if row not in lines]
    return len(lines) == 1 and bool(others) and all(_NUMBER_ROW.match(row) for row in others)


def is_text_plot(rows: list[str]) -> bool:
    if any(_TABLE_RULE.match(row) for row in rows):
        return False
    if _is_number_line_sketch(rows):
        return True
    if len(rows) < 3:
        return False
    axis = sum(bool(_Y_AXIS.match(row)) for row in rows) >= 3 or any(
        _X_AXIS.search(row) for row in rows
    )
    marked = sum(bool(_MARK.search(row)) for row in rows) >= 2
    return axis and marked


# What points a direction in a drawing: a slash, an arrow written or in characters, a caret,
# a box-drawing line or block.
_DIRECTION = re.compile(r"[/\\^\u2190-\u21ff\u2500-\u257f\u25a0-\u25ff]|->|<-")
_LETTERS = re.compile(r"[^\W\d_]{3,}")
# A slash between two characters of a word or a number is a fraction or a unit ("3/4",
# "m/s"), never a stroke.
_WRITTEN_SLASH = re.compile(r"(?<=\w)/(?=\w)")
# A stroke only a drawing makes: an arrow, a bar, a caret, a backslash, box-drawing.
_REAL_STROKE = re.compile(r"[\\|^\u2190-\u21ff\u2500-\u257f\u25a0-\u25ff]|->|<-")
# A drawn row may carry a short label ("R1", "X"), never a word, a sum or an equation.
_MOST_LABEL = 2


def _drawn_row(row: str) -> bool:
    row = _WRITTEN_SLASH.sub(" ", row)
    ink = [char for char in row if not char.isspace()]
    if len(ink) < 3 or "=" in row or _LETTERS.search(row):
        return False
    labels = sum(char.isalnum() for char in ink)
    if labels > _MOST_LABEL:
        return False
    # A bar alone draws a line of a picture only in a row with no label: "| 1 | 2 |" is a
    # table's row.
    return bool(_DIRECTION.search(row)) or (labels == 0 and "|" in row)


def is_arrow_sketch(rows: list[str]) -> bool:
    """Rows drawing a situation in slashes, bars and arrows: two or more drawn, and more of
    them drawn than written. A table's border ("+------+"), a derivation ("x = 2 ⇒ y = 4")
    and a LaTeX line ending in ``\\\\`` are no drawing."""
    inked = [row for row in rows if row.strip()]
    drawn = sum(_drawn_row(row) for row in inked)
    # A block of slashes alone ("3/4" over "1/2", "m/s" rows) draws nothing: a drawing has
    # a stroke only a drawing makes.
    stroked = any(_REAL_STROKE.search(_WRITTEN_SLASH.sub(" ", row)) for row in inked)
    return drawn >= 2 and drawn * 2 >= len(inked) and stroked


# A flowchart or a Mermaid diagram the user asked for is theirs, never a stand-in to take out.
_ASKED_FOR_DIAGRAM = re.compile(
    r"\b(?:flow[\s-]?charts?|mermaid|sequence diagram|mind[\s-]?maps?|state diagram)\b",
    re.IGNORECASE,
)


def asks_for_a_diagram(user_text: str) -> bool:
    """The user asked for a flowchart or a Mermaid diagram of their own."""
    return _ASKED_FOR_DIAGRAM.search(user_text) is not None
