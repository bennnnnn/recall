"""Deterministic estimates for recurring-pay questions with a calendar end date.

These requests combine arithmetic with the user's local date. Sending them to
general chat previously let the model ask for today's date even though Recall
already knows it, or count paychecks without stating whether today is a payday.
This module owns the narrow, fully specified case and makes every assumption
visible in the reply.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from app.core.timezone import resolve_timezone
from app.services.text_normalize import collapse_ws

_MAX_REQUEST_CHARS = 500

_INCOME_CUE = re.compile(
    r"\b(?:pay|paid|paycheck|salary|wage|income|make|earn|earning|receive|receiving)\b",
    re.IGNORECASE,
)
_TOTAL_CUE = re.compile(
    r"\b(?:how much|what (?:would|will|do) i|total|altogether|by|until|untill|through)\b",
    re.IGNORECASE,
)
_TARGET_CUE = re.compile(
    r"\b(?:by|until|untill|till|through|thru|before|up to|from today|from now|"
    r"between today|between now)\b",
    re.IGNORECASE,
)

_AMOUNT_TEXT = r"(?P<amount>\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)"
_INCOME_AMOUNT = re.compile(
    rf"\b(?:make|earn|earning|earned|receive|receiving|get paid|am paid|paid)\s+"
    rf"(?:about\s+)?(?:\$\s*|usd\s*)?{_AMOUNT_TEXT}",
    re.IGNORECASE,
)
_PAY_IS_AMOUNT = re.compile(
    rf"\b(?:my\s+)?(?:pay|paycheck|salary|wage|income)\s+(?:is|of)\s+"
    rf"(?:\$\s*|usd\s*)?{_AMOUNT_TEXT}",
    re.IGNORECASE,
)
_CURRENCY_AMOUNT = re.compile(rf"(?:\$\s*|\busd\s*){_AMOUNT_TEXT}", re.IGNORECASE)

_NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "fourteen": 14,
}
_INTERVAL = re.compile(
    r"\b(?:once\s+)?(?:every|each|per)\s+"
    r"(?:(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fourteen)\s+)?"
    r"(weeks?|days?)\b",
    re.IGNORECASE,
)
_BIWEEKLY = re.compile(r"\b(?:bi[\s-]?weekly|fortnightly|every\s+other\s+week)\b", re.IGNORECASE)

_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
    # Common mobile typo from the reported production question.
    "dcember": 12,
}
_WORD_DATE = re.compile(
    r"\b([a-z]+)\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?\b",
    re.IGNORECASE,
)
_DAY_MONTH_DATE = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]+)\.?(?:\s+(\d{4}))?\b",
    re.IGNORECASE,
)
_ISO_DATE = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
_SLASH_DATE = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2}|\d{4}))?\b")


@dataclass(frozen=True)
class RecurringPayEstimate:
    amount: Decimal
    interval_days: int
    start: date
    target: date

    @property
    def elapsed_days(self) -> int:
        return (self.target - self.start).days

    @property
    def full_periods(self) -> int:
        return max(0, self.elapsed_days // self.interval_days)

    @property
    def remainder_days(self) -> int:
        return max(0, self.elapsed_days % self.interval_days)


def _parse_amount(text: str) -> Decimal | None:
    match = (
        _INCOME_AMOUNT.search(text) or _PAY_IS_AMOUNT.search(text) or _CURRENCY_AMOUNT.search(text)
    )
    if match is None:
        return None
    try:
        amount = Decimal(match.group("amount").replace(",", ""))
    except (InvalidOperation, ValueError):
        return None
    return amount if Decimal("0") < amount <= Decimal("1000000000") else None


def _parse_interval_days(text: str) -> int | None:
    if _BIWEEKLY.search(text):
        return 14
    match = _INTERVAL.search(text)
    if match is None:
        return None
    raw_count, unit = match.groups()
    count = 1 if raw_count is None else _NUMBER_WORDS.get(raw_count.lower())
    if count is None:
        try:
            count = int(raw_count)
        except (TypeError, ValueError):
            return None
    days = count * (7 if unit.lower().startswith("week") else 1)
    return days if 1 <= days <= 365 else None


def _year_or_next(month: int, day: int, raw_year: str | None, start: date) -> date | None:
    if raw_year:
        year = int(raw_year)
        if year < 100:
            year += 2000
    else:
        year = start.year
    try:
        parsed = date(year, month, day)
        if raw_year is None and parsed < start:
            parsed = date(year + 1, month, day)
    except ValueError:
        return None
    return parsed


def _parse_target_date(text: str, start: date) -> date | None:
    iso = _ISO_DATE.search(text)
    if iso is not None:
        try:
            return date(*(int(value) for value in iso.groups()))
        except ValueError:
            return None

    for match in _WORD_DATE.finditer(text):
        month = _MONTHS.get(match.group(1).lower())
        if month is not None:
            return _year_or_next(month, int(match.group(2)), match.group(3), start)
    for match in _DAY_MONTH_DATE.finditer(text):
        month = _MONTHS.get(match.group(2).lower())
        if month is not None:
            return _year_or_next(month, int(match.group(1)), match.group(3), start)

    slash = _SLASH_DATE.search(text)
    if slash is not None:
        month, day, raw_year = slash.groups()
        return _year_or_next(int(month), int(day), raw_year, start)
    return None


def parse_recurring_pay_request(
    text: str,
    timezone: str | None,
    *,
    now: datetime | None = None,
) -> RecurringPayEstimate | None:
    """Parse the narrow amount + cadence + end-date request, or decline it."""
    if not text or len(text) > _MAX_REQUEST_CHARS:
        return None
    cleaned = collapse_ws(text)
    if (
        (_INCOME_CUE.search(cleaned) is None and _CURRENCY_AMOUNT.search(cleaned) is None)
        or _TOTAL_CUE.search(cleaned) is None
        or _TARGET_CUE.search(cleaned) is None
    ):
        return None
    amount = _parse_amount(cleaned)
    interval_days = _parse_interval_days(cleaned)
    if amount is None or interval_days is None:
        return None
    tz = resolve_timezone(timezone)
    local_now = now.astimezone(tz) if now is not None and now.tzinfo else now
    start = (local_now or datetime.now(tz)).date()
    target = _parse_target_date(cleaned, start)
    if target is None:
        return None
    return RecurringPayEstimate(amount, interval_days, start, target)


def _money(value: Decimal) -> str:
    rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{rounded:,.0f}" if rounded == rounded.to_integral() else f"{rounded:,.2f}"


def _latex_money(value: Decimal) -> str:
    return rf"\${_money(value).replace(',', '{,}')}"


def _date_label(value: date) -> str:
    return f"{value.strftime('%A, %B')} {value.day}, {value.year}"


def _payday_labels(estimate: RecurringPayEstimate) -> str | None:
    if not 1 <= estimate.full_periods <= 12:
        return None
    labels = []
    for index in range(1, estimate.full_periods + 1):
        payday = estimate.start + timedelta(days=estimate.interval_days * index)
        labels.append(f"{payday.strftime('%b')} {payday.day}")
    return " → ".join(labels)


def format_recurring_pay_reply(estimate: RecurringPayEstimate) -> str:
    """Show the interval count and the two ambiguous real-world interpretations."""
    if estimate.elapsed_days < 0:
        return (
            f"{_date_label(estimate.target)} is before today "
            f"({_date_label(estimate.start)}). Give me a future end date and I'll calculate it."
        )

    full_total = estimate.amount * estimate.full_periods
    payday_total = estimate.amount * (estimate.full_periods + 1)
    prorated_total = (
        estimate.amount * Decimal(estimate.elapsed_days) / Decimal(estimate.interval_days)
    )
    paydays = _payday_labels(estimate)
    period_name = "two-week" if estimate.interval_days == 14 else f"{estimate.interval_days}-day"

    chunks = [
        f"**From:** {_date_label(estimate.start)}  \n**Through:** {_date_label(estimate.target)}",
        (
            "**1. Count the time**\n"
            f"${estimate.elapsed_days}\\ \\text{{days}} = "
            f"{estimate.full_periods} \\times {estimate.interval_days}\\ \\text{{days}}"
            f" + {estimate.remainder_days}\\ \\text{{days}}$"
        ),
        (
            f"**2. Count completed {period_name} pay periods**\n"
            f"${estimate.full_periods} \\times {_latex_money(estimate.amount)}"
            f" = {_latex_money(full_total)}$"
        ),
    ]
    if paydays:
        chunks.append(f"**Payment dates:** {paydays}")
    chunks.extend(
        [
            (
                f"Assuming today starts a new pay period and the first payment arrives in "
                f"{estimate.interval_days} days:"
            ),
            f"```answer\n{_latex_money(full_total)}\n```",
            (
                f"If **today is already a payday**, count today too: "
                f"${estimate.full_periods + 1} \\times {_latex_money(estimate.amount)}"
                f" = {_latex_money(payday_total)}$."
            ),
            (
                "If the pay accrues evenly each day instead of by completed pay periods: "
                f"${estimate.elapsed_days} \\div {estimate.interval_days} \\times "
                f"{_latex_money(estimate.amount)} = {_latex_money(prorated_total)}$."
            ),
        ]
    )
    return "\n\n".join(chunks) + "\n"


def maybe_recurring_pay_reply(
    text: str,
    timezone: str | None,
    *,
    now: datetime | None = None,
) -> str | None:
    estimate = parse_recurring_pay_request(text, timezone, now=now)
    return format_recurring_pay_reply(estimate) if estimate is not None else None
