"""A prefixed unit symbol that is also an ordinary word is no unit (PR #2482 review)."""

from __future__ import annotations


def test_a_tv_is_no_teravolt() -> None:
    """ "1 TV draws a current of 2 A" read 10^12 V (Gemini, PR #2482): tera- spelled as an
    ordinary word or abbreviation is left out, as G and M are."""
    from app.modules.physics.givens import PHYSICS_UNITS
    from app.services.law_binding.fit import read_givens

    read = read_givens("1 TV draws a current of 2 A.", PHYSICS_UNITS)
    assert [given.dimension for given in read if given.dimension] == ["[current]^1"]
