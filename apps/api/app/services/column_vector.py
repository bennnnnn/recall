"""A column vector as maths writes it: ``\\begin{pmatrix}5\\\\2\\end{pmatrix}``.

A textbook writes a velocity as a column, 5 over 2 in brackets, and its answer the same
way. The owner's ball question (2026-11-25) gave its velocity so and was answered in î and
ĵ: a turn whose question writes columns is answered in columns
(``turn_reading.vector_notation`` reads the question), and the worked layout writes a
column's unit beside it and rounds each of its entries by the card's rule
(``chat.worked_figures``), as it does a single value.
"""

from __future__ import annotations

import re
from collections.abc import Callable

# A matrix environment that draws a vector: no bracket, round or square ones. A bar or a
# brace one (vmatrix, Bmatrix) is a determinant or a set.
MATRIX = re.compile(r"\\begin\{(?P<env>[pb]?matrix)\}(?P<body>[^$]*?)\\end\{(?P=env)\}")
# The markup around and between a matrix's entries, which names no symbol.
MATRIX_MARKUP = re.compile(r"\\(?:begin|end)\{[pb]?matrix\}|\\\\")
# An entry that is a number alone.
_NUMBER = re.compile(r"[ \t]*+(?P<sign>[-\u2212]?)[ \t]*+(?P<digits>\d+(?:\.\d+)?)[ \t]*+")
_ROW_BREAK = "\\\\"
_LIMIT = 4000


def column_entries(body: str) -> list[str] | None:
    """A matrix body's entries when it is one column of two or three (``5\\\\2``); None for a
    row, a grid or a single entry."""
    rows = [row.strip() for row in body.split(_ROW_BREAK)]
    rows = rows[:-1] if rows and not rows[-1] else rows
    if not 2 <= len(rows) <= 3 or any(not row or "&" in row for row in rows):
        return None
    return rows


def writes_column(tex: str) -> bool:
    """``tex`` holds a column vector written as a matrix."""
    return any(column_entries(found["body"]) for found in MATRIX.finditer(tex[:_LIMIT]))


def without_matrix_markup(tex: str) -> str:
    """``tex`` with a matrix's environment and row breaks blanked: what is left is its
    entries, so a column of numbers reads as numbers, never as the letters of "pmatrix"."""
    return MATRIX_MARKUP.sub(" ", tex)


def columns_as_values(tex: str, mark: str) -> str:
    """``tex`` with each column of numbers written as ``mark``: a column is one value, never
    the subtraction its row break and minus sign ("4\\\\-3") read as."""
    return MATRIX.sub(lambda found: mark if _numbers(found) is not None else found[0], tex)


def _numbers(found: re.Match[str]) -> list[re.Match[str]] | None:
    """A matrix's entries, each read as one number, when it is a column of numbers."""
    entries = column_entries(found["body"])
    numbers = [_NUMBER.fullmatch(entry) for entry in entries or ()]
    if not numbers or any(number is None for number in numbers):
        return None
    return [number for number in numbers if number is not None]


def round_column(tex: str, shown: Callable[[float], str]) -> str | None:
    """``tex``, one column of numbers whole, with each entry written by ``shown`` (the card's
    rounding) in the bracket it was written in; None when ``tex`` is no such column."""
    found = MATRIX.fullmatch(tex.strip())
    numbers = _numbers(found) if found is not None else None
    if found is None or numbers is None:
        return None
    written = []
    for number in numbers:
        value = float(number["digits"])
        written.append(shown(-value if number["sign"] and value else value))
    env = found["env"]
    return rf"\begin{{{env}}}" + _ROW_BREAK.join(written) + rf"\end{{{env}}}"
