"""A question in another language put into English for the pattern readers, if it is
the same question (docs/MODEL_READER.md, "translate, then read with the patterns").

The English pattern readers read almost nothing in another language; a model can put the
question into English, but a translation may change a number, a unit or a scale. So the
server keeps a translation only when every value the original writes is in it, nothing
else is, and every unit the original writes after a value (as a subject's unit table reads
it) is there at the same scale. A unit written as a word in another script ("120 ሜትር")
may come back as its symbol ("120 m"); a unit appearing from nowhere may not.
"""

from __future__ import annotations

import logging
import math
import re
import time
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from app.core.config import Settings
from app.models.routing_lanes import ROUTING
from app.modules.model_reader.checks import POWER, VALUE, plain_text, readings
from app.services.law_binding.units import UnitTable, unit_dimension

logger = logging.getLogger(__name__)

_MAX_INPUT_CHARS = 1500

_PROMPT = """Translate a student's question into English, as an English textbook would write it.

- Keep every number's value, written the English way: a decimal point, no thousands dot
  (4,6 becomes 4.6; 1.200 meaning one thousand two hundred becomes 1200), the same
  decimal places and powers of ten.
- Copy every unit symbol exactly (m, kg, s, N, mol/L, °C, …). A unit written as a word in
  the original language becomes its usual symbol right after its number.
- Keep every condition, negation ("not"), comparison and the exact question asked.
- Add nothing: no solution, no explanation, no number the question does not write.

Return JSON only: {"text": "<the English question>"}"""

TranslationReason = Literal[
    "ok", "no_read", "numbers_not_english", "numbers_changed", "units_changed", "failed"
]


class _English(BaseModel):
    text: str = Field(max_length=3000)


@dataclass(frozen=True, slots=True)
class Translated:
    """The English the server kept, or why it kept none."""

    english: str | None
    reason: TranslationReason
    ms: float
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True, slots=True)
class _Value:
    readings: frozenset[float]  # what the written number may mean ("1.200": 1.2 or 1200)
    dotted: bool  # written "1.200": a thousands dot or three decimals, by language
    unit: str | None  # the Pint expression a table reads right after it
    word_after: bool  # a word in another script follows it instead


# A number written the English way: "4.6", "1,200", "1200", ".5". Not "4,6".
_ENGLISH_NUMBER = re.compile(r"-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|-?\.\d+")
_DOTTED = re.compile(r"-?\d{1,3}\.\d{3}")


def _after(text: str, end: int) -> bool:
    """A word in a script other than Latin starts right after ``end`` (a unit as a word)."""
    rest = text[end:].lstrip()
    return bool(rest) and rest[0].isalpha() and not rest[0].isascii()


def _values(text: str, tables: Sequence[UnitTable], *, english: bool) -> list[_Value] | None:
    """Each value ``text`` writes; None when English text writes one another way."""
    plain = plain_text(text)
    found: list[_Value] = []
    taken: list[tuple[int, int]] = []
    for power in POWER.finditer(plain):
        mantissas = readings(power.group(1))
        if english and not _ENGLISH_NUMBER.fullmatch(power.group(1)):
            return None
        scale = 10 ** int(power.group(2))
        unit = _unit_at(plain, power.end(), tables)
        found.append(_Value(frozenset(m * scale for m in mantissas), False, unit, False))
        taken.append(power.span())
    for value in VALUE.finditer(plain):
        if any(start <= value.start() < end for start, end in taken):
            continue
        token = value.group(0)
        if english and not _ENGLISH_NUMBER.fullmatch(token):
            return None
        meant = (
            frozenset({float(token.replace(",", ""))}) if english else frozenset(readings(token))
        )
        unit = _unit_at(plain, value.end(), tables)
        word = unit is None and _after(plain, value.end())
        found.append(_Value(frozenset(meant), bool(_DOTTED.fullmatch(token)), unit, word))
    return found


def _unit_at(text: str, end: int, tables: Sequence[UnitTable]) -> str | None:
    for table in tables:
        read = table.at(text, end)
        if read is not None:
            return read[1]
    return None


def _same_scale(first: str, second: str) -> bool:
    one, two = unit_dimension(first), unit_dimension(second)
    return (
        one is not None
        and two is not None
        and one[0] == two[0]
        and math.isclose(one[1], two[1], rel_tol=1e-9)
        and math.isclose(one[2], two[2], abs_tol=1e-9)
    )


def _same_number(original: _Value, english: _Value) -> bool:
    """A value the original may mean, written so an English reader reads that value:
    "1.200" from a language with thousands dots comes back as 1200 or 1.2, never "1.200"."""
    return english.readings <= original.readings and not (original.dotted and english.dotted)


def _carries(original: _Value, english: _Value) -> bool:
    """``english`` is ``original``: the same number, its unit at the same scale, or a unit
    word in another script now written as a symbol."""
    if not _same_number(original, english):
        return False
    if original.unit is not None:
        return english.unit is not None and _same_scale(original.unit, english.unit)
    return english.unit is None or original.word_after


def check_translation(
    original: str, english: str, tables: Sequence[UnitTable]
) -> TranslationReason:
    """``ok`` when ``english`` writes exactly the original's values, each with its unit."""
    before = _values(original, tables, english=False) or []
    after = _values(english, tables, english=True)
    if after is None:
        return "numbers_not_english"
    if len(before) != len(after):
        return "numbers_changed"
    left = list(after)
    for value in sorted(before, key=lambda item: item.unit is None):
        match = next((other for other in left if _carries(value, other)), None)
        if match is None:
            same = any(_same_number(value, other) for other in left)
            return "units_changed" if same else "numbers_changed"
        left.remove(match)
    return "ok"


async def english_for_patterns(
    text: str, settings: Settings, tables: Sequence[UnitTable]
) -> Translated:
    """The question in English, checked; never raises."""
    from app.gateways.structured_completion import complete_structured

    started = time.perf_counter()
    usage: dict[str, int] = {}

    def done(english: str | None, reason: TranslationReason) -> Translated:
        elapsed = round((time.perf_counter() - started) * 1000, 1)
        return Translated(
            english, reason, elapsed, int(usage.get("input", 0)), int(usage.get("output", 0))
        )

    question = unicodedata.normalize("NFC", text.strip())[:_MAX_INPUT_CHARS]
    try:
        reply = await complete_structured(
            settings=settings,
            model_alias=ROUTING.reader_translation,
            messages=[
                {"role": "system", "content": _PROMPT},
                {"role": "user", "content": question},
            ],
            schema=_English,
            max_tokens=800,
            timeout_seconds=settings.model_reader_timeout_seconds,
            usage=usage,
            allow_fallback=False,
            quiet_timeout=True,
        )
    except Exception as exc:
        logger.info("translation for the patterns failed (%s)", type(exc).__name__)
        return done(None, "failed")
    if reply is None or not reply.text.strip():
        return done(None, "no_read")
    checked = check_translation(question, reply.text, tables)
    return done(reply.text if checked == "ok" else None, checked)
