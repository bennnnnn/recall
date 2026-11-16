"""A physics question written down as maths by a model, in any wording and any language.

No catalog law and no phrase list: the model writes what the question gives (each value with
its unit and the question's own words for it), what it asks, and the equations of the physics
that join them (``services.formal.problem.FormalProblem``). The server checks and solves that
setup (``services.formal.solve``); the model's own final answer comes with it, to be compared.
"""

from __future__ import annotations

import logging

from app.core.config import Settings
from app.models.routing_lanes import ROUTING
from app.services.formal.problem import FormalProblem

logger = logging.getLogger(__name__)

_MAX_TOKENS = 900
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
    "heat) is a given with constant true and no quote. Never invent any other value; when "
    "a value the answer needs is missing, solvable is false.\n"
    "unknowns: the quantity asked, and every other symbol the equations use that is not a "
    "given, each with its unit.\n"
    'equations: the physics that joins them, one relation per entry, "lhs = rhs" in the '
    "symbols, with * / ** and sqrt sin cos tan asin acos atan exp log pi. Put no given "
    "value into an equation as a number: use its symbol (small factors like 2 or 1/2 are "
    "fine). An angle in degrees is a given in degree; a temperature change is in delta_degC "
    "or K, a temperature in degC or K.\n"
    "target (always): the symbol asked for; target_unit: the unit the question asks for it in, or "
    "the usual SI unit.\n"
    "answer: your own final numeric answer, in target_unit.\n"
    "solvable: false when the message is no question with one numeric answer (a concept, "
    "an explanation, several separate questions).\n"
    "\n"
    'Example: "A car speeds up from 10 m/s to 30 m/s in 4 s. How far does it go?" -> '
    '{"solvable": true, "givens": [{"symbol": "u", "value": "10", "unit": "m/s", "quote": '
    '"10 m/s"}, {"symbol": "v", "value": "30", "unit": "m/s", "quote": "30 m/s"}, '
    '{"symbol": "t", "value": "4", "unit": "s", "quote": "4 s"}], "unknowns": [{"symbol": '
    '"d", "unit": "m"}], "equations": ["d = (u + v)/2*t"], "target": "d", "target_unit": '
    '"m", "answer": 80}'
)


async def read_physics_setup(
    settings: Settings, question: str, *, model_alias: str | None = None
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
            model_alias=model_alias or ROUTING.math_extract,
            messages=[
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": question[:_MAX_CHARS]},
            ],
            schema=FormalProblem,
            max_tokens=_MAX_TOKENS,
            timeout_seconds=settings.stem_solve_timeout_seconds * 3,
            allow_fallback=False,
            quiet_timeout=True,
        )
    except Exception as exc:  # A read is a hint: any failure reads nothing.
        logger.info("physics setup read failed (%s)", type(exc).__name__)
        return None
