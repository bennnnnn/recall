"""Optics extractors: lenses, mirrors, refraction, magnification."""

from __future__ import annotations

import re

from app.models.schemas.physics import PhysicsIntent
from app.modules.physics.extractors.common import (
    _INCLINE_ANGLE_RE,
    _LENGTH_UNIT_PATTERN,
    _NUMBER,
    _VELOCITY_UNIT_PATTERN,
    _find_value_with_specific_unit,
    _has_cue,
    _strip_param_assignments,
)
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
            r"from\s+(-?\d+(?:\.\d+)?)\s*(?:degrees?|deg|\u00b0)?\s*to\s+"
            r"(-?(?<!\d)\d+(?:\.\d+)?)\s*(?:degrees?|deg|\u00b0)",
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
    return PhysicsIntent(
        kind="optics",
        physics_op="image_distance",
        physics_params={"focal": focal[0], "d_obj": obj[0]},
        physics_units={"focal": focal[1] or "m", "d_obj": obj[1] or "m"},
        operation="solve",
    )
