"""An inequality's card and number line: solved once, from the question as written.

The number line solved the inequality a second time, from text cut at the expression cap:
an inequality longer than the cap was solved as another one (audit 2026-11-25).
"""

from __future__ import annotations

from app.core.config import get_settings
from app.modules.math.schemas import MathIntent
from app.modules.math.solve import inequalities
from app.modules.math.tools.block import _build_verified_block


def _intent(lhs: str, rhs: str, comparator: str = ">") -> MathIntent:
    return MathIntent(kind="inequality", lhs=lhs, rhs=rhs, comparator=comparator, variable="x")


def test_the_card_and_the_number_line_share_one_solve() -> None:
    inequalities.inequality_solution_set.cache_clear()
    block = _build_verified_block(_intent("x**2 - 5*x + 6", "0"), get_settings())

    assert block is not None and block.canonical_fence is not None
    assert block.canonical_fence["type"] == "number_line"
    info = inequalities.inequality_solution_set.cache_info()
    assert (info.misses, info.hits) == (1, 1)


def test_a_side_past_the_cap_is_declined_not_cut() -> None:
    """Cut at 256 characters, 10^256 was 10^255, and x > 10^255 came back checked."""
    rhs = "1" + "0" * get_settings().math_max_expr_length

    assert _build_verified_block(_intent("x", rhs), get_settings()) is None


def test_a_long_compound_inequality_never_draws_a_cut_number_line() -> None:
    """Every side within the cap, the whole past it: the number line read its first 256
    characters, "1 < x < 5" for 1 < x < 20, under the checked card."""
    lower = "1" + " + 0" * 4
    middle = "x" + " + 0" * 28
    upper = "5" + " + 0" * 28 + " + 0*1 + 15"
    intent = MathIntent(
        kind="inequality",
        lower=lower,
        comparator="<",
        lhs=middle,
        comparator_upper="<",
        rhs=upper,
        variable="x",
    )
    assert len(f"{lower} < {middle} < {upper}") > get_settings().math_max_expr_length

    block = _build_verified_block(intent, get_settings())

    assert block is not None
    fence = block.canonical_fence or {}
    if fence.get("type") == "number_line":
        assert [(i["start"], i["end"]) for i in fence["intervals"]] == [(1.0, 20.0)]
