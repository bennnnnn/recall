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
from app.modules.billing.plan import pick_math_lane, pick_preferred_tier
from app.modules.chat.decider_read import READ_SUBJECTS

Effort = Literal["none", "low", "high"]
_EFFORTS: tuple[Effort, ...] = ("none", "low", "high")
# none answers at once; low takes the model's cheapest level that thinks; high its most.
_LEVELS: dict[Effort, ThinkingLevel] = {"none": "off", "low": "hard", "high": "deep"}
# Maths, physics and chemistry think only when the read calls them hard. It called 43% of
# easy textbook problems "low" (2026-11-10), and thinking on them took DeepSeek 11.7 s
# (C17, atoms in 2 mol of glucose) and 15.5 s (C14) to the first word, live 2026-11-10;
# with thinking off it kept the worked layout on all 17 unverified questions tried and
# was right on 97-100% at 0.4 s.
_STEM = frozenset(READ_SUBJECTS)


def decided_level(subject: str | None, effort: Effort) -> ThinkingLevel:
    """The thinking level the read's subject and effort ask for. A hard STEM problem (the
    four runners' speeds, 2026-11-09) thinks at the model's level that thinks, not its
    most: the answer is the solver's kind of work, laid out step by step."""
    if subject in _STEM:
        return "hard" if effort == "high" else "off"
    return _LEVELS[effort]


def decided_lane(
    subject: str,
    effort: Effort,
    pool: list[str],
    *,
    unsteady: frozenset[str] = frozenset(),
    strong_everyday: bool = False,
    math_lane: tuple[str, str] | None = None,
) -> str | None:
    """Auto's model for the read's subject and effort, from the user's ``pool``; None keeps
    the word rules' lane (a subject the table leaves out, money). A model whose breaker is
    open or half-open (``unsteady``) is passed over while another is left: the turn would
    wait out its timeout. ``strong_everyday``: the plan's everyday lane is the stronger
    model (Pro, ``entitlements.has_strong_everyday_model``). ``math_lane``: the plan's maths
    lane and its backup (billing's ``math_lane_for``)."""
    lanes = ROUTING.decided.get(subject)
    if lanes is None or not pool:
        return None
    lane = lanes[_EFFORTS.index(effort)]
    usable = [alias for alias in pool if alias not in unsteady] or pool
    if lane == "everyday" and strong_everyday and ROUTING.everyday_strong in usable:
        return ROUTING.everyday_strong
    if lane == "math":
        return pick_math_lane(math_lane, usable)
    preferred = {"everyday": ROUTING.everyday, "hard": ROUTING.hard}[lane]
    return pick_preferred_tier(preferred, usable)


def math_backups(
    subject: str, lane: str, pool: list[str], unsteady: frozenset[str] = frozenset()
) -> list[str]:
    """The model a STEM turn falls back to first when its maths lane fails: Qwen3.8 Flash
    behind DeepSeek and GLM 5.3 Flash behind Qwen3.7 Flash (``ROUTING.math_backups``), when
    the pool has it and its breaker is closed. Other subjects keep the pool's order."""
    backup = ROUTING.math_backups.get(lane)
    if subject not in _STEM or backup is None or backup not in pool or backup in unsteady:
        return []
    return [backup]
