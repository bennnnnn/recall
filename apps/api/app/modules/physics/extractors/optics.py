"""Optics extractors: lenses, mirrors, refraction, magnification."""

from __future__ import annotations

import re

from app.modules.physics.extractors.angles import _INCLINE_ANGLE_RE
from app.modules.physics.extractors.common import (
    _DECIMAL,
    _DEGREE_WORD,
    _LENGTH_UNIT_PATTERN,
    _NUMBER,
    _VELOCITY_UNIT_PATTERN,
    _find_value_with_specific_unit,
    _strip_param_assignments,
)
from app.modules.physics.extractors.cues import (
    _has_cue,
)
from app.modules.physics.schemas import PhysicsIntent
from app.services.law_binding.ask import ASK_VERBS
from app.services.text_match import has_equation

_OPTICS_CUES = (
    "focal length",
    "refractive index",
    "critical angle",
    "index of refraction",
    "converging lens",
    "convex lens",
    "concave mirror",
    "converging mirror",
    "magnification",
    "snell",
    "lens power",
    "double slit",
    "double-slit",
    "fringe spacing",
    "single slit diffraction",
    "single-slit diffraction",
    "malus",
    "brewster",
    # Not a bare "mirror": "I bought a bathroom mirror for 30 dollars" is not optics.
    "plane mirror",
    "angle of reflection",
    "angle of incidence",
    "reflected ray",
)

# The law of reflection. One angle is given, against the normal or against the
# mirror's surface, and the asked angle is against one of them too.
_NOT_REFLECTION_RE = re.compile(
    r"refract|snell|critical angle|index of refraction|\blens|focal|concave|convex"
)
_NORMAL_REF_RE = re.compile(r"\bnormal\b|\bangle\s+of\s+incidence\b|\bincident\s+angle\b")
_SURFACE_REF_RE = re.compile(r"\b(?:surface|mirror|glancing|grazing)\b")
_SURFACE_ASK_RE = re.compile(
    r"\b(?:with|and|to|from|against|relative\s+to)\s+(?:the\s+)?(?:plane\s+)?"
    r"(?:mirror(?:'s)?(?:\s+surface)?|surface)\b"
)
_BETWEEN_RAYS_RE = re.compile(
    r"between\s+the\s+(?:incident|incoming)\s+(?:ray\s+)?and\s+(?:the\s+)?reflected"
    r"|between\s+the\s+reflected\s+(?:ray\s+)?and\s+(?:the\s+)?(?:incident|incoming)"
)
_CLAUSE_END_RE = re.compile(r"[.?!;](?:\s|$)")
# "If the angle of incidence is 42.5 degrees, what is ...": the comma ends the given.
_GIVEN_END_RE = re.compile(r"[.?!;,](?:\s|$)")
# "the angle between the incident ray and the mirror is 50 degrees"
_SURFACE_BEFORE_RE = re.compile(
    r"\b(?:between|with)\b[^.?!]{0,40}\b(?:mirror|surface)\s+(?:is|of|=|measures)\s*$"
)
_CLAUSE_LEAD_RE = re.compile(r"\b(?:when|if|where|as|after|while)\b")


def _reflection_intent(cleaned: str) -> PhysicsIntent | None:
    """35 degrees to a mirror's surface is 55 to the normal, and so is the reflection.

    Asked of the model, it answered 35. An angle given without saying which
    line it is measured from is left alone: guessing the line is the error.
    """
    lower = cleaned.lower()
    if "reflect" not in lower or _NOT_REFLECTION_RE.search(lower):
        return None
    angles = list(_INCLINE_ANGLE_RE.finditer(cleaned))
    if len(angles) != 1:
        return None
    match = angles[0]
    value = float(match.group(1))
    if not 0 <= value <= 90:
        return None
    # The given angle's clause: from its sentence start, or from "when" in a
    # one-sentence question, to the end of its sentence.
    after = lower[match.end() :]
    end = _GIVEN_END_RE.search(after)
    clause_end = match.end() + (end.start() if end else len(after))
    clause_start = max(
        (found.end() for found in _CLAUSE_END_RE.finditer(lower, 0, match.start())), default=0
    )
    lead = list(_CLAUSE_LEAD_RE.finditer(lower, clause_start, match.start()))
    if lead:
        clause_start = lead[-1].start()
    given_clause = lower[clause_start:clause_end]
    if _NORMAL_REF_RE.search(given_clause):
        param = "angle"
    elif (
        _SURFACE_REF_RE.search(lower[match.end() : clause_end])
        or _SURFACE_BEFORE_RE.search(lower[clause_start : match.start()])
        or re.search(r"\b(?:glancing|grazing)\b", given_clause)
    ):
        param = "angle_surface"
    else:
        return None
    asked = lower[:clause_start] + " " + lower[clause_end:]
    if not ASK_VERBS.search(asked) and "?" not in asked:
        return None
    if _BETWEEN_RAYS_RE.search(asked):
        op = "reflection_ray_angle"
    elif _SURFACE_ASK_RE.search(asked) and "normal" not in asked:
        op = "reflection_surface_angle"
    elif "normal" in asked or "angle of reflection" in asked or "reflected" in asked:
        op = "reflection_angle"
    else:
        return None
    return PhysicsIntent(
        kind="optics",
        physics_op=op,
        physics_params={param: value},
        physics_units={param: "deg"},
        operation="solve",
    )


