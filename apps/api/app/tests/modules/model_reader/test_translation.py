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
    assert frozenset().union(*(ask.kinds for ask in asked)) == kinds


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


# The second review's probes (PR #2171): (id, language, original, English, reason).
ROUND_TWO: list[tuple[str, str, str, str, str]] = [
    (
        "fr-kilometres-noaccent",
        "fr",
        "Une voiture roule 3 kilometres en 2 heures. Quelle est sa vitesse ?",
        "A car travels 3 km in 2 h. What is its speed?",
        "ok",
    ),
    (
        "es-kms-plural-abbr",
        "es",
        "Un ciclista recorre 15 kms en 1 hora. ¿Cuál es su rapidez?",
        "A cyclist travels 15 km in 1 h. What is its speed?",
        "ok",
    ),
    (
        "es-km-por-hora-good",
        "es",
        "Un coche va a 72 km por hora durante 2 h. ¿Qué distancia recorre?",
        "A car moves at 72 km/h for 2 h. What distance does it travel?",
        "ok",
    ),
    (
        "es-km-por-hora-dropped",
        "es",
        "Un coche va a 72 km por hora durante 2 h. ¿Qué distancia recorre?",
        "A car moves 72 km for 2 h. What distance does it travel?",
        "units_changed",
    ),
    (
        "ar-mm-double-lam",
        "ar",
        "قطر سلك ٢ ملليمتر. ما مساحة مقطعه؟",
        "A wire has a diameter of 2 mm. What is its cross-sectional area?",
        "ok",
    ),
    (
        "hi-km-dotted-abbr",
        "hi",
        "एक बस 120 कि.मी. 2 घंटे में चलती है। उसकी चाल क्या है?",
        "A bus travels 120 km in 2 h. What is its speed?",
        "ok",
    ),
    (
        "am-metres-plural",
        "am",
        "አንድ ልጅ 100 ሜትሮችን በ20 ሰከንድ ሮጠ። ፍጥነቱ ስንት ነው?",
        "A child ran 100 m in 20 s. What is his speed?",
        "ok",
    ),
    (
        "ar-ms2-digit-2",
        "ar",
        "يتسارع جسم بمقدار ٤ م/ث٢ لمدة ٥ ث. ما سرعته النهائية إذا بدأ من السكون؟",
        "A body accelerates at 4 m/s² for 5 s. What is its final speed if it starts from rest?",
        "ok",
    ),
    (
        "ar-g-per-mol-good",
        "ar",
        "الكتلة المولية للماء ١٨ غ/مول. كم مولًا في ٣٦ غ من الماء؟",
        "The molar mass of water is 18 g/mol. How many moles are in 36 g of water?",
        "ok",
    ),
    (
        "ar-g-per-mol-dropped",
        "ar",
        "الكتلة المولية للماء ١٨ غ/مول. كم مولًا في ٣٦ غ من الماء؟",
        "The mass of water is 18 g. How many moles are in 36 g of water?",
        "units_changed",
    ),
    (
        "ar-mol-per-L-dropped",
        "ar",
        "محلول تركيزه ٠٫٥ مول/لتر حجمه ٢ لتر. كم عدد المولات؟",
        "A solution of 0.5 mol has a volume of 2 L. How many moles are there?",
        "units_changed",
    ),
    (
        "es-molL-as-M",
        "es",
        "¿Cuántos moles hay en 2 L de una disolución 0,5 mol/L?",
        "How many moles are in 2 L of a 0.5 M solution?",
        "ok",
    ),
    (
        "fr-kWh-as-kW",
        "fr",
        "Un radiateur consomme 3 kWh en 2 h. Quelle est sa puissance ?",
        "A heater uses 3 kW in 2 h. What is its power?",
        "units_changed",
    ),
    (
        "hi-ms2",
        "hi",
        "एक कार 3 मी/से² के त्वरण से 4 सेकंड चलती है। अंतिम वेग क्या है?",
        "A car accelerates at 3 m/s² for 4 s. What is its final velocity?",
        "ok",
    ),
    ("es-por-ciento", "es", "¿Cuánto es el 25 por ciento de 80?", "What is 25% of 80?", "ok"),
    (
        "hi-pratishat",
        "hi",
        "एक मशीन की दक्षता 80 प्रतिशत है और निवेश 500 जूल है। निर्गत ऊर्जा कितनी है?",
        "A machine has an efficiency of 80% and an input of 500 J. What is the output energy?",
        "ok",
    ),
    ("ar-arabic-percent", "ar", "ما هو ١٥٪ من ٢٠٠؟", "What is 15% of 200?", "ok"),
    (
        "es-percent-dropped",
        "es",
        "Un precio de 200 sube un 20 %. ¿Cuál es el nuevo precio?",
        "A price of 200 rises by 20. What is the new price?",
        "units_changed",
    ),
    (
        "es-medio-km",
        "es",
        "Un ciclista recorre medio kilómetro en 50 s. ¿Cuál es su rapidez?",
        "A cyclist covers 0.5 km in 50 s. What is its speed?",
        "ok",
    ),
    (
        "es-tercio-as-half",
        "es",
        "¿Cuánto es un tercio de 90?",
        "What is half of 90?",
        "numbers_changed",
    ),
    (
        "hi-aadha-as-quarter",
        "hi",
        "एक टंकी में 40 लीटर पानी है। आधा पानी निकाल दिया गया। कितना पानी बचा?",
        "A tank holds 40 L of water. A quarter of the water is removed. How much water is left?",
        "numbers_changed",
    ),
    (
        "es-mil-as-million",
        "es",
        "La luz recorre 300 mil kilómetros en un segundo. ¿Cuál es su rapidez?",
        "Light travels 300 million km in one second. What is its speed?",
        "numbers_changed",
    ),
    (
        "hi-hazaar-as-million",
        "hi",
        "एक रॉकेट 3 हज़ार मीटर ऊपर जाता है। कितना समय लगेगा यदि चाल 100 मी/से है?",
        "A rocket rises 3 million metres. How long does it take if its speed is 100 m/s?",
        "numbers_changed",
    ),
    (
        "hi-devanagari-digits",
        "hi",
        "एक कार १२० किमी २ घंटे में चलती है। उसकी चाल क्या है?",
        "A car travels 120 km in 2 h. What is its speed?",
        "ok",
    ),
    (
        "am-latin-units",
        "am",
        "መኪናው በ20 m/s ለ5 ሰከንድ ተጓዘ። ርቀቱ ስንት ነው?",
        "The car travels at 20 m/s for 5 s. What is the distance?",
        "ok",
    ),
    (
        "es-5km-nospace",
        "es",
        "Un corredor recorre 5km en 25 min. ¿Cuál es su rapidez?",
        "A runner covers 5 km in 25 min. What is its speed?",
        "ok",
    ),
    (
        "es-H2SO4-good",
        "es",
        "¿Cuántos gramos hay en 2 mol de H2SO4?",
        "How many grams are in 2 mol of H2SO4?",
        "ok",
    ),
    (
        "es-glucose-swapped",
        "es",
        "¿Cuál es la masa de 2 mol de C6H12O6?",
        "What is the mass of 2 mol of C6H6?",
        "formulas_changed",
    ),
    (
        "fr-H2O2-as-H2O",
        "fr",
        "Quelle est la masse de 3 mol de H2O2 ?",
        "What is the mass of 3 mol of H2O?",
        "formulas_changed",
    ),
    (
        "fr-CaOH2-subscript",
        "fr",
        "Quelle masse de Ca(OH)2 faut-il pour 0,5 L d'une solution 0,1 M ?",
        "What mass of Ca(OH)₂ is needed for 0.5 L of a 0.1 M solution?",
        "ok",
    ),
    (
        "es-equation-coefs",
        "es",
        "Según 2H2 + O2 → 2H2O, ¿cuántos moles de agua se forman con 4 mol de H2?",
        "According to 2H2 + O2 → 2H2O, how many moles of water form from 4 mol of H2?",
        "ok",
    ),
    (
        "fr-exercise-number",
        "fr",
        "Exercice 2.15 : Une voiture de 1 000 kg roule à 20 m/s. Quelle est son énergie cinétique ?",
        "Exercise 2.15: A 1000 kg car moves at 20 m/s. What is its kinetic energy?",
        "ok",
    ),
    (
        "es-year",
        "es",
        "En 2023, un tren recorrió 150 km en 2 h. ¿Cuál fue su rapidez?",
        "In 2023, a train travelled 150 km in 2 h. What was its speed?",
        "ok",
    ),
    (
        "es-range-spaced-dash",
        "es",
        "La temperatura del agua sube de 5 a 10 °C. ¿Cuánto calor absorben 2 kg?",
        "The water temperature rises 5 – 10 °C. How much heat do 2 kg absorb?",
        "ok",
    ),
    (
        "fr-range-endash",
        "fr",
        "Un ressort s'allonge de 5–10 cm. Quelle est la variation de longueur ?",
        "A spring stretches from 5–10 cm. What is the change in length?",
        "ok",
    ),
    ("es-minus-to-plus", "es", "¿Cuánto es 8−3?", "What is 8+3?", "operators_changed"),
    (
        "es-square-to-cube",
        "es",
        "Resuelve x² − 5x + 6 = 0",
        "Solve x³ − 5x + 6 = 0",
        "operators_changed",
    ),
    (
        "fr-power-ten-changed",
        "fr",
        "Une onde a une fréquence de 5 × 10¹⁴ Hz. Quelle est sa longueur d'onde ?",
        "A wave has a frequency of 5 × 10¹² Hz. What is its wavelength?",
        "numbers_changed",
    ),
    (
        "es-time-as-distance",
        "es",
        "Un coche va a 20 m/s y recorre 400 m. ¿Cuánto tiempo tarda?",
        "A car goes at 20 m/s and travels 400 m. What distance does it cover?",
        "ask_changed",
    ),
    (
        "es-time-good",
        "es",
        "Un coche va a 20 m/s y recorre 400 m. ¿Cuánto tiempo tarda?",
        "A car goes at 20 m/s and travels 400 m. How long does it take?",
        "ok",
    ),
    (
        "fr-distance-as-time",
        "fr",
        "Un train roule à 30 m/s pendant 60 s. Quelle distance parcourt-il ?",
        "A train moves at 30 m/s for 60 s. How long does it take?",
        "ask_changed",
    ),
    (
        "ar-time-as-distance",
        "ar",
        "تتحرك سيارة بسرعة ٢٥ م/ث لمسافة ٥٠٠ م. كم من الوقت تستغرق؟",
        "A car moves at 25 m/s over 500 m. How far does it go?",
        "ask_changed",
    ),
    (
        "hi-time-as-speed",
        "hi",
        "एक ट्रेन 60 मी/से की चाल से 1200 मीटर चलती है। कितना समय लगेगा?",
        "A train moves 1200 m at 60 m/s. What is its speed?",
        "ask_changed",
    ),
    (
        "am-time-as-distance",
        "am",
        "መኪና በ15 ሜ/ሰ ፍጥነት 300 ሜትር ተጓዘ። ምን ያህል ጊዜ ወሰደበት?",
        "A car travelled 300 m at 15 m/s. How far did it go?",
        "ask_changed",
    ),
    (
        "fr-grams-as-moles",
        "fr",
        "Combien de grammes de NaCl faut-il pour 0,5 mol ?",
        "How many moles of NaCl are needed for 0.5 mol?",
        "ask_changed",
    ),
    (
        "es-side-unread",
        "es",
        "Un cuadrado tiene un área de 49 cm². ¿Cuánto mide su lado?",
        "A square has an area of 49 cm². How long is its side?",
        "ok",
    ),
    (
        "es-average-as-final",
        "es",
        "Un coche pasa de 10 m/s a 30 m/s en 5 s. ¿Cuál es su rapidez media?",
        "A car goes from 10 m/s to 30 m/s in 5 s. What is its final speed?",
        "ask_changed",
    ),
]


@pytest.mark.parametrize(
    ("name", "language", "original", "english", "reason"),
    ROUND_TWO,
    ids=[row[0] for row in ROUND_TWO],
)
def test_every_token_of_the_original_is_kept(
    name: str, language: str, original: str, english: str, reason: str
) -> None:
    assert check_translation(original, english, _TABLES, language) == reason


# A change of meaning that keeps every token: what the check does not see. The second
# translation (another model, read to the same solve) is what guards these.
MEANING_ONLY = [
    (
        "es",
        "Un coche que no parte del reposo acelera a 2 m/s² durante 5 s.",
        "A car starting from rest accelerates at 2 m/s² for 5 s.",
    ),
    (
        "fr",
        "Deux résistances de 10 Ω chacune sont en parallèle sur 5 V.",
        "Two 10 Ω resistors are across 5 V.",
    ),
]


@pytest.mark.parametrize(("language", "original", "english"), MEANING_ONLY)
def test_a_meaning_change_that_keeps_every_token_passes_the_check(
    language: str, original: str, english: str
) -> None:
    assert check_translation(original, english, _TABLES, language) == "ok"
