"""Spring, pendulum, SHM, and wave extractors."""

from __future__ import annotations

import re
from typing import Literal

from app.models.schemas.physics import PhysicsIntent
from app.modules.physics.extractors.common import (
    _G_DEFAULT,
    _LENGTH_UNIT_PATTERN,
    _NUMBER,
    _VELOCITY_UNIT_PATTERN,
    _detect_gravity,
    _find_value_with_specific_unit,
    _has_cue,
    _ordered_values,
    _strip_param_assignments,
)
from app.services.text_match import has_equation

_WAVE_CUES = (
    "wavelength",
    "doppler",
    "sound wave",
    "light wave",
    "water wave",
    "wave on a string",
    "string tension",
    "linear density",
    "standing wave",
    "open pipe",
    "closed pipe",
    "sound intensity",
    "beat frequency",
)

_HERTZ_PATTERN = r"Hz|hertz|kHz|kilohertz|MHz|megahertz"

_SOUND_SOURCE = r"siren|ambulance|police|horn|whistle|train|engine|speaker|source"

_WAVE_CUE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(rf"\bwaves?\b.{{0,80}}?\d\s*(?:{_HERTZ_PATTERN})\b", re.IGNORECASE),
    re.compile(rf"\d\s*(?:{_HERTZ_PATTERN})\b.{{0,80}}?\bwaves?\b", re.IGNORECASE),
    re.compile(rf"\b(?:{_SOUND_SOURCE})\b.{{0,80}}?\d\s*(?:{_HERTZ_PATTERN})\b", re.IGNORECASE),
    re.compile(rf"\d\s*(?:{_HERTZ_PATTERN})\b.{{0,80}}?\b(?:{_SOUND_SOURCE})\b", re.IGNORECASE),
    re.compile(rf"\bbeats?\b.{{0,80}}?\d\s*(?:{_HERTZ_PATTERN})\b", re.IGNORECASE),
    re.compile(rf"\d\s*(?:{_HERTZ_PATTERN})\b.{{0,80}}?\bbeats?\b", re.IGNORECASE),
    # A wave stated by its period carries no Hz at all. The time unit has to
    # follow "period", so "a wave of layoffs over a 3 week period" cannot match
    # - it puts its number before the word, and weeks are not in the pattern.
    re.compile(
        r"\bwaves?\b.{0,80}?\bperiod\b\s*(?:of\s*)?\d+(?:\.\d+)?\s*"
        r"(?:seconds?|secs?|milliseconds?|ms|s)\b",
        re.IGNORECASE,
    ),
)

_APPROACHING_RE = re.compile(
    r"\bapproach\w*\b|\btowards?\b|\bcoming\s+(?:at|toward)\b|\bnearing\b", re.IGNORECASE
)

_RECEDING_RE = re.compile(
    r"\breced\w*\b|\baway\s+from\b|\bmoving\s+away\b|\bdeparting\b", re.IGNORECASE
)

_SPEED_OF_SOUND = 343.0


