"""What every period word in a request belongs to, and how often the loan is paid.

Two reviews of the rate-period reader (2026-11-14) found a frequency that belonged to
something else setting the loan's schedule ("how much do I pay annually?" worked as one
payment a year; "My salary is $4,000, paid weekly" and "I also have a car lease; the
payments are quarterly" made a mortgage weekly or quarterly), and a rate's period said a few
words from its percent read as a yearly rate ("The bank charges 2% on the unpaid balance
each month"). Each period word is now given what it belongs to, and only a positive form
changes anything:

- the rate's own period beside its percent ("2% per month", "a monthly rate of 2%",
  ``periods.rate_spans``), a compounding's ("compounded quarterly"), a sum's ("$200 a
  month"), the payments' ("quarterly payments", "repaid weekly", "pay it monthly"), an
  amount asked ("how much a month", "cost per month"), or another noun's ("annual income",
  "quarterly taxes"). Anything else is loose.
- A loose period in a percent's sentence leaves the rate unknown, never yearly
  (``loose_rate_period``).
- How often the loan is paid is read only from the loan's own sentence (the one naming it or
  its rate), in a message naming one loan, in one positive form: its payments' noun phrase
  with only a count, a sum, "equal" or the loan's name in it, opened by a word such as
  "with", "in" or "the", with nothing after it but a sum, a term, a rate or the clause's end
  ("in 8 equal quarterly payments", "payments are made each quarter", "12 payments a
  year"); or the loan repaid or paid, as its own participle or with the loan as object
  ("a loan of $10,000 at 6%, payable quarterly", "repay it monthly"). A non-monthly period
  of the payments in any other form, there or in a sentence about payments, makes the
  schedule unknown, so nothing is worked; one in a sentence about something else ("My
  salary is $4,000, paid weekly.") is ignored. A question about a period's total ("how much
  do I pay annually?") changes nothing: the loan stays monthly.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Iterator
from dataclasses import dataclass
from typing import Literal

from app.modules.money.periods import (
    FLOW,
    OTHER_DURATION,
    PERIOD,
    UNKNOWN,
    paid_by,
    rate_periods_spans,
    rate_spans,
    times_a_year,
)
from app.modules.money.phrases import COUNT, CURRENCY_WORDS, RATE, TERM, count_value

Role = Literal["rate", "compounding", "sum", "payments", "asked", "describes", "loose"]
Schedule = Literal["said", "asked", "total", ""]

# An EMI is an equated monthly instalment: "repaid in 24 EMIs".
_EMI = re.compile(r"\bEMIs?\b", re.I)
# The payments named at all: "monthly payments", "each instalment", "my EMI"; a down payment
# is not one.
_NAMES_PAYMENTS = re.compile(
    r"(?<!down\s)(?<!down-)\b(?:(?:re)?payments?|instal(?:l)?ments?|EMIs?)\b", re.I
)
# Where a sentence ends: never a decimal point ("6.5%") or an abbreviation ("p.a.", "Rs.").
_SENTENCE_END = re.compile(r"(?<![.\s][a-z])(?<!\bRs)(?<!\bvs)[.?!;](?=\s|$)|\n", re.I)
_CLAUSE = re.compile(
    r"[.?!;:,(\n](?=\s|$)|\b(?:and|but|so|then|if|when|while|because|although|though|or)\b",
    re.I,
)
_SUM = (
    rf"(?:(?:{CURRENCY_WORDS})\s)?(?:[$€£¥₹₦]\s?)?\d[\d,.]*+"
    rf"(?:\s?(?:k|m|thousand|million|grand))?(?:\s?(?:{CURRENCY_WORDS}))?"
)
_PERCENT = r"\d{1,3}(?:[.,]\d{1,4})?\s?(?:%|percent\b|per\s?cent\b|pct\b)"
_TERM = rf"(?:{COUNT})\s?-?\s?(?:years?|yrs?|months?|mos?)\b"

# --- What a period word belongs to ----------------------------------------------------

_COMPOUNDING_BEFORE = re.compile(
    r"\bcompound(?:ed|ing|s)?(?:\s+interest)?(?:\s+(?:is|are))?\s+(?:on\s+an?\s+)?$", re.I
)
_COMPOUNDING_AFTER = re.compile(r"\s+(?:basis\s+)?compound(?:ed|ing)\b", re.I)
_SUM_BEFORE = re.compile(rf"(?<![\w.,]){_SUM}\s?(?:at\s+the\s+end\s+of\s+)?$", re.I)
# "quarterly payments", "monthly car loan payments": up to three words between.
_NOUN_AFTER = re.compile(rf"(?P<words>(?:\s++[\w'\u2019-]++){{0,3}}?)\s++(?P<noun>{FLOW})\b", re.I)
# "payments each quarter", "the payments are quarterly", "payments made each quarter".
_NOUN_BEFORE = re.compile(
    rf"\b(?P<noun>{FLOW})\s++(?:(?:are|is|was|were|be|will\s++be|to\s++be|must\s++be)\s++)?"
    r"(?:(?:made|due|paid|payable)\s++)?$",
    re.I,
)
_OBJECT = (
    r"(?:it|them|him|her|me|us"
    r"|(?:the|this|that|my|our|his|her|their|your)(?:\s++[\w'\u2019-]++){1,3}?)"
)
# Paying or being paid: "repaid quarterly", "pay it back weekly", "paying it weekly",
# "payable quarterly", "paid weekly".
_PAID = re.compile(
    rf"\b(?P<verb>repa(?:y|ys|id|ying|yable)|pa(?:y|ys|id|ying|yable))"
    rf"(?:\s++(?P<object>{_OBJECT}))?(?:\s++(?:back|off))?\s++$",
    re.I,
)
_ASKED_BEFORE = re.compile(
    r"\b(?:how\s++much|what(?:['\u2019]s)?|cost(?:s|ing)?|spend|budget)\b"
    r"(?:\s++(?:is|it|that|this|would|will|be|me|us|you|i|we|do|does|did|per))*\s*+$",
    re.I,
)
_BASIS = re.compile(r"\bon\s+an?\s+$", re.I)
_BASIS_AFTER = re.compile(r"\s+basis\b", re.I)
# A describing word before another noun: "annual income", "quarterly taxes". A word that
# only joins ("applied monthly to the balance", "weekly or monthly") is no noun.
_WORD_AFTER = re.compile(r"\s++(?P<word>[a-z]+)", re.I)
_JOINS = frozenset(
    "to and or nor on in at for from with by of the a an is are was were be until over into "
    "after before so but if then than as per each every it its this that which while when "
    "instead basis".split()
)

# --- The loan's own schedule ----------------------------------------------------------

_BETWEEN = frozenset("equal level fixed regular".split())
# Words that open a payment's noun phrase: a determiner, a preposition, a verb of paying or
# having, a question's word, a conjunction, the rate or the term said just before ("at 6%
# quarterly payments"). "HOA", "extra" and "tax" do not.
_OPENS = frozenset(
    "a an the its his her their my our your these those each every all both any this that "
    "with in by of via through over on for as into at under across from within after "
    "make makes making made pay pays paying paid repay repays repaid repaying repayable "
    "payable is are was were be been being take takes taking took have has had having want "
    "wants need needs choose chooses prefer prefers do does did afford affords get gets got "
    "schedule scheduled set split spread divided owe owes plan plans use using offer offers "
    "require requires allow allows agree agreed find calculate compute determine work what "
    "what's whats which how it's that's there and then but so also percent pct year years yr "
    "yrs month months mos total regular usual estimated expected current new".split()
)
_OFFERS = frozenset("or nor vs vs. versus either".split())  # "weekly or monthly payments"
_MODIFIER = re.compile(
    rf"{COUNT}|{_SUM}|equal|level|fixed|regular|consecutive|successive|scheduled", re.I
)
_PHRASE_WORDS = 5
_CLAUSE_END = ",.;:!?(\u2013\u2014-"
# What may follow the loan's own payments: nothing, a sum, a term, a rate.
_CLEAN_AFTER = re.compile(
    rf"\s*+(?:$|[,.;:!?)\]]|(?:and|but|so|then|which|that|starting|beginning)\b"
    rf"|of\s++{_SUM}|(?:for|over|in)\s++{_TERM}|at\s++{_PERCENT}"
    rf"|(?:on|to|toward|towards|into|for)\s++(?P<payee>(?:it|them)\b|(?:a|an|the|this|that|my|"
    r"our|his|her|their|your)(?:\s++[\w'\u2019-]++){1,3}))",
    re.I,
)
_OFFERED = re.compile(r"\s*+,?\s*+(?:or|nor|vs\.?|versus)\s++", re.I)
_COUNT_BEFORE = re.compile(
    rf"(?<![\w.,])(?P<count>{COUNT})\s++(?:(?:equal|level|fixed|regular)\s++)*+$", re.I
)
# The loan named with its numbers, read from its end: "a loan of $10,000 at 6% for 3 years".
_DETAIL = re.compile(
    rf"\s++(?:(?:of|at|for|over|from)\s++)?(?:{_PERCENT}(?:\s++(?:annual\s++)?interest)?"
    rf"(?:\s++(?:per|a|an)\s++(?:year|annum)\b|\s++p\.?\s?a\.?)?|{_TERM}|{_SUM})\s*+$",
    re.I,
)
_LEAD = re.compile(
    rf"^(?:(?:a|an|the|this|that|my|our|his|her|their|your)\s++)?(?:{_SUM}\s++)?", re.I
)
_BE = re.compile(
    r"(?:\b(?:is|are|was|were|be|will\s++be|to\s++be|is\s++to\s++be|must\s++be)"
    r"|['\u2019](?:m|re|s))\s*+$",
    re.I,
)
_ASKS = re.compile(
    r"\b(?:do|does|did|would|will|should|could|can|must|shall|might|may)\s++"
    r"(?:i|we|you|he|she|they)\s++(?:(?:have|need|want)\s++to\s++)?$",
    re.I,
)
_HOW_MUCH = re.compile(r"\b(?:how\s++much|how\s++many|what)\b", re.I)
_REACH = 120
# A sentence about the loan without its name: "The rate is 6%.", "It is repaid in 36
# monthly payments", "the interest is charged monthly".
_ABOUT_THE_LOAN = re.compile(r"\b(?:it|them|the\s+loan|rates?|interest|apr|apy)\b", re.I)


@dataclass(frozen=True)
class Period:
    """One period word: where it is, how often, and what it belongs to."""

    start: int
    end: int
    per_year: int
    role: Role
    # The payments': said positively as the loan's own schedule ("said"), asked of it ("the
    # quarterly payment"), a question about a period's total, or none of these.
    schedule: Schedule = ""


def names_payments(text: str) -> bool:
    """The message names payments: "what is each monthly payment?", "repaid in 24 EMIs"."""
    return _NAMES_PAYMENTS.search(text) is not None


def sentences(text: str) -> list[tuple[int, int]]:
    """Each sentence's start and end: split at ".", "?", "!", ";" and a new line."""
    spans, start = [], 0
    for end in _SENTENCE_END.finditer(text):
        spans.append((start, end.start()))
        start = end.end()
    spans.append((start, len(text)))
    return [(begin, end) for begin, end in spans if text[begin:end].strip()]


