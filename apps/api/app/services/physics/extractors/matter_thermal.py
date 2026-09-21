"""Optics, thermal, fluid, and materials extractors."""

from __future__ import annotations

import re

from app.models.schemas.physics import PhysicsIntent
from app.services.physics.extractors.common import (
    _LENGTH_UNIT_PATTERN,
    _NUMBER,
    _VELOCITY_UNIT_PATTERN,
    _detect_gravity,
    _find_value_with_specific_unit,
    _has_cue,
    _ordered_values,
    _strip_param_assignments,
)
from app.services.physics.extractors.mechanics import _INCLINE_ANGLE_RE, _MASS_UNITS
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
            r"(-?\d+(?:\.\d+)?)\s*(?:degrees?|deg|\u00b0)",
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
        img = _find_value_with_specific_unit(
            cleaned, _LENGTH_UNIT_PATTERN, ("image",), require_keyword=True
        )
        if img is None or obj is None:
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


_THERMAL_CUES = (
    "specific heat",
    "heat capacity",
    "ideal gas",
    "gas constant",
    "thermal expansion",
    "linear expansion",
    "coefficient of linear expansion",
    "latent heat",
    "first law of thermodynamics",
    "internal energy",
    "carnot",
    "entropy",
    "heat conduction",
    "thermal conductivity",
)

_KELVIN_PATTERN = r"K|kelvins?"

_CELSIUS_PATTERN = r"°C|degrees?\s+c(?:elsius)?|celsius|C(?![A-Za-z])"

_THERMAL_CUE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(
        rf"\b(?:heat|warm|cool)\w*\b.{{0,80}}?\d\s*(?:{_KELVIN_PATTERN}|{_CELSIUS_PATTERN})",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\d\s*(?:{_KELVIN_PATTERN}|{_CELSIUS_PATTERN}).{{0,80}}?\b(?:heat|warm|cool)\w*\b",
        re.IGNORECASE,
    ),
    re.compile(r"\befficiency\b.{0,80}?\d\s*(?:J|joules?|kJ|kilojoules?)\b", re.IGNORECASE),
    re.compile(r"\d\s*(?:J|joules?|kJ|kilojoules?)\b.{0,80}?\befficiency\b", re.IGNORECASE),
    # "the pressure of 2 moles of gas at 300 K" names no thermal word at all -
    # a mole count beside a temperature is the signature itself.
    re.compile(
        rf"\d\s*mol(?:e|es)?\b.{{0,80}}?\d\s*(?:{_KELVIN_PATTERN}|{_CELSIUS_PATTERN})",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\d\s*(?:{_KELVIN_PATTERN}|{_CELSIUS_PATTERN}).{{0,80}}?\d\s*mol(?:e|es)?\b",
        re.IGNORECASE,
    ),
)

_WATER_SPECIFIC_HEAT = 4186.0

_GAS_CONSTANT = 8.314462618


def _temperature_value(cleaned: str, keywords: tuple[str, ...]) -> tuple[float, str] | None:
    """A temperature with an explicit scale, or nothing.

    27 C and 27 K differ by a factor of eleven, so a bare number is refused
    rather than assumed - and "degrees" alone cannot help, because it means an
    *angle* everywhere else in this file.
    """
    kelvin = _find_value_with_specific_unit(cleaned, _KELVIN_PATTERN, keywords)
    if kelvin is not None:
        return kelvin[0], "K"
    match = re.search(
        rf"(-?\d+(?:\.\d+)?)\s*(?:{_CELSIUS_PATTERN})",
        cleaned,
        re.IGNORECASE,
    )
    if match is not None:
        return float(match.group(1)), "degC"
    return None


