"""Canonicalize complete numeric literals before heuristic physics extraction.

This is lexical normalization, not calculation: units and the user's stored
message stay unchanged. Refuse malformed or oversized tokens rather than let
an extractor consume a suffix (``.5`` as ``5``, or ``2e1`` as ``1``).
"""

from __future__ import annotations

import math
import re
from decimal import Decimal, InvalidOperation
from functools import lru_cache

from app.modules.physics.givens import ANGLE, unit_at, unit_dimension
from app.services.number_text import LITERAL_START, NUMERIC_LITERAL
from app.services.symbolic_text import _MAX_PHYSICS_REQUEST

_GROUPED_CANDIDATE = re.compile(r"(?<![\w.])[+-]?\d(?:[\d,]*\d)?(?:\.\d+)?(?:[eE][+-]?\d+)?")
_GROUPED_LITERAL = re.compile(r"[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?(?:[eE][+-]?\d+)?")
# Legacy keyword scanners inspect 40-character windows. Never expand a
# literal beyond that window and thereby make a prefix look like the value.
_MAX_LITERAL_CHARS = 36
_MAX_INPUT_CHARS = _MAX_PHYSICS_REQUEST


_UNIT_NORMALIZATIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"\b(?:met(?:er|re)s?|m)\s*(?:/|per)\s*(?:seconds?|secs?|s)\s+squared\b",
            re.IGNORECASE,
        ),
        "m/s^2",
    ),
    (
        re.compile(r"\bsquare\s+met(?:er|re)s?\b|\bm\s+squared\b", re.IGNORECASE),
        "m^2",
    ),
    (
        re.compile(r"\bcubic\s+met(?:er|re)s?\b|\bm\s+cubed\b", re.IGNORECASE),
        "m^3",
    ),
    (
        re.compile(r"\bmicrocoulombs?\b|(?<!\w)[µμ]C\b", re.IGNORECASE),
        "uC",
    ),
    # "left on for a whole week": one week, written as a number a law can bind.
    (
        re.compile(
            r"\bfor\s+(?:a|an|one)\s+(?:whole\s+|full\s+|entire\s+)?"
            r"(second|minute|hour|day|week|year)\b",
            re.IGNORECASE,
        ),
        r"for 1 \1",
    ),
    # "(v sound = 343 m/s)": the speed of sound, as the wave readers name it.
    (re.compile(r"\bv[ _]?sound\b", re.IGNORECASE), "speed of sound"),
    # "120 kph": the speed readers split a speed at its slash.
    (re.compile(r"(?<=\d)(\s*)(?:kph|kmph|kmh)\b", re.IGNORECASE), r"\1km/h"),
    # "9.8 m s-2", "m s^-2", "m·s⁻¹": a unit written as a product of powers, which
    # the readers know only with a slash. "ms" stays milliseconds.
    (re.compile(r"(?<=\d)(\s*)m(?:\s+|\s*[·*]\s*)s\s*(?:\^\s*-\s*2|-2|⁻²)(?!\d)"), r"\1m/s^2"),
    (re.compile(r"(?<=\d)(\s*)m(?:\s+|\s*[·*]\s*)s\s*(?:\^\s*-\s*1|-1|⁻¹)(?!\d)"), r"\1m/s"),
)


# A phone keyboard's spellings of the asked word: "accelaration?" asks what
# "acceleration?" asks. Only whole words a physics question uses, each mapped
# to the one word it can only be.
_SPELLING_NORMALIZATIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"\b(?:accelaration|accleration|accelration|acceleraton|accelleration"
            r"|acceleation|accerlation|acceration)\b",
            re.IGNORECASE,
        ),
        "acceleration",
    ),
    (
        re.compile(r"\b(?:acclerat|accelarat|accelerrat|accellerat)(es|ed|ing|e)\b", re.IGNORECASE),
        r"accelerat\1",
    ),
    (re.compile(r"\b(?:velocty|velcity|veloctiy|volocity)\b", re.IGNORECASE), "velocity"),
    # "whats the total distance?" asks as "what's" does.
    (re.compile(r"\b(w)hats\b", re.IGNORECASE), r"\1hat's"),
    # "2000 km above the earths surface" names Earth.
    (re.compile(r"\b(e)arths\b", re.IGNORECASE), r"\1arth's"),
)


