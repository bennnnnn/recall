"""A top a question states, checked against the one its own launch reaches.

"Thrown straight up at 10 m/s, it reaches a maximum height of 20 m" (live round, 2026-11-21)
has no answer as written: at 10 m/s a ball rises v₀²/2g = 5.10 m. The stated tops are read
by ``stated_peak`` (which the extractors ask, so it reads text alone); this solves the
launch's own top and says why the values contradict each other when the two differ.
"""

from __future__ import annotations

import math

from pint.errors import PintError

from app.modules.physics.display import plain_number
from app.modules.physics.extract import extract_physics_intent
from app.modules.physics.schemas import PhysicsIntent
from app.modules.physics.solver import solve_physics
from app.modules.physics.solvers.si import to_si
from app.modules.physics.stated_peak import stated_peaks
from app.services.solving import SolveServiceError

# A stated top and the one the values give agree within this: g read as 9.8 or 10 m/s², a
# value rounded as typed. Past it the values contradict each other.
_AGREE = 0.05
# The law each motion's top is, by the reader's kind.
_PEAK_OPS = {"kinematics": "vertical_max_height", "projectile": "max_height"}


def _metres(value: float, unit: str) -> float | None:
    try:
        return float(to_si(value, unit or "m"))
    except (SolveServiceError, PintError, ValueError):  # A unit Pint cannot read: no top.
        return None


def stated_peak_conflict(text: str) -> str | None:
    """Why the question has no answer as written, when the top it states is not the one its
    launch gives: "thrown up at 10 m/s, it rises 5.10 m, not the 20 m stated". None when it
    states no top, its values give none to check, or the two agree."""
    peaks = stated_peaks(text)
    if not peaks:
        return None
    intent = extract_physics_intent(text)
    if intent is None or intent.kind not in _PEAK_OPS:
        return None
    reached = _peak_of(intent, _PEAK_OPS[intent.kind])
    if reached is None or reached <= 0:
        return None
    params, units = intent.physics_params or {}, intent.physics_units or {}
    start = (_metres(params["h0"], units.get("h0", "m")) or 0.0) if "h0" in params else 0.0
    # Above the ground or above the hand: either is a top the question may mean.
    tops = {reached, reached + start} if start > 0 else {reached}
    for peak in peaks:
        stated = _metres(float(peak.group("value")), peak.group("unit"))
        if stated is None or stated <= 0:
            continue
        if any(math.isclose(stated, top, rel_tol=_AGREE) for top in tops):
            continue
        return _reason(intent, reached, peak.group(0).strip(), stated)
    return None


def _peak_of(intent: PhysicsIntent, op: str) -> float | None:
    """The top the intent's launch reaches, in metres, by its own law; None when that law
    cannot be solved from what was read."""
    try:
        peak = intent.model_copy(
            update={"physics_op": op, "requested_ops": [], "asked": (), "asked_unit": None}
        )
        result = solve_physics(PhysicsIntent.model_validate(peak.model_dump()))
    except (SolveServiceError, ValueError):
        return None
    quantity = next(iter(result.quantities), None)
    return None if quantity is None else _metres(quantity.value, quantity.unit)


def _reason(intent: PhysicsIntent, reached: float, stated_text: str, stated: float) -> str:
    params = intent.physics_params or {}
    speed = params.get("v0")
    launch = f"launched at {plain_number(speed)} m/s" if speed else "launched as it states"
    return (
        f"Its values contradict each other: {launch}, a body rises to "
        f"{plain_number(reached)} m, so it cannot reach the {plain_number(stated)} m it "
        f'states ("{stated_text}"). Name the two values, and ask which one they meant.'
    )
