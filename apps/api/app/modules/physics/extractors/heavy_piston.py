"""Closed heavy-piston equilibrium: upright, isobaric heating, and inversion.

The gas pressure is what the force balance finds. An isobaric word in the same
sentence must not decline the problem for lack of a stated gas pressure, and it
must not treat atmospheric pressure as that gas pressure.
"""

from __future__ import annotations

import re

from app.models.schemas.physics import PhysicsIntent
from app.modules.physics.extractors.common import _NUMBER
from app.modules.physics.extractors.school_common import _PRESSURE, _intent

_MASS_UNIT = r"kg|kilograms?|grams?|g"
_AREA_UNIT = r"cm\^2|m\^2|cm2|m2"
_MOLE_UNIT = r"mol(?:e|es)?"
_KELVIN_UNIT = r"K|kelvins?"
_ACCEL_UNIT = r"m/s\^2|m/s2"
_SCIENCE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:\\times|\u00d7|\bx\b|\*)\s*10\^(-?\d+)",
    re.IGNORECASE,
)
_BARE_POWER = re.compile(r"(?<![\d.])10\^(-?\d+)")
_SUBSCRIPT_CHARS = "₀₁₂₃₄₅₆₇₈₉"
_SUBSCRIPTS = str.maketrans(_SUBSCRIPT_CHARS, "0123456789")
_DOUBLES = re.compile(
    r"\b(?:volume\s+(?:doubles|is\s+doubled|doubled)|"
    r"(?:doubles|doubled)\s+(?:its\s+|the\s+)?volume|"
    r"twice\s+(?:its\s+|the\s+)?(?:original\s+)?volume|"
    r"volume\s+(?:becomes|is)\s+twice|"
    r"v_2\s*=\s*2\s*v_1|v2\s*=\s*2\s*v1)\b",
    re.IGNORECASE,
)
_HEAT_ASK = re.compile(
    r"\bheat\s+(?:supplied|absorbed|added|transferred|required|given)\b"
    r"|\b(?:supplied|absorbed|added|transferred)\s+heat\b"
    r"|\bhow much heat\b",
    re.IGNORECASE,
)
_FLIP = re.compile(r"\b(?:upside\s+down|inverted|turned\s+over)\b", re.IGNORECASE)
_FLIP_OTHER_TEMP = re.compile(
    r"\badiabatic\w*\b|\bnew temperature\b|\btemperature changes\b|\bat\s+t_?2\b",
    re.IGNORECASE,
)
_UPRIGHT = re.compile(
    r"\b(?:upright|vertically|vertical)\b"
    r"|\bpiston\b.{0,40}\babove\b"
    r"|\babove\s+the\s+gas\b",
    re.IGNORECASE,
)
_CV = re.compile(r"\bC_?\s*[vV]\s*=\s*\(?\s*(" + _NUMBER + r")\s*\)?\s*R\b")
_CP = re.compile(r"\bC_?\s*[pP]\s*=\s*\(?\s*(" + _NUMBER + r")\s*\)?\s*R\b")
_R_VALUE = re.compile(r"\bR\s*=\s*(" + _NUMBER + r")(?:\s*(?P<tail>\S+))?")
_R_JOULE = re.compile(r"^(?:J|joule)", re.IGNORECASE)
_R_OTHER = re.compile(r"^(?:atm|bar|psi|cal|L|litre|liter)\b", re.IGNORECASE)
_R_WORD = re.compile(r"(?:and|with|where|take)\b", re.IGNORECASE)
_G_VALUE = re.compile(
    r"\bg\s*=\s*(" + _NUMBER + r")(?:\s*(?P<unit>" + _ACCEL_UNIT + r"|[A-Za-z/]+))?"
)
_GRAVITY = re.compile(
    r"\bgravity\s*(?:=|is)\s*(" + _NUMBER + r")(?:\s*(?:" + _ACCEL_UNIT + r"))?",
    re.IGNORECASE,
)
_MASS_PHRASE = re.compile(
    r"\b(?:piston(?:'s)?\s+(?:of\s+)?mass|mass\s+of\s+(?:the\s+)?piston)\s*"
    r"(?:=|is|of)?\s*(" + _NUMBER + r")\s*(" + _MASS_UNIT + r")\b",
    re.IGNORECASE,
)
_AREA_PHRASE = re.compile(
    r"\b(?:cross[-\s]?sectional\s+)?area\s*(?:=|is|of)?\s*("
    + _NUMBER
    + r")\s*("
    + _AREA_UNIT
    + r")\b",
    re.IGNORECASE,
)
_ATM_PHRASE = re.compile(
    r"\batmospheric pressure\s*(?:=|is|of)?\s*(" + _NUMBER + r")\s*(" + _PRESSURE + r")\b",
    re.IGNORECASE,
)
_TEMP_PHRASE = re.compile(
    r"\btemperature\s*(?:=|is|of)?\s*(" + _NUMBER + r")\s*(" + _KELVIN_UNIT + r")\b",
    re.IGNORECASE,
)


