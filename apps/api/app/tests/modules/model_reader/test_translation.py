"""A translation is kept only when it keeps the original's signed values, each with its
unit at its scale, nothing new, and the kind of quantity asked (docs/MODEL_READER.md).

The original is read by the server in its own language's notation and word tables; the
English strictly in English notation. The probes are the review's (PR #2171): each wrong
translation it found accepted, and each faithful one it found refused.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from app.core.config import Settings
from app.gateways import structured_completion
from app.modules.chemistry.given_units import CHEMISTRY_UNITS
from app.modules.model_reader.checks import readings
from app.modules.model_reader.notation import NOTATIONS, number_value, written_values
from app.modules.model_reader.translation import check_translation, english_for_patterns
from app.modules.model_reader.words import asked_kinds
from app.modules.physics import PHYSICS_UNITS

_TABLES = (PHYSICS_UNITS, CHEMISTRY_UNITS)
_MINUS = chr(0x2212)
_TIMES = chr(0x00D7)


@pytest.mark.parametrize(
    ("language", "original", "english"),
    [
        # A unit word in another script, or in Spanish, comes back as its symbol.
        ("am", "መኪና በ8 ሰከንድ ውስጥ 120 ሜትር ተጓዘ።", "A car travels 120 m in 8 s."),
        ("es", "Un coche recorre 120 metros en 8 segundos.", "A car travels 120 m in 8 s."),
        ("es", "¿Cuál es el pH de HCl 0,01 M?", "What is the pH of 0.01 M HCl?"),
        ("ar", "٣٫٥ كغ من الماء", "3.5 kg of water"),
        ("ar", "سيارة كتلتها ١٬٢٠٠ كغ", "A car of mass 1200 kg"),
        ("es", f"La luz viaja a 3 {_TIMES} 10⁸ m/s.", f"Light travels at 3 {_TIMES} 10^8 m/s."),
        ("es", "Una masa de 4,6 g", "A mass of 4.6 g"),
        # Thousands with a space, Ethiopic numerals, a sign in words or as a minus sign.
        ("fr", "Une voiture parcourt 1 200 m en 60 s.", "A car travels 1200 m in 60 s."),
        ("am", "መኪና ፪፻ ሜትር ተጓዘ።", "A car travelled 200 m."),
        ("am", "፲፪ ኪሎግራም", "12 kg"),
        ("es", "El agua pasa de 5 °C bajo cero a 30 °C.", "Water goes from -5 °C to 30 °C."),
        ("fr", f"L'eau passe de {_MINUS}20 °C à 30 °C.", "Water goes from -20 °C to 30 °C."),
        # A count keeps no unit; a percent and an "each" read the same.
        ("es", "Cada caja pesa 5 kg; hay 4 cajas.", "Each box weighs 5 kg; there are 4 boxes."),
        ("es", "¿Cuánto es el 25 % de 80?", "What is 25 percent of 80?"),
    ],
)
def test_a_faithful_translation_is_kept(language: str, original: str, english: str) -> None:
    assert check_translation(original, english, _TABLES, language) == "ok"


@pytest.mark.parametrize(
    ("language", "original", "english", "reason"),
    [
        # A unit word read as another unit, or a unit where the original has a count.
        ("am", "በ4 ሰከንድ 120 ሴንቲሜትር ተጓዘ።", "It travels 120 m in 4 s.", "units_changed"),
        ("ar", "جسم كتلته ٥٠٠ غرام", "A body of mass 500 kg", "units_changed"),
        (
            "hi",
            "एक गेंद 20 मिलीसेकंड में 10 मीटर चलती है।",
            "A ball moves 10 m in 20 s.",
            "units_changed",
        ),
        (
            "hi",
            "एक कार 3 किलोमीटर 120 सेकंड में चलती है।",
            "A car travels 3 m in 120 s.",
            "units_changed",
        ),
        (
            "es",
            "Un coche recorre 3 kilómetros en 120 s.",
            "A car travels 3 m in 120 s.",
            "units_changed",
        ),
        ("am", "5 መኪኖች 1200 kg ናቸው።", "5 kg cars have 1200 kg.", "units_changed"),
        ("fr", "5 élèves portent chacun 2 kg.", "5 kg students each carry 2 kg.", "units_changed"),
        # A decimal comma copied or read away; a number its language writes two ways.
        (
            "es",
            "¿Cuántos gramos hay en 0,125 mol?",
            "How many grams are in 0,125 mol?",
            "numbers_not_english",
        ),
        ("fr", "0,5 mol dans 2,500 L", "0.5 mol in 2,500 L", "numbers_changed"),
        ("es", "Una masa de 3,5 kg cae.", "A mass of 35 kg falls.", "numbers_changed"),
        ("es", "Un objeto de 1.5 kg.", "A 15 kg object.", "numbers_changed"),
        ("ar", "سيارة كتلتها ١٬٢٠٠ كغ", "A car of mass 1.2 kg", "numbers_changed"),
        ("es", "Un coche de 1.200 kg.", "A 1200 kg car.", "original_unreadable"),
        ("fr", "Une voiture parcourt 1 200 m.", "A car travels 1 200 m.", "numbers_changed"),
        ("am", "መኪና ፪፻ ሜትር ተጓዘ።", "A car travelled 2 m.", "numbers_changed"),
        # A sign dropped, as a minus sign or as words.
        (
            "fr",
            f"L'eau passe de {_MINUS}20 °C à 30 °C.",
            "Water goes from 20 °C to 30 °C.",
            "signs_changed",
        ),
        (
            "es",
            "El agua pasa de 5 °C bajo cero a 30 °C.",
            "Water goes from 5 °C to 30 °C.",
            "signs_changed",
        ),
        # Another kind of quantity asked: "how far" became "how long".
        (
            "es",
            "Un avión a 70 m/s suelta un paquete desde 200 m. ¿Qué distancia recorre el paquete?",
            "A plane at 70 m/s drops a package from 200 m. How long does the package fall?",
            "ask_changed",
        ),
    ],
)
def test_a_changed_translation_is_refused(
    language: str, original: str, english: str, reason: str
) -> None:
    assert check_translation(original, english, _TABLES, language) == reason


@pytest.mark.parametrize(
    ("language", "token", "value"),
    [
        ("es", "3,5", 3.5),
        ("es", "1.5", 1.5),
        ("es", "1.200,5", 1200.5),
        ("es", "1,200.5", 1200.5),
        ("es", "1.200", None),
        ("es", "0,125", 0.125),
        ("fr", "2,500", 2.5),
        ("fr", "1.200", 1200.0),
        ("en", "2,500", 2500.0),
        ("en", "0,125", None),
        ("en", "3,5", None),
        ("hi", "1,20,000", 120000.0),
        ("ar", "1,5", 1.5),
    ],
)
def test_a_number_has_one_value_in_its_language(
    language: str, token: str, value: float | None
) -> None:
    assert number_value(token, NOTATIONS[language]) == value


def test_written_values_read_signs_powers_and_names() -> None:
    read = written_values(f"x-5 = 3, {_MINUS}5 °C, 1.8 x 10⁻⁵ and H2O", "en")
    assert read is not None
    assert [item.value for item in read[1]] == [5.0, 3.0, -5.0, 1.8e-05]


@pytest.mark.parametrize(
    ("number", "values"),
    [("3,5", {3.5}), ("1.5", {1.5}), ("1.200", {1.2, 1200.0}), ("0,125", {0.125})],
)
def test_a_mark_is_dropped_only_before_three_digits(number: str, values: set[float]) -> None:
    assert readings(number) == values


@pytest.mark.parametrize(
    ("language", "text", "kinds"),
    [
        ("en", "How long does it take for the package to fall?", {"time"}),
        ("en", "How far does the package travel?", {"length"}),
        ("en", "Work out the speed of the car.", {"speed"}),
        ("en", "What is the kinetic energy of a body of mass 2 kg moving at 3 m/s?", {"energy"}),
        ("en", "What mass of salt is in 2 moles?", {"mass"}),
        ("en", "What is 25% of 80?", set()),
        # Amharic "ፍጥነት" names a speed and an acceleration ("ፍጥነቱ በ m/s²").
        ("am", "ፍጥነቱ ስንት ነው?", {"speed", "acceleration"}),
        ("am", "36 ግራም ውሃ ለመሥራት ስንት ግራም H2 መቃጠል አለበት?", {"mass"}),
        ("en", "If the temperature stays constant, how many liters does it fill?", {"volume"}),
        ("es", "¿Dos resistencias de 10 ohmios en paralelo a 5 V, corriente total?", {"current"}),
        ("es", "área de un círculo con radio 7 cm", {"area"}),
        ("en", "What is the molar mass of sodium chloride?", {"molar_mass"}),
        ("hi", "गतिज ऊर्जा कितनी है?", {"energy"}),
        ("es", "¿Qué distancia recorre?", {"length"}),
    ],
)
def test_the_kind_asked_is_named_beside_an_ask_word(
    language: str, text: str, kinds: set[str]
) -> None:
    asked = asked_kinds(text, language)
    assert asked is not None
    assert frozenset().union(*asked) == kinds


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
    translated = await english_for_patterns(
        "Un coche recorre 120 m en 8 s.", Settings(), _TABLES, "es"
    )
    assert translated.reason == reason
    assert (translated.english is not None) is kept
    assert translated.candidate == english
    assert translated.input_tokens == 50
