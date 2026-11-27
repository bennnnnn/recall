"""Whether a text carries a topic's cue words or cue patterns."""

from __future__ import annotations

import re

# Words that say a question has no friction: "a frictionless pulley", "no friction",
# "ignore friction". The word "friction" inside them names no friction to read.
NO_FRICTION_RE = re.compile(
    r"\b(?:frictionless|without\s+friction|no\s+friction|"
    r"(?:ignore|ignoring|neglect|neglecting)\s+friction)\b",
    re.IGNORECASE,
)
# A stated coefficient of friction, as every reader of one reads it ("friction.py",
# ``net_force.friction_coefficients``): "between the block and the plane" before its value
# ("The coefficient of kinetic friction between the block and the plane is 0.20"); its symbol's
# subscript either way ("μₖ = 0.20", "mu_k = 0.20"); and what leads from its name to its value,
# "of", "=", "is", a label's colon and a list's symbol ("Coefficient of kinetic friction: μₖ =
# 0.20").
_SURFACE_NAME = r"(?:the\s+)?[a-z]+(?:\s+[a-z]+)?"
COEFFICIENT_BETWEEN = rf"(?:\s+between\s+{_SURFACE_NAME}\s+and\s+{_SURFACE_NAME})?"
MU_SUBSCRIPT = r"(?:_?[ks]|[\u2096\u209b])?"
# Each run of space is read once (possessive): "mu" and a run of spaces took quadratic time.
COEFFICIENT_LEADS = rf"\s*+(?:of|=|is|:)?\s*+(?:(?:\bmu|\u03bc){MU_SUBSCRIPT}\s*+=\s*+)?"

# Words that start a body from rest, the one reader of them: "released from rest", "starts at
# rest", "from a standstill", "initially at rest", "initially stationary". A stated starting
# speed of 0 says it again.
FROM_REST_RE = re.compile(
    r"\bfrom\s+(?:rest|a\s+standstill|standstill|a\s+standing\s+start|a\s+stop)\b"
    r"|\b(?:starts?|initially)\s+at\s+rest\b|\binitially\s+stationary\b",
    re.IGNORECASE,
)


def _has_cue_either_case(
    cleaned: str,
    cues: tuple[str, ...],
    regexes: tuple[re.Pattern[str], ...] = (),
) -> bool:
    """`has_cue`, but the regexes see the text as written as well as lowered.

    A few cue regexes mean the SI symbols `V` and `A` and are case-sensitive on
    purpose - "12 V and 3 A" is a circuit, "12 v cards and 3 a piece" is not.
    Handing them only lowercased text silently disables them, which is exactly
    what the pre-filter did: `needs_symbolic` dropped questions the extractor
    would have answered, because the extractor saw the original casing and the
    pre-filter did not. The two have to see the same thing.

    A case-insensitive regex finds the same thing in both, so it reads once.
    """
    lower = cleaned.lower()
    if any(cue in lower for cue in cues):
        return True
    return any(
        rx.search(cleaned) or (not rx.flags & re.IGNORECASE and rx.search(lower)) for rx in regexes
    )


def has_cue(
    lower: str,
    cues: tuple[str, ...],
    regexes: tuple[re.Pattern[str], ...] = (),
) -> bool:
    """Cue match: plain substrings, plus regexes for cues that need a boundary.

    Most cues are safe as substrings ("net force"). A few are not: "find f"
    sits inside "find factors", and "KE" inside "take". Those are expressed as
    regexes instead of widening the tuple.
    """
    if any(cue in lower for cue in cues):
        return True
    return any(rx.search(lower) for rx in regexes)
