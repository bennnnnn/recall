"""Which letters of a written expression the writer used as names.

Implicit multiplication splits any letter run it cannot resolve, so a parse
can hold symbols nobody wrote: ``log2(x)`` became ``2*g*l*o*x`` and ``5 kg``
became ``5*g*k``. Each then solved as ordinary algebra and was certified.

Two more spellings are not names either. A unit after a number is part of a
quantity: "v = 3 x 10^8 m/s" solved for m, "t = 2.02 s" for s and "m/q =
1.25 x 10^-6 kg/C" for C. A letter with a subscript (``P1``, ``V2``, ``v0``,
``NH3``) names one quantity, which single-letter algebra would read as ``P·1``
or ``V²``. A parse that holds either is not what was written.

Nor is a name the parser does not know. A model's reading of "the cube root of 27a^3 + …"
wrote ``cube_root(27a^3 + …)``: the parser made ``cube_root`` one symbol times the
polynomial, "simplified" it to itself and certified the question as its answer
(2026-11-01). ``cuberoot(8)`` would have been the letters c·u·b·e·r·o·o·t times 8. A name
must be a function or constant SymPy knows, a Greek letter, a letter with a subscript
(``x_1``), a name the caller declared, or one-letter variables written together (``ab``,
``abc``): never a word.
"""

from __future__ import annotations

import re
from typing import Any

import sympy

from app.modules.math.function_names import MATH_FUNCTION_NAMES, names_longest_first
from app.modules.math.match.letter_runs import MATH_MULTI_LETTER
from app.modules.math.solve.discrete import GREEK_NAMES
from app.services.solving import SolveServiceError

# Longest first, so ``sinh`` is not read as ``sin`` + ``h``.
_FUNCTION_WORDS = names_longest_first(MATH_FUNCTION_NAMES)
_PREFIXED_UNIT = r"kg|km|cm|mm|mg|mL|ml|ms|mol|kJ|kN|kW|kPa|hPa|Pa|Hz|hrs?|min|mph|atm"
# SI symbols that are also school variables, so they count as units only after a
# number: inside a compound unit, or alone at the end of the side.
_SI_LETTER = r"[mgshNJWVACKL]"
_UNIT = rf"(?:{_PREFIXED_UNIT}|{_SI_LETTER})(?:\^-?\d)?"
# The number may end in a digit or in the bracket of a folded power: ``10^(-6) kg``.
_UNIT_AFTER_NUMBER_RE = re.compile(
    rf"[\d)]\s*(?:{_PREFIXED_UNIT})\b"
    rf"|[\d)]\s*{_UNIT}(?:\s*/\s*{_UNIT})+(?![A-Za-z])"
    rf"|[\d)](?:\s+{_UNIT})+\s*$"
)
_LETTER_RUN_RE = re.compile(r"[^\W\d_]+")
# ``P1``, ``Ka2``, ``CO2``: a capitalised name with digits. ``x0`` and ``v1``: one
# lowercase letter with 0 or 1, which is never the glued power ``x2`` is.
_SUBSCRIPTED = re.compile(r"(?<![A-Za-z\\])(?:([A-Z][A-Za-z]*)\d|[a-z][01](?!\d))")


def _written_letters(text: str) -> set[str]:
    """Single letters the writer used as names, not inside a function or unit word."""
    letters: set[str] = set()
    for run in _LETTER_RUN_RE.findall(_UNIT_AFTER_NUMBER_RE.sub(" ", text)):
        lowered = run.lower()
        for word in _FUNCTION_WORDS:
            if lowered.startswith(word):
                run = run[len(word) :]
                break
        letters.update(run)
    return letters


def _subscripted(text: str) -> bool:
    return any(
        match.group(1) is None or match.group(1).lower() not in MATH_FUNCTION_NAMES
        for match in _SUBSCRIPTED.finditer(text)
    )


def reject_unwritten_symbols(expr: str, parsed: Any) -> None:
    """Every one-letter symbol must be a letter the writer wrote as a name.

    A subscripted name fails even when nothing is left of it: ``2v0/g`` parses as 0.
    """
    names = {symbol.name for symbol in getattr(parsed, "free_symbols", ()) if len(symbol.name) == 1}
    if _subscripted(expr) or (names and not names <= _written_letters(expr)):
        raise SolveServiceError(f"Could not parse expression: {expr}")


# A name in the parser's own text (``_normalize_expr``): not the e of ``2e5``, nor a digit run.
_NAME = re.compile(r"(?<![\w.])[A-Za-z_][A-Za-z0-9_]*")
_KNOWN_NAMES = frozenset(sympy.__all__) | MATH_MULTI_LETTER | frozenset(GREEK_NAMES)
# ``x_1``, ``a_n``, ``theta_0``: one letter, or a Greek one, with a subscript.
_SUBSCRIPTED_NAME = re.compile(rf"(?:[A-Za-z]|{'|'.join(GREEK_NAMES)})_[A-Za-z0-9]+")
# One-letter variables written together are at most three (``abc`` in a^3 + b^3 + c^3 - 3abc).
_MAX_PRODUCT = 3


def reject_unknown_names(normalized: str, declared: set[str]) -> None:
    """Every name in the parser's text is one it knows, or letters written together.

    A word (four letters or more, a letter twice, or three applied to a bracket like
    ``fog(x)``) is a name nobody defined, and so is one joined by ``_`` (``cube_root``).
    """
    for match in _NAME.finditer(normalized):
        name = match.group()
        if len(name) == 1 or name in declared or name in _KNOWN_NAMES:
            continue
        if name.lower() in _KNOWN_NAMES or _SUBSCRIPTED_NAME.fullmatch(name):
            continue
        applied = normalized[match.end() : match.end() + 1] == "("
        if (
            not name.isalpha()
            or len(name) > _MAX_PRODUCT
            or len(set(name)) < len(name)
            or (applied and len(name) == _MAX_PRODUCT)
        ):
            raise SolveServiceError(f"Could not parse expression: {name}")


def defined_variable(lhs: str, rhs: str | None = None) -> str | None:
    """``E = 2 + 3`` defines E, an energy: Euler's number is never what an equation defines.

    Given the other side, E is the unknown only when that side names no other letter:
    ``E = mc^2`` is a formula, whose E is still a quantity (``lone_quantity``).
    """
    if lhs.strip() != "E":
        return None
    return "E" if rhs is None or _written_letters(rhs) <= {"e", "E"} else None


def lone_quantity(expr: str) -> list[str]:
    """A side that is only ``E`` names the quantity E, which SymPy would read as e."""
    return ["E"] if expr.strip() == "E" else []
