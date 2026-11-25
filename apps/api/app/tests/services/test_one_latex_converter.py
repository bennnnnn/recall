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
    time, so its last line's TeX is still read."""
    reply = ("Some working.\n" * 2_000) + r"So $v = 35.3\,\mathrm{m/s}$."
    assert len(reply) > 20_000
    assert _clean(reply).splitlines()[-1].strip() == "So  v = 35.3 m/s ."


def test_a_signed_fraction_reads_as_its_value() -> None:
    numbers = read_value(_clean(r"\frac{-3}{4}"))
    assert numbers is not None and [float(number.value) for number in numbers] == [-0.75]


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