def _extract_waves_intent(cleaned: str) -> PhysicsIntent | None:
    lower = cleaned.lower()
    if not _has_cue(lower, _WAVE_CUES, _WAVE_CUE_RES):
        return None
    if has_equation(_strip_param_assignments(cleaned)):
        return None

    frequencies = _ordered_values(cleaned, _HERTZ_PATTERN)

    # --- Waves on strings: v = sqrt(T / mu) ----------------------------
    if "string" in lower and ("tension" in lower or "linear density" in lower):
        tension = _find_value_with_specific_unit(cleaned, r"N|newtons?", ("tension",))
        linear_density = _find_value_with_specific_unit(
            cleaned,
            r"kg/m|g/m|kilograms?\s+per\s+met(?:er|re)|grams?\s+per\s+met(?:er|re)",
            ("linear density", "mass per unit length"),
        )
        if tension is None or linear_density is None:
            return None
        return PhysicsIntent(
            kind="waves",
            physics_op="string_wave_speed",
            physics_params={"tension": tension[0], "linear_density": linear_density[0]},
            physics_units={
                "tension": tension[1] or "N",
                "linear_density": linear_density[1] or "kg/m",
            },
            operation="solve",
        )

    # --- Open/closed pipes and strings: f_n = n v / (k L) --------------
    if any(cue in lower for cue in ("standing wave", "open pipe", "closed pipe")):
        length = _find_value_with_specific_unit(
            cleaned, _LENGTH_UNIT_PATTERN, ("length", "long", "pipe", "string")
        )
        speed = _find_value_with_specific_unit(cleaned, _VELOCITY_UNIT_PATTERN)
        if length is None or speed is None:
            return None
        harmonic_match = re.search(
            rf"\b({_NUMBER})(?:st|nd|rd|th)?\s+(?:harmonic|mode)\b", cleaned, re.IGNORECASE
        )
        named_harmonic = re.search(
            r"\b(first|second|third|fourth|fifth|sixth)\s+(?:harmonic|mode)\b",
            cleaned,
            re.IGNORECASE,
        )
        harmonic_names = {
            "first": 1.0,
            "second": 2.0,
            "third": 3.0,
            "fourth": 4.0,
            "fifth": 5.0,
            "sixth": 6.0,
        }
        if harmonic_match is not None:
            harmonic = float(harmonic_match.group(1))
        elif named_harmonic is not None:
            harmonic = harmonic_names[named_harmonic.group(1).lower()]
        elif "fundamental" in lower:
            harmonic = 1.0
        else:
            # An unnamed harmonic is not automatically the fundamental.
            return None
        mode_factor = 4.0 if "closed pipe" in lower else 2.0
        return PhysicsIntent(
            kind="waves",
            physics_op="resonance_frequency",
            physics_params={
                "v_wave": speed[0],
                "L": length[0],
                "harmonic": harmonic,
                "mode_factor": mode_factor,
            },
            physics_units={
                "v_wave": speed[1] or "m/s",
                "L": length[1] or "m",
                "harmonic": "",
                "mode_factor": "",
            },
            operation="solve",
        )

    # --- Sound spreading from a point source: I = P / (4 pi r^2) -------
    if "sound intensity" in lower:
        power = _find_value_with_specific_unit(
            cleaned, r"W|watts?|kW|kilowatts?", ("power", "source", "emits")
        )
        radius = _find_value_with_specific_unit(
            cleaned, _LENGTH_UNIT_PATTERN, ("distance", "radius", "away", "at")
        )
        if power is None or radius is None:
            return None
        return PhysicsIntent(
            kind="waves",
            physics_op="sound_intensity",
            physics_params={"sound_power": power[0], "r": radius[0]},
            physics_units={"sound_power": power[1] or "W", "r": radius[1] or "m"},
            operation="solve",
        )

    # --- Beats: f_b = |f_1 - f_2| --------------------------------------
    if "beat" in lower:
        if len(frequencies) != 2:
            return None
        return PhysicsIntent(
            kind="waves",
            physics_op="beat_frequency",
            physics_params={"freq": frequencies[0][0], "freq2": frequencies[1][0]},
            physics_units={
                "freq": frequencies[0][1] or "Hz",
                "freq2": frequencies[1][1] or "Hz",
            },
            operation="solve",
        )

    freq = _find_value_with_specific_unit(cleaned, _HERTZ_PATTERN)
    wavelength = _find_value_with_specific_unit(
        cleaned, _LENGTH_UNIT_PATTERN, ("wavelength",), require_keyword=True
    )
    speed = _find_value_with_specific_unit(cleaned, _VELOCITY_UNIT_PATTERN)
    period = _find_value_with_specific_unit(
        cleaned, _SHM_TIME_UNITS, ("period",), require_keyword=True
    )

    moving_source = re.search(rf"\b(?:{_SOUND_SOURCE})\b", lower) is not None
    if "doppler" in lower or (freq is not None and speed is not None and moving_source):
        approaching = _APPROACHING_RE.search(cleaned) is not None
        receding = _RECEDING_RE.search(cleaned) is not None
        if freq is None or speed is None or approaching == receding:
            return None
        return PhysicsIntent(
            kind="waves",
            physics_op="doppler_frequency",
            physics_params={
                "freq": freq[0],
                "v_src": speed[0] if approaching else -speed[0],
                "v_sound": _SPEED_OF_SOUND,
            },
            physics_units={"freq": freq[1] or "Hz", "v_src": "m/s", "v_sound": "m/s"},
            operation="solve",
        )

    # f = 1/T and T = 1/f, whichever of the pair is missing.
    if period is not None and freq is None:
        return PhysicsIntent(
            kind="waves",
            physics_op="wave_frequency_from_period",
            physics_params={"period": period[0]},
            physics_units={"period": period[1] or "s"},
            operation="solve",
        )
    if freq is not None and wavelength is None and speed is None and "period" in lower:
        return PhysicsIntent(
            kind="waves",
            physics_op="wave_period",
            physics_params={"freq": freq[0]},
            physics_units={"freq": freq[1] or "Hz"},
            operation="solve",
        )

    # v = f lambda, solved for whichever of the three is absent.
    given = {
        "freq": freq,
        "wavelength": wavelength,
        "v_wave": speed,
    }
    present = {key: value for key, value in given.items() if value is not None}
    if len(present) != 2:
        return None
    missing = ({"freq", "wavelength", "v_wave"} - set(present)).pop()
    op = {
        "freq": "wave_frequency",
        "wavelength": "wavelength",
        "v_wave": "wave_speed",
    }[missing]
    defaults = {"freq": "Hz", "wavelength": "m", "v_wave": "m/s"}
    return PhysicsIntent(
        kind="waves",
        physics_op=op,  # type: ignore[arg-type]
        physics_params={key: value[0] for key, value in present.items()},
        physics_units={key: (value[1] or defaults[key]) for key, value in present.items()},
        operation="solve",
    )


