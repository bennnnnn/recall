"""Gravitation and modern-physics extractors."""

from __future__ import annotations

import re
from typing import Literal

from app.models.schemas.physics import PhysicsIntent
from app.modules.physics.extractors.common import (
    _ELECTRON_MASS,
    _LENGTH_UNIT_PATTERN,
    _NUMBER,
    _VELOCITY_UNIT_PATTERN,
    _find_value_with_specific_unit,
    _has_cue,
    _ordered_values,
    _strip_param_assignments,
)
from app.modules.physics.extractors.matter_thermal import (
    _AREA_PATTERN,
    _INCLINE_ANGLE_RE,
    _temperature_value,
)
from app.modules.physics.extractors.mechanics import _MASS_UNITS
from app.modules.physics.extractors.oscillations_waves import _HERTZ_PATTERN
from app.services.text_match import has_equation, word_index

_GRAVITATION_CUES = (
    "gravitational force",
    "gravitational attraction",
    "gravitational constant",
    "gravitational field",
    "orbital velocity",
    "orbital speed",
    "escape velocity",
    "escape speed",
    "surface gravity",
    "newton's law of gravitation",
    "law of universal gravitation",
)

_GRAVITATION_CUE_RES: tuple[re.Pattern[str], ...] = (
    # "the force between two 1000 kg masses 10 m apart" names no topic word.
    re.compile(r"\bforce\s+between\b.{0,80}?\d\s*(?:kg|tonnes?|tons?)\b", re.IGNORECASE),
    re.compile(r"\bg\s+on\s+a\s+planet\b", re.IGNORECASE),
)

_BODY_PROPERTIES: dict[str, tuple[float, float]] = {
    "earth": (5.9722e24, 6.371e6),
    "moon": (7.342e22, 1.7374e6),
    "mars": (6.4171e23, 3.3895e6),
    "jupiter": (1.8982e27, 6.9911e7),
    "sun": (1.9885e30, 6.957e8),
}

_IDENTICAL_PAIR_RE = re.compile(
    r"\b(?:two|a\s+pair\s+of|both)\b[^.?!]{0,40}?"
    r"\b(?:masses|spheres|balls|objects|bodies|blocks|stars|planets|satellites)\b",
    re.IGNORECASE,
)


def _named_body(lower: str) -> tuple[float, float] | None:
    for name, properties in _BODY_PROPERTIES.items():
        if word_index(lower, name) != -1:
            return properties
    return None


def _extract_gravitation_intent(cleaned: str) -> PhysicsIntent | None:
    lower = cleaned.lower()
    if not _has_cue(lower, _GRAVITATION_CUES, _GRAVITATION_CUE_RES):
        return None
    if has_equation(_strip_param_assignments(cleaned)):
        return None

    body = _named_body(lower)
    masses = _ordered_values(cleaned, r"kg|tonnes?|tons?")
    radius = _find_value_with_specific_unit(
        cleaned, _LENGTH_UNIT_PATTERN, ("radius", "radii"), require_keyword=True
    )
    if radius is None:
        radius_assignment = re.search(
            rf"\bR\s*=\s*({_NUMBER})\s*({_LENGTH_UNIT_PATTERN})(?![A-Za-z0-9/^])",
            cleaned,
        )
        if radius_assignment is not None:
            radius = (float(radius_assignment.group(1)), radius_assignment.group(2))
    altitude = _find_value_with_specific_unit(
        cleaned, _LENGTH_UNIT_PATTERN, ("above", "altitude", "height"), require_keyword=True
    )
    separation = _find_value_with_specific_unit(
        cleaned, _LENGTH_UNIT_PATTERN, ("apart", "separation", "between", "distance")
    )

    if "escape" in lower:
        planet_mass, planet_radius = _resolve_body(body, masses, radius)
        if planet_mass is None or planet_radius is None:
            return None
        return PhysicsIntent(
            kind="gravitation",
            physics_op="escape_velocity",
            physics_params={"M": planet_mass, "radius_body": planet_radius},
            physics_units={"M": "kg", "radius_body": "m"},
            operation="solve",
        )

    if "orbital" in lower:
        planet_mass, planet_radius = _resolve_body(body, masses, radius)
        if planet_mass is None or planet_radius is None:
            return None
        # An orbit is measured from the centre, so an altitude adds to the
        # radius - but the two are rarely in the same unit ("400 km above the
        # earth"), so they are passed separately and added after `_to_si`
        # rather than summed here in whatever units they arrived in.
        params: dict[str, float] = {"M": planet_mass, "radius_body": planet_radius}
        units: dict[str, str] = {"M": "kg", "radius_body": "m"}
        if altitude is not None:
            params["altitude"] = altitude[0]
            units["altitude"] = altitude[1] or "m"
        return PhysicsIntent(
            kind="gravitation",
            physics_op="orbital_velocity",
            physics_params=params,
            physics_units=units,
            operation="solve",
        )

    if "surface gravity" in lower or "gravitational field" in lower or "g on a planet" in lower:
        planet_mass, planet_radius = _resolve_body(body, masses, radius)
        if planet_mass is None or planet_radius is None:
            return None
        return PhysicsIntent(
            kind="gravitation",
            physics_op="surface_gravity",
            physics_params={"M": planet_mass, "radius_body": planet_radius},
            physics_units={"M": "kg", "radius_body": "m"},
            operation="solve",
        )

    # F = G M m / r^2 between two stated masses. "two 1000 kg masses" gives one
    # number for both bodies, which is the commonest wording of this question.
    if len(masses) == 1 and separation is not None and _IDENTICAL_PAIR_RE.search(cleaned):
        masses = [masses[0], masses[0]]
    if len(masses) >= 2 and separation is not None:
        return PhysicsIntent(
            kind="gravitation",
            physics_op="gravitational_force",
            physics_params={"m1": masses[0][0], "m2": masses[1][0], "r": separation[0]},
            physics_units={
                "m1": masses[0][1] or "kg",
                "m2": masses[1][1] or "kg",
                "r": separation[1] or "m",
            },
            operation="solve",
        )
    return None


