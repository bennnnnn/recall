"""Whose payments a frequency names: the loan's own schedule, or something else's.

Live (2026-11-14, a review of the rate-period reader): any "pay" or "paid" before a
frequency set how often the loan is paid. "$300,000 mortgage at 6% for 30 years, how much do
I pay annually?" was worked as one payment a year (21,794.67, where the mortgage costs
1,798.65 a month), and "school fees paid quarterly", "HOA dues paid quarterly", "I earn
$2,000 paid weekly", "My pay is weekly" and "I can make extra payments annually" each
changed the loan's schedule. A frequency is the loan's schedule only where a positive
grammar reads it as the loan's own; anything else leaves the loan monthly:

- Its payments, named as a noun: "48 equal monthly payments", "with quarterly instalments",
  "payments each quarter", "the payments are quarterly", "12 payments a year". The noun
  phrase holds only a count, a sum, "equal" and its like, or the loan's own name, after a
  word that opens one ("with", "in", "the", "make", a clause's start). "HOA payments",
  "extra payments" and "student loan payments" beside a mortgage are another's.
- The loan repaid: "repaid quarterly", "repayable quarterly", "pay it back weekly".
- The loan paid by its borrower, or said to be paid: "I'm paying it weekly", "I want to pay
  weekly", "payable quarterly", "a loan of $10,000 paid quarterly", ", paid every week". A
  wage ("I get paid weekly", "my husband is paid weekly") and anything else paid ("school
  fees paid quarterly", "$2,000 paid weekly", "the total paid yearly") is not the loan.

A question about what a period costs ("how much do I pay annually?", "what do I pay each
quarter?") asks a total, not a schedule. Some words leave the schedule open and work no
numbers: two frequencies offered ("monthly or quarterly payments"), a percent before "paid
quarterly" (the interest's, or the loan's), and "the yearly payment" with no schedule said
beside it ("what is my yearly mortgage payment?" may be twelve monthly ones).
"""

from __future__ import annotations

import re
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Literal

from app.modules.money.compounding import UNKNOWN
from app.modules.money.periods import ADJECTIVE, NOUN, paid_by, times_a_year
from app.modules.money.phrases import COUNT, CURRENCY_WORDS

# A frequency a payment may run by: "quarterly", "each quarter", "a year", "every two weeks".
_FREQUENCY = re.compile(rf"{NOUN}|{ADJECTIVE}", re.I)
# What a loan or a card is paid by, and what savings are paid into as well.
_PAYMENTS = r"(?:re)?payments?|instal(?:l)?ments?"
_DEPOSITS = rf"{_PAYMENTS}|deposits?|contributions?"
# An EMI is an equated monthly instalment: "repaid in 24 EMIs".
_EMI = re.compile(r"\bEMIs?\b", re.I)
# The payments named at all: "monthly payments", "each instalment", "my EMI"; a down payment
# is not one.
_NAMES_PAYMENTS = re.compile(
    r"(?<!down\s)(?<!down-)\b(?:(?:re)?payments?|instal(?:l)?ments?|EMIs?)\b", re.I
)
# Two frequencies offered: "monthly or quarterly payments", "weekly vs monthly".
_OFFERED = re.compile(r"\s*+,?\s*+(?:or|nor|vs\.?|versus)\s++", re.I)

