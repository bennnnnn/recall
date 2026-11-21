"""A motion's top stated as a fact about it: its result, never where it starts.

"A ball thrown straight up at 10 m/s reaches a maximum height of 20 m. How long does it take
to reach the top?" (live round, 2026-11-21): the launch-height reader took "height of 20 m"
for a starting height, verified t = v₀/g = 1.02 s, and drew the ball thrown from a 20 m
ledge. The 20 m is what the throw reaches, and at 10 m/s nothing reaches it: thrown up at
10 m/s a ball rises v₀²/2g = 5.10 m. So:

- a stated top is never a launch height (``without_stated_peaks`` hides it from that
  reader);
- the top the question's own values give is checked against the one it states
  (``stated_peak_conflict``): values that contradict each other have no answer as written,
  and the reply says so instead of a verified card for one reading of them.

Only a top said to be one is read ("maximum height", "max height", "peak height",
"greatest height", "highest point"): "how long to reach a height of 20 m" asks for a
position on the way, which no top has to equal.
"""

from __future__ import annotations

import math
import re

from app.modules.physics.extractors.unit_patterns import (
    LENGTH_UNIT_PATTERN,
    NUMBER,
    VELOCITY_UNIT_PATTERN,
)

# "a maximum height of 20 m", "max height = 20 m", "its highest point is 20 m above the
# ground", "a peak height of 5.1 m". The value follows within a few joining words.
_STATED_PEAK = re.compile(
    r"\b(?:(?:maximum|max\.?|peak|greatest)\s+(?:height|altitude)|highest\s+point)\s*"
    r"(?:(?:of|is|was|will\s+be|=|:|at|reached|reaches)\s*){0,2}"
    rf"(?P<value>{NUMBER})\s*(?P<unit>{LENGTH_UNIT_PATTERN})\b(?![/^])",
    re.IGNORECASE,
)
# The words that state the top, read out with it: "and reaches a maximum height of 20 m".
# Read back word by word from the top's phrase, never by a pattern searched from every place.
_STATING_WORDS = frozenset(
    {
        *("and", "which", "that", "it", "then", "just", "finally", "to", "up"),
        *("reach", "reaches", "reached", "rises", "rose", "attains", "attained", "climbs"),
        *("goes", "went", "has", "had", "with", "a", "an", "its", "the"),
    }
)
_STATING_REACH = 8
# A launch speed stated: "at 10 m/s", "with 15 km/h".
_LAUNCH_SPEED = re.compile(
    rf"(?<![\w.])(?:{NUMBER})\s*(?:{VELOCITY_UNIT_PATTERN})(?![\w/])", re.IGNORECASE
)
# A stated top and the one the values give agree within this: g read as 9.8 or 10 m/s², a
# value rounded as typed. Past it the values contradict each other.
_AGREE = 0.05
# The law each motion's top is, by the reader's kind.
_PEAK_OPS = {"kinematics": "vertical_max_height", "projectile": "max_height"}


def stated_peaks(text: str) -> list[re.Match[str]]:
    """Each top the text states, value and unit."""
    return list(_STATED_PEAK.finditer(text))


def without_stated_peaks(text: str) -> str:
    """``text`` with each stated top's value blanked, same length: a launch height's reader
    never reads it."""
    for match in reversed(stated_peaks(text)):
        start, end = match.start("value"), match.end("unit")
        text = text[:start] + " " * (end - start) + text[end:]
    return text


def without_redundant_peaks(text: str) -> str:
    """``text`` with each top it states read out, when it states the launch speed too: the
    launch decides the top, so the stated one is a check of the values (``stated_peak_conflict``)
    and no reader takes it for a given. Without a launch speed the top may be what the
    question gives ("reaches a maximum height of 20 m: how fast was it thrown?")."""
    peaks = stated_peaks(text)
    if not peaks or _LAUNCH_SPEED.search(text) is None:
        return text
    for match in reversed(peaks):
        start = _stating_start(text, match.start())
        text = text[:start].rstrip(" ,") + text[match.end() :]
    return text


def _stating_start(text: str, end: int) -> int:
    """Where the words stating the top begin: back from ``end`` over the stating words."""
    start = end
    for _ in range(_STATING_REACH):
        at = start
        while at > 0 and text[at - 1] in " ,":
            at -= 1
        word_end = at
        while at > 0 and text[at - 1].isalpha():
            at -= 1
        if at == word_end or text[at:word_end].lower() not in _STATING_WORDS:
            break
        start = at
    return start


def _metres(value: float, unit: str) -> float | None:
    from app.modules.physics.solvers.si import to_si

    try:
        return float(to_si(value, unit or "m"))
    except Exception:  # A unit Pint cannot read is no top to check.
        return None


def stated_peak_conflict(text: str) -> str | None:
    """Why the question has no answer as written, when the top it states is not the one its
    launch gives: "thrown up at 10 m/s, it rises 5.10 m, not the 20 m stated". None when it
    states no top, its values give none to check, or the two agree."""
    peaks = stated_peaks(text)
    if not peaks:
        return None
    from app.modules.physics.extract import extract_physics_intent

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


def _peak_of(intent: object, op: str) -> float | None:
    """The top the intent's launch reaches, in metres, by its own law; None when that law
    cannot be solved from what was read."""
    from app.modules.physics.schemas import PhysicsIntent
    from app.modules.physics.solver import solve_physics
    from app.services.solving import SolveServiceError

    if not isinstance(intent, PhysicsIntent):
        return None
    try:
        peak = intent.model_copy(
            update={"physics_op": op, "requested_ops": [], "asked": (), "asked_unit": None}
        )
        result = solve_physics(PhysicsIntent.model_validate(peak.model_dump()))
    except (SolveServiceError, ValueError):
        return None
    quantity = next(iter(result.quantities), None)
    return None if quantity is None else _metres(quantity.value, quantity.unit)


def _reason(intent: object, reached: float, stated_text: str, stated: float) -> str:
    from app.modules.physics.display import plain_number

    params = getattr(intent, "physics_params", None) or {}
    speed = params.get("v0")
    launch = f"launched at {plain_number(speed)} m/s" if speed else "launched as it states"
    return (
        f"Its values contradict each other: {launch}, a body rises to "
        f"{plain_number(reached)} m, so it cannot reach the {plain_number(stated)} m it "
        f'states ("{stated_text}"). Name the two values, and ask which one they meant.'
    )