def periods(text: str, own: Collection[str]) -> Iterator[Period]:
    """Every period word in ``text`` and what it belongs to; ``own`` are the loan's names in
    lower case, none when another loan is named too (then no schedule is the loan's)."""
    names = frozenset(own)
    taken = [span for rate in RATE.finditer(text) for span in rate_spans(text, *rate.span())]
    taken += rate_periods_spans(text)
    # A length of time is no period: "two and a half years" holds "a half years".
    lengths = [
        found.span() for pattern in (TERM, OTHER_DURATION) for found in pattern.finditer(text)
    ]
    for match in PERIOD.finditer(text):
        start, end = match.span()
        if any(begin <= start < stop for begin, stop in lengths):
            continue
        per_year = times_a_year(match)
        if any(begin <= start < stop for begin, stop in taken):
            yield Period(start, end, per_year, "rate")
            continue
        yield _belongs(text, match, per_year, names)


def _belongs(text: str, match: re.Match[str], per_year: int, own: frozenset[str]) -> Period:
    start, end = match.span()
    before = text[max(0, start - _REACH) : start]
    basis = _BASIS.search(before)
    basis_after = _BASIS_AFTER.match(text, end) if basis is not None else None
    if basis is not None and basis_after is not None:
        # "paid on a quarterly basis" is "paid quarterly".
        before, end = before[: basis.start()], basis_after.end()
    if _COMPOUNDING_BEFORE.search(before) or _COMPOUNDING_AFTER.match(text, end):
        return Period(start, end, per_year, "compounding")
    adjective = any(key.startswith("a") and value for key, value in match.groupdict().items())
    if adjective and (after := _NOUN_AFTER.match(text, end)) is not None:
        own_words = _between(after["words"], own)
        if own_words is not None:
            said = (
                bool(own) and own_words and _opens(before, own) and _clean(text, after.end(), own)
            )
            singular = not after["noun"].lower().endswith("s")
            schedule: Schedule = ("asked" if singular else "said") if said else ""
            return Period(start, end, per_year, "payments", schedule)
    if _SUM_BEFORE.search(before):
        return Period(start, end, per_year, "sum")
    if (noun := _NOUN_BEFORE.search(before)) is not None:
        return _counted(text, before[: noun.start()], start, end, per_year, adjective, own)
    word = _WORD_AFTER.match(text, end) if adjective else None
    if word is not None and word["word"].lower() not in _JOINS:
        # "pay annual property tax", "quarterly taxes": the describing word is the noun's.
        return Period(start, end, per_year, "describes")
    if (verb := _PAID.search(before)) is not None:
        return Period(start, end, per_year, "payments", _paid(text, before, verb, end, own))
    if _ASKED_BEFORE.search(before):
        return Period(start, end, per_year, "asked")
    return Period(start, end, per_year, "loose")