_SPRING_CUES = (
    "hooke",
    "spring constant",
    "simple harmonic",
    "oscillation",
    "oscillating",
    "oscillates",
)

_SPRING_CUE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bspring\b.{0,80}?(?:\d+\s*N/m|\bk\s*=)", re.IGNORECASE),
    re.compile(r"(?:\d+\s*N/m|\bk\s*=).{0,80}?\bspring\b", re.IGNORECASE),
)

_SPRING_K_RE = re.compile(r"\bk\s*=\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE)

_DISPLACEMENT_KEYWORDS = (
    "stretched",
    "compressed",
    "extended",
    "displacement",
    "amplitude",
    "extension",
    "by",
)

_PENDULUM_CUE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bpendulum\b.{0,80}?\d\s*(?:centimet(?:er|re)s?|met(?:er|re)s?|cm|m)\b", re.I),
    re.compile(r"\d\s*(?:centimet(?:er|re)s?|met(?:er|re)s?|cm|m)\b.{0,80}?\bpendulum\b", re.I),
)

_PENDULUM_PERIOD_RE = re.compile(
    r"\bperiod\b|\bhow long\b|\bswing\w*\b|\boscillat\w*\b|\btime\s+for\s+(?:one|a)\b",
    re.IGNORECASE,
)


def _extract_pendulum_intent(cleaned: str) -> PhysicsIntent | None:
    if not _has_cue(cleaned.lower(), (), _PENDULUM_CUE_RES):
        return None
    if not _PENDULUM_PERIOD_RE.search(cleaned):
        return None
    if has_equation(_strip_param_assignments(cleaned)):
        return None

    length = _find_value_with_specific_unit(
        cleaned, _LENGTH_UNIT_PATTERN, ("pendulum", "length", "long", "string", "cord")
    )
    if length is None:
        return None

    params: dict[str, float] = {"L": length[0]}
    units: dict[str, str] = {"L": length[1] or "m"}
    gravity = _detect_gravity(cleaned)
    if gravity != _G_DEFAULT:
        params["g"], units["g"] = gravity, "m/s^2"
    return PhysicsIntent(
        kind="spring",
        physics_op="pendulum_period",
        physics_params=params,
        physics_units=units,
        operation="solve",
    )


_SHM_FREQUENCY_RE = re.compile(
    r"\bfrequency\b.{0,80}?\bperiod\b|\bperiod\b.{0,80}?\bfrequency\b",
    re.IGNORECASE,
)

