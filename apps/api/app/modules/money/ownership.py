"""Whose payments a phrase names: the request's own loan's, or another payee's.

A review of the payment-count reader (2026-11-14) found another payee's payments setting
the loan's term and schedule ("A $20,000 car loan at 6%, and we pay our insurance in 4
quarterly payments" worked over 12 months, quarterly), and a count followed by words that
make it no term read as one ("with 24 monthly payments missed", "already made", "left").
Payments are the loan's only when their clause's subject or object is the loan ("A $20,000
car loan at 6% with …", "repay it in …", "is to be repaid in …"), the clause follows the
loan after a comma, or they are said to be on it ("12 quarterly payments on a loan of
10,000"); and only when nothing follows them but the clause's end, a sum, a term, a rate or
the loan.
"""

from __future__ import annotations

import re
from collections.abc import Collection

from app.modules.money.phrases import COUNT, CURRENCY_WORDS, RATE

CLAUSE = re.compile(
    r"[.?!;:,(\n](?=\s|$)|\b(?:and|but|so|then|if|when|while|because|although|though|or)\b",
    re.I,
)
SUM = (
    rf"(?:(?:{CURRENCY_WORDS})\s)?(?:[$€£¥₹₦]\s?)?\d[\d,.]*+"
    rf"(?:\s?(?:k|m|thousand|million|grand))?(?:\s?(?:{CURRENCY_WORDS}))?"
)
_PERCENT = r"\d{1,3}(?:[.,]\d{1,4})?\s?(?:%|percent\b|per\s?cent\b|pct\b)"
_TERM = rf"(?:{COUNT})\s?-?\s?(?:years?|yrs?|months?|mos?)\b"

OBJECT = (
    r"(?:it|them|him|her|me|us"
    r"|(?:the|this|that|my|our|his|her|their|your)(?:\s++[\w'\u2019-]++){1,3}?)"
)
BETWEEN = frozenset("equal level fixed regular".split())
MODIFIER = re.compile(
    rf"{COUNT}|{SUM}|equal|level|fixed|regular|consecutive|successive|scheduled", re.I
)
# What may follow the loan's own payments: nothing, a sum, a term, a rate.
_CLEAN_AFTER = re.compile(
    rf"\s*+(?:$|[,.;:!?)\]]|(?:and|but|so|then)\b"
    rf"|of\s++{SUM}|(?:for|over|in)\s++{_TERM}|at\s++{_PERCENT}"
    rf"|(?:on|to|toward|towards|into|for)\s++(?P<payee>(?:it|them)\b|(?:a|an|the|this|that|my|"
    r"our|his|her|their|your)(?:\s++[\w'\u2019-]++){1,3}))",
    re.I,
)
# The loan named with its numbers, read from its end: "a loan of $10,000 at 6% for 3 years".
_DETAIL = re.compile(
    rf"\s++(?:(?:of|at|for|over|from|in)\s++)?(?:{_PERCENT}(?:\s++(?:annual\s++)?interest)?"
    r"(?:\s++(?:per|a|an|each|every)\s++[a-z-]+|\s++p\.?\s?[am]\.?)?"
    rf"|(?:{COUNT})\s?-?\s?(?:years?|yrs?|months?|mos?|quarters?|weeks?)\b|{SUM}"
    r"|from\s++(?:a|an|the)\s++[a-z]+|compounded\s++(?:(?:per|each|every)\s++)?[a-z-]+"
    r"|at\s++(?:(?:a|an|the)\s++)?(?:[a-z]+\s++){0,2}?(?:rate|interest)"
    r"|with\s++(?:(?:a|an|the)\s++)?(?:[a-z]+\s++){0,2}?rate"
    r"|on\s++(?:the\s++|its\s++)?(?:outstanding|unpaid|reducing|declining|remaining)\s++balance)"
    r"\s*+$",
    re.I,
)
# The loan held or borrowed: "I took a loan", "we have a mortgage", "A man borrows",
# "Birr 20,000 is borrowed".
_HOLDS = re.compile(r"^(?:[\w',]+\s++){0,3}?(?:a|an|the|my|this|that)\s++(?P<name>[\w' -]+)$", re.I)
_BORROWED = re.compile(r"^(?:[\w',$€£¥₹₦.]+\s++){0,4}?borrow(?:s|ed|ing)?$", re.I)
# A verb the loan is repaid by, ending a clause: "repay it", "is to be repaid", "agreed to
# repay the loan".
_REPAID_BY = re.compile(
    r"\b(?:repa(?:y|ys|id|ying|yable)|pa(?:y|ys|id|ying|yable)|amorti[sz](?:e|ed|es|ing))"
    rf"(?:\s++(?P<object>{OBJECT}))?(?:\s++(?:back|off))?\s*+$",
    re.I,
)
_AUXILIARY = re.compile(
    r"(?:\b(?:is|are|was|were|be|been|being|will|shall|must|to|agreed|agrees|agree|has|have|"
    r"had|wants?|plans?|needs?|can|could|would|should|i|we|you|he|she|they)\s++)+$",
    re.I,
)
# A word that opens a payment's phrase and is no verb: "with", "in", "the".
_GOVERNS = re.compile(
    r"\b(?:in|with|by|over|of|for|through|via|the|a|an|its|my|our|these|those|each|every|all)\s*+$",
    re.I,
)
_LEAD = re.compile(
    rf"^(?:(?:a|an|the|this|that|my|our)\s++)?(?:(?:[a-z]{{1,4}}\.?\s?)?{SUM}\s++)?", re.I
)
# A payee that is the debt itself, not a thing bought with it: "on it", "on the loan", never
# "on my old car" (2026-11-14 review: "36 monthly payments on my old car" was the term).
_DEBT = re.compile(r"\b(?:it|them|loans?|mortgages?|debt|balance|financing)\b", re.I)
# The loan after its rate: "The rate is 2% on a $10,000 loan", "I pay 6% on a loan of 5,000".
_ON = re.compile(r"\b(?:on|for|of)\s++", re.I)
# Someone else's: "her loan", "my sister's loan".
_ANOTHERS = re.compile(r"^(?:his|her|their|your|[\w]+['\u2019]s)\b", re.I)


