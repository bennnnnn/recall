# ruff: noqa: RUF001, RUF002, RUF003 -- the module reads − and ᵀ as a question writes them.
"""Whether a question writes its vectors as columns, as a textbook prints them.

A column vector reaches the server in several spellings: LaTeX
(``\\begin{pmatrix}5\\\\2\\end{pmatrix}``), its entries stacked in a bracket one a line as the
phone and a scan flatten the printed column ("[ 5\\n2]"), split by semicolons on one line
("[5; 2]"), a row transposed ("(5, 2)^T") or a tall bracket's pieces, one entry a line
(⎡5⎤ over ⎣2⎦). The owner's ball question (2026-11-25) gave its velocity so and was answered
in î and ĵ; the reply keeps the question's notation (``chat.worked_turn`` tells the model so).
A question in î and ĵ, in a size and an angle, with an interval ([0, 5]), a point ((2, 3)) or
a matrix (⎡1 2⎤ over ⎣3 4⎦) writes no column.

The one-line semicolon form is also how French, Russian and Portuguese write a closed
interval ("sur [0 ; 5]", "на отрезке [−1; 1]", "[0 ; 5] s"), so it is a column only beside a
sign that it is a vector: a unit after it from a closed table of what a vector quantity is
measured in (a velocity, an acceleration, a force, a momentum: "[3; -1] m/s"), or a vector's
symbol set to it ("\\vec{a} = [3; 4]"; a unit vector \\vec{i} is none). The message's words
never reach Pint, which reads prose as units ("c" is light's speed) and evaluates a written
power. An entry may be written with a decimal comma ("2,5"), without its leading zero (".5")
or as a simple fraction ("1/2"); the transposed row, whose entries a comma separates, reads a
decimal point only.
"""

from __future__ import annotations

import re

from app.services.column_vector import writes_column
from app.services.law_binding.units import UnitTable

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
# Entries split by semicolons in square brackets, a column typed on one line: [5; 2].
_SEMICOLONS = re.compile(
    rf"\[[ \t]*+{_ENTRY.pattern}[ \t]*+(?:;[ \t]*+{_ENTRY.pattern}[ \t]*+){{1,2}}\]"
)
# A row transposed: (5, 2)^T, [5, 2]ᵀ.
_TRANSPOSED = re.compile(
    rf"[\[(][ \t]*+{_ROW_ENTRY.pattern}[ \t]*+(?:,[ \t]*+{_ROW_ENTRY.pattern}[ \t]*+){{1,2}}[\])][ \t]*+(?:\^[ \t]*+\{{?T\}}?|ᵀ)"
)
# A tall bracket's pieces, one entry a line, as a scan or SymPy prints a column: ⎡5⎤ ⎢ ⎥ ⎣2⎦.
# A line with two numbers between its pieces is a matrix's row, never a column's.
_TALL = re.compile(
    rf"[⎛⎡][ \t]*+{_ENTRY.pattern}[ \t]*+[⎞⎤][ \t]*+\r?\n"
    rf"(?:[^\n⎛⎡⎝⎣]{{0,24}}?[⎜⎢][ \t]*+(?:{_ENTRY.pattern}[ \t]*+)?[⎟⎥][ \t]*+\r?\n){{0,3}}"
    rf"[^\n⎛⎡⎝⎣]{{0,24}}?[⎝⎣][ \t]*+{_ENTRY.pattern}[ \t]*+[⎠⎦]"
)
# A vector's symbol set to the bracket after it: "\vec{v} = [", "\overrightarrow{AB} = [",
# "v⃗ = [". A unit vector (\vec{i}) names a direction, not this vector.
_NAMED = re.compile(
    r"(?:\\vec[ \t]*+(?:\{(?![ijk]\})[^{}\n]{1,12}\}|(?![ijk](?![A-Za-z]))[A-Za-z])"
    r"|\\overrightarrow[ \t]*+\{[^{}\n]{1,12}\}|[A-Za-z]⃗)"
    r"(?:_\{?\w{1,6}\}?)?[ \t]*+=[ \t]*+\$?[ \t]*+$"
)
# What a vector quantity is written in after its column: a velocity, an acceleration, a force,
# a momentum. A closed table of spellings, read by pattern only.
_VECTOR_UNITS = UnitTable(
    {
        "m/s": "meter / second",
        "cm/s": "centimeter / second",
        "km/h": "kilometer / hour",
        "m s^-1": "meter / second",
        "ms^-1": "meter / second",
        "m/s^2": "meter / second ** 2",
        "m s^-2": "meter / second ** 2",
        "ms^-2": "meter / second ** 2",
        "N": "newton",
        "kN": "kilonewton",
        "N s": "newton * second",
        "N·s": "newton * second",
        "Ns": "newton * second",
        "kg m/s": "kilogram * meter / second",
        "kg·m/s": "kilogram * meter / second",
        "kg m s^-1": "kilogram * meter / second",
        "kgm/s": "kilogram * meter / second",
        "м/с": "meter / second",
        "м/с^2": "meter / second ** 2",
        "Н": "newton",
        "кг·м/с": "kilogram * meter / second",
        "кг м/с": "kilogram * meter / second",
    },
    {},
)
# How far back a vector's name may stand before its bracket.
_NAME_REACH = 40
_LIMIT = 4000


def writes_column_vectors(text: str) -> bool:
    """The message writes a vector as a column, in any spelling above."""
    message = text[:_LIMIT]
    if writes_column(message) or _TALL.search(message):
        return True
    if _STACKED.search(message) or _TRANSPOSED.search(message):
        return True
    return any(
        _VECTOR_UNITS.at(message, found.end()) is not None
        or _NAMED.search(message[max(0, found.start() - _NAME_REACH) : found.start()]) is not None
        for found in _SEMICOLONS.finditer(message)
    )
