"""How often a request says interest compounds: "compounded quarterly" is 4 times a year.

Live (2026-10-31, an Ethiopian grade 11 book): "6% interest rate per year, compounded
quarterly" was worked monthly, and the card's interest was off by birr. A product that
grows money (``Product.settings`` has ``per_year``) works the frequency said. Each word of
compounding is read with what follows it ("compounded per quarter", "compounded on a
quarterly basis", "compounded twice a year"), else with the one word before it ("semi
annual compounding", "quarterly compounded"), in the vocabulary every money reader shares
(``periods``). Any compounding word whose frequency is not read so ("compounded
continuously", "compounded and paid quarterly", "compounding happens quarterly", a bare
"compounded"), or two frequencies that disagree, is ``UNKNOWN``: the request gets no
worked numbers, never monthly ones.
"""

from __future__ import annotations

import re

from app.modules.money.periods import ADJECTIVE, FREQUENCIES, PERIOD, UNKNOWN, times_a_year

__all__ = ["UNKNOWN", "compounding_per_year"]

_COMPOUND = re.compile(r"\bcompound(?:ed|ing|s)?\b", re.I)
# What may stand between the word and its frequency: "compounded interest is paid ...".
_LEAD = re.compile(r"(?:\s+interest)?(?:\s+(?:is|are))?\s+(?:on\s+an?\s+)?", re.I)
_BEFORE = re.compile(rf"{ADJECTIVE}\s+$", re.I)


def compounding_per_year(text: str) -> int | None:
    """Times a year ``text`` says interest compounds; None when no word of compounding is
    in it, ``UNKNOWN`` (0) when one is that this does not read, or two disagree."""
    text = re.sub(r"\b(semi|bi|half)[\s-]+(?=\w)", r"\1-", text)
    said: set[int] = set()
    for word in _COMPOUND.finditer(text):
        count = None
        lead = _LEAD.match(text, word.end())
        after = PERIOD.match(text, lead.end()) if lead is not None else None
        if after is not None:
            count = times_a_year(after)
        else:
            before = _BEFORE.search(text, 0, word.start())
            count = times_a_year(before) if before is not None else None
        if count not in FREQUENCIES:
            # "compounded every 2 months" is no frequency a product works.
            return UNKNOWN
        said.add(count)
    if len(said) > 1:
        return UNKNOWN
    return said.pop() if said else None
