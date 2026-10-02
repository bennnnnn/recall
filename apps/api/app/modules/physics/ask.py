"""What a physics question asks for, read as physical dimensions.

An extractor that does not recognise how a question is asked falls back to its
default operation: "a ball is dropped from 80 m, what is its speed just before
it hits the ground" was answered with a time, 4.04 s. Reading the asked
quantity independently lets the block refuse a result of another dimension.

Only a confident reading counts. A question whose ask cannot be read, or that
names an ambiguous quantity ("field strength", "components"), gets no guard.
"""

from __future__ import annotations

import re

from app.modules.physics.givens import ANGLE, unit_at, unit_dimension

_DIMENSIONLESS = "dimensionless"
_UNKNOWN = ""

# Asked phrase -> Pint expression. ANGLE and dimensionless stand for themselves;
# an empty string marks a phrase that is a quantity of no single dimension, so
# the reading is abandoned rather than guessed.
_QUANTITIES: dict[str, str] = {
    # Time
    "how long": "second",
    "time of flight": "second",
    "flight time": "second",
    "time taken": "second",
    "time constant": "second",
    "half-life": "second",
    "half life": "second",
    "period": "second",
    "duration": "second",
    "time": "second",
    # Length
    "how far": "meter",
    "how high": "meter",
    "how deep": "meter",
    "distance": "meter",
    "displacement": "meter",
    "height": "meter",
    "range": "meter",
    "length": "meter",
    "wavelength": "meter",
    "radius": "meter",
    "depth": "meter",
    "extension": "meter",
    "compression": "meter",
    "focal length": "meter",
    "separation": "meter",
    "position": "meter",
    # Motion
    "how fast": "meter / second",
    "speed": "meter / second",
    "velocity": "meter / second",
    "velocities": "meter / second",
    "speeds": "meter / second",
    "acceleration": "meter / second ** 2",
    "deceleration": "meter / second ** 2",
    "retardation": "meter / second ** 2",
    "gravitational field strength": "meter / second ** 2",
    "angular velocity": "radian / second",
    "angular speed": "radian / second",
    "angular frequency": "radian / second",
    "angular acceleration": "radian / second ** 2",
    "angular displacement": ANGLE,
    "angular momentum": "kilogram * meter ** 2 / second",
    "center of mass": "meter",
    "centre of mass": "meter",
    "moment of inertia": "kilogram * meter ** 2",
    "momentum": "kilogram * meter / second",
    "impulse": "kilogram * meter / second",
    # Force and energy
    "force": "newton",
    "forces": "newton",
    "tension": "newton",
    "weight": "newton",
    "thrust": "newton",
    "upthrust": "newton",
    "buoyant force": "newton",
    "normal force": "newton",
    "friction": "newton",
    "drag": "newton",
    "torque": "newton * meter",
    "moment": "newton * meter",
    "energy": "joule",
    "work": "joule",
    "work done": "joule",
    "work function": "joule",
    "heat": "joule",
    "kinetic energy": "joule",
    "potential energy": "joule",
    "heat energy": "joule",
    "latent heat energy": "joule",
    "mass energy": "joule",
    "rest energy": "joule",
    "energy equivalent": "joule",
    "ke": "joule",
    "pe": "joule",
    "gpe": "joule",
    "rate of heat": "watt",
    "heat conduction rate": "watt",
    "conduction rate": "watt",
    "mass flow rate": "kilogram / second",
    "flow rate": "meter ** 3 / second",
    "surface tension": "newton / meter",
    "power": "watt",
    "lens power": "1 / meter",
    "optical power": "1 / meter",
    "pressure": "pascal",
    "stress": "pascal",
    "young modulus": "pascal",
    "young's modulus": "pascal",
    "youngs modulus": "pascal",
    "bulk modulus": "pascal",
    "shear modulus": "pascal",
    "modulus": "pascal",
    "mass": "kilogram",
    "density": "kilogram / meter ** 3",
    "volume": "meter ** 3",
    "area": "meter ** 2",
    "spring constant": "newton / meter",
    "stiffness": "newton / meter",
    # Waves and thermal
    "frequency": "hertz",
    "frequencies": "hertz",
    "pitch": "hertz",
    "temperature": "kelvin",
    "specific heat capacity": "joule / kilogram / kelvin",
    "specific heat": "joule / kilogram / kelvin",
    "latent heat": "joule / kilogram",
    "entropy": "joule / kelvin",
    "number of moles": "mole",
    "moles": "mole",
    # Electricity and magnetism
    "current": "ampere",
    "voltage": "volt",
    "electric potential": "volt",
    "electric potential energy": "joule",
    "potential difference": "volt",
    "emf": "volt",
    "e.m.f.": "volt",
    "terminal voltage": "volt",
    "resistance": "ohm",
    "impedance": "ohm",
    "reactance": "ohm",
    "resistivity": "ohm * meter",
    "charge": "coulomb",
    "capacitance": "farad",
    "inductance": "henry",
    "magnetic field": "tesla",
    "flux density": "tesla",
    "magnetic flux": "weber",
    "electric field": "volt / meter",
    "activity": "1 / second",
    "decay constant": "1 / second",
    # Pure numbers and angles
    "angle": ANGLE,
    "efficiency": _DIMENSIONLESS,
    "refractive index": _DIMENSIONLESS,
    "index of refraction": _DIMENSIONLESS,
    "coefficient of friction": _DIMENSIONLESS,
    "coefficient of static friction": _DIMENSIONLESS,
    "coefficient of kinetic friction": _DIMENSIONLESS,
    "coefficient of performance": _DIMENSIONLESS,
    "coefficient": _DIMENSIONLESS,
    "reynolds number": _DIMENSIONLESS,
    "magnification": _DIMENSIONLESS,
    "lorentz factor": _DIMENSIONLESS,
    "fraction": _DIMENSIONLESS,
    "ratio": _DIMENSIONLESS,
    "strain": _DIMENSIONLESS,
    # Quantities of no single dimension: stop reading rather than guess.
    "field strength": _UNKNOWN,
    "field": _UNKNOWN,
    "component": _UNKNOWN,
    "components": _UNKNOWN,
    "value": _UNKNOWN,
    "answer": _UNKNOWN,
}

