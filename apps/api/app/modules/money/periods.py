"""How often a request's rate, payments and deposits run: "2% per month", "48 monthly payments".

Live (2026-11-14, an Ethiopian grade 12 book): "repay the loan in 48 equal monthly payments.
If the bank charges 2% per month on the unpaid balance, compounded monthly, how much is each
payment?" was worked as a yearly rate of 2% over a 5-year term it assumed: 1,665.14 a month,
where the loan costs 3,097.17. The catalog's rates are yearly and its terms years or months,
so the reader says what the words mean in those, or works nothing:

- A rate's period is said beside its percent: after it ("2% per month", "1% a month", "3%
  per quarter", "12% per annum", "2% interest per month", "2% monthly interest") or before
  it ("a monthly rate of 2%", "the interest rate per quarter is 3%"). Its yearly rate is the
  percent times its periods a year, as an APR is: 2% a month is 24% a year. A describing
  word alone after a percent ("1.5% monthly", "4% quarterly") may be the rate's period or
  how often it is paid or compounded, so it is ``UNKNOWN`` unless it is a year's ("6%
  annually", "12% p.a."): both readings are one yearly rate then. One before a payment or a
  compounding ("6% monthly payments", "5% quarterly compounded") is not the rate's at all.
- A period said of the interest or the rate away from the percent ("interest per month at
  the rate of 2%", "pays interest each month at 4%", "the quarterly rate") must be the one
  the percent's own words say; with none beside the percent, nothing is worked.
- How often payments or deposits run: "48 equal monthly payments", "quarterly installments",
  "payments made each quarter", "repaid quarterly", "12 payments a year". Every two weeks,
  twice a month or daily is no frequency a product pays (``FREQUENCIES`` has no key for it).
- A count of payments is a term: "48 monthly payments" is 4 years, "8 quarterly payments" 2.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.modules.money.compounding import UNKNOWN
from app.modules.money.phrases import COUNT, count_value


@dataclass(frozen=True)
class Frequency:
    """A period a rate or a payment may run by, in the block's words and the card's label."""

    per_year: int
    adjective: str  # "quarterly": a "quarterly payment"
    per: str  # "a quarter": "3% a quarter"
    # The card's label for a payment made this often; "" when no product pays so.
    payment_key: str = ""


FREQUENCIES: dict[int, Frequency] = {
    item.per_year: item
    for item in (
        Frequency(1, "yearly", "a year", "money.yearly_payment"),
        Frequency(2, "half-yearly", "every half-year", "money.semiannual_payment"),
        Frequency(4, "quarterly", "a quarter", "money.quarterly_payment"),
        Frequency(12, "monthly", "a month", "money.monthly_payment"),
        Frequency(52, "weekly", "a week", "money.weekly_payment"),
        Frequency(365, "daily", "a day"),
    )
}

# (a period named after "per", "a", "each" or "every"; named as a describing word; its
# abbreviation, a "per" of its own; times a year). Every two weeks, twice a month and every
# two months are said too, so they are never read as a week or a month: no product works
# them (``UNKNOWN``).
_WORDS: tuple[tuple[str, str, str, int], ...] = (
    (r"years?|yrs?|annum", r"annual(?:ly)?|yearly", r"p\.\s?a\.?|pa", 1),
    (r"half[\s-]?years?|six\s+months|6\s+months",
     r"semi[\s-]?annual(?:ly)?|half[\s-]?yearly", "", 2),
    (r"quarters?|three\s+months|3\s+months", r"quarterly", "", 4),
    (r"months?|mos?", r"monthly", r"p\.\s?m\.?", 12),
    (r"weeks?|wks?", r"weekly", "", 52),
    (r"days?", r"daily", "", 365),
    (r"(?:two|2)\s+(?:weeks|months)|fortnight|other\s+(?:week|month)",
     r"bi[\s-]?(?:weekly|monthly)|fortnightly|semi[\s-]?monthly|twice[\s-]monthly", "", UNKNOWN),
)  # fmt: skip
_NOUNS = "|".join(rf"(?P<n{index}>{noun})" for index, (noun, _, _, _) in enumerate(_WORDS))
_ADJECTIVES = "|".join(rf"(?P<a{index}>{word})" for index, (_, word, _, _) in enumerate(_WORDS))
_SHORT = "|".join(
    rf"(?P<s{index}>{short})" for index, (_, _, short, _) in enumerate(_WORDS) if short
)
_PER = r"(?:per|a|an|each|every|/)\s*"
_NOUN = rf"(?:{_PER}(?:{_NOUNS})\b|(?<![\w.])(?:{_SHORT})(?![\w.]))"
_ADJECTIVE = rf"(?<![\w-])(?:{_ADJECTIVES})(?![\w-])"
_FLOW = r"(?:re)?payments?|instal(?:l)?ments?|deposits?|contributions?"
_RATE_WORDS = r"(?:interest\s+rate|interest|rate)"
# After a rate's percent: "2% per month", "2% interest per month" ("a month ago" is a time),
# "2% monthly interest", or a describing word on its own ("6% annually", "1.5% monthly").
# Each starts at the end of a word and reads its space once, so a run of spaces is read
# in one pass.
_RATE_NOUN_AFTER = re.compile(rf"(?<!\s)(?:\s++{_RATE_WORDS})?\s*+{_NOUN}(?!\s+ago\b)", re.I)
_RATE_ADJECTIVE_AFTER = re.compile(rf"(?<!\s)\s++{_ADJECTIVE}(?P<rate>\s++{_RATE_WORDS}\b)?", re.I)
# A describing word after a percent that is a payment's or a compounding's, not the rate's.
_NOT_THE_RATES = re.compile(rf"(?<!\s)\s++(?:(?:equal|level)\s++)?(?:{_FLOW}|compound\w*)\b", re.I)
# Another payee's payments are not the loan's: "property tax payments each year".
_OTHER_PAYEE = re.compile(
    r"\b(?:rent|tax(?:es)?|insurance|premiums?|bills?|phone|utilit(?:y|ies)|tuition"
    r"|subscriptions?|membership|salary|wages?|pension|dividends?|alimony|support)\s+$",
    re.I,
)
# Before it: "a monthly rate of 2%", "monthly interest of 2%", "the interest rate per month
# is 2%". "Monthly interest at 4%" and "interest each month at 4%" may be interest paid
# monthly at a yearly 4%: not read.
_RATE_BEFORE = (
    re.compile(
        rf"{_ADJECTIVE}\s+(?:(?:interest|percentage)\s+)?rate\s*(?:(?:of|is|was|at)\s+|[:=]\s*)?$",
        re.I,
    ),
    re.compile(rf"{_ADJECTIVE}\s+interest\s*(?:(?:of|is|was)\s+|[:=]\s*)?$", re.I),
    re.compile(rf"\b(?:interest\s+)?rate\s+{_NOUN}\s*(?:(?:of|is|was|at)\s+|[:=]\s*)?$", re.I),
    re.compile(rf"\binterest\s+{_NOUN}\s*(?:(?:of|is|was)\s+|[:=]\s*)?$", re.I),
)
# The interest or the rate said to run by a period anywhere: "interest per month", "the
# quarterly rate", "interest rate each month".
_RATE_PERIOD = re.compile(
    rf"\b{_RATE_WORDS}\s+{_NOUN}|{_ADJECTIVE}\s+(?:interest\s+)?rates?\b", re.I
)
# How often payments or deposits run: "48 equal monthly payments", "quarterly installments";
# "payments made each quarter", "repaid quarterly", "pay it back monthly".
_FLOW_BEFORE = re.compile(
    rf"{_ADJECTIVE}\s+(?:(?:equal|level|fixed|regular|loan|mortgage)\s+)?(?:{_FLOW})\b", re.I
)
_FLOW_AFTER = re.compile(
    rf"\b(?:{_FLOW}|repa(?:y|ys|id|ying)(?:\s+(?:it|them|the\s+loan|the\s+balance))?"
    r"|pa(?:y|ys|id|ying)(?:\s+(?:it|them))?(?:\s+(?:back|off))?)"
    rf"\s+(?:(?:are|is|will\s+be|to\s+be|be)\s+)?(?:(?:made|due|paid)\s+)?(?:{_NOUN}|{_ADJECTIVE})",
    re.I,
)
# Someone paid by the period is a wage, not a loan's payment: "I get paid weekly".
_PAID_PERSON = re.compile(
    r"\b(?:get|gets|got|getting|am|i'?m|we'?re|is|are|was|were|being|be)\s+$", re.I
)
# An EMI is an equated monthly instalment: "repaid in 24 EMIs".
_EMI = re.compile(r"\bEMIs?\b", re.I)
# "12 payments a year": the count is the frequency, never a yearly payment or a term.
_A_YEAR = r"\s+(?:per|a|each|every)\s+(?:year|yr|annum)\b"
_TIMES_A_YEAR = re.compile(rf"\b(?P<count>\d{{1,3}})\s+(?:{_FLOW}){_A_YEAR}", re.I)
# A count of payments or deposits: "48 equal monthly payments", "24 monthly instalments",
# "60 payments"; its frequency is its describing word's, else the message's.
PAYMENT_COUNT = re.compile(
    rf"(?<![\w.,$€£¥₹₦])(?P<count>{COUNT})\s+(?:(?:equal|level|fixed|regular|consecutive"
    rf"|successive|more)\s+){{0,2}}(?:{_ADJECTIVE}\s+)?(?:(?:equal|level|loan|mortgage)\s+)?"
    rf"(?:{_FLOW}|(?P<emi>EMIs?))\b(?!{_A_YEAR})",
    re.I,
)
# Payments gone by or a part of the term: "after 12 payments", "missed 2 payments", "the
# first 12 monthly payments".
_COUNT_GONE = re.compile(r"\b(?:made|missed|skipped|after|first|paid|late)\s+$", re.I)
# A length in another period than a year or a month: "8 quarters", "104 weeks", "90 days".
OTHER_DURATION = re.compile(
    rf"\b(?P<n>{COUNT})\s?-?\s?(?P<unit>quarters?|weeks?|wks?|days?)\b(?!\s+ago\b)", re.I
)
# A sum's period said before it: "monthly deposits of $200", "quarterly payments of 500".
_SUM_PERIOD = re.compile(
    rf"{_ADJECTIVE}\s+(?:{_FLOW})(?:\s+(?:of|is|are|was|were))?\s*+[:=]?\s*+$", re.I
)


def _times(match: re.Match[str]) -> int:
    """Times a year of the period ``match`` named."""
    found = match.groupdict()
    return next(
        count
        for index, (_, _, _, count) in enumerate(_WORDS)
        if any(found.get(f"{kind}{index}") for kind in "nas")
    )


def _one(said: set[int]) -> int | None:
    """The one period said; None for none, ``UNKNOWN`` for two."""
    if len(said) > 1:
        return UNKNOWN
    return next(iter(said), None)


def rate_period(text: str, start: int, end: int) -> int | None:
    """Times a year the percent at ``text[start:end]`` is charged by its own words, or None
    when they say none (a yearly rate); ``UNKNOWN`` when they say one no product reads."""
    after = _RATE_NOUN_AFTER.match(text, end)
    if after is not None:
        return _times(after)
    after = _RATE_ADJECTIVE_AFTER.match(text, end)
    if after is not None and after.group("rate"):
        return _times(after)
    if after is not None and not _NOT_THE_RATES.match(text, after.end()):
        # "1.5% monthly" may be paid or compounded monthly at a yearly 1.5%; a year's word
        # is one yearly rate either way.
        return 1 if _times(after) == 1 else UNKNOWN
    before = text[max(0, start - 60) : start]
    for pattern in _RATE_BEFORE:
        found = pattern.search(before)
        if found is not None:
            return _times(found)
    return None


def rate_periods_said(text: str) -> set[int]:
    """Every period the message says the interest or the rate runs by, anywhere in it."""
    return {_times(match) for match in _RATE_PERIOD.finditer(text)}


def flow_frequency(text: str) -> int | None:
    """Times a year the message's payments or deposits are made; None when it says no
    frequency, ``UNKNOWN`` for one no product pays or two that disagree."""
    said = {int(match["count"]) for match in _TIMES_A_YEAR.finditer(text)}
    if _EMI.search(text):
        said.add(12)
    rest = _TIMES_A_YEAR.sub(" ", text)
    for pattern in (_FLOW_BEFORE, _FLOW_AFTER):
        said |= {
            _times(match)
            for match in pattern.finditer(rest)
            if not _paid_to_another(rest[max(0, match.start() - 24) : match.start()])
        }
    found = _one(said)
    if found is not None and found != UNKNOWN and not paid_by(found):
        return UNKNOWN
    return found


def _paid_to_another(before: str) -> bool:
    """The payments or the pay after ``before`` are another payee's or a wage."""
    return bool(_OTHER_PAYEE.search(before) or _PAID_PERSON.search(before))


