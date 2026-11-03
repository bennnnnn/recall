"""Naming a worked reply's givens: the ``where`` line that closes **Given**.

A given is a value on its line (``$v_0 = 20\\,\\mathrm{m/s}$``); what its symbol stands
for is said once, on the line after the givens ("where $v_0$ = initial speed"), in every
subject. A given written with its meaning as a note at its right (``$r = 3$ — radius``) has
that note moved onto the line (``named_givens``): nothing sits at the right edge of a value.
"""

from __future__ import annotations

import re

# The separator of a move's note after its state (``services/workout``).
_NOTE_SEPARATOR = " — "


def note_at(line: str) -> int:
    """Where the move's note separator starts outside maths, or -1."""
    in_math = False
    for at, char in enumerate(line):
        if char == "$":
            in_math = not in_math
        elif not in_math and line.startswith(_NOTE_SEPARATOR, at):
            return at
    return -1


# One symbol set to a stated value (``$r = 3\\,\\mathrm{cm}$``); an equation the student's
# words give (``$m = 3 \\times s$ — "Maria …"``, ``$2x + 3 = 11$ — the problem``) names none.
_GIVEN_VALUE = re.compile(
    r"\$(?P<symbol>\\?[A-Za-z][\w{}\\^']*)\s*=\s*-?\d[\d.,]*(?:\\[,;! ][^$]*)?\$"
)
_MEANING = re.compile(r"[A-Za-z][A-Za-z '-]*")


def named_givens(lines: tuple[str, ...]) -> tuple[str, ...]:
    """A given with its meaning as a note (``$r = 3\\,\\mathrm{cm}$ — radius``) is the
    value alone, and the meaning goes on the ``where`` line closing Given, as every
    subject's: nothing at the right edge of a value (``where_line``)."""
    rows: list[str] = []
    named: list[tuple[str, str]] = []
    for line in lines:
        at = note_at(line)
        value = _GIVEN_VALUE.fullmatch(line[:at].rstrip()) if at >= 0 else None
        meaning = line[at + len(_NOTE_SEPARATOR) :].strip() if value is not None else ""
        if value is None or _MEANING.fullmatch(meaning) is None:
            rows.append(line)
            continue
        rows.append(value.group(0))
        named.append((value.group("symbol").strip(), meaning))
    naming = where_line(named) if named else None
    if naming is None or any(row.startswith("where ") for row in rows):
        return tuple(lines)
    return (*rows, naming)


_IRREGULAR_PLURALS = {"index": "indices"}


def _plural(noun: str) -> str:
    """``mass`` → ``masses``; the last word of a phrase takes the plural."""
    head, _, last = noun.rpartition(" ")
    if last in _IRREGULAR_PLURALS:
        word = _IRREGULAR_PLURALS[last]
    elif last.endswith("y") and last[-2:-1] not in ("a", "e", "i", "o", "u"):
        word = last[:-1] + "ies"  # velocity → velocities
    else:
        word = last + ("es" if last.endswith(("s", "sh", "ch", "x")) else "s")
    return f"{head} {word}" if head else word


def where_line(definitions: list[tuple[str, str]]) -> str | None:
    """``where $v_0$ = initial speed; $m_1$, $m_2$ = masses`` from (symbol, meaning) pairs.

    A symbol named twice is named once; symbols with the same meaning are named together,
    and then semicolons keep one group's commas from running into the next.
    """
    groups: dict[str, list[str]] = {}
    for symbol, meaning in definitions:
        shown = groups.setdefault(meaning, [])
        if symbol not in shown and all(symbol not in other for other in groups.values()):
            shown.append(symbol)
    parts = [
        f"{', '.join(f'${symbol}$' for symbol in symbols)} = "
        + (_plural(meaning) if len(symbols) > 1 else meaning)
        for meaning, symbols in groups.items()
        if symbols
    ]
    grouped = any(len(symbols) > 1 for symbols in groups.values())
    return f"where {('; ' if grouped else ', ').join(parts)}" if parts else None
