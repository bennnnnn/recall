"""The words that say what a number in a change line is (``follow_up``).

Each rule names the role only where the words make it certain, and a line with a
number no rule places is no follow-up. Reviewed on the branch (2026-10-25): with looser
rules "what if property tax is 1.2%" became a 1.2 % mortgage, "what if I pay 400
instead?" a $400 loan, "what if the trade-in is worth 4000" a $4,000 one, and "what if
rates are 5% in 2 years" a 2-year mortgage at $13,161 a month.
"""

from __future__ import annotations

import re

# Words between a role word and its number: "at about 5%", "for only 18k".
_FILLER = r"\s(?:(?:a|an|only|just|about|around|like|maybe)\s)*$"

CUE = re.compile(
    r"\b(?:what\s+(?:if|about|would)|how\s+about|instead|rather|suppose|supposing|"
    r"let'?s\s+(?:say|try|do)|make\s+it|change\s+it|switch\s+to|try|"
    r"and\s+(?:if|with|at|over|for|in))\b"
    r"|^\W*(?:(?:hmm+|ok(?:ay)?|so|and|but|oh|well|then|now)\W+)*(?:if|with|at|over|for|say)\b",
    re.I,
)
# A line of nothing but numbers, units and joining words: "36 months?", "and 5000 down?",
# "what about 400k?".
ONLY_THE_CHANGE = re.compile(
    r"^(?:[\W\d]|(?<=\d)[km]\b|\b(?:what\s+about|how\s+about|what\s+if|and|or|so|ok(?:ay)?|then|hmm+|at|"
    r"over|for|with|a|an|the|down|years?|yrs?|months?|mos?|percent|k|instead|please|maybe|"
    r"now|apr|rate|term|dollars?)\b)*$",
    re.I,
)
# "3 years instead of 5", "7% not 7.16%": the old value is no change.
OLD_VALUE = re.compile(
    r"\b(?:instead\s+of|rather\s+than|in\s+place\s+of|not|from)\s+(?:the\s+)?"
    r"(?:[$€£¥₹₦]\s?)?\d[\d,.]*\s?(?:%|percent|k\b|grand|years?|yrs?|months?|mos?)?",
    re.I,
)
# "1% lower", "2000 more down", "an extra 200", "if rates drop 1%": a change by an amount.
RELATIVE = re.compile(
    r"\b(?:by|extra|another|additional|drops?|dropped|falls?|fell|rises?|rose|"
    r"increase[sd]?|decrease[sd]?|(?:go(?:es)?|went)\s+(?:up|down)|cut|raise[sd]?)"
    r"\s+(?:an?\s+)?(?:[$€£¥₹₦]\s?)?\d"
    r"|\d[\d,.]*\s?(?:%|percent|k\b|grand|dollars?|years?|months?)?\s+"
    r"(?:more|less|lower|higher|extra|cheaper|longer|shorter|fewer|off)\b",
    re.I,
)
# Something the request has no input for: a tax, insurance, a raise, a trade-in, rent. Its
# number is not the rate or the price ("what if sales tax is 7%", "with 60k salary").
OTHER_THING = re.compile(
    r"\b(?:tax(?:es)?|pmi|insurance|inflation|raise|salary|income|earn(?:s|ed|ing)?|wages?|"
    r"bonus|fees?|cash\s?back|rebate|discount|commission|appreciat(?:es|ed|ing|ion)|"
    r"depreciat\w*|returns?|dividends?|yield|growth|trade[\s-]?in|trad(?:e|ed|ing)|"
    r"rent(?:s|ed|ing)?|lease[sd]?|leasing|gas|fuel|hoa|closing|score|refinanc\w*|"
    r"budget|afford)\b",
    re.I,
)
NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
# A percent is the rate by the words before it ("at 5%", "the rate was 6.5%", "interest
# rate of 5%", "what if it's 5%", "what if I get 4.5%") or after it ("5% APR").
RATE_BEFORE = re.compile(
    r"(?:\bat|\b(?:rates?|aprs?|apy|interest)(?:\srate)?(?:\s(?:is|are|was|were|of|at|to|"
    r"became|(?:drops?|dropped|falls?|fell|goes|go|went|comes?|came)\s(?:down\s|up\s)?to))?|"
    r"\b(?:it|that)(?:'s|\s(?:is|was|were|became))|"
    r"\b(?:get|got|getting|quoted|offered|approved\s(?:for|at)|qualif(?:y|ied)\sfor))"
    rf"{_FILLER}",
    re.I,
)
RATE_AFTER = re.compile(r"\s?(?:apr|apy|rate|interest|fixed)\b", re.I)
# A length of time is the loan's term by the words before it: "do 3 years", "over 48
# months", "make it 4 years", "pay it off in 2 years", "a 15 year mortgage", "36 months?".
# "Wait 2 years", "keep it for 10 years", "rates are 5% in 2 years" say no term.
TERM_BEFORE = re.compile(
    r"(?:^|[,;:?!.(]|\d\s?(?:%|k\b)?|\b(?:what\s+if|what\s+about|how\s+about|and|or|so|"
    r"ok(?:ay)?|hmm+|then|instead|do|did|doing|make|made|go|went|try|say|take|took|get|got|"
    r"pick|picked|choose|chose|change|switch|finance[sd]?|financing|borrow(?:ed)?|spread|"
    r"sav(?:e|ing)|invest(?:ing)?|leave|with|at|to|on|over|a|an|down|"
    r"off\s+(?:in|after|within)|(?:do|finish|repay|clear)\s+(?:it\s+)?(?:in|within)|"
    r"(?:loan|mortgage|term|it|that)(?:'s|\s+(?:was|is|were|be))))"
    r"\s*(?:(?:i|we|it|only|just|the|maybe|like|for|over|out|about|around)\s+)*$",
    re.I,
)
PER_PERIOD = re.compile(
    r"\s?(?:(?:a|an|per|each|every|/)\s?(?:year|yr|week|wk|day|hour|hr)\b"
    r"|annually|yearly|weekly|daily|hourly)",
    re.I,
)
# A card's payment and balance: "what if I pay 300", "what if I owe 8000".
PAYING = re.compile(rf"\b(?:pay(?:s|ing)?|paid){_FILLER}", re.I)
BALANCE_BEFORE = re.compile(
    rf"\b(?:owe[ds]?|owing|balance(?:\s(?:is|was|were|of|became))?){_FILLER}", re.I
)
# "What if I only borrow 8000", "a 25000 car loan": the sum borrowed, with nothing put down.
BORROWED = re.compile(
    rf"\b(?:borrow(?:ed|ing)?|financ(?:e|ed|ing)|(?:loan|mortgage)\sof){_FILLER}", re.I
)
LOAN_AFTER = re.compile(r"\s?(?:[a-z-]+\s)?(?:loan|mortgage)\b", re.I)
# A sum paid, sold, saved or earned is no price: "what if I pay 400 instead?" asks about a
# monthly payment, "I sell my old car for 4000" about a trade.
NOT_THE_PRICE = re.compile(
    r"\b(?:pay(?:s|ing)?|paid|worth|sell(?:s|ing)?|sold|sav(?:e|ed|ing)|spend\w*|make|made|"
    r"making|earn\w*|cash)\b[^.?!,]{0,24}$",
    re.I,
)
# The price by the words before it: "what if the car was 18k", "the house is 400k", "a new
# one for 30000", "bought a new car for 30000", "priced at 25k"; or after it: "a 20k car".
PRICE_BEFORE = re.compile(
    r"(?:\b(?:car|house|home|condo|truck|suv|vehicle|price|it|one|that)(?:'s|\s(?:was|is|were|"
    r"became|costs?))|\b(?:car|house|home|condo|truck|suv|vehicle|one)\sfor|"
    r"\b(?:buy|bought|buying|purchase[ds]?|purchasing)\b[^.?!,]{0,24}\bfor|\bpriced(?:\sat)?|"
    rf"\bcosting){_FILLER}",
    re.I,
)
THING_AFTER = re.compile(r"\s?(?:[a-z-]+\s)?(?:car|house|home|condo|truck|suv|vehicle|one)\b", re.I)


def whole_word(word: str, text: str) -> bool:
    return re.search(rf"\b{re.escape(word)}\b", text) is not None