def _resolve_body(
    body: tuple[float, float] | None,
    masses: list[tuple[float, str]],
    radius: tuple[float, str] | None,
) -> tuple[float | None, float | None]:
    """A named body, or a stated mass and radius - never a mix of guesses.

    A question that *describes* a planet without naming it and supplies only
    one of the two is refused: silently finishing it with Earth's other number
    is the same defect as the projectile default, one layer up.
    """
    if body is not None:
        return body
    if masses and radius is not None:
        return masses[0][0], radius[0]
    return None, None


_MODERN_CUES = (
    "photon",
    "de broglie",
    "planck",
    "photoelectric",
    "rest energy",
    "mass energy",
    "energy equivalent",
    "lorentz factor",
    "time dilation",
    "length contraction",
    "special relativity",
    "uncertainty principle",
    "momentum uncertainty",
    "particle in a box",
    "infinite box",
    "hydrogen energy",
    "hydrogen atom",
    "compton",
    "wien's law",
    "wien law",
    "stefan-boltzmann",
    "blackbody power",
)

_DECAY_SUBJECT = r"sample|isotope|radioactive|radioisotope|decay|nuclei|nuclide|substance"

_MODERN_CUE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(rf"\bhalf[- ]li(?:ves|fe)\b.{{0,80}}?\b(?:{_DECAY_SUBJECT})\b", re.IGNORECASE),
    re.compile(rf"\b(?:{_DECAY_SUBJECT})\b.{{0,80}}?\bhalf[- ]li(?:ves|fe)\b", re.IGNORECASE),
)

_HALF_LIFE_COUNT_RE = re.compile(rf"({_NUMBER})\s*half[- ]li(?:ves|fe)", re.IGNORECASE)

_DECAY_TIME_UNITS = (
    r"seconds?|secs?|s|minutes?|mins?|min|hours?|hrs?|hr|days?|weeks?|months?|years?|yr"
)


