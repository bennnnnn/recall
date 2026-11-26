"""Review round 2 on #2591: each finding's case, which failed before its fix."""

from __future__ import annotations

import math

import pytest

from app.core.config import Settings
from app.modules.chat.card_lists import known_value
from app.modules.chat.card_numbers import card_numbers
from app.modules.physics import build_verified_physics_block, extract_physics_intent
from app.modules.physics.bodies import orbiting_mass_fills
from app.services.rounding_rule import RULE, Precision, number_latex, working_figures

_SETTINGS = Settings(math_tools_enabled=True)


def _intent_and_answer(question: str) -> tuple[dict[str, float] | None, str | None]:
    intent = extract_physics_intent(question)
    block = None if intent is None else build_verified_physics_block(intent, _SETTINGS)
    params = (
        None if intent is None or intent.physics_params is None else dict(intent.physics_params)
    )
    return params, None if block is None else block.canonical_answer


def _card(working: str, card: str) -> str:
    reply = f"{working}\n\n**Answer**\n\n```answer\nverified: false\n{card}\n```"
    return card_numbers(reply, RULE).split("verified: false\n", 1)[1].split("\n```", 1)[0]


# --- 4707702740: the orbiting body's mass is set aside in every unit M is read in ---------


@pytest.mark.parametrize(
    "question",
    [
        "A 2000 lb satellite orbits a planet of radius 6.4 × 10^6 m. Find its orbital speed.",
        "A 500 g satellite orbits a planet of radius 6.4 × 10^6 m. Find its orbital speed.",
    ],
)
def test_a_satellites_mass_in_any_unit_is_never_the_planets(question: str) -> None:
    params, answer = _intent_and_answer(question)
    assert answer is None
    assert params is None or "M" not in params


def test_an_astronauts_pounds_leave_the_planets_mass_alone() -> None:
    params, answer = _intent_and_answer(
        "A 150 lb astronaut on a planet of mass 6.4e23 kg, radius 3.4e6 m, surface gravity?"
    )
    assert params is not None and params["M"] == pytest.approx(6.4e23)
    assert answer is not None and answer.startswith("3.7")


@pytest.mark.parametrize(("mass", "unit"), [(2000.0, "lb"), (500.0, "g"), (3.0, "tonnes")])
def test_an_orbiting_mass_that_filled_m_is_seen_in_any_unit(mass: float, unit: str) -> None:
    text = f"A {mass:g} {unit} satellite orbits a planet."
    assert orbiting_mass_fills({"M": mass}, text)


# --- 4707703231: a precision asked for keeps every digit it asked for ---------------------


@pytest.mark.parametrize(
    ("value", "precision", "shown"),
    [
        (math.pi, Precision(places=15), "3.141592653589793"),
        (math.e, Precision(places=13), "2.7182818284590"),
        (math.pi, Precision(figures=15), "3.14159265358979"),
        # The rule's own rounding still takes a hair under a tie for the tie.
        (0.0001 * 50**2 / 2, RULE, "0.13"),
        (0.1 * 0.1235, RULE, "0.0124"),
    ],
)
def test_an_asked_precision_is_never_snapped(
    value: float, precision: Precision, shown: str
) -> None:
    assert number_latex(value, precision) == shown


# --- 4707703677: a power of ten is never written out with padded places -------------------


@pytest.mark.parametrize(
    "card",
    [r"E = 1.5 \times 10^{3}\,\mathrm{J}", r"c = 3.00 \times 10^{8}\,\mathrm{m/s}"],
)
def test_a_power_of_ten_card_keeps_its_figures(card: str) -> None:
    shown = _card("The working reaches no value.", card)
    assert "." not in shown.split("=")[1].split("\\")[0] or "times" in shown, shown
    assert "1500.0" not in shown and "300000000.00" not in shown, shown


# --- 4707705426: a value restated with its unit is no working out -------------------------


@pytest.mark.parametrize(
    ("number", "after", "working"),
    [
        ("2.4", " m/s", r"$v = 2.4\,\mathrm{m/s}$"),
        ("43.9", "°", r"$\theta = 43.9\,^\circ$"),
        ("43.9", "°", r"$\theta = (43.9)^\circ$"),
    ],
)
def test_a_restated_value_is_not_known(number: str, after: str, working: str) -> None:
    assert known_value(number, after, working) is None


def test_a_restated_value_keeps_its_figures_on_the_card() -> None:
    assert _card(r"$v = 2.4\,\mathrm{m/s}$", "v = 2.4 m/s") == "v = 2.4 m/s"
    assert _card(r"$\theta = 43.9\,^\circ$", "θ = 43.9°") == "θ = 43.9°"


# --- 4707705931: a superscript power is never padded away ---------------------------------


@pytest.mark.parametrize("card", ["d = 1.5 × 10³ m", "d = 1.5 × 10³ m, t = 1.5 s"])
def test_a_superscript_power_keeps_its_power(card: str) -> None:
    """t's 1.5 is known from its line; d's 1.5 x 10^3 is another number, never 1.50 m."""
    shown = _card(r"$t = \frac{3}{2} = 1.5\,\mathrm{s}$", card)
    assert shown.startswith(("d = 1500 m", "d = 1.5 × 10³ m")), shown


# --- 4707706945: three dots end a number as the ellipsis does -----------------------------


@pytest.mark.parametrize(
    ("card", "shown"),
    [("0.357142857...", "0.36"), ("12.546951... m/s, 43.9° north of west", "12.55 m/s")],
)
def test_three_dots_after_a_number_round_it(card: str, shown: str) -> None:
    assert _card("No working.", card).startswith(shown)


def test_three_dots_in_working_are_the_calculators() -> None:
    assert working_figures("x = 0.357142857...") == "x = 0.357143"


def test_a_number_written_for_one_symbol_is_never_known_from_anothers() -> None:
    """t's working ends on 1.5; x's 1.5 is not t's, so it keeps its figures."""
    working = r"$t = \frac{3}{2} = 1.5\,\mathrm{s}$"
    assert _card(working, "x = 1.5 m") == "x = 1.5 m"
    assert _card(working, "t = 1.5 s") == "t = 1.50 s"
    assert (
        _card(r"$\theta = \tan^{-1}(8.695652 / 9.043478)$  $\theta = 43.9^\circ$", "θ = 43.9°")
        == "θ = 43.88°"
    )