# A school book's machine abbreviations, in capitals and only beside a machine, after
# "the", "its" or a part's letter: "the M.A of the machine", "b. MA", "a. VR". A small
# "mA" is a milliamp, "12 V. R = 6 ohm" a voltage and a resistance, "Boston, MA" a state.
_MACHINE = re.compile(
    r"\b(?:machines?|effort|levers?|pulleys?|planks?|ramps?|inclined\s+plane)\b",
    re.IGNORECASE,
)
_ABBREVIATION_LEAD = (
    r"(?:(?<=\bthe )|(?<=\bits )|(?<=\b[a-hA-H]\. )|(?<=\b[a-hA-H]\) )|(?<=\()|(?<=: )"
    r"|(?<=\bfind )|(?<=\bFind )|(?<=\bcalculate )|(?<=\bCalculate )|(?<=\bdetermine )"
    r"|(?<=\bDetermine )|(?<=^)|(?<=, )|(?<=\band ))"
)
# "MA = 5 kg" names block A's mass and "VR = 12 V" a voltage: a value assigned is a name.
_NOT_NAMED = r"(?!\s*=)"
_MACHINE_ABBREVIATIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    # "M.A." loses its last dot when the sentence goes on; "MA." keeps its full stop.
    (
        re.compile(rf"{_ABBREVIATION_LEAD}M\.A(?:\.(?=\s+[a-z]))?(?![\w.]){_NOT_NAMED}"),
        "mechanical advantage",
    ),
    (re.compile(rf"{_ABBREVIATION_LEAD}MA\b(?!\.\w){_NOT_NAMED}"), "mechanical advantage"),
    (
        re.compile(rf"{_ABBREVIATION_LEAD}V\.R(?:\.(?=\s+[a-z]))?(?![\w.]){_NOT_NAMED}"),
        "velocity ratio",
    ),
    (re.compile(rf"{_ABBREVIATION_LEAD}VR\b(?!\.\w){_NOT_NAMED}"), "velocity ratio"),
)
# "a 20 m plank": a length written before the thing it measures is that thing's length.
# ``\b(?<!\.)`` before a digit is the same test as ``(?<![\w.])``: the number starts here, not
# inside a word or after a point. CodeQL's ReDoS check reads ``\b`` as where a match starts;
# past the lookbehind it saw a run of digits read again from each digit.
_LENGTH_BEFORE_PLANK = re.compile(
    r"\b(?<!\.)(\d+(?:\.\d+)?\s*(?:m|cm|km|metres?|meters?))\s+(planks?|ramps?|slopes?|boards?)\b",
    re.IGNORECASE,
)


def quantity_unit_at(text: str, end: int) -> tuple[str, str] | None:
    """A unit of a quantity at ``end``: "one turn every 2 s" counts, it measures nothing."""
    unit = unit_at(text, end)
    return None if unit is None or unit[1] == "dimensionless" else unit


def normalize_physics_units(text: str) -> str:
    """Canonicalize common spoken unit spellings before cue detection.

    This is lexical only. It deliberately does not infer a unit that the user
    did not write; it makes equivalent written forms visible to the existing
    dimension-checked extractors and Pint conversion layer. A misspelt asked
    word ("accelaration") is read as the word it can only be.
    """
    from app.modules.physics.stated_equivalence import apply_stated_equivalence

    normalized = apply_stated_equivalence(text)
    for pattern, replacement in (*_UNIT_NORMALIZATIONS, *_SPELLING_NORMALIZATIONS):
        normalized = pattern.sub(replacement, normalized)
    if _MACHINE.search(normalized):
        for pattern, replacement in _MACHINE_ABBREVIATIONS:
            normalized = pattern.sub(replacement, normalized)
        normalized = _LENGTH_BEFORE_PLANK.sub(r"\1 long \2", normalized)
    return unit_names_as_symbols(normalized)


# A number, where a unit written after it may start.
_NUMBER_END = re.compile(r"\d(?![\d.])")
# A unit that goes on past its name ("metres per second", "joules/kg") is read whole by
# the table or not at all: its first word alone is not its symbol.
_UNIT_GOES_ON = re.compile(r"\s*(?:/|per\b|squared\b|cubed\b|\^)", re.IGNORECASE)


def unit_names_as_symbols(text: str) -> str:
    """A unit named in words after its number, written as its symbol: "30 Newtons" is 30 N.

    The givens scan reads every spelling the unit table lists, but each extractor reads the
    symbols its own pattern lists, so "a net force of 30 Newtons" had no force for F = ma and
    "100 grams" no mass for a density (phone test, 2026-11-11). The symbol is the table's
    own reading of the same unit. A kind every reader reads in words (``_READ_AS_WORDS``),
    a temperature scale and a name the table has no symbol for are left as written.
    """
    pieces: list[str] = []
    cursor = 0
    for number in _NUMBER_END.finditer(text):
        if number.end() <= cursor:
            continue
        unit = unit_at(text, number.end())
        symbol = _symbol_of_name(unit[0]) if unit is not None else None
        if symbol is None or unit is None:
            continue
        start = text.find(unit[0], number.end())
        end = start + len(unit[0])
        if _UNIT_GOES_ON.match(text, end):
            continue
        pieces.extend((text[cursor:start], symbol))
        cursor = end
    return "".join(pieces) + text[cursor:] if pieces else text


