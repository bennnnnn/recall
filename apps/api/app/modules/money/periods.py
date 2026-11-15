"""How often a request's rate, payments and deposits run, in one vocabulary every reader uses.

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
- How often payments or deposits run, when they are the loan's own (``schedule``): "48
  equal monthly payments", "quarterly installments", "repaid quarterly", "12 payments a
  year". Every two weeks, twice a month or daily is no frequency a product pays
  (``FREQUENCIES`` has no key for it).
- A period is said as a word ("quarterly"), after "per", "a", "each" or "every" ("each
  quarter"), as a count ("twice a year", "four times a year", "every 3 months", "every six
  months", spelled or in digits) or abbreviated ("p.a.", "pm"). Compounding (``compounding``),
  sums (``sums``) and payments (``schedule``) read periods with this one vocabulary
  (2026-11-14 review: "compounded twice a year" was read while "paid twice a year" was
  silently monthly).
- A period said as a time is none ("6% a month from now", "a month ago", "in a month", "for
  a year").
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.modules.money.phrases import COUNT, count_value

# A period no product works, or two that disagree: the request gets no worked numbers.
UNKNOWN = 0


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
    (r"half[\s-]?years?", r"semi[\s-]?annual(?:ly)?|half[\s-]?yearly", "", 2),
    (r"quarters?", r"quarterly", "", 4),
    (r"months?|mos?", r"monthly", r"p\.\s?m\.?|pm", 12),
    (r"weeks?|wks?", r"weekly", "", 52),
    (r"days?", r"daily", "", 365),
    (r"fortnight|other\s+(?:week|month)",
     r"bi[\s-]?(?:weekly|monthly)|fortnightly|semi[\s-]?monthly|twice[\s-]monthly", "", UNKNOWN),
)  # fmt: skip
# A period's unit, for a count of them: "twice a year", "every 3 months".
_UNITS = {"year": 1, "quarter": 4, "month": 12, "week": 52, "day": 365}
_ONCE = {"once": 1, "twice": 2, "thrice": 3}
_COUNTED = (
    rf"(?P<times>once|twice|thrice|{COUNT}\s+times)\s+(?:a|per|each|every)\s+"
    r"(?P<tunit>year|quarter|month|week|day)\b"
    rf"|(?:every|each)\s+(?P<every>{COUNT})\s+(?P<eunit>years?|quarters?|months?|weeks?|days?)\b"
)
_NOUNS = "|".join(rf"(?P<n{index}>{noun})" for index, (noun, _, _, _) in enumerate(_WORDS))
_ADJECTIVES = "|".join(rf"(?P<a{index}>{word})" for index, (_, word, _, _) in enumerate(_WORDS))
_SHORT = "|".join(
    rf"(?P<s{index}>{short})" for index, (_, _, short, _) in enumerate(_WORDS) if short
)
# "A month" said as a time is no period: "6% a month from now", "a month ago", "a year
# later", "in a month", "within a year", "for a year".
_A_TIME = r"\s++(?:ago|from\s++(?:now|today|then)|later|earlier|hence|away|ahead|prior)\b"
_PER = (
    r"(?:(?<!\bin\s)(?<!\bwithin\s)(?<!\bfor\s)(?<!\bafter\s)(?:a|an)\s*"
    r"|(?:per|each|every|/)\s*)"
)
NOUN = rf"(?:{_COUNTED}|{_PER}(?:{_NOUNS})\b(?!{_A_TIME})|(?<![\w.])(?:{_SHORT})(?![\w.]))"
ADJECTIVE = rf"(?<![\w-])(?:{_ADJECTIVES})(?![\w-])"
# Any period in the vocabulary: "quarterly", "each quarter", "twice a year", "p.a.".
PERIOD = re.compile(rf"{NOUN}|{ADJECTIVE}", re.I)
FLOW = r"(?:re)?payments?|instal(?:l)?ments?|deposits?|contributions?"
_RATE_WORDS = r"(?:interest\s+rate|interest|rate|apr|apy)"
# After a rate's percent: "2% per month", "2% interest per month", "2% monthly interest",
# "2% (per month)", or a describing word on its own ("6% annually", "1.5% monthly", "2%
# interest monthly", "2% [monthly]"). Each starts at the end of a word and reads its space
# once, so a run of spaces is read in one pass.
_BRACKET = r"(?:\s*+[(\[]\s*+|\s++)"
_RATE_NOUN_AFTER = re.compile(rf"(?<!\s)(?:\s++{_RATE_WORDS})?(?:{_BRACKET}|){NOUN}", re.I)
_RATE_ADJECTIVE_AFTER = re.compile(
    rf"(?<!\s)(?:\s++{_RATE_WORDS})?{_BRACKET}{ADJECTIVE}(?P<rate>\s++{_RATE_WORDS}\b)?", re.I
)
# A describing word after a percent that is a payment's or a compounding's, not the rate's.
_NOT_THE_RATES = re.compile(rf"(?<!\s)\s++(?:(?:equal|level)\s++)?(?:{FLOW}|compound\w*)\b", re.I)
# Before it: "a monthly rate of 2%", "monthly interest of 2%", "the interest rate per month
# is 2%". "Monthly interest at 4%" and "interest each month at 4%" may be interest paid
# monthly at a yearly 4% (``_INTEREST_AT``).
_RATE_BEFORE = (
    re.compile(
        rf"{ADJECTIVE}\s+(?:(?:interest|percentage)\s+)?rate\s*(?:(?:of|is|was|at)\s+|[:=]\s*)?$",
        re.I,
    ),
    re.compile(rf"{ADJECTIVE}\s+interest\s*(?:(?:of|is|was)\s+|[:=]\s*)?$", re.I),
    re.compile(rf"\b(?:interest\s+)?rate\s+{NOUN}\s*(?:(?:of|is|was|at)\s+|[:=]\s*)?$", re.I),
    re.compile(rf"\binterest\s+{NOUN}\s*(?:(?:of|is|was)\s+|[:=]\s*)?$", re.I),
)
# The interest's period said before the percent, "at" it: "monthly interest at 2%", "interest
# per month at 2%". It may be 2% a month or a yearly 2% paid each month, so only a year's is
# read ("annual interest at 6%").
_INTEREST_AT = re.compile(rf"(?:{ADJECTIVE}\s++interest|\binterest\s++{NOUN})\s++at\s*+$", re.I)
# The interest or the rate said to run by a period anywhere: "interest per month", "the
# quarterly rate", "interest rate each month".
_RATE_PERIOD = re.compile(rf"\b{_RATE_WORDS}\s+{NOUN}|{ADJECTIVE}\s+(?:interest\s+)?rates?\b", re.I)
# "12 payments a year": the count is the frequency, never a yearly payment or a term.
_A_YEAR = r"\s+(?:per|a|each|every)\s+(?:year|yr|annum)\b"
# A count of payments or deposits: "48 equal monthly payments", "24 monthly instalments",
# "60 payments"; its frequency is its describing word's, else the message's.
PAYMENT_COUNT = re.compile(
    rf"(?<![\w.,$€£¥₹₦])(?P<count>{COUNT})\s+(?:(?:equal|level|fixed|regular|consecutive"
    rf"|successive|more)\s+){{0,2}}(?:{ADJECTIVE}\s+)?(?:(?:equal|level|loan|mortgage)\s+)?"
    rf"(?:{FLOW}|(?P<emi>EMIs?))\b(?!{_A_YEAR})",
    re.I,
)
# A length in another period than a year or a month: "8 quarters", "104 weeks", "90 days".
OTHER_DURATION = re.compile(
    rf"\b(?P<n>{COUNT})\s?-?\s?(?P<unit>quarters?|weeks?|wks?|days?)\b(?!\s+ago\b)", re.I
)
# A sum's period said before it: "monthly deposits of $200", "quarterly payments of 500".
_SUM_PERIOD = re.compile(
    rf"{ADJECTIVE}\s+(?:{FLOW})(?:\s+(?:of|is|are|was|were))?\s*+[:=]?\s*+$", re.I
)


def times_a_year(match: re.Match[str]) -> int:
    """Times a year of the period ``match`` named; ``UNKNOWN`` for a count of periods that is
    no whole number a year ("every 5 months", "every 2 years")."""
    found = match.groupdict()
    if found.get("times"):
        said = found["times"].lower()
        count = _ONCE.get(said) or count_value(said.rsplit(None, 1)[0])
        return _whole(count * _UNITS[found["tunit"].lower()])
    if found.get("every"):
        unit = found["eunit"].lower().rstrip("s")
        return _whole(_UNITS[unit] / count_value(found["every"]))
    return next(
        count
        for index, (_, _, _, count) in enumerate(_WORDS)
        if any(found.get(f"{kind}{index}") for kind in "nas")
    )


def _whole(per_year: float) -> int:
    return int(per_year) if per_year >= 1 and float(per_year).is_integer() else UNKNOWN


def rate_spans(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """Where the percent at ``text[start:end]`` says its own period, as ``rate_period``
    reads it ("2% per month", "a monthly rate of 2%"): those words are the rate's, never a
    payment's. "6% monthly payments" says none: "monthly" there is the payments'."""
    after = _RATE_NOUN_AFTER.match(text, end)
    if after is not None:
        return [after.span()]
    after = _RATE_ADJECTIVE_AFTER.match(text, end)
    if after is not None and (after.group("rate") or not _NOT_THE_RATES.match(text, after.end())):
        return [after.span()]
    offset = max(0, start - 60)
    before = text[offset:start]
    for pattern in (*_RATE_BEFORE, _INTEREST_AT):
        found = pattern.search(before)
        if found is not None:
            return [(offset + found.start(), offset + found.end())]
    return []


def rate_period(text: str, start: int, end: int) -> int | None:
    """Times a year the percent at ``text[start:end]`` is charged by its own words, or None
    when they say none (a yearly rate); ``UNKNOWN`` when they say one no product reads."""
    after = _RATE_NOUN_AFTER.match(text, end)
    if after is not None:
        return times_a_year(after)
    after = _RATE_ADJECTIVE_AFTER.match(text, end)
    if after is not None and after.group("rate"):
        return times_a_year(after)
    if after is not None and not _NOT_THE_RATES.match(text, after.end()):
        # "1.5% monthly" may be paid or compounded monthly at a yearly 1.5%; a year's word
        # is one yearly rate either way.
        return 1 if times_a_year(after) == 1 else UNKNOWN
    before = text[max(0, start - 60) : start]
    for pattern in _RATE_BEFORE:
        found = pattern.search(before)
        if found is not None:
            return times_a_year(found)
    found = _INTEREST_AT.search(before)
    if found is not None:
        return 1 if times_a_year(found) == 1 else UNKNOWN
    return None


def rate_periods_said(text: str) -> set[int]:
    """Every period the message says the interest or the rate runs by, anywhere in it."""
    return {times_a_year(match) for match in _RATE_PERIOD.finditer(text)}


def rate_periods_spans(text: str) -> list[tuple[int, int]]:
    """Where the message says the interest or the rate runs by a period: "interest per
    month", "the quarterly rate"."""
    return [match.span() for match in _RATE_PERIOD.finditer(text)]


def paid_by(per_year: int) -> bool:
    """A payment made ``per_year`` times a year is one a product works and labels."""
    frequency = FREQUENCIES.get(per_year)
    return frequency is not None and bool(frequency.payment_key)


def payment_counts(text: str) -> list[tuple[re.Match[str], float, int | None]]:
    """Each count of payments the message states, its number and the frequency its own words
    give (None: the count says none, "60 payments"). Whether it is the term is ``terms``'."""
    counts = []
    for match in PAYMENT_COUNT.finditer(text):
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
    return times_a_year(found) if found is not None else None


def rate_words(rate: float, per_year: int) -> str:
    """A yearly ``rate`` as the user said it: 24 at 12 a year is "2% a month"."""
    frequency = FREQUENCIES[per_year]
    return f"{round(rate / per_year, 4):g}% {frequency.per}"
