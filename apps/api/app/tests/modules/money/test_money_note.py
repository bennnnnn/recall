"""The server's note comparing the user's rate with today's average."""

from __future__ import annotations

from dataclasses import replace

from app.modules.money.catalog import product
from app.modules.money.note import market_note
from app.modules.money.rates import MarketRate
from app.modules.money.read import MoneyRequest
from app.modules.money.solve import Worked, work
from app.tests.modules.money.money_support import average


def _worked(**values: float) -> Worked:
    found = work(MoneyRequest(product("mortgage"), dict(values)), 6.27)
    assert found is not None
    return found


def test_a_rate_far_below_the_average_is_not_realistic() -> None:
    note = market_note(_worked(amount=300000, rate=1), average(), 2.0)
    assert note == (
        "**Note:** 1% is not a realistic 30-year fixed mortgage rate. As of Oct 16, 2026, the "
        "average in the United States is 6.27% ([Mortgage Rates - Freddie Mac]"
        "(https://www.freddiemac.com/pmms))."
    )


def test_a_rate_far_above_the_average_is_not_realistic_either() -> None:
    note = market_note(_worked(amount=300000, rate=14), average(), 2.0)
    assert note is not None and "14% is not a realistic" in note


def test_a_rate_near_the_average_gets_it_for_reference() -> None:
    note = market_note(_worked(amount=300000, rate=6.5), average(), 2.0)
    assert note is not None and note.startswith("**Note:** for reference, the average")


def test_a_rate_taken_from_the_average_says_so() -> None:
    note = market_note(_worked(amount=300000), average(), 2.0)
    assert note is not None and note.startswith("**Note:** this uses today's average")


def test_no_average_no_note() -> None:
    assert market_note(_worked(amount=300000, rate=1), None, 2.0) is None


def _savings(**values: float) -> Worked:
    found = work(MoneyRequest(product("savings"), dict(values)), 0.37)
    assert found is not None
    return found


def _savings_average() -> MarketRate:
    lookup = product("savings").rate_lookup()
    assert lookup is not None
    return replace(
        average(0.37, "savings account interest rate (APY)"),
        source_title="Best High-Yield Savings Accounts - October 2026 | US News Money",
        spread=lookup.spread,
    )


def test_a_high_yield_rate_is_never_unrealistic_beside_the_national_average() -> None:
    """Live, 2026-11-02: "4% is not a realistic savings account interest rate (APY)" beside
    a 0.37% national average, which big banks paying almost nothing pull down."""
    note = market_note(_savings(deposit=50, rate=4, years=3), _savings_average(), 2.0)
    assert note is not None
    assert "not a realistic" not in note
    assert note.startswith("**Note:** for reference, the average savings account")
    assert note.endswith("high-yield savings accounts pay much more.")


def test_an_average_of_one_kind_still_judges_a_rate() -> None:
    """Only an average of mixed kinds is for reference alone: a mortgage's still judges."""
    assert product("mortgage").rate_lookup() is not None
    assert not product("mortgage").rate_lookup().spread  # type: ignore[union-attr]
    note = market_note(_worked(amount=300000, rate=14), average(), 2.0)
    assert note is not None and "is not a realistic" in note


def test_a_savings_average_used_as_the_rate_says_what_it_averages() -> None:
    note = market_note(_savings(deposit=50, years=3), _savings_average(), 2.0)
    assert note is not None and note.startswith("**Note:** this uses today's average")
    assert "high-yield savings accounts pay much more." in note