# A phrase naming the quantity itself ("how long"), not an ask before one.
_SELF_NAMING = ("how long", "how far", "how fast", "how high", "how deep")

_ASK = re.compile(
    r"\b(?:find|calculate|compute|determine|work\s+out|estimate|evaluate|"
    r"what|"
    r"how\s+(?:long|far|fast|high|deep|much|many))\b",
    re.IGNORECASE,
)
_QUANTITY = re.compile(
    r"\b(?:"
    + "|".join(re.escape(phrase) for phrase in sorted(_QUANTITIES, key=len, reverse=True))
    + r")(?![\w-])",
    re.IGNORECASE,
)
# What may sit between two asked quantities in one list: "the time of flight,
# the maximum height and the range".
_CONNECTOR = re.compile(
    r"\s*,?\s*(?:and\s+|as\s+well\s+as\s+)?(?:also\s+)?(?:the\s+|its\s+|their\s+)?"
    r"(?:(?:maximum|max|minimum|min|total|final|initial|average|horizontal|vertical|"
    r"resultant|net|peak|new|common|equivalent|effective|kinetic|potential)\s+)*",
    re.IGNORECASE,
)
_SENTENCE_END = re.compile(r"[?!]|\.(?:\s|$)")
# "a planet of mass 6e24 kg": a quantity followed by its own value is a given.
# "the energy equivalent of 2 kg" is still the ask: kg is not an energy.
_VALUE_AFTER = re.compile(
    r"\s*(?P<link>of\s+|=\s*|is\s+|:\s*)?(?P<number>[-+]?(?:\d+(?:\.\d+)?|\.\d+)(?:e[-+]?\d+)?)",
    re.IGNORECASE,
)
# The asked quantity follows its verb closely: "find the speed", "what is the
# magnitude of the resultant force". Further on, a noun is part of a given.
_ASK_REACH = 60
_LENS = re.compile(r"\blens\b|\bdiopt", re.IGNORECASE)


def _labels_a_value(clause: str, noun: re.Match[str], text: str) -> bool:
    value = _VALUE_AFTER.match(clause, noun.end())
    if value is None:
        return False
    link = (value.group("link") or "").strip()
    unit = unit_at(clause, value.end("number"))
    if unit is None:
        # "strain of 0.001" is a label; "the energy of 2" is too vague to call.
        return link != "of" or _dimension(noun.group(), text) == _DIMENSIONLESS
    if link == "=":
        return True
    reading = unit_dimension(unit[1])
    return reading is not None and reading[0] == _dimension(noun.group(), text)


def _dimension(phrase: str, text: str) -> str | None:
    expression = _QUANTITIES[phrase.lower()]
    if expression == "watt" and _LENS.search(text):
        return None
    if expression in {ANGLE, _DIMENSIONLESS}:
        return expression
    if expression == _UNKNOWN:
        return None
    reading = unit_dimension(expression)
    return None if reading is None else reading[0]


def asked_phrases(text: str) -> tuple[str, ...]:
    """The quantities the last question asks for, lowercased, in order.

    "Find the time of flight, the maximum height and the range" asks for three.
    Empty when no asked quantity follows the question's verb closely.
    """
    asks = list(_ASK.finditer(text))
    if not asks:
        return ()
    ask = asks[-1]
    self_naming = re.sub(r"\s+", " ", ask.group().lower()).startswith(_SELF_NAMING)
    start = ask.start() if self_naming else ask.end()
    end_match = _SENTENCE_END.search(text, start)
    clause = text[start : end_match.start() if end_match else len(text)]
    nouns = [noun for noun in _QUANTITY.finditer(clause) if not _labels_a_value(clause, noun, text)]
    if not nouns or nouns[0].start() > _ASK_REACH:
        return ()
    phrases: list[str] = []
    previous_end = nouns[0].start()
    for noun in nouns:
        if phrases and not _CONNECTOR.fullmatch(clause, previous_end, noun.start()):
            break
        phrases.append(re.sub(r"\s+", " ", noun.group().lower()))
        previous_end = noun.end()
    return tuple(phrases)


def asked_dimensions(text: str) -> tuple[str, ...]:
    """Dimensions of the asked quantities; empty unless every one is certain."""
    dimensions = [_dimension(phrase, text) for phrase in asked_phrases(text)]
    if None in dimensions:
        return ()
    return tuple(dict.fromkeys(dimension for dimension in dimensions if dimension is not None))


def result_dimension(unit: str) -> str | None:
    """Dimension of a solver's result unit; None when it cannot be read."""
    from app.modules.physics.solvers.common import _UNIT_ALIASES

    spelled = unit.strip()
    if not spelled or spelled == "%":
        return _DIMENSIONLESS
    alias = _UNIT_ALIASES.get(spelled.lower(), spelled).replace("·", "*").replace("^", "**")
    if alias in {"deg", "degree", "radian", "rad"}:
        return ANGLE
    if alias in {"D", "dioptre", "diopter", "dioptres", "diopters"}:
        alias = "1 / meter"
    reading = unit_dimension(alias)
    if reading is None:
        return None
    return _DIMENSIONLESS if reading[0] == "dimensionless" else reading[0]
