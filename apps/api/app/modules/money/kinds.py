"""Which kind of a product a message names: a catalog ``Variant`` ("a used car") or the
product's own kind ("a new car"), read as describing words only.

"Used" is also a verb ("I used a calculator", "I'm used to paying 300") and "new" is
everywhere ("a new job"), so each counts only where it describes what is bought.
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
_VERB_AFTER = re.compile(
    r"\s(?:to|for|by|as|in|on|with|at|it|them|this|that|a|an|the|my|your|our|their)\b", re.I
)
# "New" is everywhere ("a new job"); it names the kind only beside what is bought: "a new
# car", "a new one", "buy new instead", "it was new?".
_PLAIN_KIND_AFTER = re.compile(
    r"\s(?:car|one|vehicle|truck|suv|auto|model)\b|\s?(?:instead\b|[?.!,]|$)", re.I
)


def named_variant(product: Product, text: str) -> str:
    """The kind of ``product`` the message names ("a used car": "used"), or ""."""
    lowered = text.lower()
    for variant in product.variants:
        for word in variant.words:
            for match in re.finditer(rf"(?<![\w-]){re.escape(word)}(?!\w)", lowered):
                before = lowered[max(0, match.start() - 16) : match.start()]
                if _VERB_BEFORE.search(before) or _VERB_AFTER.match(lowered, match.end()):
                    continue
                return variant.key
    return ""


def named_plain_kind(product: Product, text: str) -> bool:
    """The message names the product's own kind against its variants: "a new car"."""
    lowered = text.lower()
    return any(
        _PLAIN_KIND_AFTER.match(lowered, match.end())
        for word in product.plain_words
        for match in re.finditer(rf"(?<![\w-]){re.escape(word)}(?!\w)", lowered)
    )
