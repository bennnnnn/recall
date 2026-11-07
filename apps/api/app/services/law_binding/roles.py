"""Which end of a change a quantity belongs to: where it starts, or where it ends.

A law with paired inputs (u and v, T₁ and T₂, V₁ and V₂) names each one's end by its
words, and a question can name the end it asks for ("its starting speed", "the new
volume"). A question never asks for a value it already states, so when the ask names
an end:

- a law whose result is the other end does not answer it. "A car is going 30 m/s after
  accelerating at 4 m/s² for 5 s. What was its starting speed?" was answered with
  v = u + at = 50 m/s; the starting speed is 10 m/s. The law for the starting speed is
  the answer, or nothing is;
- a stated value of the asked kind never fills the input at the asked end: the one
  speed stated is the other end's, or the question states its own answer.

Roles are read from what the catalog already writes: an input's ``words`` ("initial",
"final") or a subscript 0 on its symbol (v₀), and a law's ``asks`` ("final speed", "new
volume"). A law or an input whose words name both ends, or neither, has no role and is
never ruled out.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from functools import lru_cache
from typing import Literal

from app.services.law_binding.spec import Binding, FormulaSpec, VariableSpec
from app.services.law_binding.units import dimension_of

Role = Literal["initial", "final"]

# Words that put a quantity at one end of the change, as a law's asks and an input's
# words write them. "from" and "to" are not here: "from" is also a place ("2 m from
# the lens"), and an input that has only them names no end.
_ROLE_WORDS: dict[Role, tuple[str, ...]] = {
    "initial": (
        "initial",
        "initially",
        "original",
        "originally",
        "starting",
        "starts at",
        "started at",
        "starting at",
        "at first",
    ),
    "final": ("final", "finally", "new", "ends at", "ended at"),
}


@lru_cache(maxsize=1)
def _role_patterns() -> dict[Role, re.Pattern[str]]:
    return {
        role: re.compile(
            r"(?<![\w])(?:" + "|".join(re.escape(word) for word in words) + r")(?![\w])",
            re.IGNORECASE,
        )
        for role, words in _ROLE_WORDS.items()
    }


def _named_role(phrases: Iterable[str]) -> Role | None:
    """The one end these phrases name; None for both ends or neither."""
    named = {
        role
        for role, pattern in _role_patterns().items()
        if any(pattern.search(phrase) for phrase in phrases)
    }
    return named.pop() if len(named) == 1 else None


# A subscript 0 is the start: v₀ launches, L₀ is the length before it expands.
_AT_THE_START = re.compile(r"_\{?0\}?$")


def role_words(words: Iterable[str]) -> tuple[str, ...]:
    """The words among these that name an end of the change ("initial", not "at")."""
    return tuple(word for word in words if _named_role((word,)) is not None)


def variable_role(variable: VariableSpec) -> Role | None:
    """The end this input is at: as its words name it (u's "initial", T₂'s "final"), or
    as its symbol does (v₀)."""
    named = _named_role(variable.words)
    if named is None and _AT_THE_START.search(variable.symbol):
        return "initial"
    return named


def result_role(binding: Binding | None) -> Role | None:
    """The end this law's result is at, as its asks name it: "final speed", "new volume"."""
    return None if binding is None else _named_role(binding.asks)


# The asked noun's adjectives: the words just before it ("its starting speed").
_ADJECTIVES = 3
# An adverb after it: "its speed at first", "how fast was it going initially". The
# words after the noun stop at a condition, which states a given instead ("what is the
# acceleration if it initially moves at 10 m/s").
_CONDITION = re.compile(r"\b(?:if|given|assuming|when|where|with|and|so|but)\b|[,;:]")
_AFTER: dict[Role, re.Pattern[str]] = {
    "initial": re.compile(
        r"\b(?:initially|originally|at\s+first|to\s+(?:begin|start)\s+with"
        r"|at\s+the\s+(?:start|beginning|outset))\b"
        # "how fast was it going before?", "... before it started to brake": before the
        # change the question describes. "Before it hit the ground" is its other end, and
        # "before it starts to fall" the top of a rise, not its start.
        r"|\bbefore\s*$"
        r"|\bbefore\s+(?:(?:it|he|she|they|the\s+[a-z]+)\s+)?(?:(?:was|were|had|began|"
        r"started|starts|begins)\s+(?:to\s+)?)?(?:accelerat|decelerat|brak|slow|speed"
        r"|heat|warm|cool|compress|expand|the\s+(?:brakes|change|acceleration))",
        re.IGNORECASE,
    ),
    "final": re.compile(r"\b(?:finally|at\s+the\s+end|in\s+the\s+end)\b", re.IGNORECASE),
}


def asked_role(clause: str, start: int, end: int) -> Role | None:
    """The end the asked quantity at ``clause[start:end]`` is at, or None.

    The adjective right before it names it ("its starting speed"), or else an adverb
    after it within the ask ("how fast was it going at first").
    """
    named = _named_role((" ".join(clause[:start].split()[-_ADJECTIVES:]),))
    if named is not None:
        return named
    after = clause[end:]
    stop = _CONDITION.search(after)
    after = after[: stop.start()] if stop is not None else after
    found = [role for role, pattern in _AFTER.items() if pattern.search(after)]
    return found[0] if len(found) == 1 else None


def contradicts(spec: FormulaSpec, role: Role | None, kind: str | None = None) -> bool:
    """This law's result is at the other end from the one asked for.

    ``kind`` is the asked quantity's dimension: only a law whose result is of that kind
    answers it, so only such a law can contradict it ("find the distance and its initial
    speed" rules out no distance law). An ask of no kind rules out nothing.
    """
    binding = spec.binding
    found = result_role(binding)
    if role is None or found is None or found == role or binding is None:
        return False
    return kind is not None and kind in {dimension_of(unit) for unit in binding.result}


def counterparts(spec: FormulaSpec, role: Role, laws: Iterable[FormulaSpec]) -> list[FormulaSpec]:
    """The laws that answer what ``spec`` answers, at the asked end instead.

    "How fast was it going at first?" names v = u + at by its "how fast"; the law it
    asks is u = v - at, of the same kind and result, whose result is the starting speed.
    """
    if spec.binding is None:
        return []
    return [
        law
        for law in laws
        if law.kind == spec.kind
        and law.binding is not None
        and law.binding.result == spec.binding.result
        and result_role(law.binding) == role
    ]


def binds_the_asked(
    spec: FormulaSpec, filled: Iterable[str], role: Role | None, asked_kind: str | None
) -> bool:
    """A filled input is the asked quantity itself: at the asked end, of the asked kind.

    "Starts at 10 m/s ... what was its initial speed?" states its own answer; u = 10
    read as a given would answer another question.
    """
    if role is None or asked_kind is None:
        return False
    variables = {variable.name: variable for variable in spec.variables}
    return any(
        (variable := variables.get(name)) is not None
        and variable_role(variable) == role
        and dimension_of(variable.dimension or "") == asked_kind
        for name in filled
    )
