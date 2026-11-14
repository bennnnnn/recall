# ruff: noqa: RUF003 -- a form is written as a reader sees it (× 100%).
"""How a form of a law stands to the law, read by evaluating both (``law_binding.same_law``).

After the "same law for these quantities" note went (review 2026-11-12, D4), a reply could
print ``N/N₀ = (½)ⁿ`` straight above ``N/N₀ = 100(½)ⁿ`` with nothing to say why both hold.
"""

from __future__ import annotations

import pytest

from app.services.law_binding.same_law import (
    as_percent,
    differs_at,
    same_function,
    zeroed_symbol,
)


@pytest.mark.parametrize(
    ("form", "law"),
    [
        (r"\frac{g t^{2}}{2}", r"\tfrac{1}{2}gt^2"),
        (r"\frac{m L^{2}}{3}", r"\frac{1}{3}mL^2"),
        (r"\frac{\sqrt{\frac{g}{L}}}{2 \pi}", r"\frac{1}{2\pi}\sqrt{\frac{g}{L}}"),
        # t/RC divides by RC, as the formula means it.
        (r"V_0 (1 - e^{\frac{-t}{R C}})", r"V_0\left(1 - e^{-t/RC}\right)"),
        # Spellings the reader takes as the same number: × 100 as a percent, a unit after a
        # thin space, log₁₀ as ln over ln 10, "⇒ ω_f" naming what is worked out next.
        (r"\frac{E_{out}}{E_{in}} 100", r"\frac{E_{out}}{E_{in}} \times 100\%"),
        (r"331.3 \sqrt{\frac{T}{273.15}}", r"331.3\sqrt{\frac{T}{273.15\,\mathrm{K}}}"),
        (r"\frac{10 \ln(\frac{I}{I_0})}{\ln(10)}", r"10\log_{10}\frac{I}{I_0}"),
        (r"I_f\omega_f \Rightarrow \omega_f", r"I_f\omega_f"),
    ],
)
def test_a_form_written_differently_is_the_same_law(form: str, law: str) -> None:
    assert same_function(form, law)
    assert not as_percent(form, law)


@pytest.mark.parametrize(
    ("form", "law"),
    [
        # Another law brought in (Ohm's), a percent, a law at a value: not the same.
        (r"I^2 R", "VI"),
        (r"100 (\frac{1}{2})^{n}", r"\left(\frac{1}{2}\right)^{n}"),
        (r"\frac{v_0^2}{2g}", r"h_0 + \frac{v_0^2}{2g}"),
        # Outside the reader's grammar: no answer, never a guess.
        (r"v_i t + \tfrac{1}{2}at^2", r"\int_0^t |v_i+a\tau|\,d\tau"),
    ],
)
def test_a_different_form_is_not_the_same_law(form: str, law: str) -> None:
    assert not same_function(form, law)


def test_a_hundred_times_the_law_is_it_as_a_percent() -> None:
    assert as_percent(r"100 (\frac{1}{2})^{n}", r"\left(\frac{1}{2}\right)^{n}")
    assert as_percent(r"\frac{100 F_{out} h}{F_{in} L}", r"\frac{F_{out} h}{F_{in} L}")
    assert not as_percent(r"86400 P t", "P t")


@pytest.mark.parametrize(
    ("form", "law", "symbol"),
    [
        (r"\frac{v_0^2}{2g}", r"h_0 + \frac{v_0^2}{2g}", "h_0"),
        (r"v_0 t", r"v_0 t + \tfrac{1}{2}at^2", "a"),
        # A sine at 90° is 1, not a symbol at 0; another law is no value of this one.
        (r"F d", r"Fd\sin(\theta)", None),
        (r"I^2 R", "VI", None),
    ],
)
def test_a_form_that_is_the_law_with_a_symbol_at_zero(
    form: str, law: str, symbol: str | None
) -> None:
    assert zeroed_symbol(form, law) == symbol


@pytest.mark.parametrize(
    ("givens", "differs"),
    [
        # Braking stops the train at 20 s: after 30 s it has gone 300 m, not 225 m.
        ({"v_i": 30.0, "a": -1.5, "t": 30.0}, True),
        # At the moment it stops both forms give 300 m.
        ({"v_i": 30.0, "a": -1.5, "t": 20.0}, False),
        # A given missing: nothing to compare.
        ({"v_i": 30.0, "a": -1.5}, False),
    ],
)
def test_a_form_that_gives_another_number_for_the_givens(
    givens: dict[str, float], differs: bool
) -> None:
    assert differs_at(r"\frac{v_i^2}{2|a|}", r"v_i t + \tfrac{1}{2}at^2", givens) is differs
