"""Read a question straight into a physics catalog operation, from its givens and its ask.

The extractors are written for the phrasings they know. Many questions just
state a law's inputs and ask for its result in words the catalog can list:
"accelerates from 10 m/s to 30 m/s in 5 s. Find its acceleration." The binder
reads the asked clause (``ask``), finds every operation whose ``Binding`` names
that ask, and fills each from the stated values with the shared engine
(``services.law_binding.fit``), with physics' settings for an unstated input
(g, the named planet's mass).

Anything short of one operation with one way to fill it declines: two
operations fit, a value has no input, an input could take either of two
values, or the ask names nothing the catalog lists. It runs after the
extractors, so it only answers questions they declined.
"""

from __future__ import annotations

import re
from functools import lru_cache

from app.models.schemas.physics import PhysicsIntent
from app.modules.physics.ask import ask_clause, asked_dimensions, asked_unit
from app.modules.physics.binding_values import fallback_value, si_unit
from app.modules.physics.catalog import CATALOG
from app.modules.physics.givens import FRACTION_OF_C, PHYSICS_UNITS, unit_expression
from app.services.law_binding.fit import Question, Subject, fit, read_givens
from app.services.law_binding.spec import FormulaSpec
from app.services.law_binding.units import dimension_of
from app.services.law_binding.words import ask_strength, word_pattern

# A school question states a handful of values; a paste full of numbers is
# not one law's inputs, and reading it all would cost every chat turn.
_MAX_GIVENS = 16
# A second request in the same message ("... and tell me a joke") is not a
# question the verified answer finishes.
_SECOND_REQUEST = re.compile(
    r"\b(?:and|also|then)\s+(?:also\s+)?"
    r"(?:tell|explain|show|write|give|convert|calculate|compute|solve|draw|plot|describe)\b",
    re.IGNORECASE,
)
_PHYSICS = Subject(units=PHYSICS_UNITS, fallback=fallback_value, unit_of=si_unit)


def bind_physics_intent(text: str) -> PhysicsIntent | None:
    """The one catalog operation this question states and asks for, or None.

    The word checks run first, so text that names no operation's ask costs a
    few regex searches and never reads units. Detection calls this on every
    chat turn.
    """
    clause = ask_clause(text)
    if clause is None or _SECOND_REQUEST.search(text):
        return None
    lower = text.lower()
    # "0.8c" is a speed of light: the phrase relativity's cues are written as.
    cue_text = f"{lower} speed of light" if FRACTION_OF_C.search(lower) else lower
    asked_clause = clause.lower()
    named = [
        (spec, strength)
        for spec in _bindable()
        if spec.binding is not None
        and (
            not spec.binding.cues
            or any(word_pattern(cue).search(cue_text) for cue in spec.binding.cues)
        )
        and not any(word_pattern(word).search(lower) for word in spec.binding.excludes)
        and (
            strength := ask_strength(clause, spec.binding.asks, spec.binding.result, PHYSICS_UNITS)
        )
    ]
    if not named:
        return None
    givens = read_givens(text, PHYSICS_UNITS)
    if len(givens) > _MAX_GIVENS:
        return None
    unit = asked_unit(text)
    question = Question(
        text=text,
        lower=lower,
        givens=givens,
        asked=frozenset(asked_dimensions(text)),
        asked_in=dimension_of(unit_expression(unit) or "") if unit else None,
        asked_from=lower.rfind(asked_clause),
    )
    fits = [
        filled
        for spec, strength in named
        if (filled := fit(spec, strength, question, _PHYSICS)) is not None
    ]
    if not fits:
        return None
    strongest = max(filled.strength for filled in fits)
    top = [filled for filled in fits if filled.strength == strongest]
    if len(top) != 1:
        return None
    chosen = top[0]
    try:
        return PhysicsIntent(
            kind=chosen.spec.kind,  # type: ignore[arg-type]
            physics_op=chosen.spec.id,
            physics_params=chosen.params,
            physics_units=chosen.units,
        )
    except ValueError:
        return None


@lru_cache(maxsize=1)
def _bindable() -> tuple[FormulaSpec, ...]:
    return tuple(spec for spec in CATALOG.values() if spec.binding is not None)