def _extract_thermal_intent(cleaned: str) -> PhysicsIntent | None:
    lower = cleaned.lower()
    if not _has_cue(lower, _THERMAL_CUES, _THERMAL_CUE_RES):
        return None
    if has_equation(_strip_param_assignments(cleaned)):
        return None

    if "carnot" in lower:
        hot = _temperature_value(cleaned, ("hot reservoir", "hot", "source"))
        cold = _temperature_value(cleaned, ("cold reservoir", "cold", "sink"))
        if hot is None or cold is None or hot[1] != "K" or cold[1] != "K":
            return None
        return PhysicsIntent(
            kind="thermal",
            physics_op="carnot_efficiency",
            physics_params={"temp": hot[0], "temp_env": cold[0]},
            physics_units={"temp": "K", "temp_env": "K"},
            operation="solve",
        )

    if "entropy" in lower:
        heat = _find_value_with_specific_unit(
            cleaned, r"kilojoules?|joules?|kJ|J", ("heat", "energy")
        )
        temp = _temperature_value(cleaned, ("temperature", "at"))
        if heat is None or temp is None or temp[1] != "K":
            return None
        return PhysicsIntent(
            kind="thermal",
            physics_op="entropy_change",
            physics_params={"heat": heat[0], "temp": temp[0]},
            physics_units={"heat": heat[1] or "J", "temp": "K"},
            operation="solve",
        )

    if "heat conduction" in lower or "thermal conductivity" in lower:
        conductivity = _find_value_with_specific_unit(
            cleaned,
            r"W/m/K|W/\(m\s*K\)|watts?\s+per\s+met(?:er|re)\s+per\s+kelvin",
            ("thermal conductivity", "conductivity"),
        )
        area = _find_value_with_specific_unit(cleaned, _AREA_PATTERN, ("area",))
        thickness = _find_value_with_specific_unit(
            cleaned, _LENGTH_UNIT_PATTERN, ("thickness", "length"), require_keyword=True
        )
        rise = _temperature_value(cleaned, ("temperature difference", "difference", "delta t"))
        if conductivity is None or area is None or thickness is None or rise is None:
            return None
        return PhysicsIntent(
            kind="thermal",
            physics_op="heat_conduction_rate",
            physics_params={
                "thermal_conductivity": conductivity[0],
                "area": area[0],
                "delta_temp": rise[0],
                "L": thickness[0],
            },
            physics_units={
                "thermal_conductivity": conductivity[1] or "W/m/K",
                "area": area[1] or "m^2",
                "delta_temp": "K",
                "L": thickness[1] or "m",
            },
            operation="solve",
        )

    # --- linear thermal expansion: dL = alpha L0 dT --------------------
    if "expansion" in lower:
        length = _find_value_with_specific_unit(
            cleaned, _LENGTH_UNIT_PATTERN, ("rod", "wire", "length", "long")
        )
        alpha_match = re.search(
            rf"(?:coefficient(?:\s+of\s+linear\s+expansion)?|alpha|\u03b1)\s*"
            rf"(?:of|is|=|:)?\s*({_NUMBER})\s*(1/K|/K|K\^?-?1|1/°C|/°C)",
            cleaned,
            re.IGNORECASE,
        )
        rise = _temperature_value(cleaned, ("heated by", "temperature change", "change", "by"))
        if length is None or alpha_match is None or rise is None:
            return None
        return PhysicsIntent(
            kind="thermal",
            physics_op="linear_expansion",
            physics_params={
                "L0": length[0],
                "alpha": float(alpha_match.group(1)),
                "delta_temp": rise[0],
            },
            physics_units={
                "L0": length[1] or "m",
                "alpha": alpha_match.group(2),
                "delta_temp": "K",
            },
            operation="solve",
        )

    # --- phase change: Q = m L -----------------------------------------
    if "latent heat" in lower:
        mass = _find_value_with_specific_unit(cleaned, _MASS_UNITS, ("mass", "of"))
        latent = _find_value_with_specific_unit(
            cleaned,
            r"J/kg|kJ/kg|joules?\s+per\s+kilogram|kilojoules?\s+per\s+kilogram",
            ("latent heat",),
        )
        if mass is None or latent is None:
            return None
        return PhysicsIntent(
            kind="thermal",
            physics_op="latent_heat",
            physics_params={"m": mass[0], "latent_heat": latent[0]},
            physics_units={"m": mass[1] or "kg", "latent_heat": latent[1] or "J/kg"},
            operation="solve",
        )

    # --- first law: dU = Q - W (work done by the system is positive) ----
    if "first law" in lower or "internal energy" in lower:
        heat_match = re.search(
            rf"(?:heat|energy)\s+(?:added|absorbed|supplied)\D{{0,20}}?({_NUMBER})\s*"
            r"(kilojoules?|joules?|kJ|J)",
            cleaned,
            re.IGNORECASE,
        )
        work_match = re.search(
            rf"work\s+(?:done\s+)?by\s+(?:the\s+)?(?:system|gas)\D{{0,20}}?({_NUMBER})\s*"
            r"(kilojoules?|joules?|kJ|J)",
            cleaned,
            re.IGNORECASE,
        )
        if heat_match is None or work_match is None:
            # Refuse ambiguous sign conventions such as bare "work = 200 J".
            return None
        return PhysicsIntent(
            kind="thermal",
            physics_op="first_law_internal_energy",
            physics_params={"heat": float(heat_match.group(1)), "W": float(work_match.group(1))},
            physics_units={"heat": heat_match.group(2), "W": work_match.group(2)},
            operation="solve",
        )

    # --- efficiency: only from two energies -----------------------------
    if "efficiency" in lower:
        if not any(word in lower for word in ("engine", "thermal", "heat")):
            # Machine/mechanical efficiency is handled by the energy
            # extractor, which runs later in the registry.
            return None
        energies = _ordered_values(cleaned, r"kilojoules?|joules?|kJ|J")
        if len(energies) != 2:
            # Two temperatures is a Carnot question, which needs absolute
            # temperatures and a different formula. Not solved here.
            return None
        work, supplied = sorted((energies[0][0], energies[1][0]))
        if supplied <= 0:
            return None
        return PhysicsIntent(
            kind="thermal",
            physics_op="thermal_efficiency",
            physics_params={"W_out": work, "Q_in": supplied},
            physics_units={"W_out": "J", "Q_in": "J"},
            operation="solve",
        )

    # --- ideal gas: P V = n R T -----------------------------------------
    moles = _find_value_with_specific_unit(cleaned, r"mol|moles?")
    if moles is not None or "ideal gas" in lower:
        volume = _find_value_with_specific_unit(cleaned, r"m\^?3|cm\^?3|litres?|liters?|l|ml")
        temp = _temperature_value(cleaned, ("temperature", "at"))
        if moles is None or volume is None or temp is None:
            return None
        if temp[1] != "K":
            # PV = nRT needs an absolute temperature. Celsius would be wrong by
            # 273 and look plausible.
            return None
        return PhysicsIntent(
            kind="thermal",
            physics_op="ideal_gas_pressure",
            physics_params={"moles": moles[0], "volume": volume[0], "temp": temp[0]},
            physics_units={
                "moles": "mol",
                "volume": volume[1] or "m^3",
                "temp": "K",
            },
            operation="solve",
        )

    # --- Q = m c dT ------------------------------------------------------
    mass = _find_value_with_specific_unit(cleaned, _MASS_UNITS, ("mass", "of"))
    rise = _temperature_value(cleaned, ("by", "rise", "raise", "change"))
    if rise is None:
        # A temperature *difference* is the same number in kelvin and celsius,
        # so a bare "by 10 degrees" is unambiguous here in a way an absolute
        # "at 300 degrees" is not. Only the interval may be loose.
        bare = re.search(
            rf"(?:by|rises?|raise[sd]?|warms?|cools?)\s+(?:by\s+)?({_NUMBER})\s*"
            r"(?:degrees?|deg|\u00b0)(?![A-Za-z0-9])",
            cleaned,
            re.IGNORECASE,
        )
        if bare is not None:
            rise = (float(bare.group(1)), "K")
    if mass is None or rise is None:
        return None
    capacity = _find_value_with_specific_unit(
        cleaned,
        r"J/kg/K|J/\(kg\s*(?:K|°?C)\)|J/kgK|J/(?:kg\s*[·*]\s*(?:K|°?C))",
        ("specific heat", "capacity", "c =", "c is"),
    )
    if capacity is not None:
        c_value = capacity[0]
    elif "water" in lower:
        c_value = _WATER_SPECIFIC_HEAT
    else:
        # No capacity and no named substance: the answer would be a guess.
        return None
    # A temperature *difference* is the same number in kelvin and celsius, so
    # this one does not need the scale the absolute reading above does.
    return PhysicsIntent(
        kind="thermal",
        physics_op="heat_energy",
        physics_params={"m": mass[0], "c_heat": c_value, "delta_temp": rise[0]},
        physics_units={"m": mass[1] or "kg", "c_heat": "J/kg/K", "delta_temp": "K"},
        operation="solve",
    )