_HEIGHT_RE = re.compile(r"\b(?:tall|high|height)\b")
_DIVERGING_RE = re.compile(
    r"\bdiverging\b|\bconcave\s+lens\b|\bvirtual\s+image\b|\bnegative\s+focal\b",
    re.IGNORECASE,
)


def _extract_optics_intent(cleaned: str) -> PhysicsIntent | None:
    lower = cleaned.lower()
    if not _has_cue(lower, _OPTICS_CUES):
        return None
    without_index_assignments = re.sub(r"\bn[12]\s*=\s*" + _NUMBER, "", cleaned, flags=re.I)
    if has_equation(_strip_param_assignments(without_index_assignments)):
        return None
    if _DIVERGING_RE.search(cleaned):
        return None
    # The catalog owns a microscope and the lens-maker equation. This reader
    # would treat "objective" as an object distance.
    if "microscope" in lower or "lens maker" in lower or "lensmaker" in lower:
        return None

    reflection = _reflection_intent(cleaned)
    if reflection is not None:
        return reflection

    if "malus" in lower:
        intensity = _find_value_with_specific_unit(
            cleaned, r"W/m\^?2|watts?\s+per\s+square\s+met(?:er|re)", ("intensity",)
        )
        angle_match = _INCLINE_ANGLE_RE.search(cleaned)
        if intensity is None or angle_match is None:
            return None
        return PhysicsIntent(
            kind="optics",
            physics_op="malus_intensity",
            physics_params={"intensity0": intensity[0], "angle": float(angle_match.group(1))},
            physics_units={"intensity0": intensity[1] or "W/m^2", "angle": "deg"},
            operation="solve",
        )

    if "brewster" in lower:
        indexes = [
            float(value)
            for value in re.findall(rf"\bn[12]\s*(?:=|is)\s*({_NUMBER})", cleaned, re.I)
        ]
        if len(indexes) != 2:
            return None
        return PhysicsIntent(
            kind="optics",
            physics_op="brewster_angle",
            physics_params={"n1": indexes[0], "n2": indexes[1]},
            physics_units={"n1": "", "n2": ""},
            operation="solve",
        )

    if "double slit" in lower or "double-slit" in lower or "fringe spacing" in lower:
        wavelength = _find_value_with_specific_unit(
            cleaned, _LENGTH_UNIT_PATTERN, ("wavelength",), require_keyword=True
        )
        screen = _find_value_with_specific_unit(
            cleaned,
            _LENGTH_UNIT_PATTERN,
            ("screen distance", "to the screen"),
            require_keyword=True,
        )
        separation = _find_value_with_specific_unit(
            cleaned, _LENGTH_UNIT_PATTERN, ("slit separation", "slits"), require_keyword=True
        )
        if wavelength is None or screen is None or separation is None:
            return None
        return PhysicsIntent(
            kind="optics",
            physics_op="double_slit_fringe_spacing",
            physics_params={"wavelength": wavelength[0], "L": screen[0], "d": separation[0]},
            physics_units={
                "wavelength": wavelength[1] or "m",
                "L": screen[1] or "m",
                "d": separation[1] or "m",
            },
            operation="solve",
        )

    if "single slit" in lower or "single-slit" in lower:
        wavelength = _find_value_with_specific_unit(
            cleaned, _LENGTH_UNIT_PATTERN, ("wavelength",), require_keyword=True
        )
        screen = _find_value_with_specific_unit(
            cleaned,
            _LENGTH_UNIT_PATTERN,
            ("screen distance", "to the screen"),
            require_keyword=True,
        )
        width = _find_value_with_specific_unit(
            cleaned, _LENGTH_UNIT_PATTERN, ("slit width", "aperture"), require_keyword=True
        )
        if wavelength is None or screen is None or width is None:
            return None
        return PhysicsIntent(
            kind="optics",
            physics_op="diffraction_central_width",
            physics_params={"wavelength": wavelength[0], "L": screen[0], "d": width[0]},
            physics_units={
                "wavelength": wavelength[1] or "m",
                "L": screen[1] or "m",
                "d": width[1] or "m",
            },
            operation="solve",
        )

    if "lens power" in lower:
        focal = _find_value_with_specific_unit(
            cleaned, _LENGTH_UNIT_PATTERN, ("focal length", "focal"), require_keyword=True
        )
        if focal is None:
            return None
        return PhysicsIntent(
            kind="optics",
            physics_op="lens_power",
            physics_params={"focal": focal[0]},
            physics_units={"focal": focal[1] or "m"},
            operation="solve",
        )

    index_values = [
        float(m.group(1))
        for m in re.finditer(
            r"(?:refractive\s+index|index\s+of\s+refraction)\s*(?:of|is|=)?\s*"
            r"(-?\d+(?:\.\d+)?)",
            cleaned,
            re.IGNORECASE,
        )
    ]
    angles = [float(m.group(1)) for m in _INCLINE_ANGLE_RE.finditer(cleaned)]
    if len(angles) < 2:
        # "bends from 30 to 20 degrees" puts the unit on the second angle only,
        # so the scan above sees one number where the question gave two.
        pair = re.search(
            rf"from\s+(-?\d+(?:\.\d+)?)\s*{_DEGREE_WORD}?\s*to\s+"
            rf"({_DECIMAL})\s*{_DEGREE_WORD}",
            cleaned,
            re.IGNORECASE,
        )
        if pair is not None:
            angles = [float(pair.group(1)), float(pair.group(2))]

    if "critical angle" in lower:
        if len(index_values) != 1 or index_values[0] <= 1:
            return None
        return PhysicsIntent(
            kind="optics",
            physics_op="critical_angle",
            physics_params={"n1": index_values[0]},
            physics_units={"n1": ""},
            operation="solve",
        )

    if "refractive index" in lower or "index of refraction" in lower or "snell" in lower:
        # n = sin(t1) / sin(t2) when both angles are given and the index is not.
        if len(angles) == 2 and not index_values:
            return PhysicsIntent(
                kind="optics",
                physics_op="refractive_index",
                physics_params={"angle": angles[0], "angle2": angles[1]},
                physics_units={"angle": "deg", "angle2": "deg"},
                operation="solve",
            )
        medium_speed = _find_value_with_specific_unit(
            cleaned,
            _VELOCITY_UNIT_PATTERN,
            ("travels", "speed", "in glass", "in water", "in the medium"),
        )
        if medium_speed is not None and not index_values:
            return PhysicsIntent(
                kind="optics",
                physics_op="refractive_index",
                physics_params={"v_wave": medium_speed[0]},
                physics_units={"v_wave": medium_speed[1] or "m/s"},
                operation="solve",
            )
        return None

    focal_match = re.search(
        rf"\bfocal(?:\s+length)?\b\s*(?:of|is|=|:)?\s*({_NUMBER})\s*"
        rf"({_LENGTH_UNIT_PATTERN})(?![A-Za-z0-9/^])",
        cleaned,
        re.IGNORECASE,
    )
    focal = (
        (float(focal_match.group(1)), focal_match.group(2))
        if focal_match is not None
        else _find_value_with_specific_unit(
            cleaned, _LENGTH_UNIT_PATTERN, ("focal length", "focal"), require_keyword=True
        )
    )
    obj_match = re.search(
        rf"\bobject(?:\s+distance)?\b\s*(?:of|is|=|:)?\s*({_NUMBER})\s*"
        rf"({_LENGTH_UNIT_PATTERN})(?![A-Za-z0-9/^])",
        cleaned,
        re.IGNORECASE,
    ) or re.search(
        # "An object is placed 15 cm from the mirror": the object's own
        # sentence. The nearest number was the focal length just before it.
        rf"\bobject\b[^.?!]{{0,30}}?\b(?:placed|located|positioned|sits|is)\s+(?:at\s+)?"
        rf"({_NUMBER})\s*({_LENGTH_UNIT_PATTERN})(?![A-Za-z0-9/^])",
        cleaned,
        re.IGNORECASE,
    )
    obj = (
        (float(obj_match.group(1)), obj_match.group(2))
        if obj_match is not None
        else _find_value_with_specific_unit(
            cleaned, _LENGTH_UNIT_PATTERN, ("object",), require_keyword=True
        )
    )
    if "magnification" in lower:
        # Heights only: "the image forms 60 cm from the lens" is a distance,
        # and m = -v/u (the catalog binder) answers that one.
        img = _find_value_with_specific_unit(
            cleaned, _LENGTH_UNIT_PATTERN, ("image",), require_keyword=True
        )
        if img is None or obj is None or _HEIGHT_RE.search(lower) is None:
            return None
        return PhysicsIntent(
            kind="optics",
            physics_op="magnification",
            physics_params={"h_img": img[0], "h_obj": obj[0]},
            physics_units={"h_img": img[1] or "m", "h_obj": obj[1] or "m"},
            operation="solve",
        )

    if focal is None or obj is None:
        return None
    # Only the ray diagram reads it: a concave mirror reflects, a lens transmits.
    mirror = {"mirror": 1.0} if "mirror" in lower else {}
    return PhysicsIntent(
        kind="optics",
        physics_op="image_distance",
        physics_params={"focal": focal[0], "d_obj": obj[0], **mirror},
        physics_units={
            "focal": focal[1] or "m",
            "d_obj": obj[1] or "m",
            **dict.fromkeys(mirror, ""),
        },
        operation="solve",
    )
