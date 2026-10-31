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
import time
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from app.core.config import Settings
from app.models.routing_lanes import ROUTING
from app.modules.model_reader.checks import POWER, VALUE, plain_text, value_of
from app.services.law_binding.units import UnitTable, unit_dimension

logger = logging.getLogger(__name__)

_MAX_INPUT_CHARS = 1500

_PROMPT = """Translate a student's question into English, as an English textbook would write it.

- Copy every number exactly as written: the same digits, decimal places and powers of ten.
- Copy every unit symbol exactly (m, kg, s, N, mol/L, °C, …). A unit written as a word in
  the original language becomes its usual symbol right after its number.
- Keep every condition, negation ("not"), comparison and the exact question asked.
- Add nothing: no solution, no explanation, no number the question does not write.

Return JSON only: {"text": "<the English question>"}"""

TranslationReason = Literal["ok", "no_read", "numbers_changed", "units_changed", "failed"]


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
    number: float
    unit: str | None  # the Pint expression a table reads right after it
    word_after: bool  # a word in another script follows it instead


def _after(text: str, end: int) -> bool:
    """A word in a script other than Latin starts right after ``end`` (a unit as a word)."""
    rest = text[end:].lstrip()
    return bool(rest) and rest[0].isalpha() and not rest[0].isascii()


def _values(text: str, tables: Sequence[UnitTable]) -> list[_Value]:
    plain = plain_text(text)
    found: list[_Value] = []
    taken: list[tuple[int, int]] = []
    for power in POWER.finditer(plain):
        mantissa = value_of(power.group(1))
        if mantissa is not None:
            number = mantissa * 10 ** int(power.group(2))
            found.append(_Value(number, _unit_at(plain, power.end(), tables), False))
            taken.append(power.span())
    for value in VALUE.finditer(plain):
        if any(start <= value.start() < end for start, end in taken):
            continue
        number = value_of(value.group(0))
        if number is not None:
            unit = _unit_at(plain, value.end(), tables)
            found.append(_Value(number, unit, unit is None and _after(plain, value.end())))
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


def _carries(original: _Value, english: _Value) -> bool:
    """``english`` is ``original``: the same number, its unit at the same scale, or a unit
    word in another script now written as a symbol."""
    if not math.isclose(english.number, original.number, rel_tol=1e-12):
        return False
    if original.unit is not None:
        return english.unit is not None and _same_scale(original.unit, english.unit)
    return english.unit is None or original.word_after


def check_translation(
    original: str, english: str, tables: Sequence[UnitTable]
) -> TranslationReason:
    """``ok`` when ``english`` writes exactly the original's values, each with its unit."""
    before, after = _values(original, tables), _values(english, tables)
    if sorted(value.number for value in before) != sorted(value.number for value in after):
        return "numbers_changed"
    left = list(after)
    for value in sorted(before, key=lambda item: item.unit is None):
        match = next((other for other in left if _carries(value, other)), None)
        if match is None:
            return "units_changed"
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
