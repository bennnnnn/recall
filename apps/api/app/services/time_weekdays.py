"""A weekday written next to its date, checked against the calendar.

The model counts weekdays badly ("Christmas 2026 falls on a Monday"; it is a
Friday). A reply's "Weekday, Month D, YYYY" is corrected before it is saved.
"""

from __future__ import annotations

import re
from datetime import datetime

# "**Monday**, December 25, 2026" is checked too: bold may wrap the weekday.
_WEEKDAY_DATE = re.compile(
    r"\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)(?:\*\*)?,?\s+"
    r"(?:\*\*)?(January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+"
    r"(\d{1,2}),?\s+(\d{4})\b",
    re.IGNORECASE,
)


def correct_weekday_dates(text: str) -> str:
    """Replace a weekday that does not belong to the date written next to it."""

    def replace(match: re.Match[str]) -> str:
        weekday = match.group(1)
        month = match.group(2)
        day_raw = match.group(3)
        year_raw = match.group(4)
        try:
            when = datetime.strptime(f"{month} {int(day_raw)} {int(year_raw)}", "%B %d %Y")
        except ValueError:
            return match.group(0)
        actual = when.strftime("%A")
        if actual.lower() == weekday.lower():
            return match.group(0)
        return match.group(0).replace(weekday, actual, 1)

    return _WEEKDAY_DATE.sub(replace, text)
