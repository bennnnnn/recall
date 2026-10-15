"""Replay the previous chemistry problem when this line only continues it.

Each shape declines instead of guessing: explain the result, ask for another
quantity of the same setup ("and the pOH?"), or replace or scale one given
("and 0.001 M?", "what if the concentration doubles?"). A new
question that brings its own data is not a follow-up. Exact phrases such as
``why`` and ``explain`` stay on the shared continuation list; this resolver
is the line that is not one of those phrases.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from app.modules.chemistry.extract import extract_chemistry_intent
from app.modules.chemistry.given_units import CHEMISTRY_UNITS
from app.modules.chemistry.request import is_chemistry_question
from app.services.law_binding.fit import read_givens
from app.services.law_binding.units import dimension_of
from app.services.problem_followup import (
    EXPLAIN_RE,
    adjacent_problem,
    ask_replaced,
    followup_line,
    given_name,
    new_value,
    replace_given,
    scaled_given,
    scaled_value,
)

CHEMISTRY_FOLLOWUP_HINT = (
    "This short request continues the immediately preceding chemistry problem. "
    "Explain that verified result: why the formula applies and how the numbers "
    "produce it. Do not start a new problem. Copy the verified numbers; do not "
    "recompute them. When the request changes one given or asks for a different "
    "quantity, the verified block is that new result."
)

# The asked word as the catalog writes it. A rewrite is accepted only when the
# verified find or answer names this word, so an extractor that ignores the ask
# cannot verify the previous law.
_ASKS = {
    "ph": "pH",
    "poh": "pOH",
    "pka": "pKa",
    "pkb": "pKb",
    "ka": "Ka",
    "kb": "Kb",
    "molar mass": "molar mass",
    "density": "density",
    "molality": "molality",
    "percent ionization": "percent ionization",
    "equilibrium constant": "equilibrium constant",
    "enthalpy": "enthalpy",
    "absorbance": "absorbance",
    "ionic strength": "ionic strength",
    "optical purity": "optical purity",
    "partition coefficient": "partition coefficient",
    "heat": "heat",
}
_NAMED_DIMENSIONS = {
    "concentration": "mole / liter",
    "molarity": "mole / liter",
    "mass": "gram",
    "volume": "liter",
    "temperature": "kelvin",
    "pressure": "atmosphere",
    "molality": "mole / kilogram",
}
_ABOUT = re.compile(
    r"^(?:(?:and )?(?:what|how) about |and |now )(?:the |its )?(?P<ask>[a-z][a-z' ]{0,40}?)\??$"
)
_CHANGED = re.compile(
    r"^(?:but )?(?:what )?if "
    r"(?:it (?:was|were|is) |"
    r"(?:the )?(?P<name>[A-Za-z][A-Za-z ]{0,30}?) (?:was|were|is) )"
    r"(?P<value>[-+]?(?:\d+(?:\.\d+)?|\.\d+)(?:e[-+]?\d+)?) ?"
    r"(?P<unit>[A-Za-zμµ°/^0-9][A-Za-zμµ°/^0-9. ]{0,16})?\??$",
    re.IGNORECASE,
)


def chemistry_followup_problem(query: str | None, recent: Sequence[Any]) -> str | None:
    """The problem to verify again, or None when this line is not that follow-up."""
    text = followup_line(query)
    prior = adjacent_problem(recent, is_chemistry_question)
    if text is None or prior is None or extract_chemistry_intent(text) is not None:
        return None
    folded = text.lower()
    if EXPLAIN_RE.fullmatch(folded):
        return prior
    about = _ABOUT.fullmatch(folded)
    if about is not None:
        return _another_quantity(prior, about.group("ask"))
    changed = _CHANGED.fullmatch(text)
    if changed is not None:
        return _changed_given(
            prior, changed.group("name"), changed.group("value"), changed.group("unit")
        )
    scaled = scaled_given(text)
    if scaled is not None:
        return _scaled_given(prior, *scaled)
    value = new_value(text)
    if value is not None:
        return _changed_given(prior, None, *value)
    return None


def _scaled_given(prior: str, name: str, factor: float) -> str | None:
    """``what if the concentration doubles``: the one given of that kind, times the factor."""
    named_dim = _dimension_of_phrase(given_name(name).lower())
    if named_dim is None:
        return None
    givens = read_givens(prior, CHEMISTRY_UNITS)
    matches = [given for given in givens if given.dimension == named_dim]
    if len(matches) != 1:
        return None
    given = matches[0]
    rewritten = replace_given(prior, given, scaled_value(given.value, factor), given.unit)
    return rewritten if rewritten != prior and _verifies(rewritten) else None


def _another_quantity(prior: str, ask: str) -> str | None:
    phrase = " ".join(ask.split())
    written = _ASKS.get(phrase)
    if written is None:
        return None
    rewritten = ask_replaced(prior, written)
    return rewritten if _verifies(rewritten, ask=written) else None


def _changed_given(prior: str, name: str | None, value: str, unit: str | None) -> str | None:
    if not unit or not unit.strip():
        return None
    written_unit = " ".join(unit.split())
    new_dim = _dimension_of_unit(written_unit)
    if new_dim is None:
        return None
    if name:
        named_dim = _dimension_of_phrase(given_name(name).lower())
        if named_dim is None or named_dim != new_dim:
            return None
    matches = [given for given in read_givens(prior, CHEMISTRY_UNITS) if given.dimension == new_dim]
    if len(matches) != 1:
        return None
    rewritten = replace_given(prior, matches[0], value, written_unit)
    if rewritten == prior:
        return None
    return rewritten if _verifies(rewritten) else None


def _verifies(text: str, *, ask: str | None = None) -> bool:
    """True when one operation answers this wording, including the asked word."""
    intent = extract_chemistry_intent(text)
    if intent is None:
        return False
    from app.modules.chemistry.block import build_verified_chemistry

    verified = build_verified_chemistry(intent)
    if verified is None:
        return False
    if ask is None:
        return True
    haystack = f"{verified.result.find} {verified.result.answer}".lower()
    return re.search(rf"(?<![a-z0-9]){re.escape(ask.lower())}(?![a-z0-9])", haystack) is not None


def _dimension_of_unit(unit: str) -> str | None:
    return dimension_of(CHEMISTRY_UNITS.expression(unit) or "")


def _dimension_of_phrase(phrase: str) -> str | None:
    expression = _NAMED_DIMENSIONS.get(phrase)
    return None if expression is None else dimension_of(expression)
