from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.services.recurring_pay import (
    format_recurring_pay_reply,
    maybe_recurring_pay_reply,
    parse_recurring_pay_request,
)

NOW = datetime(2026, 9, 26, 12, 0, tzinfo=ZoneInfo("America/Los_Angeles"))


def test_reported_biweekly_question_uses_local_today_and_shows_assumptions() -> None:
    text = (
        "if i make 3400 a every 2 weeks, how much money would i make untill dcember 11th from today"
    )
    estimate = parse_recurring_pay_request(text, "America/Los_Angeles", now=NOW)
    assert estimate is not None
    assert estimate.elapsed_days == 76
    assert estimate.interval_days == 14
    assert estimate.full_periods == 5
    assert estimate.remainder_days == 6

    reply = format_recurring_pay_reply(estimate)
    assert "Saturday, September 26, 2026" in reply
    assert "Friday, December 11, 2026" in reply
    assert "76\\ \\text{days} = 5 \\times 14" in reply
    assert "Oct 10 → Oct 24 → Nov 7 → Nov 21 → Dec 5" in reply
    assert "```answer\n\\$17{,}000\n```" in reply
    assert "today is already a payday" in reply
    assert "\\$20{,}400" in reply
    assert "\\$18{,}457.14" in reply


@pytest.mark.parametrize(
    "text",
    [
        "I get paid $3,400 biweekly. How much will I earn by December 11?",
        "$3,400 every two weeks — what is my total through 12/11/2026?",
        "My pay is USD 3400 per 14 days. What would I make between now and 2026-12-11?",
        "I earn 1700 every week. How much money will I make until 11 December 2026?",
        "I receive 3400 every other week. What is the total between today and Dec 11th?",
    ],
)
def test_equivalent_phrasings_are_owned_by_the_same_calculator(text: str) -> None:
    reply = maybe_recurring_pay_reply(text, "America/Los_Angeles", now=NOW)
    assert reply is not None
    assert "**1. Count the time**" in reply
    assert "```answer" in reply


@pytest.mark.parametrize(
    "text",
    [
        "How much money is 3400 US dollars in euros by December 11?",
        "I get paid every two weeks. How much by December 11?",
        "I make 3400 every 2 weeks. What is that annually?",
        "Schedule a meeting every 2 weeks until December 11.",
    ],
)
def test_declines_requests_without_amount_cadence_income_and_end_date(text: str) -> None:
    assert maybe_recurring_pay_reply(text, "America/Los_Angeles", now=NOW) is None


def test_explicit_past_date_gets_a_clear_correction() -> None:
    reply = maybe_recurring_pay_reply(
        "I earn $3400 every two weeks. How much by December 11, 2025?",
        "America/Los_Angeles",
        now=NOW,
    )
    assert reply is not None
    assert "is before today" in reply
