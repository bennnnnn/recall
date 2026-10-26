"""A turn about the chat's loan that builds no card of its own: the loan's figures, the app's.

Live (2026-10-25): "House buying for 400k" then "60k at 6 percent" (card: 340,000 at 6% over
30 years, $2,038.47 a month), then "How", "Yes" and "Yes", the last taking the reply's
offer of a 15-year comparison. No line after the card was a money request, so the model
worked the 15-year loan itself: $2,921.00 a month and $185,780.00 interest, where the loan
costs $2,869.11 and $176,440.06.

While the chat's last money request stands in the user's recent lines
(``follow_up.standing_request``) and this message is about it (``about_the_loan``: money
words, or a short "yes" / "how" after a reply about the loan), the model reads the loan's
figures at its own term and the common others (``block.standing_block``). Prompts do not
hold, so ``correct_figures`` then reads the reply: a sum written to the cent that misses
the loan's figure at a term the reply names by a few percent is that figure, worked wrong,
and is put right. Every other number stays as written, and a reply that names another
rate is left alone: its figures are for a loan the app did not work.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.modules.money.catalog import Product
from app.modules.money.read import MoneyRequest
from app.modules.money.solve import Worked, output_value, rate_name
from app.services.md_fence_scan import line_fences

# The terms a reply about a loan most often compares, by product; the rest are the card's.
COMMON_TERMS: dict[str, tuple[float, ...]] = {
    "mortgage": (15, 20, 30),
    "car": (36, 48, 60, 72),
    "student": (5, 10, 20),
    "personal": (24, 36, 60),
    "loan": (3, 5, 10),
    "savings": (5, 10, 20, 30),
}
_MONEY_WORDS = re.compile(
    r"\b(?:pay(?:ment|ments|ing|off)?|interest|rates?|aprs?|apy|terms?|loans?|mortgages?"
    r"|monthly|afford\w*|years?|yrs?|months?|down\s?payment|compar\w*|refinanc\w*|principal"
    r"|amorti[sz]\w*|cheaper|totals?|borrow\w*|owe|costs?)\b|[%$€£¥₹₦]",
    re.IGNORECASE,
)
# A reply about the loan: what makes a bare "yes" or "how" about it too.
_LOAN_TALK = re.compile(
    r"\b(?:payments?|interest|loans?|mortgages?|aprs?|borrow\w*|principal)\b", re.IGNORECASE
)
_SHORT = re.compile(
    r"^\W*(?:(?:yes|yeah|yep|yup|sure|ok(?:ay)?|please|go\sahead|do\sit|do\sthat|sounds\sgood"
    r"|let'?s\sdo\sit|show\sme|how|why|explain|how\sso|really|go\son|continue)\W*){1,3}"
    r"(?:(?:please|thanks|thank\syou)\W*)?$"
    r"|^\W*(?:how\sdid\syou\s(?:get|work\sout|calculate)|show\s(?:me\s)?(?:the\s)?"
    r"(?:math|maths|working|steps|calculation)|explain\s(?:that|it|this|the\smath))\b[^.!?\n]*\W*$",
    re.IGNORECASE,
)
# A sum written to the cent: "2,921.00", "2{,}921.00" in LaTeX, "185780.00".
_CENTS = re.compile(r"(?<![\d.^])(\d{1,3}(?:(?:,|\{,\})\d{3})+|\d+)\.(\d{2})(?![\d%])")
_PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s?(?:\\?%|percent\b)", re.IGNORECASE)
_YEARS = re.compile(r"\b(\d{1,2})[\s-]?(?:years?|yrs?)\b", re.IGNORECASE)
_MONTHS = re.compile(r"\b(\d{1,3})[\s-]?months?\b", re.IGNORECASE)
# A sum the reply names as what is borrowed or bought: "a $350,000 loan", "borrow 30k". One
# that is not this loan's makes the reply's figures another loan's.
_AMOUNT_NAMED = re.compile(
    r"(?:\b(?:borrow(?:ing|ed)?|loan\s+of|price\s+of|principal\s+of|financ(?:e|ing))\s+\$?\s?"
    r"(?P<a>\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{2})?\s?(?P<ak>k\b)?)"
    r"|(?:\$?\s?(?P<b>\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{2})?\s?(?P<bk>k\b)?\s+"
    r"(?:\w+\s+){0,2}(?:loan|mortgage|house|home|condo|car|truck|price|principal)\b)",
    re.IGNORECASE,
)
# How far a sum may miss a figure and still be that figure worked wrong.
_NEAR = 0.06
# A sum within this of a figure is that figure, rounded another way.
_ROUNDING = 1.0
_SMALLEST = 50.0


@dataclass(frozen=True)
class Figures:
    """The loan's outputs at every term its slider offers, at its own rate."""

    term_name: str
    by_term: dict[float, dict[str, float]]