_FLUIDS_CUES = (
    "upthrust",
    "buoyant force",
    "buoyancy",
    "archimedes",
    "hydrostatic",
    "flow rate",
    "pascal's principle",
    "hydraulic",
    "bernoulli",
    "mass flow rate",
    "torricelli",
    "stokes drag",
    "stokes' drag",
    "reynolds number",
    "surface tension",
    "laplace pressure",
    "soap bubble",
)

_AREA_PATTERN = r"m\^?2|cm\^?2|mm\^?2|square\s+met(?:er|re)s?"

_VOLUME_PATTERN = r"m\^?3|cm\^?3|litres?|liters?|ml"

_DENSITY_PATTERN = r"kg/m\^?3|g/cm\^?3|kg\s+per\s+cubic\s+met(?:er|re)"

_PRESSURE_PATTERN = r"Pa|pascals?|kPa|kilopascals?|MPa|megapascals?"

_FLUIDS_CUE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(
        rf"\bpressure\b.{{0,80}}?\d\s*(?:{_AREA_PATTERN}|{_PRESSURE_PATTERN})\b", re.IGNORECASE
    ),
    re.compile(
        rf"\d\s*(?:{_AREA_PATTERN}|{_PRESSURE_PATTERN})\b.{{0,80}}?\bpressure\b", re.IGNORECASE
    ),
    re.compile(r"\bpressure\b.{0,80}?\bdepth\b", re.IGNORECASE),
    re.compile(rf"\bdensity\b.{{0,80}}?\d\s*(?:{_VOLUME_PATTERN})\b", re.IGNORECASE),
    re.compile(
        rf"(?=.*\bdensity\b)(?=.*\d\s*(?:{_MASS_UNITS})\b)"
        rf"(?=.*\d\s*(?:{_VOLUME_PATTERN})\b)",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(rf"\d\s*(?:{_DENSITY_PATTERN})\b", re.IGNORECASE),
    re.compile(rf"\bpipe\b.{{0,80}}?\d\s*(?:{_AREA_PATTERN})\b", re.IGNORECASE),
)

