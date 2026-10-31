"""How often a request says interest compounds: "compounded quarterly" is 4 times a year.

Live (2026-10-31, an Ethiopian grade 11 book): "6% interest rate per year, compounded
quarterly" was worked monthly, and the card's interest was off by birr. A product that
grows money (``Product.settings`` has ``per_year``) works the frequency said; a loan or a
card is worked monthly, so a request saying any other frequency for one is left to the
model. A frequency the catalog cannot write as a count a year ("compounded continuously",
"bi-monthly", "every 2 months") is never read as monthly: the request is left too.
"""

from __future__ import annotations

import re

# (said after "compounded", said as the describing word of "compounding", times a year).
# Only a single word goes before: "deposit 100 every month, compounded quarterly" is
# deposited monthly and compounded quarterly.
_FREQUENCIES: tuple[tuple[str, str, int], ...] = (
    (r"semi-?annual(?:ly)?|half-?yearly|half\syearly|twice\s(?:a|per|each)\syear"
     r"|every\s(?:6|six)\smonths|every\shalf\syear", r"semi-?annual|half-?yearly", 2),
    (r"quarterly|every\squarter|each\squarter|every\s(?:3|three)\smonths"
     r"|(?:4|four)\stimes\s(?:a|per)\syear", "quarterly", 4),
    (r"monthly|every\smonth|each\smonth|(?:12|twelve)\stimes\s(?:a|per)\syear", "monthly", 12),
    (r"weekly|every\sweek|each\sweek", "weekly", 52),
    (r"daily|every\sday|each\sday", "daily", 365),
    (r"annual(?:ly)?|yearly|every\syear|each\syear|once\s(?:a|per)\syear", "annual|yearly", 1),
)  # fmt: skip
_WORD = r"\bcompound(?:ed|ing|s)?\b(?:\s+interest)?(?:\s+is)?\s+"
_SAID = [
    (re.compile(rf"{_WORD}(?:{after})\b|(?<![\w-])(?:{before})\s+compounding\b", re.I), count)
    for after, before, count in _FREQUENCIES
]
# A frequency of a shape the list has no count for.
_OTHER = re.compile(
    rf"{_WORD}(?:continu\w*|bi-?\w+|semi-?month\w*|fortnight\w*|every\b|each\b|twice\b|"
    r"once\b|\w+\s+times\b)"
    r"|\b(?:continuous|continual|bi-?\w+|semi-?monthly|fortnightly)\s+compounding\b",
    re.I,
)

UNKNOWN = 0


def compounding_per_year(text: str) -> int | None:
    """Times a year ``text`` says interest compounds; None when it says none, ``UNKNOWN``
    (0) when it says one the catalog cannot write, or two that disagree."""
    said = {count for pattern, count in _SAID if pattern.search(text)}
    if len(said) > 1:
        return UNKNOWN
    if said:
        return said.pop()
    return UNKNOWN if _OTHER.search(text) else None
