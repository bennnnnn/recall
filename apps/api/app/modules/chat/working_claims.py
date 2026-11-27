"""A claim the working makes in names that its own values contradict.

"Energy check: … giving $\\tfrac{1}{2}mv_5^2 = 405.5$ J, the same as the kinematics value"
(live, 2026-11-27): with the working's own m = 10 kg and v₅ = 5.66 m/s, ½mv₅² is 160.3 J,
so the two do not agree and the check says nothing. A side written only in names and simple
factors (½, 2, π, powers), each name with one value in the working, said to equal a number,
is worked out with those values; when it is another number by more than the slack a rounding
chain has, it is a claim the working does not bear out.

An equation solved for its unknown is no claim: a name that a statement of numbers is
solved for ("2.8 = 1.1 + 0.05F", "19.6H = 156.25") takes its value from that equation, so
no claim is held to it, and a side with a number of its own (1.1 - 0.05F) is an equation, not
a formula. Pure: no IO; nothing is eval-ed.
"""

from __future__ import annotations

import ast
import itertools
import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pint.errors import PintError

from app.modules.chat.tex_arithmetic import math_statement_spans, plain_arithmetic
from app.modules.chat.working_check import NAME, statement_parts
from app.modules.chat.working_numbers import shown_number
from app.modules.chat.working_units import (
    quantity,
    quantity_unit,
    read_for_certain,
    unit_after,
    with_units,
)

# The Greek letters a name may be; any other command (\frac, \times, \sqrt) is maths.
_GREEK = frozenset(
    "alpha beta gamma delta epsilon varepsilon zeta eta theta vartheta iota kappa lambda mu nu "
    "xi pi rho sigma tau upsilon phi varphi chi psi omega Gamma Delta Theta Lambda Sigma Phi "
    "Psi Omega".split()
)
# A number, a space, then a letter: "5 m" writes a unit, never a product of names.
_NUMBER_THEN_LETTER = re.compile(r"\d\s+[A-Za-z]")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
# A unit or a word in upright type: no names of the working's.
_UPRIGHT = re.compile(r"\\(?:text|mathrm|textrm|rm|operatorname)\s*\{[^{}]*\}")
# The numbers a formula in names may hold of its own: a count or a simple factor (½mv², 2πr).
_PURE_FACTOR = 4
# A claim is held to the slack a rounding chain has: it is said in prose, not worked out.
_CLAIM_SLACK = 0.01


@dataclass(frozen=True)
class Claim:
    """A side in names said to equal a number ("\\tfrac{1}{2}mv_5^2 = 405.5") that the
    working's own values of those names make another: ``value``."""

    left: str
    said: str
    value: float


# A name's value and the unit it was written in (Pint text), as the working has them.
Known = Callable[[str], tuple[float, str] | None]
# Numbers that stand in for the names while the side is worked with units: no reply writes them.
_PLACEHOLDER = 7_000_003


def claims_in(parts: list[str], known: Known, unit_after_maths: str = "") -> list[Claim]:
    """Each side of a statement written in names said to equal the number after it, when
    the working's values of every name (``known``), worked with their units, make it another
    number in the said side's unit (inside the maths, else ``unit_after_maths``: "405.5$ J").
    A name with no unit, or a unit not read for certain, makes no claim."""
    found: list[Claim] = []
    for left, right in itertools.pairwise(parts):
        said_plain = plain_arithmetic(right.strip())
        said = shown_number(said_plain) if said_plain is not None else None
        unit = unit_after(right.strip()) or (unit_after_maths if right is parts[-1] else "")
        value = _in_names(left.strip(), known, unit)
        if said is None or value is None:
            continue
        slack = max(said[1], _CLAIM_SLACK * max(abs(value), abs(said[0])))
        if abs(value - said[0]) > slack * (1 + 1e-9):
            found.append(Claim(left.strip(), right.strip(), value))
    return found


def _in_names(tex: str, known: Known, said_unit: str) -> float | None:
    """A side written in names worked out with the working's one value of each, in
    ``said_unit`` (SI base units when it says none); None when it holds no name, a name with
    no single value or no unit read for certain, a number of its own, a unit or a word."""
    if _NUMBER_THEN_LETTER.search(tex) or _UPRIGHT.search(tex) or not read_for_certain(said_unit):
        return None
    names = names_in(tex)
    if not names or any(not _pure(number) for number in _NUMBER.findall(_without(tex, names))):
        return None
    pieces: list[str] = []
    quantities: dict[str, Any] = {}
    at = 0
    for index, match in enumerate(names):
        read = known(plain_name(match.group(0)))
        if read is None or not read[1]:
            return None
        placeholder = str(_PLACEHOLDER + index)
        value = quantity(read[0], read[1])
        if value is None:
            return None
        quantities[placeholder] = value
        pieces += [tex[at : match.start()], f"({placeholder})"]
        at = match.end()
    plain = plain_arithmetic("".join([*pieces, tex[at:]]))
    if plain is None:
        return None
    try:
        worked = with_units(ast.parse(plain, mode="eval").body, plain, quantities)
    except SyntaxError:
        return None
    return _magnitude(worked, said_unit)


def _magnitude(worked: Any, unit: str) -> float | None:
    """A worked quantity's size in ``unit``, or in SI base units for none; None for no one
    kind."""
    if worked is None:
        return None
    target = quantity_unit(unit) if unit else None
    try:
        result = worked.to(target) if target is not None else worked.to_base_units()
    except (PintError, TypeError, ValueError):
        return None
    number = float(result.magnitude)
    return number if math.isfinite(number) else None


def solved_for(reply: str) -> set[str]:
    """Every name an equation of numbers is solved for: a statement of no single name whose
    sides mix names and numbers other than simple factors ("2.8 = 1.1 + 0.05F", "19.6H =
    156.25"). Its value comes from that equation, so no claim is held to it."""
    unknowns: set[str] = set()
    for segment, _follows, _at in math_statement_spans(reply):
        parts, _starts = statement_parts(segment, 0)
        if len(parts) < 2 or NAME.fullmatch(parts[0].replace(" ", "")):
            continue
        for part in parts:
            bare = _UPRIGHT.sub(" ", part)
            names = names_in(bare)
            if names and any(not _pure(n) for n in _NUMBER.findall(_without(bare, names))):
                unknowns.update(plain_name(match.group(0)) for match in names)
    return unknowns


def _pure(number: str) -> bool:
    return "." not in number and int(number) <= _PURE_FACTOR


def names_in(tex: str) -> list[re.Match[str]]:
    """The names a side writes, never a command of maths (\\frac, \\times)."""
    return [
        match
        for match in NAME.finditer(tex)
        if not match.group(0).startswith("\\") or match.group(0)[1:].split("_")[0] in _GREEK
    ]


def _without(tex: str, names: list[re.Match[str]]) -> str:
    """``tex`` with its names blanked: their subscripts' digits are no numbers."""
    for match in reversed(names):
        tex = f"{tex[: match.start()]} {tex[match.end() :]}"
    return tex


def plain_name(tex: str) -> str:
    """A name without its spacing, braces and upright wrapper: "K_{\\text{rot}}" is K_rot."""
    compact = re.sub(r"\\(?:text|mathrm)\{([^{}]*)\}", r"\1", tex.replace(" ", ""))
    return compact.replace("{", "").replace("}", "")