def about_the_loan(text: str, last_reply: str) -> bool:
    """``text`` is about the money the chat is discussing: it has money words, or it is a
    short "yes" / "how" / "show me the math" after a reply about a loan."""
    if not text or len(text) > 600:
        return False
    if _MONEY_WORDS.search(text):
        return True
    return bool(_SHORT.match(text.strip()) and _LOAN_TALK.search(last_reply or ""))


def term_name(product: Product) -> str | None:
    return next((item.name for item in product.inputs if item.name in ("years", "months")), None)


def figures(worked: Worked) -> Figures | None:
    """The loan's outputs at each term on its slider; None for a product with no term."""
    product = worked.product
    name = term_name(product)
    item = product.input(name) if name else None
    if name is None or item is None:
        return None
    span = item.span
    step = span.step or 1.0
    by_term: dict[float, dict[str, float]] = {}
    term = span.low
    while term <= span.high + 1e-9:
        values = {**worked.values, name: term}
        outputs = {out.name: output_value(out.expression, values) for out in product.outputs}
        by_term[term] = {key: value for key, value in outputs.items() if value is not None}
        term += step
    return Figures(name, by_term)


def correct_figures(text: str, request: MoneyRequest, worked: Worked) -> str:
    """``text`` with each sum to the cent that misses one of the loan's figures put right."""
    grid = figures(worked)
    if grid is None or not _CENTS.search(text):
        return text
    rate = worked.values[rate_name(worked.product)]
    owners = line_fences(text)
    lines = text.split("\n")
    prose = "\n".join(line for line, owner in zip(lines, owners, strict=True) if owner is None)
    if any(abs(float(found) - rate) > 1e-6 for found in _PERCENT.findall(prose)):
        return text
    known = {round(value, 2) for value in (*worked.values.values(), request.price, request.down)
             if value is not None}  # fmt: skip
    if _names_another_amount(prose, known):
        return text
    terms = {worked.values[grid.term_name], *_named_terms(prose, grid.term_name)}
    named = [grid.by_term[term] for term in terms if term in grid.by_term]
    candidates = sorted({round(value, 2) for outputs in named for value in outputs.values()})
    for index, line in enumerate(lines):
        if owners[index] is None:
            lines[index] = _CENTS.sub(lambda m: _put_right(m, candidates, known), line)
    return "\n".join(lines)


def _names_another_amount(prose: str, known: set[float]) -> bool:
    for found in _AMOUNT_NAMED.finditer(prose):
        digits = found.group("a") or found.group("b")
        scale = 1_000 if (found.group("ak") or found.group("bk")) else 1
        value = float(digits.replace(",", "")) * scale
        if value >= 1_000 and round(value, 2) not in known:
            return True
    return False


def _named_terms(prose: str, name: str) -> set[float]:
    """The terms ``prose`` names, in the loan's own unit: "15-year" and "180 months"."""
    years = [float(found) for found in _YEARS.findall(prose)]
    months = [float(found) for found in _MONTHS.findall(prose)]
    if name == "years":
        return {*years, *(count / 12 for count in months if count % 12 == 0)}
    return {*months, *(count * 12 for count in years)}


def _put_right(match: re.Match[str], candidates: list[float], known: set[float]) -> str:
    written = match.group(0)
    value = float(match.group(1).replace("{,}", "").replace(",", "") + "." + match.group(2))
    if value < _SMALLEST or round(value, 2) in known:
        return written
    if any(abs(value - figure) <= _ROUNDING for figure in candidates):
        return written
    near = [figure for figure in candidates if abs(value - figure) <= _NEAR * figure]
    if len(near) != 1:
        return written
    separator = "{,}" if "{,}" in written else ","
    return f"{near[0]:,.2f}".replace(",", separator)
