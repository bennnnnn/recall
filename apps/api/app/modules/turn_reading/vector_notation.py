# ruff: noqa: RUF001, RUF002, RUF003 -- the module reads − and ᵀ as a question writes them.
"""Whether a question writes its vectors as columns, as a textbook prints them.

A column vector reaches the server in several spellings: LaTeX
(``\\begin{pmatrix}5\\\\2\\end{pmatrix}``), its entries stacked in a bracket one a line as the
phone and a scan flatten the printed column ("[ 5\\n2]"), split by semicolons on one line
("[5; 2]"), a row transposed ("(5, 2)^T") or a tall bracket's pieces (⎛ ⎝). The owner's
ball question (2026-11-25) gave its velocity so and was answered in î and ĵ; the reply keeps
the question's notation (``chat.worked_turn`` tells the model so). A question in î and ĵ, in
a size and an angle, or with an interval ([0, 5]) or a point ((2, 3)) writes no column.

The one-line semicolon form is also how French, Russian and Portuguese write a closed
interval ("sur [0 ; 5]", "на отрезке [−1; 1]", "[0 ; 5] s"), so it is a column only beside a
sign that it is a vector: a unit after it that measures a vector quantity (a velocity, an
acceleration, a force, a momentum: "[3; -1] m/s"), or a vector's symbol in the message
(``\\vec``, an arrow over a letter). An entry may be written with a decimal comma ("2,5"),
without its leading zero (".5") or as a simple fraction ("1/2"); the transposed row, whose
entries a comma separates, reads a decimal point only.
"""

from __future__ import annotations

import re

from app.services.column_vector import writes_column
from app.services.law_binding.units import dimension_of

# One entry of a stacked or semicolon column: a signed number (a decimal point or comma, a
# simple fraction) or a letter. Compiled, so no reader of the prompt's copy takes a pattern
# for a rule.
_ENTRY = re.compile(r"[-+−]?[ \t]*+(?:\d*+[.,]\d++|\d++(?:/\d++)?|[A-Za-z])")
# One entry of a transposed row, which commas separate.
_ROW_ENTRY = re.compile(r"[-+−]?[ \t]*+(?:\d*+\.\d++|\d++(?:/\d++)?|[A-Za-z])")
# Entries stacked in a bracket, one a line.
_STACKED = re.compile(
    rf"[\[(][ \t]*+{_ENTRY.pattern}[ \t]*+(?:\r?\n[ \t]*+{_ENTRY.pattern}[ \t]*+){{1,2}}\r?\n?[ \t]*+[\])]"
)
# Entries split by semicolons in square brackets, a column typed on one line: [5; 2], and the
# words after it, where a unit stands.
_SEMICOLONS = re.compile(
    rf"\[[ \t]*+{_ENTRY.pattern}[ \t]*+(?:;[ \t]*+{_ENTRY.pattern}[ \t]*+){{1,2}}\]"
    r"(?P<after>[ \t]*+[^\s,;.!?()\[\]]++(?:[ \t]++[^\s,;.!?()\[\]]++){0,2})?"
)
# A row transposed: (5, 2)^T, [5, 2]ᵀ.
_TRANSPOSED = re.compile(
    rf"[\[(][ \t]*+{_ROW_ENTRY.pattern}[ \t]*+(?:,[ \t]*+{_ROW_ENTRY.pattern}[ \t]*+){{1,2}}[\])][ \t]*+"
    r"(?:\^[ \t]*+\{?T\}?|ᵀ)"
)
# A tall bracket's top and bottom pieces, as a scan of a printed column reads them.
_TALL_TOP = re.compile(r"[⎛⎡]")
_TALL_BOTTOM = re.compile(r"[⎝⎣]")
# A vector's symbol: \vec{v}, \overrightarrow{AB}, an arrow combined over a letter (v⃗).
_VECTOR_SYMBOL = re.compile(r"\\(?:vec|overrightarrow)(?![A-Za-z])|\u20d7")
# What a vector quantity is measured in: a velocity, an acceleration, a force, a momentum.
_VECTOR_DIMENSIONS = frozenset(
    {
        "[length]^1 * [time]^-1",
        "[length]^1 * [time]^-2",
        "[length]^1 * [mass]^1 * [time]^-2",
        "[length]^1 * [mass]^1 * [time]^-1",
    }
)
_LIMIT = 4000


def writes_column_vectors(text: str) -> bool:
    """The message writes a vector as a column, in any spelling above."""
    message = text[:_LIMIT]
    if writes_column(message):
        return True
    if _TALL_TOP.search(message) and _TALL_BOTTOM.search(message):
        return True
    if _STACKED.search(message) or _TRANSPOSED.search(message):
        return True
    symbol = _VECTOR_SYMBOL.search(message) is not None
    return any(
        symbol or _vector_unit(found["after"] or "") for found in _SEMICOLONS.finditer(message)
    )


def _vector_unit(after: str) -> bool:
    """The words after a column start with the unit of a vector quantity ("m/s is struck",
    "kg m/s"); a time ("s"), a length or no unit is an interval's."""
    words = after.split()
    return any(
        dimension_of(" ".join(words[:count])) in _VECTOR_DIMENSIONS
        for count in range(len(words), 0, -1)
    )