_STRESS_WORDS = ("stress", "strain", "young", "modulus", "tensile")

_ABSOLUTE_PRESSURE_RE = re.compile(r"\babsolute\b|\batmospheric\b", re.IGNORECASE)

_WATER_DENSITY = 1000.0


def _extract_fluids_intent(cleaned: str) -> PhysicsIntent | None:
    lower = cleaned.lower()
    if not _has_cue(lower, _FLUIDS_CUES, _FLUIDS_CUE_RES):
        return None
    if any(word in lower for word in _STRESS_WORDS):
        return None
    if has_equation(_strip_param_assignments(cleaned)):
        return None

    area = _find_value_with_specific_unit(cleaned, _AREA_PATTERN)
    volume = _find_value_with_specific_unit(cleaned, _VOLUME_PATTERN)
    mass = _find_value_with_specific_unit(cleaned, _MASS_UNITS, ("mass", "of"))
    force = _find_value_with_specific_unit(cleaned, r"N|newtons?", ("force", "weight"))
    depth = _find_value_with_specific_unit(
        cleaned, _LENGTH_UNIT_PATTERN, ("depth", "deep", "below", "down"), require_keyword=True
    )
    density = _find_value_with_specific_unit(cleaned, _DENSITY_PATTERN)
    speed = _ordered_values(cleaned, _VELOCITY_UNIT_PATTERN)
    areas = _ordered_values(cleaned, _AREA_PATTERN)
    viscosity = _find_value_with_specific_unit(
        cleaned, r"Pa\s*[·*]\s*s|Pa\s*s|pascal\s*seconds?", ("viscosity",)
    )
    surface_tension = _find_value_with_specific_unit(
        cleaned, r"N/m|newtons?\s+per\s+met(?:er|re)", ("surface tension",)
    )
    radius = _find_value_with_specific_unit(
        cleaned, _LENGTH_UNIT_PATTERN, ("radius",), require_keyword=True
    )
    characteristic_length = _find_value_with_specific_unit(
        cleaned,
        _LENGTH_UNIT_PATTERN,
        ("characteristic length", "diameter", "length scale"),
        require_keyword=True,
    )
    if len(areas) < 2:
        # "narrowing from 0.04 to 0.01 m^2" carries the unit once, on the
        # second value - the same shape the resistor networks had.
        pair = re.search(
            rf"from\s+({_NUMBER})\s*(?:{_AREA_PATTERN})?\s*to\s+({_NUMBER})\s*"
            rf"({_AREA_PATTERN})",
            cleaned,
            re.IGNORECASE,
        )
        if pair is not None:
            unit = pair.group(3)
            areas = [(float(pair.group(1)), unit), (float(pair.group(2)), unit)]

    def _fluid_density() -> float | None:
        if density is not None:
            return density[0]
        if "water" in lower:
            return _WATER_DENSITY
        return None

    if "stokes" in lower:
        if viscosity is None or radius is None or len(speed) != 1:
            return None
        return PhysicsIntent(
            kind="fluids",
            physics_op="stokes_drag",
            physics_params={
                "viscosity": viscosity[0],
                "r": radius[0],
                "v": speed[0][0],
            },
            physics_units={
                "viscosity": viscosity[1] or "Pa*s",
                "r": radius[1] or "m",
                "v": speed[0][1] or "m/s",
            },
            operation="solve",
        )

    if "reynolds" in lower:
        rho = _fluid_density()
        if rho is None or viscosity is None or characteristic_length is None or len(speed) != 1:
            return None
        return PhysicsIntent(
            kind="fluids",
            physics_op="reynolds_number",
            physics_params={
                "rho": rho,
                "v": speed[0][0],
                "L": characteristic_length[0],
                "viscosity": viscosity[0],
            },
            physics_units={
                "rho": density[1] if density is not None else "kg/m^3",
                "v": speed[0][1] or "m/s",
                "L": characteristic_length[1] or "m",
                "viscosity": viscosity[1] or "Pa*s",
            },
            operation="solve",
        )

    if "laplace pressure" in lower or "soap bubble" in lower or "droplet" in lower:
        if surface_tension is None or radius is None:
            return None
        factor = 4.0 if "soap bubble" in lower else 2.0
        return PhysicsIntent(
            kind="fluids",
            physics_op="laplace_pressure",
            physics_params={
                "surface_tension": surface_tension[0],
                "r": radius[0],
                "mode_factor": factor,
            },
            physics_units={
                "surface_tension": surface_tension[1] or "N/m",
                "r": radius[1] or "m",
                "mode_factor": "",
            },
            operation="solve",
        )

    if "surface tension" in lower:
        length = _find_value_with_specific_unit(
            cleaned, _LENGTH_UNIT_PATTERN, ("length", "edge", "contact")
        )
        if force is None or length is None:
            return None
        return PhysicsIntent(
            kind="fluids",
            physics_op="surface_tension",
            physics_params={"F": force[0], "L": length[0]},
            physics_units={"F": force[1] or "N", "L": length[1] or "m"},
            operation="solve",
        )

    if "torricelli" in lower:
        if depth is None:
            return None
        return PhysicsIntent(
            kind="fluids",
            physics_op="torricelli_speed",
            physics_params={"depth": depth[0], "g": _detect_gravity(cleaned)},
            physics_units={"depth": depth[1] or "m", "g": "m/s^2"},
            operation="solve",
        )

    if "mass flow rate" in lower:
        rho = _fluid_density()
        if rho is None or area is None or len(speed) != 1:
            return None
        return PhysicsIntent(
            kind="fluids",
            physics_op="mass_flow_rate",
            physics_params={"rho": rho, "area": area[0], "v": speed[0][0]},
            physics_units={
                "rho": density[1] if density is not None else "kg/m^3",
                "area": area[1] or "m^2",
                "v": speed[0][1] or "m/s",
            },
            operation="solve",
        )

    # --- Pascal's principle: F1/A1 = F2/A2 -----------------------------
    if "hydraulic" in lower or "pascal's principle" in lower:
        if force is None or len(areas) != 2:
            return None
        return PhysicsIntent(
            kind="fluids",
            physics_op="hydraulic_force",
            physics_params={"F1": force[0], "A1": areas[0][0], "A2": areas[1][0]},
            physics_units={
                "F1": force[1] or "N",
                "A1": areas[0][1] or "m^2",
                "A2": areas[1][1] or "m^2",
            },
            operation="solve",
        )

    # --- Horizontal Bernoulli: P1 + rho v1^2/2 = P2 + rho v2^2/2 -----
    if "bernoulli" in lower:
        # Height terms are intentionally not guessed. The horizontal qualifier
        # makes the omitted rho*g*h terms exactly cancel.
        if "horizontal" not in lower:
            return None
        pressure = _find_value_with_specific_unit(cleaned, _PRESSURE_PATTERN)
        rho = _fluid_density()
        if pressure is None or rho is None or len(speed) != 2:
            return None
        return PhysicsIntent(
            kind="fluids",
            physics_op="bernoulli_pressure",
            physics_params={
                "pres1": pressure[0],
                "rho": rho,
                "v1": speed[0][0],
                "v2": speed[1][0],
            },
            physics_units={
                "pres1": pressure[1] or "Pa",
                "rho": density[1] if density is not None else "kg/m^3",
                "v1": speed[0][1] or "m/s",
                "v2": speed[1][1] or "m/s",
            },
            operation="solve",
        )

    # --- continuity: A1 v1 = A2 v2 --------------------------------------
    if len(areas) >= 2 and speed:
        if areas[1][0] == 0:
            return None
        return PhysicsIntent(
            kind="fluids",
            physics_op="continuity_velocity",
            physics_params={"A1": areas[0][0], "A2": areas[1][0], "v": speed[0][0]},
            physics_units={
                "A1": areas[0][1] or "m^2",
                "A2": areas[1][1] or "m^2",
                "v": speed[0][1] or "m/s",
            },
            operation="solve",
        )

    # --- flow rate: Q = A v ---------------------------------------------
    if "flow" in lower and area is not None and speed:
        return PhysicsIntent(
            kind="fluids",
            physics_op="flow_rate",
            physics_params={"area": area[0], "v": speed[0][0]},
            physics_units={"area": area[1] or "m^2", "v": speed[0][1] or "m/s"},
            operation="solve",
        )

    # --- upthrust: rho V g ----------------------------------------------
    if any(word in lower for word in ("upthrust", "buoyan", "archimedes")):
        rho = _fluid_density()
        if volume is None or rho is None:
            return None
        if not any(word in lower for word in ("submerged", "immersed", "displac")):
            # A floating body displaces its own weight, not its own volume.
            # Which one is meant changes the answer, so it has to be said.
            return None
        return PhysicsIntent(
            kind="fluids",
            physics_op="upthrust",
            physics_params={"rho": rho, "volume": volume[0], "g": _detect_gravity(cleaned)},
            physics_units={"rho": "kg/m^3", "volume": volume[1] or "m^3", "g": "m/s^2"},
            operation="solve",
        )

    # --- pressure at depth: rho g h -------------------------------------
    if depth is not None:
        if _ABSOLUTE_PRESSURE_RE.search(cleaned):
            return None
        rho = _fluid_density()
        if rho is None:
            return None
        return PhysicsIntent(
            kind="fluids",
            physics_op="pressure_at_depth",
            physics_params={"rho": rho, "depth": depth[0], "g": _detect_gravity(cleaned)},
            physics_units={"rho": "kg/m^3", "depth": depth[1] or "m", "g": "m/s^2"},
            operation="solve",
        )

    # --- density: rho = m / V -------------------------------------------
    if "density" in lower and mass is not None and volume is not None:
        return PhysicsIntent(
            kind="fluids",
            physics_op="density",
            physics_params={"m": mass[0], "volume": volume[0]},
            physics_units={"m": mass[1] or "kg", "volume": volume[1] or "m^3"},
            operation="solve",
        )

    # --- pressure from a force: P = F / A --------------------------------
    if force is not None and area is not None:
        return PhysicsIntent(
            kind="fluids",
            physics_op="pressure_from_force",
            physics_params={"F": force[0], "area": area[0]},
            physics_units={"F": force[1] or "N", "area": area[1] or "m^2"},
            operation="solve",
        )
    return None