def _between(words: str, own: frozenset[str]) -> bool | None:
    """The words between a frequency and its payments' noun: True when they are "equal" and
    its like or the loan's name ("quarterly loan payments"), False for another's ("monthly
    HOA payments"), None when they are no noun phrase at all."""
    spoken = words.split()
    if len(spoken) > 3:
        return None
    return all(word.lower() in _BETWEEN for word in spoken) or " ".join(spoken).lower() in own


def _counted(
    text: str, head: str, start: int, end: int, per_year: int, adjective: bool, own: frozenset[str]
) -> Period:
    """A frequency after the payments' noun ("payments each quarter"), whose noun phrase is
    ``head``'s end. A count there is the frequency itself ("12 payments a year"); "payments
    a year" with no count read says none."""
    count = _COUNT_BEFORE.search(head)
    per_phrase = not adjective and not text[start:end].lower().startswith(("each", "every"))
    if count is not None and not adjective:
        per_year = _times(count_value(count["count"]) * per_year)
    elif per_phrase:
        return Period(start, end, per_year, "payments")
    said = bool(own) and _opens(head, own) and _clean(text, end, own)
    return Period(start, end, per_year, "payments", "said" if said else "")


def _times(per_year: float) -> int:
    return int(per_year) if float(per_year).is_integer() and per_year >= 1 else UNKNOWN


