"""A question in LaTeX markup reads as its plain twin (``services/latex_markup``)."""

from __future__ import annotations

import time

import pytest

from app.services.latex_markup import without_markup


@pytest.mark.parametrize(
    ("markup", "plain"),
    [
        (r"\(q_1 = +2.0 \, \mu\text{C}\)", "q_1 = +2.0 μC"),
        (r"\(R_1 = 4.0 \, \Omega\), \(12.0 \text{ V}\)", "R_1 = 4.0 Ω, 12.0 V"),
        (r"\(\mu_k = 0.30\)", "μ_k = 0.30"),
        (
            r"\(k_e \approx 9.0 \times 10^9 \text{ N}\cdot\text{m}^2/\text{C}^2\)",
            "k_e ≈ 9.0 × 10^9 N·m^2/C^2",
        ),
        (r"(Use \(g = 9.8 \text{ m/s}^2\).)", "(Use g = 9.8 m/s^2.)"),
        (r"\[ m = 2.0\,\mathrm{kg},\quad v = 3.0\,\mathrm{m/s} \]", "m = 2.0 kg, v = 3.0 m/s"),
        (r"\(3 \, \frac{\text{m}}{\text{s}^2}\)", "3 m/s^2"),
        (r"\frac{1}{2}mv^2", "(1/2)mv^2"),
        (r"x = \frac{a+b}{2}.", "x = (a+b)/2."),
        (r"\theta = 30^{\circ}, \sin\theta", "θ = 30°, sin θ"),
        (r"\(\Delta T = 20 \, ^\circ\text{C}\)", "ΔT = 20 °C"),
        (r"\(9.8 \text{ m s}^{-2}\)", "9.8 m s^-2"),
        (r"v = \sqrt{2gh}", "v = sqrt(2gh)"),
        # A formula's subscript count and an ion's charge, as chemistry reads them.
        (r"\(\mathrm{H_2SO_4}\), \ce{Fe^{3+}}, \(\mathrm{OH^{-}}\)", "H2SO4, Fe^3+, OH^-"),
        # A thin space between digit groups is the thousands of one number.
        (r"\(1\,500\,\text{kg}\), \(2\,\text{kg}\)", "1500 kg, 2 kg"),
        # A denominator of more than one term keeps its brackets.
        (r"\frac{1}{4\pi\varepsilon_0}", "1/(4πε_0)"),
        (r"\frac{v^2}{2a}", "v^2/(2a)"),
        (r"\frac{\text{g}}{\text{cm}^3}", "g/cm^3"),
        # A fraction with no denominator is its numerator, read once.
        (r"\frac{x}", "x"),
        # A prime is a prime: f'(x) is a derivative, never "f" times a group.
        (r"find \(f^{\prime}(x)\) and \(f^{\prime\prime}(x)\)", "find f'(x) and f''(x)"),
    ],
)
def test_markup_reads_as_its_plain_text(markup: str, plain: str) -> None:
    assert without_markup(markup) == plain


@pytest.mark.parametrize(
    "text",
    [
        "A net force of 30 N acts on a 6 kg box.",
        "costs $5 and $10 a day",
        "",
    ],
)
def test_text_without_markup_is_unchanged(text: str) -> None:
    assert without_markup(text) == text


def test_a_command_it_does_not_know_is_left_for_its_reader() -> None:
    # The maths keyboard's integral is the maths reader's to read.
    assert without_markup(r"\int_{0}^{1} x^{2}\,dx") == r"\int_0^1 x^2 dx"


def test_reading_plain_text_again_changes_nothing() -> None:
    once = without_markup(r"A \(5.0 \text{ kg}\) block, \(\mu_k = 0.30\)")
    assert without_markup(once) == once


@pytest.mark.wall_clock
@pytest.mark.parametrize(
    "hostile",
    [
        "\\" + "{" * 3000 + "x" + "}" * 3000,
        "\\a " + "{" * 19_000,
        "\\text{" * 3000 + "x",
        "\\frac{1}{2} " * 1500,
        # A fraction with no denominator, nested: its numerator is read once, not twice a level.
        "\\frac{" * 3300 + "x" + "}" * 3300,
        ("\\frac{" * 8 + "x" * 50 + "}" * 8 + " ") * 150,
    ],
)
def test_a_hostile_paste_of_braces_reads_in_linear_time(hostile: str) -> None:
    # Every reader runs on every turn: a paste of braces must neither recurse nor rescan.
    start = time.perf_counter()
    without_markup(hostile)
    assert time.perf_counter() - start < 0.5
