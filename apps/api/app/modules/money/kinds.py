"""Which kind of a product a message names: a catalog ``Variant`` ("a used car").

The kind counts only when the vehicle being bought or financed is described as that
kind, in a few fixed phrases:

- "buying (a) used car" (also buy, bought, get, getting, finance, financing, purchase,
  looking at, thinking of buying),
- "a used car for 14000",
- "used car loan", "loan for a used car".

Nothing else names it. Reviews (2026-10-25) found looser readers taking "used" from the
old car or the alternative: "to replace my old used car", "trading in my used car", "or
buy a used car with cash", "what rate is used?". The live line was "i'm thinking of
buying a used car for 14000".
"""

from __future__ import annotations

import re
from functools import cache

from app.modules.money.catalog import Product

_VEHICLE = r"(?:car|truck|suv|vehicle)"
_BUYING = (
    r"(?:buy|buying|bought|get|getting|finance|financing|purchase|purchasing|looking\sat|"
    r"thinking\sof\sbuying)"
)
# "Or buy a used car with cash", "vs buying a used car": the alternative, not this loan.
_ALTERNATIVE_BEFORE = re.compile(
    r"\b(?:or|vs\.?|versus|than|instead\sof|rather\sthan|not)\s$", re.I
)


@cache
def _phrases(words: tuple[str, ...]) -> tuple[re.Pattern[str], ...]:
    kind = "(?:certified\\s)?(?:" + "|".join(re.escape(word) for word in words) + ")"
    return tuple(
        re.compile(pattern, re.I)
        for pattern in (
            rf"\b{_BUYING}\s(?:(?:a|an)\s)?{kind}[\s-]{_VEHICLE}\b",
            rf"\b(?:a|an)\s{kind}[\s-]{_VEHICLE}\sfor\s(?:[$€£¥₹₦]\s?)?\d",
            rf"\b{kind}[\s-]{_VEHICLE}\sloans?\b",
            rf"\bloan\sfor\s(?:a|an)\s{kind}[\s-]{_VEHICLE}\b",
        )
    )


def named_variant(product: Product, text: str) -> str:
    """The kind of ``product`` the message names ("buying a used car": "used"), or ""."""
    lowered = " ".join(text.lower().split())
    for variant in product.variants:
        for pattern in _phrases(variant.words):
            for match in pattern.finditer(lowered):
                before = lowered[max(0, match.start() - 16) : match.start()]
                if _ALTERNATIVE_BEFORE.search(before) is None:
                    return variant.key
    return ""