def _opens(before: str, own: frozenset[str], *, periods: bool = False) -> bool:
    """The words before a payment's noun phrase open it: what is left after a count, a sum,
    "equal", the loan's name (and with ``periods`` its frequency) is a word that opens a
    phrase, or a clause's start."""
    words = before.split()[-12:]
    while words:
        for size in range(min(_PHRASE_WORDS, len(words)), 0, -1):
            tail = " ".join(words[-size:])
            if (
                _MODIFIER.fullmatch(tail)
                or tail.lower() in own
                or (periods and PERIOD.fullmatch(tail))
            ):
                del words[-size:]
                break
        else:
            break
    if not words:
        return True
    last = words[-1].lower().replace("\u2019", "'")
    return last not in _OFFERS and (last[-1] in f"{_CLAUSE_END}%" or last in _OPENS)


def _clean(text: str, end: int, own: frozenset[str]) -> bool:
    """Nothing after the loan's payments names another payee: the clause ends, or a sum, a
    term, a rate or the loan itself follows ("quarterly payments on it")."""
    after = _CLEAN_AFTER.match(text, end)
    if after is None:
        return False
    payee = after["payee"]
    return payee is None or _names_the_loan(payee, own)


def _paid(
    text: str, before: str, verb: re.Match[str], end: int, own: frozenset[str]
) -> Literal["said", "total", ""]:
    """A frequency after paying or being paid. The loan's own schedule when the loan is
    paid: its object ("repay it monthly", "pay the loan back weekly"), or the subject or
    the clause it follows ("a loan of $10,000, payable quarterly", "the loan is repaid
    quarterly"); a question about what a period costs is a "total"."""
    if _asks(before[: verb.start("verb")]):
        return "total"
    if not own or not _clean(text, end, own):
        return ""
    paid = verb["object"]
    if paid is not None:
        return "said" if _names_the_loan(paid, own) else ""
    head = before[: verb.start()]
    breaks = [found.end() for found in _CLAUSE.finditer(head)]
    clause = head[breaks[-1] if breaks else 0 :]
    if (be := _BE.search(clause)) is not None:
        clause = clause[: be.start()]
    if clause.strip():
        return "said" if _names_the_loan(clause, own) else ""
    # A participle after a comma belongs to the clause before it: "a loan of $10,000 at 6%
    # for 3 years, paid back weekly".
    earlier = head[: breaks[-1]].rstrip(" ,") if breaks else ""
    clauses = [found.end() for found in _CLAUSE.finditer(earlier)]
    return "said" if _names_the_loan(earlier[clauses[-1] if clauses else 0 :], own) else ""


def _asks(before: str) -> bool:
    """The verb ending ``before`` asks what a period costs: "how much do I pay annually?"."""
    breaks = [found.end() for found in _CLAUSE.finditer(before)]
    clause = before[breaks[-1] if breaks else 0 :]
    return bool(_ASKS.search(before) or _HOW_MUCH.search(clause))


