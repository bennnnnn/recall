"""A translation is kept only when it is the same question: every value, each with its
unit at its scale, and nothing new (docs/MODEL_READER.md)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from app.core.config import Settings
from app.gateways import structured_completion
from app.modules.chemistry.given_units import CHEMISTRY_UNITS
from app.modules.model_reader.translation import check_translation, english_for_patterns
from app.modules.physics import PHYSICS_UNITS

_TABLES = (PHYSICS_UNITS, CHEMISTRY_UNITS)


@pytest.mark.parametrize(
    ("original", "english", "reason"),
    [
        # A unit as a word in another script comes back as its symbol.
        ("መኪና በ8 ሰከንድ ውስጥ 120 ሜትር ተጓዘ።", "A car travels 120 m in 8 s.", "ok"),
        ("¿Cuál es el pH de HCl 0,01 M?", "What is the pH of 0.01 M HCl?", "ok"),
        ("٣٫٥ كغ من الماء", "3.5 kg of water", "ok"),
        ("La luz viaja a 3 × 10⁸ m/s.", "Light travels at 3 × 10^8 m/s.", "ok"),
        ("Un coche recorre 3,000 m.", "A car travels 3000 m.", "ok"),
        # A unit at another scale, a changed or added number, a unit from nowhere.
        ("Un coche recorre 120 m en 8 s.", "A car travels 120 cm in 8 s.", "units_changed"),
        ("Un coche recorre 120 m en 8 s.", "A car travels 120 m in 9 s.", "numbers_changed"),
        ("Un coche recorre 120 m.", "A car travels 120 m in 8 s.", "numbers_changed"),
        ("Hay 5 coches.", "There are 5 kg of cars.", "units_changed"),
    ],
)
def test_a_translation_must_carry_every_value_and_unit(
    original: str, english: str, reason: str
) -> None:
    assert check_translation(original, english, _TABLES) == reason


def _reply(text: str | None) -> Any:
    async def complete_structured(**kwargs: Any) -> BaseModel | None:
        kwargs["usage"]["input"] = 50
        return None if text is None else kwargs["schema"](text=text)

    return complete_structured


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("english", "kept", "reason"),
    [
        ("A car travels 120 m in 8 s.", True, "ok"),
        ("A car travels 120 m in 9 s.", False, "numbers_changed"),
        (None, False, "no_read"),
    ],
)
async def test_english_is_kept_only_when_it_checks(
    monkeypatch: pytest.MonkeyPatch, english: str | None, kept: bool, reason: str
) -> None:
    monkeypatch.setattr(structured_completion, "complete_structured", _reply(english))
    translated = await english_for_patterns("Un coche recorre 120 m en 8 s.", Settings(), _TABLES)
    assert translated.reason == reason
    assert (translated.english is not None) is kept
    assert translated.input_tokens == 50
