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

from app.modules.physics.ask_words import _DIMENSIONLESS, _MONEY, _QUANTITIES, _UNKNOWN
from app.modules.physics.givens import ANGLE, unit_at, unit_dimension
from app.services.law_binding.ask import ask_clause

__all__ = [
    "ask_clause",
    "asked_dimensions",
    "asked_phrases",
    "asked_unit",
    "result_dimension",
    "result_reading",
]

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
# "a planet of mass 6e24 kg": a quantity followed by its own value is a given.
# "the energy equivalent of 2 kg" is still the ask: kg is not an energy.
_VALUE_AFTER = re.compile(
    r"\s*(?P<link>of\s+|=\s*|is\s+|:\s*)?(?P<number>[-+]?(?:\d+(?:\.\d+)?|\.\d+)(?:e[-+]?\d+)?)",
    re.IGNORECASE,
)
# The asked quantity follows its verb closely: "find the speed", "what is the
# magnitude of the resultant force". Further on, a noun is part of a given.
_ASK_REACH = 60
# "lens" misses "lenses": the boundary after the singular is the next letter.
_LENS = re.compile(r"\blens(?:es)?\b|\bdiopt", re.IGNORECASE)


# "How long must the runway be?" and "how long is the rope?" ask for a length.
# The article keeps "how long will it be before it lands" a time.
_LENGTH_NOUNS = (
    r"runway|track|road|rope|string|wire|ramp|pendulum|rod|bridge|cable|tube|pipe|slide"
    r"|ladder|plank|board|strip|beam|bar|lane|path|wall|side|edge"
)
_HOW_LONG_IS_LENGTH = re.compile(
    r"\bhow long\s+(?:"
    r"(?:must|should|would|will|does|do|has\s+to|have\s+to|needs?\s+to)\s+"
    r"(?:the|a|an|its|this|that|each)\s+(?:[\w-]+\s+){0,2}?be\b"
    r"|(?:is|was|are|were|must|should)\s+(?:the|a|an|its|this|that|each)\s+"
    rf"(?:[\w-]+\s+){{0,2}}?(?:{_LENGTH_NOUNS})s?\b)",
    re.IGNORECASE,
)


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
    if expression in {ANGLE, _DIMENSIONLESS, _MONEY}:
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
    clause = ask_clause(text)
    if clause is None:
        return ()
    nouns = [noun for noun in _QUANTITY.finditer(clause) if not _labels_a_value(clause, noun, text)]
    if not nouns or nouns[0].start() > _ASK_REACH:
        return ()
    phrases: list[str] = []
    previous_end = nouns[0].start()
    for noun in nouns:
        if phrases and not _CONNECTOR.fullmatch(clause, previous_end, noun.start()):
            break
        phrase = re.sub(r"\s+", " ", noun.group().lower())
        if phrase == "how long" and _HOW_LONG_IS_LENGTH.search(clause):
            phrase = "length"
        phrases.append(phrase)
        previous_end = noun.end()
    return tuple(phrases)


def asked_dimensions(text: str) -> tuple[str, ...]:
    """Dimensions of the asked quantities; empty unless every one is certain."""
    dimensions = [_dimension(phrase, text) for phrase in asked_phrases(text)]
    if None in dimensions:
        return ()
    return tuple(dict.fromkeys(dimension for dimension in dimensions if dimension is not None))


def result_reading(unit: str) -> tuple[str, float, float] | None:
    """(dimension, scale, offset) of a solver's result unit; None when unreadable."""
    from app.modules.physics.givens import unit_readings

    spelled = unit.strip()
    if not spelled or spelled == "%" or spelled.lower() in {"db", "decibel", "decibels"}:
        return _DIMENSIONLESS, 1.0, 0.0
    for reading in unit_readings(spelled):
        expression = reading.replace("·", "*").replace("^", "**")
        if expression in {"deg", "°"}:
            expression = "degree"
        if expression in {"D", "dioptre", "diopter", "dioptres", "diopters"}:
            expression = "1 / meter"
        if expression in {"Bq", "becquerel"}:
            # Pint counts decays; an activity is a rate, per second.
            expression = "1 / second"
        found = unit_dimension("radian" if expression == "rad" else expression)
        if found is not None:
            return found
    return None


def result_dimension(unit: str) -> str | None:
    """Dimension of a solver's result unit; None when it cannot be read."""
    reading = result_reading(unit)
    return None if reading is None else reading[0]


# "How much energy does it use in kWh?", "what is its speed in km/h".
_IN_UNIT = re.compile(r"\b(?:in|into)\s+(?:units?\s+of\s+)?", re.IGNORECASE)
_CLAUSE_END = re.compile(r"\s*(?:[?.!,;)]|$)")


def asked_unit(text: str) -> str | None:
    """The unit the question wants its answer in, as written; None when unsaid."""
    found: str | None = None
    for match in _IN_UNIT.finditer(text):
        unit = unit_at(text, match.end())
        if unit is None:
            continue
        end = match.end() + len(unit[0]) + (1 if text[match.end() : match.end() + 1] == " " else 0)
        if _CLAUSE_END.match(text, end):
            found = unit[0]
    return found
