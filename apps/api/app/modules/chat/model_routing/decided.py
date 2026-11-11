"""Auto's lane and thinking level for a turn its read decided (``chat.turn_decision``).

The word rules (``route``) chose Auto's lane from trigger words, a length, a code fence and
the subject readers; whatever they missed fell to the everyday lane. In a 100-chat check-up
on Pro (2026-11-10) 76 of 134 turns went to the everyday model, easy STEM questions the
readers missed thought for up to 28 s there, and a hard question almost never reached the
strong one. The read now says the subject and the effort; this maps them to a lane through
catalog data (``ROUTING.decided``) and to a level each model's catalog entry spells out
(``gateways.reasoning``), so routing names no model. The rules decide only with no read.
"""

from __future__ import annotations

from typing import Literal

from app.gateways.reasoning import ThinkingLevel
from app.models.routing_lanes import ROUTING
from app.modules.billing.plan import pick_preferred_tier
from app.modules.chat.model_routing.thinking import lane_for_think

Effort = Literal["none", "low", "high"]
_EFFORTS: tuple[Effort, ...] = ("none", "low", "high")
# none answers at once; low takes the model's cheapest level that thinks; high its most.
_LEVELS: dict[Effort, ThinkingLevel] = {"none": "off", "low": "hard", "high": "deep"}


def decided_level(effort: Effort) -> ThinkingLevel:
    """The thinking level the read's effort asks for."""
    return _LEVELS[effort]


def decided_lane(
    subject: str,
    effort: Effort,
    pool: list[str],
    *,
    unsteady: frozenset[str] = frozenset(),
    strong_everyday: bool = False,
) -> str | None:
    """Auto's model for the read's subject and effort, from the user's ``pool``; None keeps
    the word rules' lane (a subject the table leaves out, money). A model whose breaker is
    open or half-open (``unsteady``) is passed over while another is left: the turn would
    wait out its timeout. ``strong_everyday``: the plan's everyday lane is the stronger
    model (Pro, ``entitlements.has_strong_everyday_model``)."""
    lanes = ROUTING.decided.get(subject)
    if lanes is None or not pool:
        return None
    lane = lanes[_EFFORTS.index(effort)]
    usable = [alias for alias in pool if alias not in unsteady] or pool
    if lane == "everyday" and strong_everyday and ROUTING.everyday_strong in usable:
        return ROUTING.everyday_strong
    preferred = {"everyday": ROUTING.everyday, "hard": ROUTING.hard, "math": ROUTING.math}[lane]
    alias = pick_preferred_tier(preferred, usable)
    if effort == "none":
        return alias
    # A level that thinks, on the maths lane's model that sends no reasoning.
    return lane_for_think(alias, usable, unsteady) or alias