_SUM = (
    rf"(?:(?:{CURRENCY_WORDS})\s)?(?:[$€£¥₹₦]\s?)?\d[\d,.]*+"
    rf"(?:\s?(?:k|m|thousand|million|grand))?(?:\s?(?:{CURRENCY_WORDS}))?"
)
_PERCENT = (
    r"\d{1,3}(?:[.,]\d{1,4})?\s?(?:%|percent\b|per\s?cent\b|pct\b)"
    r"(?:\s++(?:annual\s++|yearly\s++)?interest\b)?"
    r"(?:\s++(?:per|a|an|each)\s++(?:year|annum|month|quarter)\b|\s++p\.?\s?[am]\.?)?"
)
_TERM = rf"(?:{COUNT})\s?-?\s?(?:years?|yrs?|months?|mos?)\b"
# Words a payment's noun phrase may hold besides its frequency and the loan's name, each
# read whole: a count, a sum, "equal".
_MODIFIER = re.compile(
    rf"{COUNT}|{_SUM}|equal|level|fixed|regular|consecutive|successive|scheduled", re.I
)
_PHRASE_WORDS = 5
# Words that open a payment's noun phrase: a determiner, a preposition, a verb of paying or
# having, a question's word, a conjunction, and the rate or the term said just before ("at
# 6% quarterly payments" gives the describing word to the payments, ``periods``). "HOA",
# "extra" and "tax" do not.
_OPENS = frozenset(
    "a an the its his her their my our your these those each every all both any this that "
    "with in by of via through over on for as into at under across from within after "
    "make makes making made pay pays paying paid repay repays repaid repaying repayable "
    "payable is are was were be been being take takes taking took have has had having want "
    "wants need needs choose chooses prefer prefers do does did afford affords get gets got "
    "schedule scheduled set split spread divided owe owes plan plans use using offer offers "
    "require requires allow allows agree agreed find calculate compute determine work what "
    "what's whats which how it's that's there and then but so also percent pct year years yr "
    "yrs month months mos".split()
)
_OFFERS = frozenset("or nor vs vs. versus either".split())
_CLAUSE_END = ",.;:!?(\u2013\u2014-"

# What a payment's noun ends right before a frequency after it: "payments each quarter",
# "the payments are quarterly", "payments made each quarter".
_NOUN_BEFORE = {
    nouns: re.compile(
        rf"\b(?P<noun>{nouns})\s++(?:(?:are|is|was|were|be|will\s++be|to\s++be|must\s++be)\s++)?"
        r"(?:(?:made|due|paid|payable)\s++)?$",
        re.I,
    )
    for nouns in (_PAYMENTS, _DEPOSITS)
}
# A frequency's words before a payment's noun: "quarterly payments", "monthly car loan
# payments" (up to three words between, each the loan's name or "equal" and its like).
_NOUN_AFTER = {
    nouns: re.compile(rf"(?P<words>(?:\s++[\w'\u2019-]++){{0,3}}?)\s++(?P<noun>{nouns})\b", re.I)
    for nouns in (_PAYMENTS, _DEPOSITS)
}
_BETWEEN = frozenset("equal level fixed regular".split())
# "12 payments a year", "12 equal payments a year": the count before the noun is the
# frequency.
_COUNT_BEFORE = re.compile(
    r"(?<![\w.,])(?P<count>\d{1,3})\s++(?:(?:equal|level|fixed|regular)\s++)*+$", re.I
)

_OBJECT = (
    r"(?:it|them|him|her|me|us"
    r"|(?:the|this|that|my|our|his|her|their|your)(?:\s++[\w'\u2019-]++){1,3}?)"
)
# The loan repaid: "repaid quarterly", "repay the loan monthly", "pay it back weekly".
_REPAID = re.compile(
    rf"\b(?P<verb>repa(?:y|ys|id|ying|yable)(?:\s++{_OBJECT})?"
    rf"|pa(?:y|ys|id|ying)(?:\s++{_OBJECT})?\s++(?:back|off)(?:\s++{_OBJECT})?)\s++$",
    re.I,
)
# Paying, by someone who pays it: "I'm paying it weekly", "I want to pay weekly".
_PAYS = re.compile(
    rf"(?:(?P<who>[\w'\u2019]++)\s++|(?<![\w'\u2019])|[{_CLAUSE_END}]\s*+)(?P<verb>pa(?:y|ys|ying))"
    rf"(?:\s++(?P<object>{_OBJECT}))?\s++$",
    re.I,
)
_PAYERS = frozenset(
    "i we you he she they i'll we'll you'll he'll she'll they'll i'd we'd you'd he'd she'd "
    "they'd i'm we're you're he's she's they're am are is will would can could should must "
    "may might shall to and then but also just only always rather".split()
)
# Said to be paid: "payable quarterly", "a loan paid quarterly", "my HOA dues are paid".
_PAID = re.compile(r"\b(?:paid|payable)\s++$", re.I)
# Someone paid by the period is a wage: "I get paid weekly".
_WAGE = re.compile(r"\b(?:get|gets|got|getting)\s++$", re.I)
_BE = re.compile(r"(?:\b(?:is|are|was|were|be|been|being)|['\u2019](?:m|re|s))\s++$", re.I)
_CLAUSE = re.compile(
    r"[.?!;:,(\n](?=\s|$)|\b(?:and|but|so|then|if|when|while|because|although|though|or)\b",
    re.I,
)
# The loan named with its numbers, read from its end: "a loan of $10,000 at 6% for 3 years".
_DETAIL = re.compile(
    rf"\s++(?:(?:of|at|for|over|from)\s++)?(?:{_PERCENT}|{_TERM}|{_SUM})\s*+$", re.I
)
_LEAD = re.compile(
    rf"^(?:(?:a|an|the|this|that|my|our|his|her|their|your)\s++)?(?:{_SUM}\s++)?", re.I
)
_PERCENT_END = re.compile(r"(?:%|\bpercent|\bper\s?cent|\bpct)\s*+$", re.I)
# A question about what a period costs: "how much do I pay annually?", "what do I pay".
_ASKS = re.compile(
    r"\b(?:do|does|did|would|will|should|could|can|must|shall|might|may)\s++"
    r"(?:i|we|you|he|she|they)\s++(?:(?:have|need|want)\s++to\s++)?$",
    re.I,
)
_HOW_MUCH = re.compile(r"\b(?:how\s++much|how\s++many|what)\b", re.I)
_REACH = 120

