"""A temperature range is a change between two readings, however its scale is written.

"How much heat is needed to raise 250 g of water from 20 C to 80 C?" was verified as
20930 J: the range was read only with "°C", so the change reader took the first reading,
20, for the rise. It is 62790 J, a change of 60.
"""

from __future__ import annotations

import pytest

from app.modules.physics.extract import extract_physics_intent
from app.modules.physics.extractors.thermal_readings import _temperature_change


@pytest.mark.parametrize(
    "question",
    [
        "How much heat is needed to raise 250 g of water from 20 C to 80 C?",
        "How much heat is needed to raise 250 g of water from 20C to 80C?",
        "How much heat is needed to raise 250 g of water from 20 °C to 80 °C?",
        "How much heat is needed to raise 250 g of water from 20 degrees to 80 degrees?",
        "How much heat raises 250 g of water from 20 degrees C to 80 degrees C?",
        "How much heat is needed to heat 250 g of water from 20 to 80 C?",
        "How much heat is needed to raise 250 g of water from 20-80 °C?",
        "How much heat warms 250 g of water between 20 and 80 degrees Celsius?",
    ],
)
def test_a_temperature_range_is_read_as_its_two_readings(question: str) -> None:
    intent = extract_physics_intent(question)
    assert intent is not None and intent.physics_op == "heat_energy"
    params = intent.physics_params or {}
    assert (params.get("temp_initial"), params.get("temp_final")) == (20.0, 80.0)
    assert "delta_temp" not in params


def test_a_ranges_first_reading_is_never_a_change() -> None:
    assert _temperature_change("raise it from 20 C to 80 C", ("raise",)) is None
    assert _temperature_change("raise it by 20 C", ("by",)) == (20.0, "K")


@pytest.mark.parametrize(
    "question",
    [
        "A 2 m steel rod with alpha = 1.2e-5 /K changes temperature from 20 C to 70 C. Find the expansion.",
        "A 2 m steel rod with alpha = 1.2e-5 /K changes temperature from 20 to 70 C. Find the expansion.",
    ],
)
def test_a_law_reading_only_a_change_never_takes_a_ranges_reading(question: str) -> None:
    # Linear expansion reads a stated change: a range's 20 or 70 is not one.
    intent = extract_physics_intent(question)
    assert intent is None or (intent.physics_params or {}).get("delta_temp") not in (20.0, 70.0)
