"""Replay the previous physics problem when this line only continues it.

Three shapes, and each declines instead of guessing: explain the result, ask
for another quantity of the same setup, or replace one named given. A new
question that brings its own data is not a follow-up.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from app.modules.physics.ask_words import _DIMENSIONLESS, _MONEY, _QUANTITIES
from app.modules.physics.extract import extract_physics_intent, needs_physics
from app.modules.physics.givens import ANGLE, PHYSICS_UNITS
from app.services.law_binding.fit import read_givens
from app.services.law_binding.givens import Given
from app.services.law_binding.units import unit_dimension

PHYSICS_FOLLOWUP_HINT = (
    "This short request continues the immediately preceding physics problem. "
    "Explain that verified result: why the formula applies and how the numbers "
    "produce it. Do not start a new problem. Copy the verified numbers; do not "
    "recompute them. When the request changes one given or asks for a different "
    "quantity, the verified block is that new result."
)

_EXPLAIN = re.compile(
    r"^(?:"
    r"why(?: is (?:it|that)(?: [-+]?\d+(?:\.\d+)?(?: [a-zμµ°/^0-9.]+)?)?)?"
    r"|how(?: come| did you get (?:that|it)| does that work)?"
    r"|i (?:didn't|did not|don't|do not) (?:get|understand)(?: it)?"
    r"|help me understand(?: it)?"
    r"|(?:that(?:'s| is)|this is|i(?:'m| am)) confus(?:ed|ing)"
    r")$"
)
_ABOUT = re.compile(r"^(?:and )?what about (?:the |its )?(?P<ask>[a-z][a-z ]{0,40}?)\??$")
_CHANGED = re.compile(
    r"^(?:but )?(?:what )?if "
    r"(?:it (?:was|were|is) |"
    r"(?:the )?(?P<name>[a-z][a-z ]{0,30}?) (?:was|were|is) )"
    r"(?P<value>[-+]?(?:\d+(?:\.\d+)?|\.\d+)(?:e[-+]?\d+)?) ?"
    r"(?P<unit>[a-zμµ°/^0-9][a-zμµ°/^0-9. ]{0,16})?\??$"
)
_ASK_SENTENCE = re.compile(r"\b(?:find|what|calculate|determine|how)\b", re.IGNORECASE)
_NAME_FILLER = re.compile(r"\b(?:final|initial|the|its|a|an)\b")


def physics_followup_problem(query: str | None, recent: Sequence[Any]) -> str | None:
    """The problem to verify again, or None when this line is not that follow-up."""
    line = _line(query)
    prior = _prior_problem(recent)
    if line is None or prior is None or extract_physics_intent(line) is not None:
        return None
    if _EXPLAIN.fullmatch(line):
        return prior
    about = _ABOUT.fullmatch(line)
    if about is not None:
        return _another_quantity(prior, about.group("ask"))
    changed = _CHANGED.fullmatch(line)
    if changed is not None:
        return _changed_given(
            prior, changed.group("name"), changed.group("value"), changed.group("unit")
        )
    return None


def _line(query: str | None) -> str | None:
    if not query or not query.strip():
        return None
    text = " ".join(query.replace("\u2019", "'").split()).strip(" \"'`")
    text = text.strip(".,!?:;").lower()
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
    if not needs_physics(prior):
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
    if phrase not in _QUANTITIES and phrase not in {
        "range",
        "time of flight",
        "maximum height",
        "max height",
        "impact speed",
    }:
        return None
    parts = re.split(r"(?<=[.?!])\s+", prior.strip())
    replacement = f"Find the {phrase}."
    if parts and _ASK_SENTENCE.search(parts[-1]):
        parts[-1] = replacement
        rewritten = " ".join(parts)
    else:
        rewritten = prior.rstrip(".?! ") + ". " + replacement
    return rewritten if _verifies(rewritten) else None


def _changed_given(prior: str, name: str | None, value: str, unit: str | None) -> str | None:
    if not unit or not unit.strip():
        return None
    written_unit = " ".join(unit.split())
    new_dim = _dimension_of_unit(written_unit)
    if new_dim is None:
        return None
    if name:
        named = _NAME_FILLER.sub(" ", name)
        named = " ".join(named.split())
        named_dim = _dimension_of_phrase(named)
        if named_dim is None or named_dim != new_dim:
            return None
    matches = [given for given in read_givens(prior, PHYSICS_UNITS) if given.dimension == new_dim]
    if len(matches) != 1:
        return None
    rewritten = _replace_given(prior, matches[0], value, written_unit)
    if rewritten == prior:
        return None
    return rewritten if _verifies(rewritten) else None


def _verifies(text: str) -> bool:
    """True when one operation answers this wording, including the ask guard."""
    intent = extract_physics_intent(text)
    if intent is None:
        return False
    from app.core.config import get_settings
    from app.modules.physics.block import build_verified_physics_block

    return build_verified_physics_block(intent, get_settings()) is not None


def _dimension_of_unit(unit: str) -> str | None:
    reading = unit_dimension(PHYSICS_UNITS.expression(unit) or "")
    return None if reading is None else reading[0]


def _dimension_of_phrase(phrase: str) -> str | None:
    expression = _QUANTITIES.get(phrase)
    if expression is None:
        return None
    if expression in {ANGLE, _DIMENSIONLESS, _MONEY}:
        return expression
    reading = unit_dimension(expression)
    return None if reading is None else reading[0]


def _replace_given(text: str, given: Given, value: str, unit: str) -> str:
    end = given.end
    tail = text[end:]
    old_unit = re.match(r"[ \t]*" + re.escape(given.unit), tail, re.IGNORECASE)
    if old_unit is not None:
        end += old_unit.end()
    return text[: given.start] + f"{value} {unit}" + text[end:]
