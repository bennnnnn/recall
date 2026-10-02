"""What a falling-body question asks for, and which way its velocity points."""

from __future__ import annotations

import re

from app.modules.physics.extractors.common import _NUMBER, _detect_gravity

_H0_KEYWORDS = (
    "from",
    "initial height",
    "height of",
    "high",
    "above",
    "cliff",
    "off",
    "ledge",
    "h0",
    "dropped",
)


# The moment of landing, said the ways people say it. With no time given,
# a speed asked at this moment is the impact speed.
_IMPACT_RE = re.compile(
    r"\bimpact\b|\b(?:hits?|strikes?|reach(?:es)?|lands?|hitting|striking|reaching|landing)\s+"
    r"(?:the\s+)?(?:ground|floor|water|bottom|surface)\b",
    re.IGNORECASE,
)


def _asks_speed(lower: str, asked: tuple[str, ...]) -> bool:
    if any(
        cue in lower for cue in ("speed after", "speed when", "impact speed", "speed at impact")
    ):
        return True
    # "how fast is it going after 2 s" is the spoken form of "speed after".
    return "how fast" in lower or asked == ("speed",)


def _asks_velocity(lower: str, asked: tuple[str, ...]) -> bool:
    if asked == ("velocity",) or "velocity after" in lower or "velocity when" in lower:
        return True
    if "what is its velocity" in lower or "what is the velocity" in lower:
        return True
    if "v when" in lower:
        return True
    return re.search(r"\b(?:find|what is)\s+v\b", lower) is not None


def _asks_position(lower: str) -> bool:
    return "height after" in lower or "position after" in lower


def _asks_max_height(lower: str) -> bool:
    """Return whether a vertical launch asks for its peak height.

    A straight-up throw is handled by the one-dimensional kinematics solver,
    not the angled-projectile extractor.  Without this check, ``how high``
    silently fell through to the kinematics default and returned the time to
    ground instead of a height.
    """
    return (
        re.search(
            r"\bmax(?:imum)?\s+height\b|\bhow high\b|\bhighest point\b|\bpeak height\b"
            r"|\bheight (?:does|will|can) (?:it |the \w+ )?(?:reach|rise)",
            lower,
        )
        is not None
    )


_STATED_ACCELERATION_RE = re.compile(r"(-?(?<!\d)\d+(?:\.\d+)?)\s*m/s\^?2(?![0-9])", re.IGNORECASE)

# The question has to ask for the acceleration. The bare word must not replace
# a time, height, or speed question, and it must not drop that question.
_ASKS_ACCELERATION_RE = re.compile(
    r"\b(?:find|what(?:'s| is)|calculate|compute|determine)\b"
    r"(?:(?!\b(?:time|height|speed|velocity|distance)\b).){0,60}\bacceleration\b",
    re.IGNORECASE,
)
_ASKS_TIME_RE = re.compile(
    r"\b(?:how long|time to|find the time|what is the time)\b",
    re.IGNORECASE,
)
_DOWN_BEFORE_RE = re.compile(
    r"\b(?:downward|downwards|thrown down|launched downward)\b",
    re.IGNORECASE,
)
_UP_BEFORE_RE = re.compile(
    r"\b(?:upward|upwards|thrown up|launched upward)\b",
    re.IGNORECASE,
)


def _velocity_is_downward(text: str, value: float, unit: str) -> bool:
    """True when downward sits on this velocity, not on a later question."""
    if value <= 0 or not unit:
        return False
    pattern = re.compile(
        rf"({_NUMBER})\s*{re.escape(unit)}(?![A-Za-z0-9/^])",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        if abs(float(match.group(1)) - value) > 1e-6:
            continue
        before = text[max(0, match.start() - 64) : match.start()]
        after = text[match.end() : match.end() + 48]
        earlier = before.rfind(".")
        if earlier != -1:
            before = before[earlier + 1 :]
        later = after.find(".")
        if later != -1:
            after = after[:later]
        after_lower = after.lower()
        down_after = re.search(r"\b(?:downward|downwards)\b", after_lower)
        if down_after is not None:
            gap = after_lower[: down_after.start()]
            if re.search(r"\b(?:after|find|what|when)\b", gap) is None:
                return True
        positions: list[tuple[int, str]] = []
        for kind, rx in (("down", _DOWN_BEFORE_RE), ("up", _UP_BEFORE_RE)):
            found = list(rx.finditer(before))
            if found:
                positions.append((found[-1].start(), kind))
        if positions and max(positions)[1] == "down":
            return True
    return False


def _states_a_non_gravity_acceleration(text: str) -> bool:
    """True when the question names an acceleration that is not the gravity in play.

    Free fall means gravity *is* the acceleration, so a question that supplies
    its own is not a free-fall question. Without this, kinematics claimed
    "a car accelerates from rest at 3 m/s^2, how long to reach 15 m/s" and
    answered **3.06 s** — which is 15/9.81, the time a ball thrown up at 15 m/s
    takes to stop. The stated 3 m/s² was discarded and Earth's gravity
    substituted for it; the true answer is 5.00 s.

    A named gravity is the exception rather than a special case: "g = 1.6",
    "gravity of 1.62", "on the moon" all set the free-fall acceleration, and
    ``_detect_gravity`` already knows what it is. Comparing against that value
    keeps those questions here and sends only the genuinely different ones on.
    """
    gravity = _detect_gravity(text)
    return any(
        abs(float(m.group(1)) - gravity) > 1e-9 for m in _STATED_ACCELERATION_RE.finditer(text)
    )
