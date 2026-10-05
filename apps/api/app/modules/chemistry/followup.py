"""Replay the previous chemistry problem when this line only continues it.

Three shapes, and each declines instead of guessing: explain the result, ask
for another quantity of the same setup, or replace one named given. A new
question that brings its own data is not a follow-up. Exact phrases such as
``why`` and ``explain`` stay on the shared continuation list; this resolver
is the line that is not one of those phrases.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from app.modules.chemistry.extract import extract_chemistry_intent
from app.modules.chemistry.given_units import CHEMISTRY_UNITS
from app.modules.chemistry.request import is_chemistry_question
from app.services.law_binding.fit import read_givens
from app.services.law_binding.givens import Given
from app.services.law_binding.units import dimension_of

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
_EXPLAIN = re.compile(
    r"^(?:"
    r"why(?: is (?:it|that)(?: [-+]?\d+(?:\.\d+)?(?: [a-zμµ°/^0-9.]+)?)?)?"
    r"|how(?: come| did you get (?:that|it)| does that work)?"
    r"|i (?:didn't|did not|don't|do not) (?:get|understand)(?: it)?"
    r"|help me understand(?: it)?"
    r"|(?:that(?:'s| is)|this is|i(?:'m| am)) confus(?:ed|ing)"
    r")$"
)
_ABOUT = re.compile(r"^(?:and )?what about (?:the |its )?(?P<ask>[a-z][a-z' ]{0,40}?)\??$")
_CHANGED = re.compile(
    r"^(?:but )?(?:what )?if "
    r"(?:it (?:was|were|is) |"
    r"(?:the )?(?P<name>[A-Za-z][A-Za-z ]{0,30}?) (?:was|were|is) )"
    r"(?P<value>[-+]?(?:\d+(?:\.\d+)?|\.\d+)(?:e[-+]?\d+)?) ?"
    r"(?P<unit>[A-Za-zμµ°/^0-9][A-Za-zμµ°/^0-9. ]{0,16})?\??$",
    re.IGNORECASE,
)
_ASK_SENTENCE = re.compile(r"\b(?:find|what|calculate|determine|how)\b", re.IGNORECASE)
_NAME_FILLER = re.compile(r"\b(?:final|initial|the|its|a|an)\b")


def chemistry_followup_problem(query: str | None, recent: Sequence[Any]) -> str | None:
    """The problem to verify again, or None when this line is not that follow-up."""
    text = _text(query)
    prior = _prior_problem(recent)
    if text is None or prior is None or extract_chemistry_intent(text) is not None:
        return None
    folded = text.lower()
    if _EXPLAIN.fullmatch(folded):
        return prior
    about = _ABOUT.fullmatch(folded)
    if about is not None:
        return _another_quantity(prior, about.group("ask"))
    changed = _CHANGED.fullmatch(text)
    if changed is not None:
        return _changed_given(
            prior, changed.group("name"), changed.group("value"), changed.group("unit")
        )
    return None


def _text(query: str | None) -> str | None:
    if not query or not query.strip():
        return None
    text = " ".join(query.replace("\u2019", "'").split()).strip(" \"'`")
    text = text.strip(".,!?:;")
    return text or None


def _prior_problem(recent: Sequence[Any]) -> str | None:
    if len(recent) < 2:
        return None
    role, prior = _role_content(recent[-2])
    answer_role, answer = _role_content(recent[-1])
    if role != "user" or answer_role != "assistant":
        return None
    if not prior or not prior.strip() or not answer or not answer.strip():
        return None
    if not is_chemistry_question(prior):
        return None
    return prior


def _role_content(message: Any) -> tuple[str | None, str | None]:
    if isinstance(message, tuple) and len(message) == 2:
        role, content = message
        if isinstance(role, str) and isinstance(content, str):
            return role, content
        return None, None
    if isinstance(message, Mapping):
        role = message.get("role")
        content = message.get("content")
    else:
        role = getattr(message, "role", None)
        content = getattr(message, "content", None)
    if not isinstance(role, str) or not isinstance(content, str):
        return None, None
    return role, content


def _another_quantity(prior: str, ask: str) -> str | None:
    phrase = " ".join(ask.split())
    written = _ASKS.get(phrase)
    if written is None:
        return None
    parts = re.split(r"(?<=[.?!])\s+", prior.strip())
    replacement = f"Find the {written}."
    if parts and _ASK_SENTENCE.search(parts[-1]):
        parts[-1] = replacement
        rewritten = " ".join(parts)
    else:
        rewritten = prior.rstrip(".?! ") + ". " + replacement
    return rewritten if _verifies(rewritten, ask=written) else None


def _changed_given(prior: str, name: str | None, value: str, unit: str | None) -> str | None:
    if not unit or not unit.strip():
        return None
    written_unit = " ".join(unit.split())
    new_dim = _dimension_of_unit(written_unit)
    if new_dim is None:
        return None
    if name:
        named = _NAME_FILLER.sub(" ", name)
        named = " ".join(named.split()).lower()
        named_dim = _dimension_of_phrase(named)
        if named_dim is None or named_dim != new_dim:
            return None
    matches = [given for given in read_givens(prior, CHEMISTRY_UNITS) if given.dimension == new_dim]
    if len(matches) != 1:
        return None
    rewritten = _replace_given(prior, matches[0], value, written_unit)
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


def _replace_given(text: str, given: Given, value: str, unit: str) -> str:
    end = given.end
    tail = text[end:]
    old_unit = re.match(r"[ \t]*" + re.escape(given.unit), tail, re.IGNORECASE)
    if old_unit is not None:
        end += old_unit.end()
    return text[: given.start] + f"{value} {unit}" + text[end:]
