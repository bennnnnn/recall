"""The shapes of a worked answer's value: two values in one record, a vector's components,
a value that writes its own unit (the owner's chat, 2026-11-20: two cars at right angles)."""

from __future__ import annotations

import re

from app.modules.chat.worked_solution import Answer
from app.modules.chat.worked_units import unit_tex
from app.services.final_value import UNIT_VECTOR

# A thousands comma, never two values: "1,000".
_THOUSANDS = re.compile(r"\d,\d{3}(?!\d)")


def top_level(tex: str, mark: str) -> list[str]:
    """``tex`` split at each ``mark`` outside any group or bracket, each piece stripped of a
    spacing command around it (``,\\ ``). A mark a command writes (``\\,``, a thin space) or
    a thousands comma splits nothing."""
    pieces, depth, start = [], 0, 0
    for at, char in enumerate(tex):
        if char in "({[":
            depth += 1
        elif char in ")}]":
            depth -= 1
        elif (
            char == mark
            and depth == 0
            and not _escaped(tex, at)
            and not _THOUSANDS.match(tex, at - 1)
        ):
            pieces.append(tex[start:at])
            start = at + 1
    pieces.append(tex[start:])
    return [piece.strip().removeprefix("\\ ").removesuffix("\\").strip() for piece in pieces]


def _escaped(tex: str, at: int) -> bool:
    """The character at ``at`` follows one backslash: ``\\,`` is a command, not a comma."""
    before = len(tex[:at]) - len(tex[:at].rstrip("\\"))
    return before % 2 == 1


def one_value_each(answer: Answer) -> list[Answer]:
    """Two quantities answered in one record ("v_A, v_B | (0\\hat{i} + 20\\hat{j}) m/s,
    (-16\\hat{i}) m/s"), each with its own value: one answer each, the note on the last."""
    symbols = top_level(answer.symbol, ",")
    values = top_level(answer.value, ",")
    if len(symbols) < 2 or len(values) != len(symbols) or not all(symbols) or not all(values):
        return [answer]
    last = len(symbols) - 1
    return [
        answer.model_copy(
            update={"symbol": symbol, "value": value, "note": answer.note if at == last else ""}
        )
        for at, (symbol, value) in enumerate(zip(symbols, values, strict=True))
    ]


_DEGREES = frozenset({"°", "deg", "degree", "degrees", "\\circ", "^\\circ"})


def writes_its_unit(tex: str, unit: str) -> bool:
    """The value writes its unit itself ("(-16\\hat{i})\\ \\mathrm{m/s}"): never twice. An
    angle that writes its degree sign ("150°", "30^\\circ") has its unit: "150°^\\circ"
    drew two (2026-11-21)."""
    if unit.strip().lower() in _DEGREES and ("°" in tex or "\\circ" in tex):
        return True
    upright = unit_tex(unit).removeprefix("\\,")
    return bool(upright) and upright in tex


def a_sum(tex: str) -> bool:
    """A vector's components, terms on unit vectors joined by a plus or a minus outside any
    group: ``3\\hat{i} + 4\\hat{j}``. A power of ten (``1.5e-3``) or a range is no sum."""
    if UNIT_VECTOR.search(tex) is None:
        return False
    depth = 0
    for at, char in enumerate(tex):
        if char in "({[":
            depth += 1
        elif char in ")}]":
            depth -= 1
        elif char in "+-" and depth == 0 and tex[:at].strip():
            return True
    return False