@lru_cache(maxsize=512)
def _symbol_of_name(spelling: str) -> str | None:
    """The symbol the unit table reads as the unit this one word names, or None."""
    from app.modules.physics.givens import PHYSICS_UNITS

    if not spelling.isalpha() or len(spelling) < 4:
        return None
    expression = PHYSICS_UNITS.word(spelling)
    reading = unit_dimension(expression) if expression is not None else None
    if (
        expression is None
        or reading is None
        or reading[0] in _READ_AS_WORDS
        or expression in _TEMPERATURE_SCALES
    ):
        return None
    symbols = [
        written
        for table in (PHYSICS_UNITS.symbols, PHYSICS_UNITS.words)
        for written, read in table.items()
        if read == expression and _is_symbol(written)
    ]
    # The shortest, and of two as short the one a keyboard types: "uC" before "µC".
    return min(symbols, key=lambda written: (len(written), not written.isascii()), default=None)


# Kinds every reader already reads in words, which stay as written: a length, a time and
# an angle ("20 metres", "5 seconds", "30 degrees"), a count ("500 turns", "20 percent").
# A temperature scale keeps its name too: "20 °c" is no spelling a reader expects.
_READ_AS_WORDS = frozenset({"[length]^1", "[time]^1", ANGLE, "dimensionless"})
_TEMPERATURE_SCALES = frozenset({"degC", "degF"})


def _is_symbol(written: str) -> bool:
    """A unit symbol: "N", "kg", "Hz", "Ω", "µF". A word, however short, is not one: "mol"
    is read as written by the readers that know it."""
    if not written.isascii():
        return True
    return len(written) <= 2 or not (written.isalpha() and written.islower())


# "only 1/16 of a sample": a fraction of something, whose denominator has only
# twos and fives, is an exact decimal. A date or a ratio is not followed by "of".
_FRACTION_OF = re.compile(r"(?<![\w./])(\d{1,3})\s*/\s*(\d{1,4})(?=\s+of\b)")


def _exact_fraction(match: re.Match[str]) -> str:
    numerator, denominator = int(match.group(1)), int(match.group(2))
    rest = denominator
    for factor in (2, 5):
        while rest > 1 and rest % factor == 0:
            rest //= factor
    if denominator == 0 or rest != 1 or numerator >= denominator:
        return match.group()
    return format(Decimal(numerator) / Decimal(denominator), "f")


def normalize_physics_numbers(text: str) -> str | None:
    """Return equivalent decimal spellings, or None for an unsafe token.

    Signed decimals, leading-dot decimals, and scientific notation are
    supported. Standard comma-grouped thousands are ungrouped before parsing;
    malformed separators, incomplete exponents, and repeated decimal points
    fail closed. Decimal bounds are checked before expansion so an exponent
    cannot allocate an unbounded string.
    """
    if len(text) > _MAX_INPUT_CHARS:
        return None
    text = normalize_physics_units(text).replace("\u2212", "-")
    text = _FRACTION_OF.sub(_exact_fraction, text)
    text = _GROUPED_CANDIDATE.sub(
        lambda match: (
            match.group().replace(",", "")
            if "," in match.group() and _GROUPED_LITERAL.fullmatch(match.group())
            else match.group()
        ),
        text,
    )
    if re.search(
        r"[A-Za-z_]\.\d|(?<!\w)[+-]{2,}(?=\d|\.\d)"
        r"|(?<!\w)[+-]\s+(?=\d|\.\d)|\d\s*/\s*[+-]?(?:\d|\.)",
        text,
    ):
        return None
    pieces: list[str] = []
    end = 0
    for start in LITERAL_START.finditer(text):
        if start.start() < end:
            continue
        match = NUMERIC_LITERAL.match(text, start.start())
        if match is None:
            return None
        token = match.group()
        tail = text[match.end() :]
        if re.match(r"(?:\.[.\d]|[,_]\d|[eE](?:[+\-\d]|\b))", tail):
            return None
        if len(token) > 128:
            return None
        try:
            value = Decimal(token)
            if not value.is_finite():
                return None
            number = float(value)
            # 1e1000000 overflows and 1e-1000000 underflows. A finite float
            # whose decimal spelling would be longer than a keyword window
            # stays scientific: refusing it dropped every law in the question.
            if not math.isfinite(number) or (value != 0 and number == 0):
                return None
            decimal = "0" if value.is_zero() else format(value, "f")
        except (InvalidOperation, ValueError, OverflowError):
            return None
        if "." in decimal:
            decimal = decimal.rstrip("0").rstrip(".")
        if decimal in {"-0", "+0"}:
            decimal = "0"
        if len(decimal) > _MAX_LITERAL_CHARS:
            decimal = format(value.normalize(), "e")
        if len(decimal) > _MAX_LITERAL_CHARS:
            return None
        pieces.extend((text[end : start.start()], decimal))
        end = match.end()
    pieces.append(text[end:])
    return "".join(pieces)