def _extract_modern_intent(cleaned: str) -> PhysicsIntent | None:
    lower = cleaned.lower()
    if not _has_cue(lower, _MODERN_CUES, _MODERN_CUE_RES):
        return None
    without_level_assignment = re.sub(r"\bn\s*=\s*\d+\b", "", cleaned, flags=re.IGNORECASE)
    if has_equation(_strip_param_assignments(without_level_assignment)):
        return None

    def _relativistic_speed() -> tuple[float, str] | None:
        speed = _find_value_with_specific_unit(cleaned, _VELOCITY_UNIT_PATTERN)
        if speed is not None:
            return speed
        fraction = re.search(rf"({_NUMBER})\s*c\b", cleaned, re.IGNORECASE)
        if fraction is not None:
            return float(fraction.group(1)) * 299792458.0, "m/s"
        return None

    if any(cue in lower for cue in ("lorentz factor", "time dilation", "length contraction")):
        speed = _relativistic_speed()
        if speed is None:
            return None
        rel_params: dict[str, float] = {"v": speed[0]}
        rel_units: dict[str, str] = {"v": speed[1] or "m/s"}
        op: Literal["lorentz_factor", "time_dilation", "length_contraction"]
        if "time dilation" in lower:
            proper = _find_value_with_specific_unit(
                cleaned, _DECAY_TIME_UNITS, ("proper time", "rest time", "clock")
            )
            if proper is None:
                return None
            rel_params["proper_time"], rel_units["proper_time"] = proper[0], proper[1] or "s"
            op = "time_dilation"
        elif "length contraction" in lower:
            proper_length = _find_value_with_specific_unit(
                cleaned, _LENGTH_UNIT_PATTERN, ("proper length", "rest length")
            )
            if proper_length is None:
                return None
            rel_params["proper_length"], rel_units["proper_length"] = (
                proper_length[0],
                proper_length[1] or "m",
            )
            op = "length_contraction"
        else:
            op = "lorentz_factor"
        return PhysicsIntent(
            kind="modern",
            physics_op=op,
            physics_params=rel_params,
            physics_units=rel_units,
            operation="solve",
        )

    if "uncertainty" in lower:
        uncertainty = _find_value_with_specific_unit(
            cleaned, _LENGTH_UNIT_PATTERN, ("position uncertainty", "delta x", "uncertainty")
        )
        if uncertainty is None:
            return None
        return PhysicsIntent(
            kind="modern",
            physics_op="uncertainty_momentum",
            physics_params={"uncertainty_x": uncertainty[0]},
            physics_units={"uncertainty_x": uncertainty[1] or "m"},
            operation="solve",
        )

    if "particle in a box" in lower or "infinite box" in lower:
        length = _find_value_with_specific_unit(
            cleaned, _LENGTH_UNIT_PATTERN, ("box", "width", "length")
        )
        level = re.search(r"\bn\s*(?:=|is)\s*(\d+)\b", cleaned, re.IGNORECASE)
        mass = _find_value_with_specific_unit(cleaned, _MASS_UNITS, ("mass", "particle"))
        if length is None or level is None or (mass is None and "electron" not in lower):
            return None
        return PhysicsIntent(
            kind="modern",
            physics_op="particle_box_energy",
            physics_params={
                "L": length[0],
                "quantum_n": float(level.group(1)),
                "m": mass[0] if mass is not None else _ELECTRON_MASS,
            },
            physics_units={
                "L": length[1] or "m",
                "quantum_n": "",
                "m": mass[1] if mass is not None else "kg",
            },
            operation="solve",
        )

    if "hydrogen" in lower and "energy" in lower:
        level = re.search(r"\bn\s*(?:=|is)\s*(\d+)\b", cleaned, re.IGNORECASE)
        if level is None:
            return None
        return PhysicsIntent(
            kind="modern",
            physics_op="hydrogen_energy_level",
            physics_params={"quantum_n": float(level.group(1))},
            physics_units={"quantum_n": ""},
            operation="solve",
        )

    if "compton" in lower:
        angle = _INCLINE_ANGLE_RE.search(cleaned)
        if angle is None:
            return None
        return PhysicsIntent(
            kind="modern",
            physics_op="compton_shift",
            physics_params={"angle": float(angle.group(1))},
            physics_units={"angle": "deg"},
            operation="solve",
        )

    if "wien" in lower:
        temp = _temperature_value(cleaned, ("temperature", "at", "blackbody"))
        if temp is None or temp[1] != "K":
            return None
        return PhysicsIntent(
            kind="modern",
            physics_op="wien_peak",
            physics_params={"temp": temp[0]},
            physics_units={"temp": "K"},
            operation="solve",
        )

    if "stefan" in lower or "blackbody power" in lower:
        temp = _temperature_value(cleaned, ("temperature", "at", "blackbody"))
        area = _find_value_with_specific_unit(cleaned, _AREA_PATTERN, ("area", "surface"))
        emissivity_match = re.search(
            rf"\bemissivity\s*(?:of|is|=)?\s*({_NUMBER})", cleaned, re.IGNORECASE
        )
        if temp is None or temp[1] != "K" or area is None:
            return None
        return PhysicsIntent(
            kind="modern",
            physics_op="stefan_boltzmann_power",
            physics_params={
                "temp": temp[0],
                "area": area[0],
                "emissivity": float(emissivity_match.group(1)) if emissivity_match else 1.0,
            },
            physics_units={"temp": "K", "area": area[1] or "m^2", "emissivity": ""},
            operation="solve",
        )

    if "photoelectric" in lower:
        freq = _find_value_with_specific_unit(cleaned, _HERTZ_PATTERN)
        work_function = _find_value_with_specific_unit(
            cleaned,
            r"eV|electron\s*volts?|J|joules?",
            ("work function", "phi", "threshold energy"),
            require_keyword=True,
        )
        if freq is None or work_function is None:
            return None
        return PhysicsIntent(
            kind="modern",
            physics_op="photoelectric_kinetic_energy",
            physics_params={"freq": freq[0], "work_function": work_function[0]},
            physics_units={"freq": freq[1] or "Hz", "work_function": work_function[1] or "J"},
            operation="solve",
        )

    if "photon" in lower or "planck" in lower:
        freq = _find_value_with_specific_unit(cleaned, _HERTZ_PATTERN)
        wavelength = _find_value_with_specific_unit(
            cleaned,
            _LENGTH_UNIT_PATTERN,
            ("wavelength",),
            require_keyword=True,
        )
        if freq is None and wavelength is None:
            return None
        if freq is not None:
            photon_params = {"freq": freq[0]}
            photon_units = {"freq": freq[1] or "Hz"}
        else:
            if wavelength is None:
                return None
            photon_params = {"wavelength": wavelength[0]}
            photon_units = {"wavelength": wavelength[1] or "m"}
        return PhysicsIntent(
            kind="modern",
            physics_op="photon_energy",
            physics_params=photon_params,
            physics_units=photon_units,
            operation="solve",
        )

    if "de broglie" in lower:
        speed = _find_value_with_specific_unit(cleaned, _VELOCITY_UNIT_PATTERN)
        mass = _find_value_with_specific_unit(cleaned, _MASS_UNITS, ("mass",))
        if speed is None:
            return None
        # An electron's mass is not in the question, and naming it is the point
        # of the question; any other particle has to state one.
        if mass is None and "electron" not in lower:
            return None
        return PhysicsIntent(
            kind="modern",
            physics_op="de_broglie_wavelength",
            physics_params={
                "m": mass[0] if mass is not None else _ELECTRON_MASS,
                "v": speed[0],
            },
            physics_units={"m": mass[1] if mass is not None else "kg", "v": speed[1] or "m/s"},
            operation="solve",
        )

    if "half li" in lower or "half-li" in lower:
        count = _HALF_LIFE_COUNT_RE.search(cleaned)
        amount = _find_value_with_specific_unit(cleaned, _MASS_UNITS, ("sample", "of"))
        if amount is None:
            return None
        params: dict[str, float] = {"m": amount[0]}
        units: dict[str, str] = {"m": amount[1] or "kg"}
        if count is not None:
            params["n_halves"] = float(count.group(1))
            units["n_halves"] = ""
        else:
            half_life_match = re.search(
                rf"\bhalf[- ]life\b\s*(?:of|is|=|:)?\s*({_NUMBER})\s*({_DECAY_TIME_UNITS})\b",
                cleaned,
                re.IGNORECASE,
            )
            elapsed_match = re.search(
                rf"\bafter\s+({_NUMBER})\s*({_DECAY_TIME_UNITS})\b",
                cleaned,
                re.IGNORECASE,
            )
            if half_life_match is None or elapsed_match is None:
                return None
            params.update(
                half_life=float(half_life_match.group(1)),
                elapsed=float(elapsed_match.group(1)),
            )
            units.update(
                half_life=half_life_match.group(2),
                elapsed=elapsed_match.group(2),
            )
        return PhysicsIntent(
            kind="modern",
            physics_op="half_life_remaining",
            physics_params=params,
            physics_units=units,
            operation="solve",
        )

    mass = _find_value_with_specific_unit(cleaned, r"kg|grams?|g", ("mass", "of"))
    if mass is None:
        return None
    return PhysicsIntent(
        kind="modern",
        physics_op="mass_energy",
        physics_params={"m": mass[0]},
        physics_units={"m": mass[1] or "kg"},
        operation="solve",
    )
