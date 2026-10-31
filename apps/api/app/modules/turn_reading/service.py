"""The model reader: two short calls, the server's checks, and the subject's own binder.

``read_with_model`` asks a model which subject and kind of law a question is (one call),
then which law of that kind and the values it states (a second call, with that kind's
laws only). The read becomes an intent only when ``checks.check_read`` finds every value
in the message and the subject's binder reads it back to the same law and values
(``physics.model_read``, ``chemistry.model_read``). Maths keeps its own typed read
(``math.tools.llm_extract``). Nothing here raises into a turn; a failure is a reason.
"""

from __future__ import annotations

import logging
import time
from functools import lru_cache

from app.core.blocking import run_blocking
from app.core.config import Settings
from app.models.routing_lanes import ROUTING
from app.modules.chemistry.model_read import chemistry_menu, chemistry_read_intent
from app.modules.math.tools.llm_extract import llm_extract_math_intent
from app.modules.physics.model_read import physics_menu, physics_read_intent
from app.modules.turn_reading.checks import check_read
from app.modules.turn_reading.prompts import law_prompt, route_prompt
from app.modules.turn_reading.schemas import LawRead, ModelRead, Reason, RouteRead
from app.services.law_binding.model_read import Stated

logger = logging.getLogger(__name__)

_MAX_INPUT_CHARS = 1500


@lru_cache(maxsize=1)
def _route_prompt() -> str:
    return route_prompt(physics_menu(), chemistry_menu())


async def _ask[T: LawRead | RouteRead](
    settings: Settings, system: str, text: str, schema: type[T], usage: dict[str, int]
) -> T | None:
    # Imported here: SymPy pool workers import the subjects, not the gateway (190 MB).
    from app.gateways.structured_completion import complete_structured

    return await complete_structured(
        settings=settings,
        model_alias=ROUTING.math_extract,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": text}],
        schema=schema,
        max_tokens=400,
        timeout_seconds=settings.model_reader_timeout_seconds,
        usage=usage,
        allow_fallback=False,
    )


async def read_with_model(text: str, settings: Settings) -> ModelRead:
    """What a model reads ``text`` to ask, checked; never raises."""
    started = time.perf_counter()
    usage: dict[str, int] = {}

    def done(
        subject: str | None, op: str | None, intent: object | None, reason: Reason
    ) -> ModelRead:
        elapsed = round((time.perf_counter() - started) * 1000, 1)
        tokens = int(usage.get("input", 0)), int(usage.get("output", 0))
        return ModelRead(subject, op, intent, reason, elapsed, *tokens)

    question = text.strip()[:_MAX_INPUT_CHARS]
    if not question:
        return done(None, None, None, "no_read")
    try:
        route = await _ask(settings, _route_prompt(), question, RouteRead, usage)
        if route is None:
            return done(None, None, None, "no_read")
        if route.subject == "none":
            return done(None, None, None, "not_subject")
        if route.subject == "math":
            intent = await llm_extract_math_intent(question, settings, usage=usage)
            kind = getattr(intent, "kind", None)
            return done("math", kind, intent, "ok" if intent is not None else "no_read")
        menu = physics_menu() if route.subject == "physics" else chemistry_menu()
        cards = menu.get(route.kind or "")
        if not cards:
            return done(route.subject, None, None, "unknown_kind")
        read = await _ask(settings, law_prompt(route.subject, cards), question, LawRead, usage)
        if read is None or read.op == "none":
            return done(route.subject, None, None, "no_read")
        if read.op not in {card.op for card in cards}:
            return done(route.subject, None, None, "unknown_op")
        checked = check_read(question, read)
        if checked != "ok":
            return done(route.subject, read.op, None, checked)
        stated = [Stated(given.name, given.value, given.unit) for given in read.givens]
        # The binder reads server-written English: off the loop, in its own small pool.
        bound: object | None
        if route.subject == "physics":
            bound = await run_blocking("model_reads", physics_read_intent, read.op, stated)
        else:
            bound = await run_blocking(
                "model_reads", chemistry_read_intent, read.op, stated, read.formula
            )
        if bound is None:
            return done(route.subject, read.op, None, "binder_disagrees")
        return done(route.subject, read.op, bound, "ok")
    except Exception as exc:
        logger.info("model read failed (%s)", type(exc).__name__)
        return done(None, None, None, "failed")
