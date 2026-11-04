"""Answer every quantity a question asks for, one catalog law after another.

The binder fills one law from one question. "A car going 72 km/h stops in 4 s: find the
deceleration and how far it goes" asks two things, and "how high does it go and how long
till it comes back down" two more; each is one law, and a question may need a law whose
input another law works out first. A student solves those by writing down what is known,
using any law that has one unknown left, and adding its result to what is known. This
does the same, over the subject's own catalog:

- every ask is answered in order by a law its words name, filled from the stated values
  and the values earlier steps worked out (``fit``'s ``known``). A value the words mark
  for another input, a value no input takes, or two ways to fill one law decline, as in
  ``fit``;
- when no named law fits, one law of the same kind may work out the input it lacks
  (two steps at most);
- two laws named alike answer only when their answers agree.

Nothing here knows a subject: the subject names the laws an ask names, the laws of a
kind, and how a filled law is solved. It also checks, over the whole chain, that every
stated value was used, since one step may use some and the next the rest.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace

from app.services.law_binding.fit import (
    Fit,
    Question,
    Subject,
    fit,
    given_kind,
    variable_kind,
)
from app.services.law_binding.spec import FormulaSpec, VariableSpec
from app.services.law_binding.units import dimension_of

_MAX_ASKS = 4
# Two answers that agree to this share are one answer read two ways.
_AGREE = 1e-3


@dataclass(frozen=True, slots=True)
class Asked:
    """One asked quantity: the words that name it, and its dimension."""

    words: str
    dimension: str


@dataclass(frozen=True, slots=True)
class Step:
    """One law applied: how it was filled, its result, and the ask it answers (None for
    a value a later law needed)."""

    fit: Fit
    value: float
    unit: str
    answers: int | None


# The laws an ask's words name, each with how strongly.
Named = Callable[[str], Sequence[tuple[FormulaSpec, int]]]
# The laws of one kind, any of which may work out an input another lacks.
OfKind = Callable[[str], Sequence[FormulaSpec]]
# A filled law's result in SI, (value, unit), or None when it does not solve.
Solve = Callable[[Fit, Asked], tuple[float, str] | None]
# Values worked out so far, by the declared variable they are. A name is a law's own
# ("W" is work in one law and an energy in another); a variable two laws declare is
# one quantity (SUVAT's u, v, a, s, t), so only it carries a value from one to the next.
_Known = Sequence[tuple[VariableSpec, float, str]]


def chain(
    question: Question,
    asks: Sequence[Asked],
    subject: Subject,
    *,
    named: Named,
    of_kind: OfKind,
    solve: Solve,
) -> tuple[Step, ...] | None:
    """The laws that answer every ask, in order, or None when any ask has no one answer."""
    if not asks or len(asks) > _MAX_ASKS:
        return None
    steps: list[Step] = []
    known: list[tuple[VariableSpec, float, str]] = []
    for index, ask in enumerate(asks):
        found = _answer(_asking(question, ask), ask, subject, known, named, of_kind, solve)
        if found is None:
            return None
        for step in found:
            result = _result_variable(step.fit)
            if result is not None and not any(result is seen for seen, _, _ in known):
                known.append((result, step.value, step.unit))
        steps.extend(replace(step, answers=index) if step is found[-1] else step for step in found)
    answering = [step.fit for step in steps if step.answers is not None]
    # Two asks the same law answers from the same values are one question asked twice.
    if len({(f.spec.id, tuple(sorted(f.params.items()))) for f in answering}) < len(answering):
        return None
    return tuple(steps)


def _asking(question: Question, ask: Asked) -> Question:
    at = question.lower.find(ask.words.lower())
    return replace(
        question,
        asked=frozenset({ask.dimension}),
        asked_in=None,
        asked_from=at if at >= 0 else question.asked_from,
    )


def _answer(
    question: Question,
    ask: Asked,
    subject: Subject,
    known: _Known,
    named: Named,
    of_kind: OfKind,
    solve: Solve,
) -> list[Step] | None:
    """The one law, or the one pair of laws, that answers this ask."""
    laws = [(spec, strength) for spec, strength in named(ask.words) if spec.binding is not None]
    direct = [
        filled
        for spec, strength in laws
        for filled in _fills(spec, strength, question, subject, known)
    ]
    if direct:
        return _agreed([[filled] for filled in direct], ask, solve)
    routes = [
        [first, second]
        for spec, strength in laws
        for first, second in _through_one(spec, strength, question, subject, known, of_kind, solve)
    ]
    return _agreed(routes, ask, solve) if routes else None


def _fills(
    spec: FormulaSpec, strength: int, question: Question, subject: Subject, known: _Known
) -> list[Fit]:
    """This law filled from the stated values its inputs take, alone or with one value
    worked out before that it declares; the first way that fits."""
    usable = [
        {variable.name: (value, unit)}
        for declared, value, unit in known
        for variable in spec.variables
        if variable is declared and variable.visible
    ]
    for extra in ({}, *usable):
        filled = fit(spec, strength, _taken_by(spec, question, subject, extra), subject, extra)
        if filled is not None:
            return [filled]
    return []


def _taken_by(
    spec: FormulaSpec, question: Question, subject: Subject, known: Mapping[str, object]
) -> Question:
    """The question with only the stated values this law's open inputs could take: the
    rest belong to another step. Whether every value was used is the chain's to check."""
    kinds = {
        variable_kind(variable)
        for variable in spec.variables
        if variable.visible and variable.name not in known
    }
    givens = tuple(g for g in question.givens if given_kind(g, subject.units) in kinds)
    return replace(question, givens=givens)


