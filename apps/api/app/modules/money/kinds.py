"""Which kind of a product a message names: a catalog ``Variant`` ("a used car"), read as
a describing word only. "Used" is also a verb ("I used a calculator", "I'm used to paying
300"), so it counts only where it describes what is bought.
"""

from __future__ import annotations

import re

from app.modules.money.catalog import Product

# A kind word that is a verb names no kind: "I used a calculator", "I'm used to paying 300",
# "the car I used to have", "what would I have used", "the rate used for car loans".
_VERB_BEFORE = re.compile(
    r"(?:\b(?:i|we|you|they|he|she|who|have|has|had|having|would|could|should|will|never|"
    r"just|already|also|once|ever|always|been|get|got)|'(?:ve|d|m|ll|re))\s$",
    re.I,
)
# "Bought it used at 9%" and "used for 14000" describe; "used for car loans" does not.
_VERB_AFTER = re.compile(
    r"\s(?:to|by|as|in|on|with|it|them|this|that|a|an|the|my|your|our|their)\b"
    r"|\sfor\s(?![$€£¥₹₦]?\d)",
    re.I,
)


def named_variant(product: Product, text: str) -> str:
    """The kind of ``product`` the message names ("a used car": "used"), or ""."""
    lowered = text.lower()
    for variant in product.variants:
        for word in variant.words:
            for match in re.finditer(rf"(?<![\w-]){re.escape(word)}(?!\w)", lowered):
                if _describes(lowered, match.start(), match.end()):
                    return variant.key
    return ""


def _describes(lowered: str, start: int, end: int) -> bool:
    """The kind word at ``start:end`` describes what is bought, not a verb ("I used")."""
    before = lowered[max(0, start - 16) : start]
    return not (_VERB_BEFORE.search(before) or _VERB_AFTER.match(lowered, end))
