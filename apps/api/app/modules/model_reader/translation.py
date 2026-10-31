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
from app.modules.model_reader.tokens import UNREAD, Quantity, Tokens, read_tokens
from app.modules.model_reader.words import Asked, asked_kinds
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
    "formulas_changed",
    "operators_changed",
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


def _carries(original: Quantity, english: Quantity) -> bool:
    """``english`` is ``original``: the same signed value, and its whole unit at its scale
    (or no unit, for a value with none or a count's noun)."""
    if not _same(original.value, english.value) or UNREAD in (original.unit, english.unit):
        return False
    if original.unit is None:
        return english.unit is None
    return english.unit is not None and _same_scale(original.unit, english.unit)


def _numbers_reason(before: Sequence[Quantity], after: Sequence[Quantity]) -> TranslationReason:
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


def _tokens_reason(before: Tokens, after: Tokens) -> TranslationReason:
    reason = _numbers_reason(before.quantities, after.quantities)
    if reason != "ok":
        return reason
    if before.formulas != after.formulas:
        return "formulas_changed"
    if before.operators != after.operators or before.powers != after.powers:
        return "operators_changed"
    return "ok"


def _ask_reason(original: str, english: str, language: str, ask: AskCheck) -> TranslationReason:
    """Each ask on either side is one the other side makes: a kind in common and the same
    qualifiers. "How far" against "how long", or "rapidez media" (average speed) against
    "final speed", is refused; Amharic "ፍጥነት" (a speed or an acceleration) against
    "acceleration" kept. An original whose ask the tables cannot read is ``ask_unread`` when
    the English asks for something (``strict``), since nothing shows the two are the same."""
    if ask == "off":
        return "ok"
    strict = ask == "strict"
    before, after = asked_kinds(original, language), asked_kinds(english, "en")
    if (
        before is None
        or after is None
        or any(_UNNAMED & asked.kinds for asked in (*before, *after))
    ):
        # "How much water": which quantity is a translator's choice the tables cannot check.
        return "ask_unread" if strict else "ok"
    if not before:
        return "ask_unread" if strict and after else "ok"

    def met(asked: Asked, others: tuple[Asked, ...]) -> bool:
        return any(
            asked.kinds & other.kinds and asked.qualifiers == other.qualifiers for other in others
        )

    if all(met(asked, after) for asked in before) and all(met(asked, before) for asked in after):
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
    before = read_tokens(original, tables, language)
    if before is None:
        return "original_unreadable"
    after = read_tokens(english, tables, "en")
    if after is None:
        return "numbers_not_english"
    reason = _tokens_reason(before, after)
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