def paid_by(per_year: int) -> bool:
    """A payment made ``per_year`` times a year is one a product works and labels."""
    frequency = FREQUENCIES.get(per_year)
    return frequency is not None and bool(frequency.payment_key)


def payment_counts(text: str) -> list[tuple[re.Match[str], float, int | None]]:
    """Each count of payments the message states, its number and the frequency its own words
    give (None: the count says none, "60 payments"). Payments gone by are left out."""
    counts = []
    for match in PAYMENT_COUNT.finditer(text):
        if _COUNT_GONE.search(text[max(0, match.start() - 12) : match.start()]):
            continue
        said = match.groupdict()
        own = 12 if said.get("emi") else None
        own = next(
            (count for index, (_, _, _, count) in enumerate(_WORDS) if said.get(f"a{index}")),
            own,
        )
        counts.append((match, count_value(match["count"]), own))
    return counts


def sum_period(before: str) -> int | None:
    """Times a year a sum is paid, said before it ("monthly deposits of $200"), or None."""
    found = _SUM_PERIOD.search(before)
    return _times(found) if found is not None else None


def rate_words(rate: float, per_year: int) -> str:
    """A yearly ``rate`` as the user said it: 24 at 12 a year is "2% a month"."""
    frequency = FREQUENCIES[per_year]
    return f"{round(rate / per_year, 4):g}% {frequency.per}"
