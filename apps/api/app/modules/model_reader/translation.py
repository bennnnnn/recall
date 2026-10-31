"""A question in another language put into English for the pattern readers, when the
English provably keeps its numbers, units and ask (docs/MODEL_READER.md, "translate, then
read with the patterns").

The English pattern readers read almost nothing in another language; a model can put the
question into English, but a translation may change a number, a unit, a sign or what is
asked. The server reads the original itself, with its language's notation and word tables
(``notation``, ``words``), and keeps the English only when:

- every original value is in it, with its sign, and nothing else is;
- each value's unit is the original's at the same scale: a unit word ("120 ሜትር") must come
  back as that unit, and a value followed by a word the tables do not know (a count, "5
  cars") must come back with no unit;
- it asks for the same kind of quantity, as far as the ask tables read the original.

That is all it guarantees. A translation may still drop a "not", an "each" or a "twice",
or swap two values' roles: a second translation by another model, read to the same solve,
is what catches those (``reader_eval``). Nothing here runs on a user's turn; a runtime path
must also check the spend cap before it calls a model.
"""

from __future__ import annotations

import math
import time
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from app.core.config import Settings
from app.models.routing_lanes import ROUTING
from app.modules.model_reader.notation import below_zero, written_values
from app.modules.model_reader.words import asked_kinds, unit_word_at
from app.services.law_binding.units import UnitTable, unit_dimension

_MAX_INPUT_CHARS = 1500

_PROMPT = """Translate a student's question into English, as an English textbook would write it.

- Keep every number's value, written the English way: a decimal point, no thousands dot
  (4,6 becomes 4.6; 1.200 meaning one thousand two hundred becomes 1200), the same
  decimal places and powers of ten, and its sign.
- Copy every unit symbol exactly (m, kg, s, N, mol/L, °C, …). A unit written as a word in
  the original language becomes its usual symbol right after its number.
- Keep every condition, negation ("not"), "each", comparison and the exact question asked.
- Add nothing: no solution, no explanation, no number the question does not write.

Return JSON only: {"text": "<the English question>"}"""

TranslationReason = Literal[
    "ok",
    "no_read",
    "original_unreadable",
    "numbers_not_english",
    "numbers_changed",
    "signs_changed",
    "units_changed",
    "ask_changed",
    "ask_unread",
]


_UNNAMED = frozenset({"unnamed"})
# How the ask is checked: "strict" also refuses an original whose ask the tables cannot read
# when the English asks for something; "lenient" lets it through; "off" skips the check.
AskCheck = Literal["strict", "lenient", "off"]


class _English(BaseModel):
    text: str = Field(max_length=3000)


@dataclass(frozen=True, slots=True)
class Translated:
    """The English the server kept, or why it kept none (``candidate`` is the model's)."""

    english: str | None
    reason: TranslationReason
    ms: float
    input_tokens: int = 0
    output_tokens: int = 0
    candidate: str | None = None


@dataclass(frozen=True, slots=True)
class _Value:
    value: float
    unit: str | None  # the Pint expression written after it; None for none or a count's noun


def _unit_at(
    text: str, end: int, tables: Sequence[UnitTable], language: str
) -> tuple[str | None, int]:
    """The unit written right after ``end`` and where it ends; the longer reading wins,
    as in a unit table ("°ሴ" is Celsius, not a degree)."""
    best: tuple[str | None, int] = (None, end)
    for table in tables:
        read = table.at(text, end)
        if read is not None:
            stop = text.index(read[0], end) + len(read[0])
            if stop > best[1]:
                best = (read[1], stop)
    word = unit_word_at(text, end, language)
    if word is not None and word[1] > best[1]:
        best = word
    return best


def _values(text: str, tables: Sequence[UnitTable], language: str) -> list[_Value] | None:
    read = written_values(text, language)
    if read is None:
        return None
    plain, written = read
    found: list[_Value] = []
    for item in written:
        unit, stop = _unit_at(plain, item.end, tables, language)
        value = -abs(item.value) if below_zero(plain, stop, language) else item.value
        found.append(_Value(value, unit))
    return found


