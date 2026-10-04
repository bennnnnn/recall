"""Whole-request guards before the existing heuristic physics extractors.

Normalize numeric spellings once. Bind two-body collision givens to their
bodies rather than silently supplying rest states. Preserve a closed list of
projectile questions rather than certifying only the first matching quantity.
No equations are solved here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.models.schemas.physics import PhysicsIntent
from app.models.schemas.physics.intent import ProjectileQuantity
from app.modules.physics.extractors.common import (
    _LENGTH_UNIT_PATTERN,
    _MASS_UNITS,
    _NUMBER,
    _VELOCITY_UNIT_PATTERN,
)
from app.modules.physics.extractors.momentum import _COLLISION_SUBJECT_RE, _TWO_DIMENSIONAL_RE
from app.modules.physics.numbers import normalize_physics_numbers, normalize_physics_units
from app.modules.physics.registry import has_supported_physics_cue
from app.services.number_text import numeric_spans

if TYPE_CHECKING:
    from app.modules.physics.catalog.spec import FormulaSpec

_MASS = re.compile(rf"({_NUMBER})\s*({_MASS_UNITS})(?![A-Za-z0-9/^])", re.IGNORECASE)
_SPEED = re.compile(rf"({_NUMBER})\s*({_VELOCITY_UNIT_PATTERN})(?![A-Za-z0-9/^])", re.IGNORECASE)
_LENGTH = re.compile(rf"({_NUMBER})\s*({_LENGTH_UNIT_PATTERN})(?![A-Za-z0-9/^])", re.IGNORECASE)
_REST = re.compile(r"\bat rest\b|\bstationary\b|\binitially still\b", re.IGNORECASE)
_ELASTIC = re.compile(r"\belastic(?:ally)?\b", re.IGNORECASE)
_STICKING = re.compile(
    r"\b(?:perfectly|completely|totally)\s+inelastic(?:ally)?\b"
    r"|\bsticks? together\b|\bstuck together\b|\bcoupled?\b"
    r"|\bembed(?:s|ded)?\b|\blocks? together\b",
    re.IGNORECASE,
)
# Direction words and restitution introduce conditions the old two-body
# extractor does not bind. Do not silently drop them or a negated rest state.
_COLLISION_QUALIFIER = re.compile(
    r"\b(?:not|never|neither|without|left|right|east|west|opposite|restitution|"
    r"energy|impulse|momentum|force|friction)\b"
    r"|\btowards? each other\b|\baway from each other\b",
    re.IGNORECASE,
)
_ASK = re.compile(r"\b(?:find|calculate|compute|determine|what\s+are)\s+", re.IGNORECASE)
_QUANTITY = re.compile(
    r"\b(?:(?:total\s+)?(?:time of flight|flight time)|"
    r"(?:maximum|max|peak) height|(?:horizontal\s+)?range|(?:impact|landing) speed)\b",
    re.IGNORECASE,
)
_GRAVITY = re.compile(
    rf"\b(?:g\s*=|gravity\s*(?:of|is|=)?)\s*{_NUMBER}(?:\s*m/s\^?2)?",
    re.IGNORECASE,
)
_ANGLE = re.compile(rf"{_NUMBER}\s*(?:degrees?|deg|°|radians?|rad)(?![A-Za-z0-9])", re.IGNORECASE)
_MATH_POWER_REQUEST = re.compile(
    r"\b(?:raised\s+to|to)\s+(?:the\s+)?"
    r"(?:\d+(?:st|nd|rd|th)?|first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)"
    r"\s+power\b"
    r"|\bto\s+the\s+power\s+of\s*[+-]?\d"
    r"|\b(?:\d+(?:st|nd|rd|th)|first|second|third|fourth|fifth|sixth|seventh|"
    r"eighth|ninth|tenth)\s+power\s+of\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PhysicsRequest:
    text: str
    rejected: bool = False
    collision: PhysicsIntent | None = None
    projectile_ops: tuple[ProjectileQuantity, ...] = ()


def _accounted_for(text: str, quantities: list[re.Match[str]]) -> bool:
    return all(
        any(quantity.start() <= start and end <= quantity.end() for quantity in quantities)
        for start, end in numeric_spans(text)
    )


def _collision_intent(text: str) -> PhysicsIntent | None:
    """Accept exactly two explicitly specified bodies and a supported model."""
    masses = list(_MASS.finditer(text))
    if len(masses) != 2 or _TWO_DIMENSIONAL_RE.search(text) or _COLLISION_QUALIFIER.search(text):
        return None
    if not _accounted_for(text, [*masses, *_SPEED.finditer(text)]):
        return None
    elastic = _ELASTIC.search(text) is not None
    sticking = _STICKING.search(text) is not None
    if elastic == sticking:
        # Generic 'inelastic' does not say that the objects stick together.
        return None
    params: dict[str, float] = {"elastic": float(elastic)}
    units: dict[str, str] = {"elastic": ""}
    consumed_speeds = 0
    for index, mass in enumerate(masses, start=1):
        value = float(mass[1])
        if value <= 0:
            return None
        end = masses[index].start() if index < len(masses) else len(text)
        clause = text[mass.end() : end]
        velocities = list(_SPEED.finditer(clause))
        at_rest = _REST.search(clause) is not None
        if len(velocities) > 1 or (not velocities and not at_rest):
            return None
        velocity, velocity_unit = (
            (float(velocities[0][1]), velocities[0][2]) if velocities else (0.0, "m/s")
        )
        if at_rest and velocity != 0:
            return None
        consumed_speeds += len(velocities)
        params.update({f"m{index}": value, f"v{index}": velocity})
        units.update({f"m{index}": mass[2], f"v{index}": velocity_unit})
    if consumed_speeds != len(list(_SPEED.finditer(text))):
        return None
    return PhysicsIntent(
        kind="momentum", physics_op="final_velocity", physics_params=params, physics_units=units
    )


def _projectile_parts(text: str) -> tuple[ProjectileQuantity, ...] | None:
    """Read a question-last list; None means a recognized but incomplete list.

    Unsupported tail requests cannot be peeled off: 'range, maximum height,
    and kinetic energy' must not be represented as two verified quantities.
    Other multipart question grammars remain outside this bounded extension.
    """
    requests = list(_ASK.finditer(text))
    if not requests:
        return None if len(list(_QUANTITY.finditer(text))) > 1 else ()
    if len(requests) > 1 and len(list(_QUANTITY.finditer(text))) >= 2:
        return None
    tail_and_suffix = re.split(r"[.?!]", text[requests[-1].end() :], maxsplit=1)
    tail = tail_and_suffix[0].strip()
    matches = list(_QUANTITY.finditer(tail))
    if len(matches) < 2:
        return None if len(list(_QUANTITY.finditer(text))) > 1 else ()
    if len(tail_and_suffix) > 1 and _QUANTITY.search(tail_and_suffix[1]):
        return None
    remainder = _QUANTITY.sub("", tail)
    if re.sub(r"\b(?:the|its|and)\b|[\s,]", "", remainder, flags=re.IGNORECASE):
        return None
    ops: list[ProjectileQuantity] = []
    for match in matches:
        phrase = match.group().lower()
        op: ProjectileQuantity
        if "time" in phrase:
            op = "time_of_flight"
        elif "height" in phrase:
            op = "max_height"
        elif "range" in phrase:
            op = "range"
        else:
            op = "impact_speed"
        if op not in ops:
            ops.append(op)
    if len(ops) < 2:
        return ()
    context = re.sub(
        r"\b(?:ignor(?:e|ing)|neglect(?:ing)?|no|without)\s+(?:the\s+)?air resistance\b",
        "",
        text,
        flags=re.IGNORECASE,
    )
    if re.search(r"\b(?:air resistance|drag|wind|spin)\b", context, re.IGNORECASE):
        return None
    # All parts describe one launch; do not choose the first of two speeds or
    # angles, or turn an unrelated length (a wall) into the launch height.
    if len(list(_SPEED.finditer(text))) != 1 or len(list(_ANGLE.finditer(text))) != 1:
        return None
    lengths = list(_LENGTH.finditer(text))
    if len(lengths) > 1:
        return None
    if lengths and not re.search(
        r"\b(?:height|cliff|ledge|platform|h0)\b",
        text[: requests[-1].start()],
        re.IGNORECASE,
    ):
        return None
    gravities = list(_GRAVITY.finditer(text))
    if len(gravities) > 1 or not _accounted_for(
        text, [*_SPEED.finditer(text), *_ANGLE.finditer(text), *lengths, *gravities]
    ):
        return None
    return tuple(ops)


def prepare_physics_request(text: str) -> PhysicsRequest:
    """Preflight at the dispatch boundary so refusals cannot fall into algebra."""
    unit_normalized = normalize_physics_units(text)
    if not has_supported_physics_cue(unit_normalized):
        return PhysicsRequest(unit_normalized)
    normalized = normalize_physics_numbers(unit_normalized)
    if normalized is None:
        return PhysicsRequest(text, rejected=True)
    if _MATH_POWER_REQUEST.search(normalized):
        # Do not use earlier physical work/time data to answer a separate
        # exponent request later in the message. The subject layer may decline
        # the compound turn, but it must never certify the unrelated 20 W.
        return PhysicsRequest(normalized, rejected=True)
    if _COLLISION_SUBJECT_RE.search(normalized) and len(list(_MASS.finditer(normalized))) >= 2:
        collision = _collision_intent(normalized)
        return PhysicsRequest(normalized, rejected=collision is None, collision=collision)
    ops = _projectile_parts(normalized)
    return PhysicsRequest(normalized, rejected=ops is None, projectile_ops=ops or ())


_LATEX_COMMAND = re.compile(r"\\[A-Za-z]+")
# An expression names g as an identifier (m*g). Latex writes the product glued
# (mg, gh_1, 2g). Commands are removed first, so the g in \log or \gamma is not one.
_G_NAME = re.compile(r"(?<![A-Za-z0-9_])g(?![A-Za-z0-9_])")


def _text_uses_g(text: str | None) -> bool:
    if not text:
        return False
    if "\\" in text or "{" in text:
        return "g" in _LATEX_COMMAND.sub(" ", text)
    return _G_NAME.search(text) is not None


def _variant_uses_g(latex: str | None, expression: str | None, lines: tuple[str, ...]) -> bool:
    return _text_uses_g(latex) or _text_uses_g(expression) or any(map(_text_uses_g, lines))


def _selection_uses_gravity(spec: FormulaSpec, params: dict[str, float]) -> bool:
    """Whether this filled formula multiplies by g.

    A variable named g on the catalog is not enough. Bernoulli declares g for
    the height variant, and the horizontal form does not use it.
    """
    from app.modules.physics.catalog import matching_variant

    if not any(variable.name == "g" for variable in spec.variables):
        return False
    variant = matching_variant(spec, params)
    if variant is not None and (variant.latex is not None or variant.expression or variant.lines):
        return _variant_uses_g(variant.latex, variant.expression, variant.lines)
    if _text_uses_g(spec.base_latex) or _text_uses_g(spec.expression):
        return True
    # g appears only in a variant that this selection did not take.
    if any(_variant_uses_g(item.latex, item.expression, item.lines) for item in spec.variants):
        return False
    return True


def complete_physics_intent(intent: PhysicsIntent, request: PhysicsRequest) -> PhysicsIntent | None:
    """Attach every requested projectile quantity, or refuse a different solve.

    A solve that skipped a stated quantity of a kind it uses is refused too.
    The asked dimensions ride along so the block can refuse an answer to a
    different question.
    """
    from app.modules.physics.accounting import competing_given
    from app.modules.physics.ask import asked_dimensions, asked_phrases, asked_unit
    from app.modules.physics.bodies import SCHOOL_GRAVITY, names_body_without_school_gravity
    from app.modules.physics.catalog import formula_spec
    from app.modules.physics.extractors.common import _detect_gravity, stated_gravity

    params = intent.physics_params or {}
    if intent.kind == "suvat":
        phrases = asked_phrases(request.text)
        displacement = (
            bool(phrases and phrases[0] == "displacement")
            if intent.physics_op == "suvat_distance"
            else "displacement" in request.text.lower()
        )
        params = {**params, "distance_path": float(not displacement)}
        intent = intent.model_copy(
            update={
                "physics_params": params,
                "physics_units": {**(intent.physics_units or {}), "distance_path": ""},
            }
        )
    if any(value < 0 for key, value in params.items() if key in {"m", "m1", "m2"}):
        return None
    spec = formula_spec(intent.physics_op or "")
    uses_g = spec is not None and _selection_uses_gravity(spec, params)
    # "On Jupiter" with no g written: Earth's school value would answer another planet.
    # Only a selection that actually multiplies by g. Horizontal Bernoulli declares
    # g for its height variant and does not use it.
    if (
        uses_g
        and stated_gravity(request.text) is None
        and names_body_without_school_gravity(request.text.lower())
    ):
        return None
    # Moon and Mars have a school g. A solver that would otherwise fill Earth's
    # must use that body's value when the question never wrote g.
    if uses_g and "g" not in params:
        detected = _detect_gravity(request.text)
        if detected != SCHOOL_GRAVITY["earth"]:
            params = {**params, "g": detected}
            units = {**(intent.physics_units or {}), "g": "m/s^2"}
            intent = intent.model_copy(update={"physics_params": params, "physics_units": units})
    if competing_given(intent, request.text) is not None:
        return None
    asked = asked_dimensions(request.text)
    unit = asked_unit(request.text)
    if request.projectile_ops:
        if intent.kind != "projectile":
            return None
        return PhysicsIntent.model_validate(
            {
                **intent.model_dump(),
                "physics_op": request.projectile_ops[0],
                "requested_ops": list(request.projectile_ops),
                "asked": asked,
                "asked_unit": unit,
            }
        )
    return intent.model_copy(update={"asked": asked, "asked_unit": unit})
