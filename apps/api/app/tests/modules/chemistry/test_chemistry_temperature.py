"""A chemistry law reads the temperature its question states, however it is written.

"E° = 0.80 V, n = 1, Q = 0.010 at 350 K. Use the Nernst equation to find E." was answered
0.92 V, verified: only "T = …" was read, so the law took 25 °C (audit 2026-11-13, CHEM-02).
Expected values are worked here from E = E° - (RT/nF) ln Q with CODATA R and F.
"""

from __future__ import annotations

import math

import pytest

from app.modules.chemistry.block import build_verified_chemistry
from app.modules.chemistry.extract import extract_chemistry_intent
from app.modules.chemistry.temperature import stated_temperature

_R = 8.314462618
_F = 96485.33212


def _nernst(standard: float, electrons: int, quotient: float, kelvin: float) -> float:
    return standard - _R * kelvin / (electrons * _F) * math.log(quotient)


@pytest.mark.parametrize(
    ("text", "kelvin"),
    [
        ("Q = 0.010 at 350 K", 350.0),
        ("T = 350 K", 350.0),
        ("at a temperature of 310 K", 310.0),
        ("the temperature is 310 kelvin", 310.0),
        ("at 25 °C", 298.15),
        ("at 25 ° C", 298.15),
        ("at 37 degrees Celsius", 310.15),
        ("at 100 °F", (100 - 32) * 5 / 9 + 273.15),
        # One temperature written twice is one temperature, rounded or not: the first is read.
        ("at 25 °C (298.15 K)", 298.15),
        ("at 25 °C (298 K)", 298.15),
        ("at 0 °C, or 273 K", 273.15),
        ("at 298 K (25 °C)", 298.0),
    ],
)
def test_a_stated_temperature_is_read_however_it_is_written(text: str, kelvin: float) -> None:
    found = stated_temperature(text)
    assert isinstance(found, float)
    assert found == pytest.approx(kelvin)


@pytest.mark.parametrize(
    "text",
    [
        "E° = 0.80 V, n = 1, Q = 0.010",
        # A constant's unit and a change of temperature are no temperature.
        "Kb = 0.512 °C/m for water",
        "ΔT = 2.5 °C",
        "the solution's boiling point rises by 0.52 K",
        "2 K + Cl2 -> 2 KCl",
        "at room temperature",
        "at standard temperature and pressure",
    ],
)
def test_no_temperature_is_stated(text: str) -> None:
    assert stated_temperature(text) is None


@pytest.mark.parametrize(
    "text",
    [
        "at body temperature",
        "T = 310",
        "heated from 300 K to 350 K",
        # Two kelvin apart is two temperatures, not one rounded.
        "at 298 K and 300 K",
        "at a higher temperature",
    ],
)
def test_a_temperature_stated_but_not_one_reading_is_refused(text: str) -> None:
    assert stated_temperature(text) is False


def _answer(text: str) -> str | None:
    intent = extract_chemistry_intent(text)
    verified = None if intent is None else build_verified_chemistry(intent)
    return None if verified is None else verified.result.answer


def _volts(answer: str | None) -> float:
    assert answer is not None
    return float(answer.split("=")[1].split("V")[0])


@pytest.mark.parametrize(
    ("text", "volts"),
    [
        (
            "E° = 0.80 V, n = 1, Q = 0.010 at 350 K. Use the Nernst equation to find E.",
            _nernst(0.80, 1, 0.010, 350),
        ),
        (
            "Use the Nernst equation: E° = 0.80 V, n = 1, Q = 0.010 at 100 °F. Find E.",
            _nernst(0.80, 1, 0.010, (100 - 32) * 5 / 9 + 273.15),
        ),
        (
            "E° = 0.80 V, n = 1, Q = 0.010. Use the Nernst equation to find E.",
            _nernst(0.80, 1, 0.010, 298.15),
        ),
        (
            "Find the cell potential of a Zn/Cu cell with [Zn2+] = 1.0 M and [Cu2+] = 0.010 M "
            "at 350 K",
            _nernst(1.10, 2, 1.0 / 0.010, 350),
        ),
        (
            "Find the cell potential of a Zn/Cu cell with [Zn2+] = 1.0 M and [Cu2+] = 0.010 M",
            _nernst(1.10, 2, 1.0 / 0.010, 298.15),
        ),
        # Answered on main, then declined as two temperatures (review 2026-11-13).
        (
            "E° = 1.10 V, n = 2, Q = 0.0100 at 25 °C (298 K). Use the Nernst equation to find E.",
            _nernst(1.10, 2, 0.0100, 298.15),
        ),
    ],
)
def test_a_cell_potential_is_worked_at_the_stated_temperature(text: str, volts: float) -> None:
    assert _volts(_answer(text)) == pytest.approx(volts, abs=0.006)


def test_kc_converts_to_kp_at_a_temperature_in_celsius() -> None:
    answer = _answer("Kc = 0.5 at 500 °C. Find Kp for N2 + 3 H2 -> 2 NH3.")
    # Kp = Kc(RT)^Δn, Δn = 2 - 4.
    expected = 0.5 * (0.082057366 * 773.15) ** -2
    assert answer is not None
    mantissa, exponent = answer.split("=")[1].split("× 10^")
    # Kc = 0.5 has one figure, so the card keeps two.
    assert float(mantissa) * 10 ** int(exponent) == pytest.approx(expected, rel=0.05)


@pytest.mark.parametrize(
    "text",
    [
        # Body temperature is a temperature, but not one this reader takes: never 25 °C.
        "E° = 0.80 V, n = 1, Q = 0.010 at body temperature. Use the Nernst equation to find E.",
        "What is the cell potential when E° = 0.80 V, n = 1 and Q = 0.010 at T = 350?",
        # Kw is 1.0e-14 at 25 °C only: a pH at another temperature is not worked with it.
        "Strong base: 0.010 M NaOH at 50 °C",
        "What is the pH of 0.010 M NaOH at 50 °C?",
        "What is the pOH of a solution with pH = 3.0 at 60 °C?",
    ],
)
def test_a_temperature_the_law_cannot_take_declines(text: str) -> None:
    assert _answer(text) is None


@pytest.mark.parametrize(
    ("text", "answer"),
    [
        ("Strong base: 0.010 M NaOH at 25 °C", "pH = 12.00"),
        ("What is the pH of 0.010 M NaOH?", "pH = 12.00"),
        (
            "For a reaction ΔH = -92 kJ/mol and ΔS = -199 J/(mol·K). Find ΔG at 25 °C.",
            "ΔG = -33 kJ/mol",
        ),
    ],
)
def test_twenty_five_degrees_stated_or_not_is_standard(text: str, answer: str) -> None:
    assert _answer(text) == answer
