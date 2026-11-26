# ruff: noqa: RUF001, RUF003 -- the module reads − and ᵀ as a question writes them.
"""Whether a question writes its vectors as columns, as a textbook prints them.

A column vector reaches the server in several spellings: LaTeX
(``\\begin{pmatrix}5\\\\2\\end{pmatrix}``), its entries stacked in a bracket one a line as the
phone and a scan flatten the printed column ("[ 5\\n2]"), split by semicolons on one line
("[5; 2]"), a row transposed ("(5, 2)^T") or a tall bracket's pieces (⎛ ⎝). The owner's
ball question (2026-11-25) gave its velocity so and was answered in î and ĵ; the reply keeps
the question's notation (``chat.worked_turn`` tells the model so). A question in î and ĵ, in
a size and an angle, or with an interval ([0, 5]) or a point ((2, 3)) writes no column.
"""

from __future__ import annotations

import re

from app.services.column_vector import writes_column

# One entry a column holds: a signed number or a letter.
_ENTRY = r"[-+−]?[ \t]*+(?:\d+(?:\.\d+)?|[A-Za-z])"
# Entries stacked in a bracket, one a line.
_STACKED = re.compile(
    rf"[\[(][ \t]*+{_ENTRY}[ \t]*+(?:\r?\n[ \t]*+{_ENTRY}[ \t]*+){{1,2}}\r?\n?[ \t]*+[\])]"
)
# Entries split by semicolons in square brackets, a column typed on one line: [5; 2].
_SEMICOLONS = re.compile(rf"\[[ \t]*+{_ENTRY}[ \t]*+(?:;[ \t]*+{_ENTRY}[ \t]*+){{1,2}}\]")
# A row transposed: (5, 2)^T, [5, 2]ᵀ.
_TRANSPOSED = re.compile(
    rf"[\[(][ \t]*+{_ENTRY}[ \t]*+(?:,[ \t]*+{_ENTRY}[ \t]*+){{1,2}}[\])][ \t]*+"
    r"(?:\^[ \t]*+\{?T\}?|ᵀ)"
)
# A tall bracket's top and bottom pieces, as a scan of a printed column reads them.
_TALL_TOP = re.compile(r"[⎛⎡]")
_TALL_BOTTOM = re.compile(r"[⎝⎣]")
_LIMIT = 4000


def writes_column_vectors(text: str) -> bool:
    """The message writes a vector as a column, in any spelling above."""
    message = text[:_LIMIT]
    if writes_column(message):
        return True
    if _TALL_TOP.search(message) and _TALL_BOTTOM.search(message):
        return True
    return any(pattern.search(message) for pattern in (_STACKED, _SEMICOLONS, _TRANSPOSED))