def on_the_loan(text: str, end: int, own: Collection[str]) -> bool:
    """The payments are said to be on the loan itself: "12 quarterly payments on a loan of
    10,000"."""
    after = _CLEAN_AFTER.match(text, end)
    return after is not None and after["payee"] is not None and _is_the_debt(after["payee"], own)


def owned(text: str, start: int, end: int, own: Collection[str]) -> bool:
    """A count of payments at ``text[start:end]`` is the loan's: its clause is about the
    loan, or its payments are said to be on the loan ("12 quarterly payments on a loan of
    10,000")."""
    return of_the_loan(text[:start], own) or on_the_loan(text, end, own)


def clean_after(text: str, end: int, own: Collection[str]) -> bool:
    """Nothing after the loan's payments names another payee: the clause ends, or a sum, a
    term, a rate or the loan itself follows ("quarterly payments on it")."""
    after = _CLEAN_AFTER.match(text, end)
    if after is None:
        return False
    payee = after["payee"]
    return payee is None or _is_the_debt(payee, own)


def _is_the_debt(payee: str, own: Collection[str]) -> bool:
    return _DEBT.search(payee) is not None and names_the_loan(payee, own)


def names_the_loan(subject: str, own: Collection[str]) -> bool:
    """``subject`` is the loan, with its numbers: "the loan", "a $10,000 loan", "a loan of
    $10,000 at 6% for 3 years", "it"."""
    name = subject.strip()
    if _ANOTHERS.match(name):
        return False
    while (detail := _DETAIL.search(name)) is not None:
        name = name[: detail.start()]
    if _BORROWED.match(name.strip()):
        return True
    holds = _HOLDS.match(name.strip())
    if holds is not None and holds["name"].strip().lower() in own:
        return True
    words = name.lower().split()
    # Someone who holds it, saves into it or borrows it: "I took a loan", "I save".
    if any(" ".join(words[-size:]) in own and len(words) - size <= 3 for size in (1, 2, 3)):
        return True
    name = _LEAD.sub("", name.strip()).lower()
    return name in own or name in ("it", "them", "which", "this")


def of_the_loan(head: str, own: Collection[str]) -> bool:
    """The payments' phrase after ``head`` is the loan's: its clause's subject or object is
    the loan ("A $20,000 car loan at 6% with …", "repay it in …", "is to be repaid in …"),
    or the clause follows the loan after a comma ("car loan $30k, 72 monthly payments").
    "We pay our insurance in 4 quarterly payments" is not (2026-11-14 review)."""
    if not own:
        return False
    breaks = list(CLAUSE.finditer(head))
    start = breaks[-1].end() if breaks else 0
    words = head[start:].split()
    while words and (MODIFIER.fullmatch(words[-1]) or words[-1].lower() in BETWEEN):
        words.pop()
    clause = " ".join(words)
    if (governs := _GOVERNS.search(clause)) is not None:
        clause = clause[: governs.start()]
    if (verb := _REPAID_BY.search(clause)) is not None:
        if verb["object"] is not None:
            return names_the_loan(verb["object"], own)
        clause = clause[: verb.start()]
        if (aux := _AUXILIARY.search(clause)) is not None:
            clause = clause[: aux.start()]
    clause = clause.strip(" ,")
    if clause:
        return names_the_loan(clause, own) or any(
            RATE.search(clause, 0, found.start()) and names_the_loan(clause[found.end() :], own)
            for found in _ON.finditer(clause)
        )
    # Nothing of its own: the clause before it, after a comma, is the loan's or not.
    earlier = head[: breaks[-1].start()].rstrip(" ,;") if breaks else ""
    clauses = [found.end() for found in CLAUSE.finditer(earlier)]
    return bool(earlier) and names_the_loan(earlier[clauses[-1] if clauses else 0 :], own)