_SHM_MAX_SPEED_RE = re.compile(
    r"\b(?:max(?:imum)?|peak)\s+(?:speed|velocity)\b.{0,80}?\bamplitude\b"
    r"|\bamplitude\b.{0,80}?\b(?:max(?:imum)?|peak)\s+(?:speed|velocity)\b",
    re.IGNORECASE,
)

_SHM_CUE_RES: tuple[re.Pattern[str], ...] = (_SHM_FREQUENCY_RE, _SHM_MAX_SPEED_RE)

_SHM_TIME_UNITS = r"seconds?|secs?|sec|s|milliseconds?|ms|minutes?|mins?|min"

_ANGULAR_FREQ_RE = re.compile(
    r"(-?\d+(?:\.\d+)?)\s*(?:rad(?:ians?)?\s*(?:/|per)\s*s(?:ec(?:ond)?s?)?)",
    re.IGNORECASE,
)


def _extract_shm_intent(cleaned: str) -> PhysicsIntent | None:
    lower = cleaned.lower()
    if not _has_cue(lower, (), _SHM_CUE_RES):
        return None
    # f = 1/T is the same arithmetic for an oscillator and a wave, but the kind
    # should say which was asked about. Waves runs later, so defer explicitly.
    if "wave" in lower:
        return None
    if has_equation(_strip_param_assignments(cleaned)):
        return None

    if _SHM_MAX_SPEED_RE.search(cleaned):
        amplitude = _find_value_with_specific_unit(
            cleaned, _LENGTH_UNIT_PATTERN, ("amplitude",), require_keyword=True
        )
        omega = _ANGULAR_FREQ_RE.search(cleaned)
        if amplitude is None or omega is None:
            return None
        return PhysicsIntent(
            kind="spring",
            physics_op="shm_max_speed",
            physics_params={"x": amplitude[0], "omega": float(omega.group(1))},
            physics_units={"x": amplitude[1] or "m", "omega": "rad/s"},
            operation="solve",
        )

    period = _find_value_with_specific_unit(
        cleaned, _SHM_TIME_UNITS, ("period",), require_keyword=True
    )
    if period is None:
        return None
    return PhysicsIntent(
        kind="spring",
        physics_op="shm_frequency",
        physics_params={"period": period[0]},
        physics_units={"period": period[1] or "s"},
        operation="solve",
    )


def _extract_spring_intent(cleaned: str) -> PhysicsIntent | None:
    lower = cleaned.lower()
    if not _has_cue(lower, _SPRING_CUES, _SPRING_CUE_RES):
        return None
    # Strip "k = 200" before the algebra check: it is a known, not an equation
    # to solve. Without this the whole question is read as algebra — which is
    # what happened before this extractor existed.
    if has_equation(_strip_param_assignments(_SPRING_K_RE.sub("", cleaned))):
        return None

    k_match = _find_value_with_specific_unit(cleaned, r"N/m")
    if k_match is not None:
        k: float | None = k_match[0]
    else:
        k_assign = _SPRING_K_RE.search(cleaned)
        k = float(k_assign.group(1)) if k_assign else None
    if k is None:
        return None

    displacement = _find_value_with_specific_unit(
        cleaned, _LENGTH_UNIT_PATTERN, _DISPLACEMENT_KEYWORDS
    )
    mass = _find_value_with_specific_unit(
        cleaned, r"kg|mg|lb|lbs|oz", ("mass", "object", "body", "block")
    )

    op: Literal["spring_force", "spring_energy", "shm_period"]
    if "period" in lower or "oscillat" in lower or "simple harmonic" in lower:
        op = "shm_period"
        if mass is None:
            return None
    elif "energy" in lower:
        op = "spring_energy"
        if displacement is None:
            return None
    elif "force" in lower:
        op = "spring_force"
        if displacement is None:
            return None
    else:
        return None

    params: dict[str, float] = {"k": k}
    units: dict[str, str] = {"k": "N/m"}
    if displacement is not None:
        params["x"] = displacement[0]
        units["x"] = displacement[1] or "m"
    if mass is not None:
        params["m"] = mass[0]
        units["m"] = mass[1] or "kg"
    return PhysicsIntent(
        kind="spring",
        physics_op=op,
        physics_params=params,
        physics_units=units,
        operation="solve",
    )
