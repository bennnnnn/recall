"""A physics question written down as maths by a model, in any wording and any language.

No catalog law and no phrase list: the model writes what the question gives (each value with
its unit and the question's own words for it), what each part asks, the equations of the
physics that join them, and the relations the values must keep (a stated balance)
(``services.formal.problem.FormalProblem``). The server checks and solves that setup
(``services.formal.solve``); the model's own answer to each part comes with it, to be
compared.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings
from app.models.routing_lanes import ROUTING
from app.services.formal.answer import FormalAnswer, FormalValue, StatedConflict
from app.services.formal.problem import FormalProblem

logger = logging.getLogger(__name__)

_MAX_TOKENS = 1400
_MAX_CHARS = 2000

PROMPT = (
    "Write this physics question down as maths, as JSON. The question may be in any "
    "language and any wording; read what it means.\n"
    "\n"
    "givens: each value the question states, one entry each: symbol, value (the number "
    "exactly as the question writes it, digits only), unit (in standard symbols even when "
    "the question writes them in its own language or script, e.g. km/h, m/s^2, ohm, "
    'degree, degC, kPa; "" for a pure number), quote (the question\'s own words that '
    'state it, copied exactly, in the question\'s language, e.g. "100 km/h"). A count '
    'written in words is a given too ("two resistors" -> value 2). A standard constant the '
    "question does not state (g, c, G, the speed of sound, water's density or specific "
    "heat) is a given with its standard value, constant true and no quote. Never invent "
    "any other value; when a value the answer needs is missing, solvable is false.\n"
    "unknowns: the quantity asked, and every other symbol the equations use that is not a "
    "given, each with its unit.\n"
    'equations: the physics that joins them, one relation per entry, "lhs = rhs" in the '
    "symbols, with * / ** and sqrt sin cos tan asin acos atan exp log pi. Put no given "
    "value into an equation as a number: use its symbol (small factors like 2 or 1/2 are "
    "fine). An angle in degrees is a given in degree; a temperature change is in delta_degC "
    "or K, a temperature in degC or K.\n"
    "asked (always): one entry per value the question asks for, in order: part (the "
    'letter of a question asked in labelled parts, a to h, else ""), symbol (the unknown '
    "asked for), unit (the unit the question asks for it in, or the usual SI unit; a "
    'percentage, an efficiency or a percent change, in "%", its equation the plain ratio '
    '(no "* 100": the unit makes it a percentage)), answer (your own numeric answer, in '
    "that unit). A part that asks for no number (a meaning, an explanation) or changes a "
    'given ("if the mass doubles") is left out.\n'
    "checks: each relation the question's values must keep that no equation already "
    "uses: a balance, an equilibrium or a constant speed the question states (a lever "
    "said to balance: load times its arm = effort times its arm), or a bound a law sets on "
    "a value the question asks or gives (a machine's mechanical advantage at most its "
    'velocity ratio). Each is relation ("lhs = rhs", or with <=, >=) in the symbols, and '
    "meaning: why it must hold, in a few words in the question's language. [] when there "
    "is none. Never write an equation the answers need as a check.\n"
    "solvable: false when the message asks no value (a concept, an explanation), asks "
    "values of unrelated setups, or lacks a value the answer needs.\n"
    "\n"
    'Example: "A car speeds up from 10 m/s to 30 m/s in 4 s. How far does it go?" -> '
    '{"solvable": true, "givens": [{"symbol": "u", "value": "10", "unit": "m/s", "quote": '
    '"10 m/s"}, {"symbol": "v", "value": "30", "unit": "m/s", "quote": "30 m/s"}, '
    '{"symbol": "t", "value": "4", "unit": "s", "quote": "4 s"}], "unknowns": [{"symbol": '
    '"d", "unit": "m"}], "equations": ["d = (u + v)/2*t"], "asked": [{"part": "", '
    '"symbol": "d", "unit": "m", "answer": 80}], "checks": []}'
)


async def read_physics_setup(
    settings: Settings,
    question: str,
    *,
    model_alias: str | None = None,
    usage: dict[str, int] | None = None,
) -> FormalProblem | None:
    """The model's setup of the question, or None when there is no read."""
    from app.core.redis import get_redis_client
    from app.gateways.structured_completion import complete_structured
    from app.services import quota as quota_service

    try:
        if await quota_service.global_spend_exceeded(get_redis_client(), settings):
            return None
        return await complete_structured(
            settings=settings,
            model_alias=model_alias or ROUTING.physics_setup,
            messages=[
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": question[:_MAX_CHARS]},
            ],
            schema=FormalProblem,
            max_tokens=_MAX_TOKENS,
            usage=usage,
            timeout_seconds=settings.formal_read_timeout_seconds,
            allow_fallback=False,
            quiet_timeout=True,
        )
    except Exception as exc:  # A read is a hint: any failure reads nothing.
        logger.info("physics setup read failed (%s)", type(exc).__name__)
        return None


@dataclass(frozen=True)
class FormalReading:
    """The model's setup of a question and the server's solve of it (``FormalResult`` JSON,
    solved or refused), both kept: the second reading a verified answer is held to
    (``physics.cross_check``) as well as the answer a reply is held to (``formal_answer``)."""

    setup: FormalProblem
    result: dict[str, Any]


async def formal_reading(
    question: str, settings: Settings, *, model_alias: str | None = None
) -> FormalReading | None:
    """The question written down by the model and solved by the server; None with no read."""
    from app.core.sympy_executor import run_sympy
    from app.services.formal.solve import solve_formal

    setup = await read_physics_setup(settings, question, model_alias=model_alias)
    if setup is None:
        return None
    try:
        raw = await run_sympy(
            solve_formal,
            setup.model_dump_json(),
            question,
            timeout=settings.stem_solve_timeout_seconds,
        )
    except Exception as exc:  # the pool timed out or failed: the setup alone is the reading
        logger.info("physics setup not solved (%s)", type(exc).__name__)
        return FormalReading(setup, {"solved": False, "reason": "not solved"})
    return FormalReading(setup, json.loads(raw))


async def formal_answer(question: str, settings: Settings) -> FormalAnswer | None:
    """The server's answers to the question, worked out from the model's setup, and the
    checks its values break; None with no read or a setup the server refuses. A part whose
    setup answer is not the server's is left out: that reading is not to be trusted."""
    reading = await formal_reading(question, settings)
    return None if reading is None else answer_of(reading.result)


def answer_of(result: dict[str, Any]) -> FormalAnswer | None:
    """A solved setup's ``FormalResult`` JSON as the answer a reply is held to."""
    if not result.get("solved"):
        return None
    values = tuple(
        FormalValue(**{**value, "uses": tuple(value.get("uses") or ())})
        for value in result.get("answers") or []
        if value.get("agrees") is True
    )
    # A broken check is said only of a setup whose own answers all agree with the server's:
    # a misread setup (the wrong arms) would open a right reply with a false contradiction.
    agreed = [value.get("agrees") for value in result.get("answers") or []]
    trusted = bool(agreed) and all(agree is True for agree in agreed)
    conflicts = tuple(
        StatedConflict(**conflict) for conflict in (result.get("conflicts") or []) if trusted
    )
    return FormalAnswer(values=values, conflicts=conflicts) if values or conflicts else None