Role = Literal["said", "asked", "total", "open"]


@dataclass(frozen=True)
class _Found:
    """A frequency the loan's payments run by: said as its schedule, asked of ("the yearly
    payment"), asked as a period's total ("how much do I pay annually?", which keeps the
    loan as it is), or left open ("monthly or quarterly")."""

    role: Role
    per_year: int


def flow_frequency(
    text: str, own: Collection[str], *, saves: bool, backing: Collection[int | None]
) -> int | None:
    """Times a year the request's own payments or deposits are made; None when it says none,
    ``UNKNOWN`` for one no product pays, two that disagree, or one the words leave open.

    ``own`` are the loan's own names in lower case ("mortgage", "loan"); ``saves`` reads
    deposits as the payments; ``backing`` are the periods the message says the interest
    compounds or is charged by, which "the quarterly payment" may stand on."""
    nouns = _DEPOSITS if saves else _PAYMENTS
    words = frozenset(own)
    said: set[int] = {12} if _EMI.search(text) else set()
    asked: set[int] = set()
    found = list(_FREQUENCY.finditer(text))
    for index, match in enumerate(found):
        frequency = _frequency(text, match, nouns, words)
        if frequency is None:
            continue
        if frequency.role == "open" or _offered(text, found, index):
            return UNKNOWN
        if frequency.role == "total":
            continue
        (asked if frequency.role == "asked" else said).add(frequency.per_year)
    if said and not asked <= said:
        return UNKNOWN
    if not said and asked - {12, *backing}:
        return UNKNOWN
    return _one(said | asked)


def names_payments(text: str) -> bool:
    """The message names payments: "what is each monthly payment?", "repaid in 24 EMIs"."""
    return _NAMES_PAYMENTS.search(text) is not None


def _one(said: set[int]) -> int | None:
    """The one frequency said; None for none, ``UNKNOWN`` for two or one no product pays."""
    if len(said) > 1:
        return UNKNOWN
    found = next(iter(said), None)
    if found is not None and found != UNKNOWN and not paid_by(found):
        return UNKNOWN
    return found


def _offered(text: str, found: Sequence[re.Match[str]], index: int) -> bool:
    """The frequency at ``index`` is one of two offered: "monthly or quarterly"."""
    for left, right in ((index - 1, index), (index, index + 1)):
        if left >= 0 and right < len(found):
            if _OFFERED.fullmatch(text, found[left].end(), found[right].start()):
                return True
    return False


def _frequency(text: str, match: re.Match[str], nouns: str, own: frozenset[str]) -> _Found | None:
    """The loan's payments' frequency ``match`` says, or None when it is no frequency of
    theirs (another's payments, a wage, a question about a period's total)."""
    per_year = times_a_year(match)
    before = text[max(0, match.start() - _REACH) : match.start()]
    adjective = any(key.startswith("a") and value for key, value in match.groupdict().items())
    if adjective:
        after = _NOUN_AFTER[nouns].match(text, match.end())
        if after is not None and _between(after["words"], own):
            if not _opens(before, own):
                # "extra quarterly payments", "I can manage quarterly payments": maybe the
                # loan's, maybe not. A monthly one is the loan's usual schedule anyway.
                return _Found("open", UNKNOWN) if per_year != 12 else None
            singular = not after["noun"].lower().endswith("s")
            return _Found("asked" if singular else "said", per_year)
    noun = _NOUN_BEFORE[nouns].search(before)
    if noun is not None:
        return _counted(before[: noun.start()], per_year, adjective, own)
    return _paid(before, per_year, own)


