"""A calculation is read from its notation, so homework in any language is never searched."""

from __future__ import annotations

import pytest

from app.modules.turn_reading.calculation import states_a_calculation
from app.modules.web_search import web_search_skip


@pytest.mark.parametrize(
    "text",
    [
        "x² + 5x + 6 = 0 को हल करें",
        "Resuelve 3x - 5 = 2x + 7",
        "Löse 2x + 3 = 11",
        "求解 x^2 - 5x + 6 = 0",
        "Calcule la dérivée de f(x) = ln(x^2 + 1)",
        "Une voiture roule à 72 km/h et freine jusqu'à l'arrêt en 4 s. Quelle est sa décélération ?",
        "Ein Körper fällt aus 45 m Höhe. Wie lange dauert der Fall? g = 9,81 m/s²",
        "Un résistor de 10 Ω sous 5 V, quel courant ?",
        "0,5 mol NaCl in 250 mL Wasser, Konzentration?",
        "light at 3 × 10^8 m/s crosses 1.5 × 10^11 m: how long?",
    ],
)
def test_states_a_calculation_reads_homework_in_any_language(text: str) -> None:
    assert states_a_calculation(text)
    assert web_search_skip(text)


@pytest.mark.parametrize(
    "text",
    [
        "who won the champions league",
        "what is the population of Ethiopia in 2026",
        "Quelle est la population de la France ?",
        "x = 5",
        "set a = b in my config",
        "price of 2 kg of rice in Addis today",
        "my flight leaves at 9 h and lands at 12 h",
        "if (x == 2) { y = 3*x }",
        "Tesla Model 3 0-100 km/h time",
        "how many km from Paris to Lyon",
        # Data in one unit is a chart's, not a sum.
        "show this in a graph: Mon 5h, Tue 7h, Wed 6h, Thu 8h, Fri 4h of sleep",
    ],
)
def test_states_a_calculation_leaves_look_alikes(text: str) -> None:
    assert not states_a_calculation(text)
