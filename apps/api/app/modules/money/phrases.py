"""The pieces every money reader shares: a percent, a length of time, a sum and its currency.

``read`` (a first ask), ``change_line`` (a follow-up) and ``purchase`` (a loan told over two
lines) read these the same way, so "seven years" is a term in all three.
"""

from __future__ import annotations

import re

from app.services.number_text import NUMBER_WORDS, count_word_pattern

# A count in words, as a book writes a term: "seven", "twenty-five", "two and a half".
_TENS = "|".join(word for word, value in NUMBER_WORDS.items() if value >= 20)
_ONES = count_word_pattern(low=1, high=9)
_SPELLED = (
    rf"(?:(?:{_TENS})(?:[\s-](?:{_ONES}))?|{count_word_pattern(low=1, high=19)})"
    r"(?:\sand\sa\shalf)?"
)
PERCENT = r"(?P<pct>\d{1,3}(?:\.\d{1,4})?)\s?(?:%|percent\b|per\s?cent\b|pct\b)"
# A length of time; its count is ``count_value``'s.
DURATION = (
    rf"(?P<n>\d{{1,3}}(?:\.\d{{1,2}})?|{_SPELLED})\s?-?\s?(?P<unit>years?|yrs?|months?|mos?)\b"
)
RATE = re.compile(PERCENT, re.I)
TERM = re.compile(rf"\b{DURATION}", re.I)
AMOUNT = re.compile(
    r"(?P<sym>[$€£¥₹₦])?\s?(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)"
    r"(?:\s?(?P<mult>k|m|thousand|million|mil|grand)\b)?",
    re.I,
)
MULTIPLIERS = {"k": 1e3, "thousand": 1e3, "grand": 1e3, "m": 1e6, "million": 1e6, "mil": 1e6}
CURRENCY_WORDS = (
    r"dollars?|bucks|usd|euros?|eur|pounds?|gbp|birr|etb|rupees?|inr|naira|ngn|"
    r"shillings?|kes|yen|jpy|cad|aud"
)
CURRENCY_WORD = re.compile(rf"\s?({CURRENCY_WORDS})\b", re.I)


def sum_phrase(name: str) -> str:
    """A sum as a phrase in a lower-cased line ("$20k", "3 grand"), read by ``read_sum``."""
    return (
        rf"(?P<{name}>[$€£¥₹₦]?\s?\d[\d,]*(?:\.\d{{1,2}})?"
        rf"(?:\s?(?:k|m|thousand|million|mil|grand))?(?:\s(?:{CURRENCY_WORDS}))?)"
    )


def count_value(text: str) -> float:
    """A duration's count, in digits or words: "3.5", "seven", "twenty-five", "two and a half"."""
    words = text.lower().replace("-", " ").split()
    if not words or words[0] not in NUMBER_WORDS:
        return float(text)
    half = words[-3:] == ["and", "a", "half"]
    return sum(NUMBER_WORDS[word] for word in words[: -3 if half else None]) + 0.5 * half