def _between(words: str, own: frozenset[str]) -> bool:
    """The words between a frequency and its payments' noun are "equal" and its like, or
    the loan's own name: "quarterly loan payments", never "monthly HOA payments"."""
    spoken = words.split()
    return all(word.lower() in _BETWEEN for word in spoken) or " ".join(spoken).lower() in own


def _counted(head: str, per_year: int, adjective: bool, own: frozenset[str]) -> _Found | None:
    """A frequency after the payments' noun ("payments each quarter"), whose noun phrase is
    ``head``'s end; a count there is the frequency itself ("12 payments a year")."""
    if not _opens(head, own):
        return None
    count = _COUNT_BEFORE.search(head)
    if count is not None and not adjective:
        per_year *= int(count["count"])
    return _Found("said", per_year)


def _opens(before: str, own: frozenset[str]) -> bool:
    """The words before a payment's noun phrase open it, so the payments are the loan's;
    never when they offer it as one of two ("or")."""
    words = before.split()[-12:]
    while words:
        for size in range(min(_PHRASE_WORDS, len(words)), 0, -1):
            tail = " ".join(words[-size:])
            if _MODIFIER.fullmatch(tail) or tail.lower() in own:
                del words[-size:]
                break
        else:
            break
    if not words:
        return True
    last = words[-1].lower().replace("\u2019", "'")
    return last not in _OFFERS and (last[-1] in f"{_CLAUSE_END}%" or last in _OPENS)


def _paid(before: str, per_year: int, own: frozenset[str]) -> _Found | None:
    """A frequency after paying or being paid: the loan repaid, paid by its borrower, or
    said to be paid; None for a wage, another thing paid or a question about a total."""
    for pattern in (_REPAID, _PAYS):
        verb = pattern.search(before)
        if verb is None:
            continue
        if pattern is _PAYS and not _payer(verb, own):
            return None
        role: Role = "total" if _asks(before[: verb.start("verb")]) else "said"
        return _Found(role, per_year)
    paid = _PAID.search(before)
    if paid is None or _WAGE.search(before, 0, paid.start()):
        return None
    be = _BE.search(before, 0, paid.start())
    end = be.start() if be is not None else paid.start()
    breaks = [found.end() for found in _CLAUSE.finditer(before, 0, end)]
    subject = before[breaks[-1] if breaks else 0 : end].strip()
    if (be is None and not subject) or _names_the_loan(subject, own):
        return _Found("said", per_year)
    if be is None and _PERCENT_END.search(subject):
        # "a car loan at 6% paid quarterly": the interest paid, or the loan.
        return _Found("open", UNKNOWN)
    return None


def _payer(verb: re.Match[str], own: frozenset[str]) -> bool:
    """ "pay" here is the borrower paying the loan: after one who pays, or a clause's start,
    and with no object but the loan ("I pay my rent weekly" is not)."""
    who = (verb["who"] or "").lower().replace("\u2019", "'")
    if who and who not in _PAYERS:
        return False
    paid = (verb["object"] or "").lower()
    return not paid or paid in ("it", "them") or _names_the_loan(paid, own)


def _asks(before: str) -> bool:
    """The verb ending ``before`` asks what a period costs: "how much do I pay annually?"."""
    breaks = [found.end() for found in _CLAUSE.finditer(before)]
    clause = before[breaks[-1] if breaks else 0 :]
    return bool(_ASKS.search(before) or _HOW_MUCH.search(clause))


def _names_the_loan(subject: str, own: frozenset[str]) -> bool:
    """``subject`` is the loan, with its numbers: "the loan", "a $10,000 loan", "a loan of
    $10,000 at 6% for 3 years", "it"."""
    name = subject
    while (detail := _DETAIL.search(name)) is not None:
        name = name[: detail.start()]
    name = _LEAD.sub("", name.strip()).lower()
    return name in own or name in ("it", "which", "that", "this")
