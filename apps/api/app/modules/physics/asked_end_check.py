"""A solve that answers the other end of the change than the question asks.

"A car is going 30 m/s after accelerating at 4 m/s² for 5 s. What was its starting
speed?" The SUVAT reader took the one speed as u and answered v = u + at = 50 m/s; the
starting speed is 10 m/s. A question never asks for a value it already states, so the
one speed is the final one. Any reader's intent (an extractor's or the binder's) is
refused here when:

- its law's result is at the other end from the asked one (``law_binding.roles``), or
- it fills the asked end's input with a stated value of the asked kind.

The binder then reads the question for the law at the asked end, or nothing answers. A
chained law that answers one asked part is held to that part (``chain_solve``).
"""

from __future__ import annotations

from app.modules.physics.ask import asked_end
from app.modules.physics.catalog import formula_spec
from app.modules.physics.schemas import PhysicsIntent
from app.services.law_binding.roles import binds_the_asked, contradicts


def answers_the_other_end(intent: PhysicsIntent, text: str, clause: str | None = None) -> bool:
    """This intent answers, or states, the end of the change the question asks for.

    ``clause`` is the one asked part a chained law answers; by default the last question.
    """
    end = asked_end(text, clause)
    if end is None:
        return False
    ops = [intent.physics_op, *(str(op) for op in intent.requested_ops)]
    specs = [spec for op in dict.fromkeys(ops) if op and (spec := formula_spec(op)) is not None]
    params = intent.physics_params or {}
    return any(
        contradicts(spec, end.role, end.dimension)
        or binds_the_asked(spec, params, end.role, end.dimension)
        for spec in specs
    )