def _names_the_loan(subject: str, own: frozenset[str]) -> bool:
    """``subject`` is the loan, with its numbers: "the loan", "a $10,000 loan", "a loan of
    $10,000 at 6% for 3 years", "it"."""
    name = subject.strip()
    while (detail := _DETAIL.search(name)) is not None:
        name = name[: detail.start()]
    name = _LEAD.sub("", name.strip()).lower()
    return name in own or name in ("it", "them", "which", "this")


# --- The readers ------------------------------------------------------------------------


def other_payments(text: str, own: Collection[str], names: Collection[str]) -> bool:
    """The loan's own sentence names payments of another kind than its level ones, or of
    another payee: "plus 2 balloon payments", "12 late payments", "extra payments", "my HOA
    payments". The loan is then no level loan the card works. A down payment is none."""
    loan, _ = sentence_kinds(text, names)
    words = frozenset(own)
    for match in _NAMES_PAYMENTS.finditer(text):
        if _place(match.start(), loan, []) != "loan":
            continue
        before = text[max(0, match.start() - _REACH) : match.start()]
        if not _opens(before, words, periods=True):
            return True
    return False


def loose_rate_period(text: str, own: Collection[str]) -> bool:
    """A period word in a percent's sentence belongs to nothing it can be read as: "The bank
    charges 2% on the unpaid balance each month", "at 2%, charged monthly". The rate is then
    unknown, never yearly."""
    spans = [(begin, end) for begin, end in sentences(text) if RATE.search(text, begin, end)]
    return any(
        item.role == "loose" and any(begin <= item.start < end for begin, end in spans)
        for item in periods(text, own)
    )


def flow_frequency(
    text: str,
    own: Collection[str],
    names: Collection[str],
    *,
    backing: Collection[int | None],
) -> int | None:
    """Times a year the request's own payments or deposits are made; None when it says
    none, ``UNKNOWN`` for one no product pays, two that disagree, or one the words leave
    open.

    ``own`` are the loan's names (none when another loan is named too); ``names`` every word
    that names the request's product, which marks the loan's own sentences; ``backing`` the
    periods the interest compounds or is charged by, which "the quarterly payment" may
    stand on."""
    loan, about = sentence_kinds(text, names)
    said: set[int] = {12} if _EMI.search(text) else set()
    asked: set[int] = set()
    found = list(periods(text, own))
    for index, item in enumerate(found):
        if item.role not in ("payments", "loose"):
            continue
        place = _place(item.start, loan, about)
        if place is None:
            continue
        if _offered(text, found, index):
            return UNKNOWN
        if item.role == "payments" and place == "loan" and item.schedule in ("said", "asked"):
            (said if item.schedule == "said" else asked).add(item.per_year)
        elif item.schedule == "total" or item.per_year == 12:
            continue
        else:
            return UNKNOWN
    if said and not asked <= said:
        return UNKNOWN
    if not said and asked - {12, *backing}:
        return UNKNOWN
    return _one(said | asked)


def sentence_kinds(
    text: str, names: Collection[str], *, rates: bool = True
) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """The loan's own sentences (naming it, or with ``rates`` its rate), and the others
    about it (naming payments, its rate or interest, "it" or "the loan")."""
    words = [re.compile(rf"\b{re.escape(word)}\b", re.I) for word in names]
    loan, about = [], []
    for begin, end in sentences(text):
        part = text[begin:end]
        if (rates and RATE.search(part)) or any(word.search(part) for word in words):
            loan.append((begin, end))
        elif _NAMES_PAYMENTS.search(part) or _ABOUT_THE_LOAN.search(part):
            about.append((begin, end))
    return loan, about


def _place(start: int, loan: list[tuple[int, int]], about: list[tuple[int, int]]) -> str | None:
    if any(begin <= start < end for begin, end in loan):
        return "loan"
    if any(begin <= start < end for begin, end in about):
        return "about"
    return None


def _offered(text: str, found: list[Period], index: int) -> bool:
    """The frequency at ``index`` is one of two offered: "monthly or quarterly"."""
    for left, right in ((index - 1, index), (index, index + 1)):
        if left >= 0 and right < len(found):
            if _OFFERED.fullmatch(text, found[left].end, found[right].start):
                return True
    return False


def _one(said: set[int]) -> int | None:
    """The one frequency said; None for none, ``UNKNOWN`` for two or one no product pays."""
    if len(said) > 1:
        return UNKNOWN
    found = next(iter(said), None)
    if found is not None and found != UNKNOWN and not paid_by(found):
        return UNKNOWN
    return found