def _through_one(
    spec: FormulaSpec,
    strength: int,
    question: Question,
    subject: Subject,
    known: _Known,
    of_kind: OfKind,
    solve: Solve,
) -> list[tuple[Fit, Fit]]:
    """This law, with the one input it lacks worked out first by another law of its kind
    that declares that same input as its result."""
    routes: list[tuple[Fit, Fit]] = []
    for variable in spec.variables:
        if not variable.visible or any(variable is seen for seen, _, _ in known):
            continue
        for helper in of_kind(spec.kind):
            if helper.id == spec.id or not _works_out(helper, variable):
                continue
            need = Asked(variable.name, _variable_dimension(variable))
            for first in _fills(helper, 0, _asking(question, need), subject, known):
                result = solve(first, need)
                if result is None:
                    continue
                more = [*known, (variable, *result)]
                routes.extend(
                    (first, second) for second in _fills(spec, strength, question, subject, more)
                )
    return routes


def _works_out(helper: FormulaSpec, variable: VariableSpec) -> bool:
    """The helper declares this very input and gives it as its result."""
    binding = helper.binding
    return (
        binding is not None
        and any(declared is variable for declared in helper.variables)
        and helper.result_symbol in {variable.name, variable.symbol}
        and _variable_dimension(variable) in {dimension_of(unit) for unit in binding.result}
    )


def _result_variable(filled: Fit) -> VariableSpec | None:
    """The declared variable a filled law's result is, when it declares one: the input
    its result symbol names that the fill left open."""
    spec = filled.spec
    for variable in spec.variables:
        if variable.name not in filled.params and spec.result_symbol in {
            variable.name,
            variable.symbol,
        }:
            return variable
    return None


def _variable_dimension(variable: VariableSpec) -> str:
    return dimension_of(variable.dimension or "") or ""


def _agreed(routes: list[list[Fit]], ask: Asked, solve: Solve) -> list[Step] | None:
    """The strongest routes' steps, when every one of them gives the same answer."""
    strongest = max((route[-1].strength, route[-1].stated) for route in routes)
    top = [route for route in routes if (route[-1].strength, route[-1].stated) == strongest]
    answers: list[list[Step]] = []
    for route in top:
        steps: list[Step] = []
        for filled in route:
            asked = ask if filled is route[-1] else Asked("", "")
            result = solve(filled, asked)
            if result is None:
                return None
            steps.append(Step(filled, result[0], result[1], None))
        answers.append(steps)
    first = answers[0][-1]
    if any(not math.isclose(steps[-1].value, first.value, rel_tol=_AGREE) for steps in answers[1:]):
        return None
    return answers[0]
