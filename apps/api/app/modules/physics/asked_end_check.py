"""A solve that answers the other end of the change than the question asks.

"A car is going 30 m/s after accelerating at 4 m/s² for 5 s. What was its starting
speed?" The SUVAT reader took the one speed as u and answered v = u + at = 50 m/s; the
starting speed is 10 m/s. A question never asks for a value it already states, so the
one speed is the final one. Any reader's intent (an extractor's or the binder's) is
refused here when:

- its law's result is at the other end from the asked one (``law_binding.roles``), or
- it fills the asked end's input with a stated value of the asked kind, or
- the question asks the average over the whole change and the law's result is at one end
  of it ("its average velocity" of v = u + at is the speed at the end).

The binder then reads the question for the law at the asked end, or nothing answers. A
chained law that answers one asked part is held to that part (``chain_solve``).
"""

from __future__ import annotations

from app.modules.physics.ask import asked_end, asks_for_a_part, averaged_asks
from app.modules.physics.catalog import formula_spec
from app.modules.physics.law_nouns import result_name
from app.modules.physics.schemas import PhysicsIntent
from app.services.law_binding.inverse import same_part, solved_input
from app.services.law_binding.roles import (
    binds_the_asked,
    contradicts,
    result_role,
    role_words,
)
from app.services.law_binding.spec import FormulaSpec
from app.services.law_binding.units import dimension_of


def asks_a_part_of(intent: PhysicsIntent, text: str) -> bool:
    """The question asks one part of a whole ("the power of the other lens") and this law,
    read forward, adds the parts up: P = P₁ + P₂ answered "together they have 5 D; one is
    3 D: the other?" with 8 D for 2 D. Solved for a part (``law_binding.inverse``) it
    answers; the parts it combines are those it takes alike (``same_part``)."""
    spec = formula_spec(intent.physics_op or "")
    if spec is None or not same_part(spec) or not asks_for_a_part(text):
        return False
    return solved_input(spec, intent.physics_params or {}) is None


def answers_the_other_end(intent: PhysicsIntent, text: str, clause: str | None = None) -> bool:
    """This intent answers, or states, the end of the change the question asks for.

    ``clause`` is the one asked part a chained law answers; by default the last question.
    """
    ops = [intent.physics_op, *(str(op) for op in intent.requested_ops)]
    specs = [spec for op in dict.fromkeys(ops) if op and (spec := formula_spec(op)) is not None]
    averaged = averaged_asks(text, clause)
    if averaged and any(_answers_a_moment(spec, averaged) for spec in specs):
        return True
    end = asked_end(text, clause)
    if end is None:
        return False
    params = intent.physics_params or {}
    return any(
        contradicts(spec, end.role, end.dimension)
        or binds_the_asked(spec, params, end.role, end.dimension)
        for spec in specs
    )


def _answers_a_moment(spec: FormulaSpec, averaged: tuple[str | None, ...]) -> bool:
    """An average asked of a law whose result is at one end of the change: v = u + at is the
    speed at the end, and "its average velocity" was answered with it, 10 m/s for 5 (Grade 7
    book, 2026-11-19). A law whose result is no end's ((v - u)/t, Q/t, W/t) is the average
    over the change, and answers it; one whose result is of another kind answers another
    asked part."""
    names = (*(spec.binding.asks if spec.binding is not None else ()), result_name(spec) or "")
    if result_role(spec.binding) is None and not role_words(names):
        return False
    if spec.binding is None:
        return True
    produced = {dimension_of(unit) for unit in spec.binding.result}
    return any(kind is None or kind in produced for kind in averaged)