_MATERIALS_CUES = ("young's modulus", "youngs modulus", "young modulus", "tensile stress")

_MATERIALS_CUE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(
        rf"\bstress\b.{{0,80}}?\d\s*(?:N|newtons?|{_PRESSURE_PATTERN})(?![A-Za-z0-9])",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\d\s*(?:N|newtons?|{_PRESSURE_PATTERN})(?![A-Za-z0-9]).{{0,80}}?\bstress\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\bstrain\b.{{0,80}}?\d\s*(?:{_LENGTH_UNIT_PATTERN})(?![A-Za-z0-9])", re.IGNORECASE
    ),
    re.compile(
        rf"\d\s*(?:{_LENGTH_UNIT_PATTERN})(?![A-Za-z0-9]).{{0,80}}?\bstrain\b", re.IGNORECASE
    ),
)


def _extract_materials_intent(cleaned: str) -> PhysicsIntent | None:
    lower = cleaned.lower()
    if not _has_cue(lower, _MATERIALS_CUES, _MATERIALS_CUE_RES):
        return None
    if has_equation(_strip_param_assignments(cleaned)):
        return None

    stress = _find_value_with_specific_unit(cleaned, _PRESSURE_PATTERN)
    strain_match = re.search(rf"strain\s*(?:of|is|=)?\s*({_NUMBER})", cleaned, re.IGNORECASE)
    force = _find_value_with_specific_unit(cleaned, r"N|newtons?", ("force", "load"))
    area = _find_value_with_specific_unit(cleaned, _AREA_PATTERN)
    original = _find_value_with_specific_unit(
        cleaned, _LENGTH_UNIT_PATTERN, ("wire", "rod", "bar", "long", "length", "original")
    )
    extension = _find_value_with_specific_unit(
        cleaned,
        _LENGTH_UNIT_PATTERN,
        ("extends", "extension", "stretches", "lengthens", "elongat"),
    )

    if "modulus" in lower:
        if stress is None or strain_match is None:
            return None
        return PhysicsIntent(
            kind="materials",
            physics_op="youngs_modulus",
            physics_params={"sigma": stress[0], "strain": float(strain_match.group(1))},
            physics_units={"sigma": stress[1] or "Pa", "strain": ""},
            operation="solve",
        )

    if "strain" in lower:
        # Two distinct lengths, not one read twice. "a wire extends by 4 mm"
        # matches both keyword sets on the same value, which would give a
        # strain of exactly 1 for any wire.
        lengths = _ordered_values(cleaned, _LENGTH_UNIT_PATTERN)
        if len(lengths) == 2:
            original, extension = lengths
        if original is None or extension is None or len(lengths) < 2:
            return None
        if original[0] == extension[0]:
            return None
        return PhysicsIntent(
            kind="materials",
            physics_op="strain",
            physics_params={"L0": original[0], "dL": extension[0]},
            physics_units={"L0": original[1] or "m", "dL": extension[1] or "m"},
            operation="solve",
        )

    if force is not None and area is not None:
        return PhysicsIntent(
            kind="materials",
            physics_op="stress",
            physics_params={"F": force[0], "area": area[0]},
            physics_units={"F": force[1] or "N", "area": area[1] or "m^2"},
            operation="solve",
        )
    return None
