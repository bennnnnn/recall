"""Stable public facade for physics detection and extraction."""

from __future__ import annotations

import re
from functools import lru_cache

from app.models.schemas.physics import PhysicsIntent
from app.modules.physics.registry import (
    PHYSICS_CUE_RES,
    PHYSICS_CUES,
    PHYSICS_EXTRACTORS,
    has_supported_physics_cue,
)
from app.services.number_text import read_scientific_numbers
from app.services.symbolic_text import (
    _MAX_PHYSICS_REQUEST,
    _MAX_SUBJECT_TEXT,
    normalize_symbolic_request,
)
from app.services.text_normalize import cap_text_head_tail

__all__ = [
    "PHYSICS_CUES",
    "PHYSICS_CUE_RES",
    "PHYSICS_EXTRACTORS",
    "extract_physics_intent",
    "has_supported_physics_cue",
    "needs_physics",
]

_DIGIT_FREE_PHYSICS_RE = re.compile(
    r"\b(?:escape velocity|escape speed|orbital velocity|orbital speed|"
    r"surface gravity|gravitational field strength)\b"
    r"[^.?!]{0,60}?\b(?:earth|moon|mars|jupiter|sun)\b"
    r"|\b(?:earth|moon|mars|jupiter|sun)\b[^.?!]{0,60}?"
    r"\b(?:escape velocity|escape speed|orbital velocity|orbital speed|"
    r"surface gravity|gravitational field strength)\b",
    re.IGNORECASE,
)

# Concept explanations also need the native-visual policy even when they do
# not state numerical inputs. Keep this request-shaped so everyday uses of
# "energy", "work", or "friction" do not claim an unrelated chat turn.
_PHYSICS_CONCEPT = (
    r"(?:physics|kinematics|thermodynamics|electromagnetism|electrostatics|"
    r"newton['\u2019]s laws?|projectile motion|simple harmonic motion|"
    r"kinetic energy|potential energy|centripetal acceleration|"
    r"conservation of (?:energy|momentum)|free[- ]body diagrams?)"
)
_CONCEPTUAL_PHYSICS_RE = re.compile(
    r"^(?:please\s+)?(?:(?:explain|describe|teach\s+me(?:\s+about)?|"
    r"what\s+(?:is|are|about)|how\s+(?:does|do))\s+(?:the\s+)?"
    + _PHYSICS_CONCEPT
    + r"\b|"
    + _PHYSICS_CONCEPT
    + r"[.!?]*$)",
    re.IGNORECASE,
)

# Recognized as physics, then left unverified. Closed school templates that
# now have a solver stay off this list, including Kirchhoff, Gauss, Faraday,
# inductors, RL, AC, Poiseuille, the quantum oscillator's levels and the
# Rydberg formula.
_UNVERIFIED_PHYSICS_PHRASES: tuple[str, ...] = (
    "schrödinger equation",
    "planck distribution",
    "binding energy",
    "mass defect",
    "general relativity",
)

_ADVANCED_PHYSICS_RE = re.compile(
    r"\b(?:schr[oö]dinger|hamilton(?:ian|'s equations?)?|lagrang(?:ian|e)|"
    r"maxwell(?:'s)? equations?|general relativity|schwarzschild|"
    r"quantum harmonic oscillator|wave ?function|probability density|"
    r"diffraction grating|capillary rise|transformer|nuclear reaction|"
    r"binding energy|mass defect|rydberg|blackbody distribution|"
    r"planck(?:'s)? distribution|gear ratio)\b",
    re.IGNORECASE,
)


# A supplied nuclear mass is a chemistry mass-defect calculation. A bare
# ``mass =`` is not that mass, so those words stay on the unverified physics path.
_SUPPLIED_NUCLEAR_MASS_RE = re.compile(
    r"\b(?:mass defect|binding energy)\b[\s\S]{0,80}\bnuclear mass\s*=\s*-?(?:\d|\.\d)",
    re.IGNORECASE,
)


# Detection reads the head and tail of a long message, where the question sits
# in a paste. It runs on every chat turn, so its cost must not grow with the
# paste; the extractors still read the whole request, up to their own cap.
_DETECTION_WINDOW = 4_000

# Detection and extraction are pure functions of the text, and one chat turn
# asks both questions of the same line from turn prep, routing, the prompt
# builder, and the direct reply. Each turn pays once.
_CACHE_SIZE = 128


@lru_cache(maxsize=_CACHE_SIZE)
def needs_physics(text: str) -> bool:
    """True for a verified template or an unmistakable physics-only request."""
    from app.modules.physics.symbolic.request import is_symbolic_physics_request

    if is_symbolic_physics_request(text):
        return True
    normalized = normalize_symbolic_request(read_scientific_numbers(text), limit=_MAX_SUBJECT_TEXT)
    if not normalized:
        return False
    cleaned = cap_text_head_tail(normalized, _DETECTION_WINDOW)
    if _SUPPLIED_NUCLEAR_MASS_RE.search(cleaned) is not None:
        return False
    if _ADVANCED_PHYSICS_RE.search(cleaned) is not None:
        return True
    if re.search(r"\bphysics\s+(?:problem|question|exercise)\b", cleaned, re.IGNORECASE):
        return True
    if _CONCEPTUAL_PHYSICS_RE.search(cleaned.strip()):
        return True
    from app.modules.physics.extractors.drag import closed_drag_request

    if closed_drag_request(cleaned):
        return True
    if not any(char.isdigit() for char in cleaned):
        return _DIGIT_FREE_PHYSICS_RE.search(cleaned) is not None
    if has_supported_physics_cue(cleaned):
        return True
    # The catalog is a cue too: a question that states one law's inputs and
    # asks for its result exactly ("the weight of a 70 kg person") is physics.
    from app.modules.physics.binding import bind_physics_intent

    return bind_physics_intent(cleaned) is not None


def extract_physics_intent(text: str) -> PhysicsIntent | None:
    """Extract one complete physics request without entering math dispatch.

    Callers get their own copy, so none can change what the next one reads.
    """
    intent = _extract_physics_intent(text)
    return None if intent is None else intent.model_copy(deep=True)


@lru_cache(maxsize=_CACHE_SIZE)
def _extract_physics_intent(text: str) -> PhysicsIntent | None:
    from app.modules.physics.request import complete_physics_intent, prepare_physics_request

    cleaned = normalize_symbolic_request(read_scientific_numbers(text), limit=_MAX_PHYSICS_REQUEST)
    if not cleaned:
        return None
    request = prepare_physics_request(cleaned)
    if request.rejected:
        return None
    if request.collision is not None:
        return complete_physics_intent(request.collision, request)
    for extractor in PHYSICS_EXTRACTORS:
        intent = extractor(request.text)
        if intent is not None:
            return complete_physics_intent(intent, request)
    # Last: a question the extractors declined may still state a catalog law's
    # inputs plainly and ask for its result. Only one exact fit is answered,
    # and only for text the physics gate calls physics, so the binder adds
    # answers to physics questions and never takes a question from math.
    if not needs_physics(text):
        return None
    from app.modules.physics.binding import bind_physics_intent

    bound = bind_physics_intent(request.text)
    return None if bound is None else complete_physics_intent(bound, request)
