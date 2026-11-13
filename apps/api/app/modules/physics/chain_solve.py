"""Every quantity a physics question asks for, each by a catalog law, laws chained.

"A ball is thrown straight up at 15 m/s. How high does it go and how long till it comes
back down?" asks for a height and a time; "a car going 72 km/h stops in 4 s, what's the
deceleration and how far does it go" for an acceleration and a distance. One law answered
one of each and the model wrote the rest unchecked (live, 2026-11-03). The shared chain
(``services/law_binding/chain``) answers every ask in turn from the stated values and the
values earlier laws worked out; this module brings physics' laws and solver to it, checks
over the whole chain that every stated value was used, and writes one verified part per
ask, a value another part needed shown in that part's working.
"""

from __future__ import annotations

import logging
from dataclasses import replace

from app.core.config import Settings
from app.modules.physics.accounting import competing_given_of
from app.modules.physics.ask import Ask, asks, has_ask, result_reading
from app.modules.physics.asked_end_check import answers_the_other_end, asks_a_part_of
from app.modules.physics.binding import (
    PHYSICS_SUBJECT,
    asks_another_thing,
    bindable_of_kind,
    drop_unit_request,
    named_laws,
)
from app.modules.physics.block import build_verified_physics_block
from app.modules.physics.counted import accounts_for_counted_items
from app.modules.physics.display import si_symbol
from app.modules.physics.extract import read_physics_request
from app.modules.physics.givens import PHYSICS_UNITS
from app.modules.physics.law_range import holds_its_range
from app.modules.physics.parts import asks_count
from app.modules.physics.request import PhysicsRequest, complete_physics_intent
from app.modules.physics.schemas import PhysicsIntent
from app.modules.physics.solver import solve_physics
from app.modules.physics.split_parts import changes_the_situation, joined_parts, part_working
from app.services.law_binding.chain import Asked, Step, chain
from app.services.law_binding.fit import Fit, read_question
from app.services.solving import PhysicsPartWorking, VerifiedPhysicsBlock

logger = logging.getLogger(__name__)

# A paste full of numbers is not one question's givens (as in the binder).
_MAX_GIVENS = 16


def solve_chain(text: str, settings: Settings) -> VerifiedPhysicsBlock | None:
    """One verified block answering every quantity ``text`` asks for, or None."""
    request = read_physics_request(text)
    if request is None or request.collision is not None or not has_ask(request.text):
        return None
    source = drop_unit_request(request.text)
    asked = asks(source)
    if (
        not asked
        or asks_another_thing(source)
        or any(changes_the_situation(ask.words) for ask in asked)
    ):
        return None
    # A part asked without a question word ("b) The power developed") is still asked:
    # answering fewer parts than the question has left the rest to the model.
    if len(asked) < asks_count(source):
        return None
    question = read_question(source, asked[0].words, PHYSICS_UNITS, max_givens=_MAX_GIVENS)
    if question is None:
        return None
    steps = chain(
        question,
        [Asked(ask.words, ask.dimension) for ask in asked],
        PHYSICS_SUBJECT,
        named=lambda words: named_laws(source, words),
        of_kind=bindable_of_kind,
        solve=lambda filled, ask: _solved_value(filled, ask, request),
    )
    if steps is None:
        return None
    intents = [_intent(step.fit, step.answers, asked, request) for step in steps]
    if None in intents:
        return None
    chained = [intent for intent in intents if intent is not None]
    # One law may use some stated values and the next the rest; each must be used.
    if competing_given_of(chained, request.text) is not None:
        return None
    if not all(accounts_for_counted_items(intent, request.text) for intent in chained):
        return None
    return _block(steps, chained, asked, source, settings)


def _intent(
    filled: Fit, answers: int | None, asked: tuple[Ask, ...], request: PhysicsRequest
) -> PhysicsIntent | None:
    try:
        # The catalog's kind is a str; the model validates it against its Literal.
        intent = PhysicsIntent.model_validate(
            {
                "kind": filled.spec.kind,
                "physics_op": filled.spec.id,
                "physics_params": dict(filled.params),
                "physics_units": dict(filled.units),
            }
        )
    except ValueError:
        return None
    if answers is not None and answers_the_other_end(intent, request.text, asked[answers].words):
        # "Hits the ground at 25 m/s … its initial speed?": the impact law took 25 m/s as v₀.
        return None
    if asks_a_part_of(intent, request.text):
        # "The combination has 2 D; one lens is 5 D: the other?" is no sum of the two.
        return None
    own = () if answers is None else (asked[answers].dimension,)
    return complete_physics_intent(intent, request, step_of=own)


def _solved_value(filled: Fit, ask: Asked, request: PhysicsRequest) -> tuple[float, str] | None:
    """The law's result in SI, for the next law and for comparing two routes."""
    intent = _intent(filled, None, (), request)
    if intent is None or filled.spec.binding is None or not holds_its_range(filled.spec, intent):
        return None
    try:
        result = solve_physics(intent)
    except Exception:
        logger.info("chained physics law declined: %s", filled.spec.id, exc_info=True)
        return None
    if len(result.quantities) != 1:
        return None
    quantity = result.quantities[0]
    reading = result_reading(quantity.unit)
    si = filled.spec.binding.result[0]
    if reading is None or (ask.dimension and reading[0] != ask.dimension):
        return None
    return quantity.value * reading[1] + reading[2], si_symbol(si)


def _block(
    steps: tuple[Step, ...],
    intents: list[PhysicsIntent],
    asked: tuple[Ask, ...],
    source: str,
    settings: Settings,
) -> VerifiedPhysicsBlock | None:
    """One part per ask; a value a part needed first is worked out in that part."""
    blocks: list[VerifiedPhysicsBlock] = []
    workings: list[PhysicsPartWorking] = []
    before: list[VerifiedPhysicsBlock] = []
    for step, intent in zip(steps, intents, strict=True):
        try:
            built = build_verified_physics_block(intent, settings)
        except Exception:
            logger.info("chained physics block declined: %s", intent.physics_op, exc_info=True)
            return None
        if built is None:
            return None
        block = built
        if step.answers is None:
            before.append(block)
            continue
        working = part_working(block, asked[step.answers].words, source)
        if working is None:
            return None
        if before:
            working = _with_steps_before(working, before)
            # The value worked out first is the reply's to explain, not a given.
            block = replace(
                block,
                text="\n\n".join([*(earlier.text for earlier in before), block.text]),
                allow_direct=False,
            )
            before = []
        blocks.append(block)
        workings.append(working)
    if not blocks:
        return None
    if len(blocks) == 1:
        only, working = blocks[0], workings[0]
        return replace(
            only,
            physics_formulas=working.formulas,
            physics_substitutions=working.substitutions,
        )
    return joined_parts(blocks, workings)


def _with_steps_before(
    working: PhysicsPartWorking, before: list[VerifiedPhysicsBlock]
) -> PhysicsPartWorking:
    formulas = tuple(row for block in before for row in block.physics_formulas)
    rows = tuple(row for block in before for row in block.physics_substitutions)
    return PhysicsPartWorking(
        op=working.op,
        symbol=working.symbol,
        title=working.title,
        formulas=formulas + working.formulas,
        substitutions=rows + working.substitutions,
        answer=working.answer,
        display_answer=working.display_answer,
    )