def _same_scale(first: str, second: str) -> bool:
    one, two = unit_dimension(first), unit_dimension(second)
    return (
        one is not None
        and two is not None
        and one[0] == two[0]
        and math.isclose(one[1], two[1], rel_tol=1e-9)
        and math.isclose(one[2], two[2], abs_tol=1e-9)
    )


def _same(first: float, second: float) -> bool:
    return math.isclose(first, second, rel_tol=1e-9, abs_tol=1e-12)


def _carries(original: _Value, english: _Value) -> bool:
    """``english`` is ``original``: the same signed value, and its unit at its scale (or no
    unit, for a value with none or a count's noun)."""
    if not _same(original.value, english.value):
        return False
    if original.unit is None:
        return english.unit is None
    return english.unit is not None and _same_scale(original.unit, english.unit)


def _numbers_reason(before: list[_Value], after: list[_Value]) -> TranslationReason:
    if len(before) != len(after):
        return "numbers_changed"
    left = list(after)
    for value in sorted(before, key=lambda item: item.unit is None):
        match = next((other for other in left if _carries(value, other)), None)
        if match is None:
            if any(_same(value.value, other.value) for other in left):
                return "units_changed"
            if any(_same(abs(value.value), abs(other.value)) for other in left):
                return "signs_changed"
            return "numbers_changed"
        left.remove(match)
    return "ok"


def _ask_reason(original: str, english: str, language: str, ask: AskCheck) -> TranslationReason:
    """Each ask on either side could be one the other side makes: "how far" against "how
    long" is refused, Amharic "ፍጥነት" (a speed or an acceleration) against "acceleration"
    kept. An original whose ask the tables cannot read is ``ask_unread`` when the English
    asks for something (``strict``), since nothing shows the two are the same."""
    if ask == "off":
        return "ok"
    strict = ask == "strict"
    before, after = asked_kinds(original, language), asked_kinds(english, "en")
    if before is None or after is None or any(_UNNAMED & kinds for kinds in (*before, *after)):
        # "How much water": which quantity is a translator's choice the tables cannot check.
        return "ask_unread" if strict else "ok"
    if not before:
        return "ask_unread" if strict and after else "ok"
    either, other = frozenset().union(*before), frozenset().union(*after)
    if all(kinds & other for kinds in before) and all(kinds & either for kinds in after):
        return "ok"
    return "ask_changed"


def check_translation(
    original: str,
    english: str,
    tables: Sequence[UnitTable],
    language: str,
    *,
    ask: AskCheck = "strict",
) -> TranslationReason:
    """``ok`` when ``english`` writes exactly the original's signed values, each with its
    unit, and asks for the same kind of quantity."""
    before = _values(original, tables, language)
    if before is None:
        return "original_unreadable"
    after = _values(english, tables, "en")
    if after is None:
        return "numbers_not_english"
    reason = _numbers_reason(before, after)
    if reason != "ok":
        return reason
    return _ask_reason(original, english, language, ask)


async def english_for_patterns(
    text: str,
    settings: Settings,
    tables: Sequence[UnitTable],
    language: str,
    *,
    model_alias: str = ROUTING.reader_translation,
) -> Translated:
    """The question in English, checked. ``complete_structured`` never raises: a failed
    call is no translation."""
    from app.gateways.structured_completion import complete_structured

    started = time.perf_counter()
    usage: dict[str, int] = {}
    question = unicodedata.normalize("NFC", text.strip())[:_MAX_INPUT_CHARS]
    reply = await complete_structured(
        settings=settings,
        model_alias=model_alias,
        messages=[{"role": "system", "content": _PROMPT}, {"role": "user", "content": question}],
        schema=_English,
        max_tokens=800,
        timeout_seconds=settings.model_reader_timeout_seconds,
        usage=usage,
        allow_fallback=False,
        quiet_timeout=True,
    )
    candidate = reply.text.strip() if reply is not None else ""
    reason: TranslationReason = (
        check_translation(question, candidate, tables, language) if candidate else "no_read"
    )
    return Translated(
        candidate if reason == "ok" else None,
        reason,
        round((time.perf_counter() - started) * 1000, 1),
        int(usage.get("input", 0)),
        int(usage.get("output", 0)),
        candidate or None,
    )
