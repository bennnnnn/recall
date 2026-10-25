"""Which kind of a product a message names: a catalog ``Variant`` ("a used car").

A kind word counts only where it describes the vehicle being financed: "buying a used
car", "a used car for 14000", "used car loan". A review (2026-10-25) found "used"
anywhere in the message making it a used car: "trading in my used car, new car loan
30000", "I don't want a used one", "what rate is used?". So the word must sit right
before the vehicle (or "car loan"), must not be a verb ("I used a calculator", "the rate
is used"), must not be about another car ("my used car", "trading in", "sold", "instead
of", "not a"), and a message that names a new car is about a new one.
"""

from __future__ import annotations

import re

from app.modules.money.catalog import Product

# The vehicle the kind word describes, a word or two after it: "used car", "pre-owned
# 2019 truck", "used car loan". Plurals and markets are about cars in general.
_VEHICLE_AFTER = re.compile(
    r"[\s-](?:[a-z0-9-]+\s){0,2}?(?:car|truck|suv|vehicle|van|auto)\b"
    r"(?!s\b|\s(?:market|prices?|values?|lots?|dealers?|dealerships?|sales|cost|costs)\b)",
    re.I,
)
# The kind word is a verb, or describes a car other than the one being financed. ("The rate
# is used" has no vehicle after it, so it never counts.)
_NOT_THIS_ONE_BEFORE = re.compile(
    r"(?:\b(?:i|we|you|they|he|she|who|have|has|had|having|would|could|should|will|never|"
    r"just|already|also|once|ever|always|been|get|got|my|our|"
    r"his|her|their|sold|sell|selling|trade|trading|traded|not|instead\sof|rather\sthan|"
    r"don't\swant|do\snot\swant|no)|'(?:ve|d|m|ll|re|s)|\btrading\sin|\btrade[\s-]in)"
    r"(?:\s(?:a|an|the|my|our))?\s$",
    re.I,
)
# A message about a new car is about a new one, whatever else it says about used ones.
_NEW_CAR = re.compile(
    r"\b(?:brand[\s-])?new\s(?:[a-z0-9-]+\s)?(?:car|truck|suv|vehicle|van|auto|one)\b", re.I
)


def named_variant(product: Product, text: str) -> str:
    """The kind of ``product`` the message names ("a used car": "used"), or ""."""
    lowered = text.lower()
    if not product.variants or _NEW_CAR.search(lowered):
        return ""
    for variant in product.variants:
        for word in variant.words:
            for match in re.finditer(rf"(?<![\w-]){re.escape(word)}(?!\w)", lowered):
                before = lowered[max(0, match.start() - 24) : match.start()]
                if _NOT_THIS_ONE_BEFORE.search(before) is None and _VEHICLE_AFTER.match(
                    lowered, match.end()
                ):
                    return variant.key
    return ""
