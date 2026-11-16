"""Every SI prefix on every unit the givens read, and the spellings left out by usage.

"Take the charges as 3.0 pC and 2.0 μC" (the owner's GCSE set, 2026-11-16) read the 3.0 as
a bare number: the table listed nC and μC but no pC. A prefixed spelling that is something
else after a number in a school question stays unread (review of feat/field-lines).
"""

from __future__ import annotations

import pytest

from app.modules.physics.givens import PHYSICS_UNITS
from app.services.law_binding.fit import read_givens


def _read(text: str) -> list[tuple[float, str, float | None]]:
    return [(g.value, g.unit, g.si) for g in read_givens(text, PHYSICS_UNITS) if g.dimension]


@pytest.mark.parametrize(
    ("text", "si"),
    [
        ("a charge of 3.0 pC", 3e-12),
        ("a charge of 2.0 μC", 2e-6),
        ("a charge of 2.0 µC", 2e-6),
        ("a charge of 2.0 uC", 2e-6),
        ("a charge of 4 kC", 4000.0),
        ("a charge of 20 picocoulombs", 2e-11),
        ("a current of 3 nA", 3e-9),
        ("a pulse of 5 ps", 5e-12),
        ("a resistance of 2 GΩ", 2e9),
        ("a reservoir of 3 GL", 3e6),
    ],
)
def test_every_prefix_on_every_base_is_read(text: str, si: float) -> None:
    ((_value, _unit, read),) = _read(text)
    assert read == pytest.approx(si)


@pytest.mark.parametrize(
    "text",
    [
        "A pilot pulls 5 Gs in the turn.",
        "A 12 GA copper wire carries the current.",
        "He drove a 2 GT to work.",
        "The train leaves at 5 pm.",
        "The solution has a value of 7 pH.",
        "The gas law product is 2 pV.",
        "An energy of 1.5 kT.",
        "A sample of 24 Mg.",
        "It costs 5 us dollars.",
    ],
)
def test_a_spelling_that_is_something_else_stays_unread(text: str) -> None:
    assert _read(text) == []


@pytest.mark.parametrize(("listed", "twin"), [("mN", "MN"), ("MPa", "mPa"), ("mA", "MA")])
def test_the_case_twin_of_a_listed_spelling_stays_unread(listed: str, twin: str) -> None:
    assert _read(f"a value of 5 {listed}")
    assert _read(f"a value of 5 {twin}") == []
