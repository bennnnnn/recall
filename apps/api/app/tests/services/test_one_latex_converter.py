"""LaTeX is written as plain text by one converter (``latex_markup.without_markup``).

The answer check, the posed-problem read and the photo reader each kept their own LaTeX
cleaner (audit, 2026-11-25), and each knew different commands: the answer check left
``\\boxed{x = 4}`` and ``\\sqrt`` alone, the posed read knew only three text runs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.modules.chat.posed_read import _unlatexed
from app.services.answer_check import _clean, read_value
from app.services.latex_markup import without_markup

_APP = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("tex", "plain"),
    [
        (r"\boxed{x = 4}", "x = 4"),
        (r"50 \rm{kg}", "50 kg"),
        (r"\frac{-3}{4}", "-3/4"),
        (r"E = \frac{hc}{\lambda}", "E = hc/λ"),
    ],
)
def test_the_converter_reads_what_the_cleaners_did(tex: str, plain: str) -> None:
    assert without_markup(tex) == plain
    assert _clean(tex).strip() == plain


def test_a_long_reply_is_read_whole() -> None:
    """The converter leaves a text past its bound as written; a reply is read a line at a
    time, so its last line's TeX, a box the old cleaner never opened, is still read."""
    reply = ("Some working.\n" * 2_000) + r"So $\boxed{v = 35.3\,\mathrm{m/s}}$."
    assert len(reply) > 20_000
    assert _clean(reply).splitlines()[-1].strip() == "So  v = 35.3 m/s ."


@pytest.mark.parametrize(
    ("tex", "plain"),
    [
        (r"\frac{F}{\pi r^2}", "F/(πr^2)"),
        (r"\frac{1}{\omega C}", "1/(ωC)"),
        (r"\frac{m}{\rho V}", "m/(ρV)"),
        (r"\frac{hc}{\lambda}", "hc/λ"),
    ],
)
def test_a_greek_letter_alone_is_the_only_bare_greek_denominator(tex: str, plain: str) -> None:
    """F/πr^2 reads as (F/π)·r² (review, #2591)."""
    assert without_markup(tex) == plain


@pytest.mark.parametrize("unit", [r"\text{ m}", r"\mathrm{m}", r"\,\mathrm{m}"])
def test_a_fraction_before_its_unit_reads_as_its_value(unit: str) -> None:
    """The unit after a fraction is no factor of it: 3/4 m, never (3/4) m (review, #2591)."""
    numbers = read_value(_clean(rf"\frac{{3}}{{4}}{unit}"))
    assert numbers is not None
    assert [(float(number.value), number.unit) for number in numbers] == [(0.75, "m")]


def test_the_posed_read_knows_every_command() -> None:
    assert _unlatexed(r"$q = 2.0\,\mu\text{C}$") == _unlatexed("q = 2.0 μC")


@pytest.mark.parametrize(
    "path",
    [
        "services/answer_check.py",
        "services/asked_value.py",
        "modules/chat/posed_read.py",
        "modules/physics/read.py",
    ],
)
def test_no_reader_keeps_its_own_converter(path: str) -> None:
    source = (_APP / path).read_text(encoding="utf-8")
    assert "without_markup" in source
    # A cleaner's own table: a text-run pattern, a fraction pattern, a Greek command list.
    for command in ("(?:mathrm", "frac\\s*", r'r"\varepsilon"'):
        assert command not in source, (path, command)
