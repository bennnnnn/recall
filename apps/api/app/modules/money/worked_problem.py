"""A money question from a lesson: a number to work out from values it all states.

"Ato Alula deposited Birr 3,000 … What is the amount of interest obtained at the end of
seven years?" and "Moges wants to buy a house that costs Birr 250,000 …" got the right
numbers in two lines over a calculator card (2026-10-31): nothing a student could follow
or hand in. A worked problem's reply is laid out the way the STEM replies are.

It is read from what the question asks, never from who is in it (a name is a brand as
often as a person): a number to work out ("What is …?", "Find …", "Calculate …"), that is
not about the asker's own money ("I", "my", "we": a textbook's "Suppose you borrow …" is
the reader's exercise) and not a choice or advice ("should", "better", "compare",
"refinance"). And the layout is only used when the server read every value it worked with
from the question (``lays_out_working``): laid out as homework, a term or a rate the app
assumed would look like the book's own.
"""

from __future__ import annotations

import math
import re

from app.modules.money.read import MoneyRequest, stated_sums
from app.modules.money.solve import Worked

_OWN = re.compile(
    r"\b(?:i|i'm|i've|i'd|i'll|me|my|mine|we|we're|we've|we'd|our|ours|us)\b", re.IGNORECASE
)
_CHOICE = re.compile(
    r"\b(?:should|shall|better|best|worth|recommend\w*|advi[cs]e|compar\w*|refinanc\w*"
    r"|versus|vs\.?|afford|or\s+(?:a|an|the)\s+\d|which\s+(?:one|is|are|of|would|should))",
    re.IGNORECASE,
)
_ASKS = re.compile(r"\?|\b(?:calculate|compute|find|determine|work\s+out)\b", re.IGNORECASE)
# Compounding the question names that the worked numbers do not use: they compound monthly.
_OTHER_COMPOUNDING = re.compile(
    r"\bcompound\w*\s+(?:annually|yearly|semi[\s-]?annually|half[\s-]?yearly|quarterly"
    r"|weekly|daily|continuously)\b|\b(?:annual|yearly|semi[\s-]?annual|half[\s-]?yearly"
    r"|quarterly|weekly|daily|continuous)\s+compounding\b",
    re.IGNORECASE,
)


def is_worked_problem(text: str) -> bool:
    """A number to work out, not about the asker's own money and not a choice."""
    return (
        _ASKS.search(text) is not None
        and _OWN.search(text) is None
        and _CHOICE.search(text) is None
    )


def lays_out_working(text: str, request: MoneyRequest, worked: Worked | None) -> bool:
    """A worked problem whose numbers are all the question's: no term, rate or sum assumed
    (a flow the question leaves out, no monthly deposit beside a lump sum, is no
    assumption), every sum and rate it states used, no compounding it names that the
    numbers do not use, and no follow-up."""
    if worked is None or request.changed or request.rates_only:
        return False
    defaults = request.product.defaults
    if any(defaults.get(name) != 0 for name in worked.assumed):
        return False
    # Every sum and rate it states is one the numbers use: "a house that costs 250,000 …
    # saved 50,000 … as a deposit" worked as a 250,000 loan left the 50,000 unread.
    used = [value for value in (*request.values.values(), request.price, request.down) if value]
    if request.rates_given > 1 or any(
        not any(math.isclose(stated, value) for value in used) for stated in stated_sums(text)
    ):
        return False
    return _OTHER_COMPOUNDING.search(text) is None and is_worked_problem(text)