def extract_heavy_piston(text: str, lower: str) -> PhysicsIntent | None:
    if re.search(r"\bpistons?\b", lower) is None:
        return None
    if re.search(r"\b(?:ideal[-\s]gas|monatomic)\b", lower) is None:
        return None
    if re.search(r"\bhorizontal\b", lower):
        return None
    prepared = _fold_scientific(_fold_subscripts(text))
    prepared_lower = prepared.lower()
    moles = _labeled_or_sole(prepared, "n", _MOLE_UNIT, "mol")
    mass = _mass(prepared)
    area = _area(prepared)
    pressure = _pressure(prepared)
    temp = _temperature(prepared)
    gravity = _gravity(prepared)
    gas_r, gas_ok = _gas_constant(prepared)
    if (
        not gas_ok
        or moles is None
        or mass is None
        or area is None
        or pressure is None
        or temp is None
        or gravity is None
    ):
        return None
    flags = _process_flags(prepared, prepared_lower)
    orientation = _orientation(prepared_lower)
    if flags is None or orientation is None:
        return None
    params: dict[str, float] = {
        "moles": moles[0],
        "M": mass[0],
        "area": area[0],
        "p_atm": pressure[0],
        "temp": temp[0],
        "g": gravity[0],
    }
    units = {
        "moles": "mol",
        "M": _mass_unit(mass[1]),
        "area": _area_unit(area[1]),
        "p_atm": _pressure_unit(pressure[1]),
        "temp": "K",
        "g": "m/s^2",
    }
    if gas_r is not None:
        params["gas_r"] = gas_r
        units["gas_r"] = "J/mol/K"
    params.update(flags)
    params.update(orientation)
    for name in (*flags, *orientation):
        units[name] = ""
    return _intent("thermal", "heavy_piston", params, units)


def _fold_subscripts(text: str) -> str:
    out: list[str] = []
    index = 0
    while index < len(text):
        if text[index] in _SUBSCRIPT_CHARS:
            end = index + 1
            while end < len(text) and text[end] in _SUBSCRIPT_CHARS:
                end += 1
            out.append("_" + text[index:end].translate(_SUBSCRIPTS))
            index = end
            continue
        out.append(text[index])
        index += 1
    return re.sub(r"_\{(\d+)\}", r"_\1", "".join(out))


def _fold_scientific(text: str) -> str:
    def coefficient(match: re.Match[str]) -> str:
        return _decimal(float(match.group(1)) * 10 ** int(match.group(2)))

    def bare(match: re.Match[str]) -> str:
        return _decimal(10 ** int(match.group(1)))

    return _BARE_POWER.sub(bare, _SCIENCE.sub(coefficient, text))


def _decimal(value: float) -> str:
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def _assignment(text: str, labels: str, unit: str, default: str) -> tuple[float, str] | None:
    found = list(
        re.finditer(
            rf"\b(?:{labels})\s*=\s*({_NUMBER})(?:\s*({unit}))?(?![A-Za-z0-9/^])",
            text,
        )
    )
    if len(found) != 1:
        return None
    raw_unit = found[0].group(2)
    return float(found[0].group(1)), raw_unit or default


def _sole(text: str, unit: str, default: str) -> tuple[float, str] | None:
    found = list(
        re.finditer(
            rf"({_NUMBER})\s*({unit})(?![A-Za-z0-9/^])",
            text,
            re.IGNORECASE,
        )
    )
    if len(found) != 1:
        return None
    return float(found[0].group(1)), found[0].group(2) or default


def _prefer(
    primary: tuple[float, str] | None,
    fallback: tuple[float, str] | None,
) -> tuple[float, str] | None:
    if primary is None:
        return fallback
    if fallback is not None and primary[0] != fallback[0]:
        return None
    return primary


def _with_fallback(
    primary: tuple[float, str] | None,
    secondary: tuple[float, str] | None,
    sole: tuple[float, str] | None,
) -> tuple[float, str] | None:
    if primary is not None and secondary is not None and primary[0] != secondary[0]:
        return None
    return primary or secondary or sole


def _labeled_or_sole(text: str, labels: str, unit: str, default: str) -> tuple[float, str] | None:
    return _prefer(_assignment(text, labels, unit, default), _sole(text, unit, default))


