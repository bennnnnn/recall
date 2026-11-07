"""An equation is read from its notation, so one asked in any language is never searched."""

from __future__ import annotations

import pytest

from app.modules.turn_reading.calculation import states_an_equation
from app.modules.web_search import web_search_skip


@pytest.mark.parametrize(
    "text",
    [
        "x² + 5x + 6 = 0 को हल करें",
        "Resuelve 3x - 5 = 2x + 7",
        "Löse 2x + 3 = 11",
        "求解 x^2 - 5x + 6 = 0",
        "Calcule la dérivée de f(x) = ln(x^2 + 1)",
        "حل المعادلة x^2 - 5x + 6 = 0",
        "Реши уравнение 2x + 3 = 11",
    ],
)
def test_an_equation_in_any_language_is_never_searched(text: str) -> None:
    assert states_an_equation(text)
    assert web_search_skip(text)


@pytest.mark.parametrize(
    "text",
    [
        "who won the champions league",
        "x = 5",
        "set a = b in my config",
        "if (x == 2) { y = 3*x }",
        # A law named, not a sum: its history may be looked up.
        "Who invented E = mc²?",
        "E = mc^2 history who first wrote it",
        # A link or markup holds "=" too.
        "qué dice este video https://youtu.be/abc123?si=9xYz4kLm",
        "https://example.com/search?q=2x+3&page=2 is this site safe?",
        '<a href="x" width=3px>',
        # Quantities with units are not read here: weather, specs and records still search.
        "Wetter Berlin morgen 15 °C 20 km/h Wind?",
        "Samsung 4K TV 120 Hz 65 inch reviews",
        "Is Usain Bolt's 100 m 9.58 s record still standing?",
    ],
)
def test_states_an_equation_leaves_look_alikes(text: str) -> None:
    assert not states_an_equation(text)