def _mass(text: str) -> tuple[float, str] | None:
    return _with_fallback(
        _assignment(text, "M", _MASS_UNIT, "kg"),
        _first_pair(_MASS_PHRASE, text),
        _sole(text, _MASS_UNIT, "kg"),
    )


def _area(text: str) -> tuple[float, str] | None:
    return _with_fallback(
        _assignment(text, "A", _AREA_UNIT, "m^2"),
        _first_pair(_AREA_PHRASE, text),
        _sole(text, _AREA_UNIT, "m^2"),
    )


def _pressure(text: str) -> tuple[float, str] | None:
    return _with_fallback(
        _assignment(text, r"P_0|P0|p_0|p0", _PRESSURE, "Pa"),
        _first_pair(_ATM_PHRASE, text),
        _sole(text, _PRESSURE, "Pa"),
    )


def _temperature(text: str) -> tuple[float, str] | None:
    return _with_fallback(
        _assignment(text, r"T_0|T0", _KELVIN_UNIT, "K"),
        _first_pair(_TEMP_PHRASE, text),
        _sole(text, _KELVIN_UNIT, "K"),
    )


def _first_pair(pattern: re.Pattern[str], text: str) -> tuple[float, str] | None:
    found = list(pattern.finditer(text))
    if len(found) != 1:
        return None
    return float(found[0].group(1)), found[0].group(2)


def _gravity(text: str) -> tuple[float, str] | None:
    labeled = list(_G_VALUE.finditer(text))
    if re.search(r"\bg\s*=", text) is not None and len(labeled) != 1:
        return None
    if len(labeled) == 1:
        unit = labeled[0].group("unit")
        if unit is not None and unit not in {"m/s^2", "m/s2"}:
            return None
        return float(labeled[0].group(1)), "m/s^2"
    phrase = list(_GRAVITY.finditer(text))
    if len(phrase) == 1:
        return float(phrase[0].group(1)), "m/s^2"
    return _sole(text, _ACCEL_UNIT, "m/s^2")


def _gas_constant(text: str) -> tuple[float | None, bool]:
    if re.search(r"\bR\s*=", text) is None:
        return None, True
    match = _R_VALUE.search(text)
    if match is None:
        return None, False
    tail = match.group("tail") or ""
    if tail and _R_OTHER.match(tail):
        return None, False
    word = re.match(r"[A-Za-z]", tail) is not None
    if tail and word and not _R_JOULE.match(tail) and not _R_WORD.match(tail):
        return None, False
    return float(match.group(1)), True


def _heat_ratio(text: str, lower: str) -> tuple[float | None, bool]:
    cv = 1.5 if re.search(r"\bmonatomic\b", lower) else None
    cv_match = _CV.search(text)
    cp_match = _CP.search(text)
    if cv_match is not None:
        stated = float(cv_match.group(1))
        if cv is not None and abs(cv - stated) > 1e-9:
            return None, False
        cv = stated
    if cp_match is not None:
        stated_cp = float(cp_match.group(1))
        if cv is not None and abs((cv + 1) - stated_cp) > 1e-9:
            return None, False
        if cv is None:
            cv = stated_cp - 1
    if cv is not None and cv <= 0:
        return None, False
    return cv, True


def _process_flags(text: str, lower: str) -> dict[str, float] | None:
    doubles = _DOUBLES.search(lower) is not None
    cv, ok = _heat_ratio(text, lower)
    if not ok:
        return None
    if _HEAT_ASK.search(lower) is not None and (cv is None or not doubles):
        return None
    flags: dict[str, float] = {}
    if doubles:
        flags["expand_ratio"] = 2.0
        if cv is not None:
            flags["cv_over_r"] = cv
    return flags


def _orientation(lower: str) -> dict[str, float] | None:
    flip = _FLIP.search(lower) is not None
    if flip and _FLIP_OTHER_TEMP.search(lower) is not None:
        return None
    flags: dict[str, float] = {}
    if _UPRIGHT.search(lower) is not None or not flip:
        flags["upright"] = 1.0
    if flip:
        flags["flip"] = 1.0
    return flags


def _mass_unit(raw: str) -> str:
    key = raw.lower()
    if key.startswith("g") and not key.startswith("kg"):
        return "g"
    return "kg"


def _area_unit(raw: str) -> str:
    key = raw.lower().replace(" ", "")
    if key.startswith("cm"):
        return "cm^2"
    return "m^2"


def _pressure_unit(raw: str) -> str:
    key = raw.lower()
    if key.startswith("mpa") or key.startswith("mega"):
        return "MPa"
    if key.startswith("kpa") or key.startswith("kilo"):
        return "kPa"
    return "Pa"
