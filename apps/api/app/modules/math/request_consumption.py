"""Whole-request integrity checks shared by every math extractor."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.schemas.math import MathIntent

_ADDITIONAL_OPERATION = re.compile(
    r"\b(?:and|then|also|plus)\s+(?:then\s+)?"
    r"(?:solve|simplify|evaluate|calculate|compute|differentiate|integrate|"
    r"factor|expand|graph|plot|find|determine|convert|compare)\b",
    re.IGNORECASE,
)
_TRIG_CALL = re.compile(r"\b(?:sin|cos|tan|sec|csc|cot)\s*\(", re.IGNORECASE)
_MEAN_AND_SPREAD = re.compile(
    r"\b(?:find|calculate|compute|determine|give|what\s+(?:is|are))\b"
    r"[^.?!]{0,30}\b(?:mean\b[^.?!]{0,30}\b(?:and|plus)\b[^.?!]{0,20}"
    r"(?:standard\s+deviation|stdev|variance)|"
    r"(?:standard\s+deviation|stdev|variance)\b[^.?!]{0,30}\b(?:and|plus)\b"
    r"[^.?!]{0,20}mean)\b",
    re.IGNORECASE,
)
_AREA_AND_PERIMETER = re.compile(
    r"\b(?:area\b[^.?!]{0,30}\band\b[^.?!]{0,20}\bperimeter|"
    r"perimeter\b[^.?!]{0,30}\band\b[^.?!]{0,20}\barea)\b",
    re.IGNORECASE,
)
_MULTIPLE_REQUESTED_STATISTICS = re.compile(
    r"\b(?:find|calculate|compute|determine|give|what\s+(?:is|are))\b"
    r"[^.?!]{0,50}\b(?:arithmetic\s+mean|mean|median|mode|range|variance|"
    r"standard\s+deviation|stdev)\b[^.?!]{0,30}\b(?:and|plus)\b"
    r"[^.?!]{0,30}\b(?:arithmetic\s+mean|mean|median|mode|range|variance|"
    r"standard\s+deviation|stdev)\b",
    re.IGNORECASE,
)
_GRAPH_REQUEST = re.compile(r"\b(?:graph|plot|sketch)\b", re.IGNORECASE)
_ROOT_OUTPUT_REQUEST = re.compile(
    r"\b(?:roots|zeros)\b"
    r"|\b(?:find|tell\s+me|give|determine|calculate|compute|what\s+is)\b"
    r"[^.?!]{0,40}\b(?:the|a|its)?\s*(?:root|zero)\b",
    re.IGNORECASE,
)
_NONDEFAULT_DOMAIN = re.compile(
    r"\b(?:in|over)\s+(?:the\s+)?(?:integers?|natural\s+numbers?|rationals?|"
    r"complex\s+numbers?)\b"
    r"|\b(?:for|where|also)\s+[a-z]\s+(?:must\s+be\s+)?"
    r"(?:positive|negative|nonnegative|nonpositive|[<>≤≥])",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ConsumptionAudit:
    complete: bool
    leftovers: tuple[str, ...] = ()


def audit_math_request(text: str, intent: MathIntent) -> ConsumptionAudit:
    """Reject semantic components the chosen intent cannot represent.

    Extractors remain responsible for their closed grammar. This final seam
    catches cross-extractor partial matches: a valid first expression must not
    hide another requested operation, statistic, trig term, or measurement.
    """
    leftovers: list[str] = []
    is_z_score = intent.school_op == "z_score"
    additional = _ADDITIONAL_OPERATION.search(text)
    if additional is not None and _prior_math_request(text[: additional.start()]):
        leftovers.append("additional requested operation")
    if not is_z_score and _MEAN_AND_SPREAD.search(text):
        # MathIntent currently represents one statistics operation. Until a
        # typed multi-stat result exists, declining is the only atomic answer.
        leftovers.append("additional requested statistic")
    if not is_z_score and _MULTIPLE_REQUESTED_STATISTICS.search(text):
        # One MathIntent carries one statistical result. Different requested
        # summaries must be represented together or declined together. Input
        # labels such as "mean 72 and standard deviation 8" are deliberately
        # excluded: they are givens for a z-score, not requested outputs.
        leftovers.append("multiple requested statistics")
    if _AREA_AND_PERIMETER.search(text) and not (intent.wants_area and intent.wants_perimeter):
        # Supported geometry intents retain both requested flags and their
        # canonical diagram contains both values. Direct output stays off for
        # those multipart cases, but the model receives both verified facts.
        # Reject only when the chosen extractor silently lost one quantity.
        leftovers.append("additional requested measurement")
    source_trig_calls = len(_TRIG_CALL.findall(text))
    intent_text = " ".join(
        part for part in (intent.expr, intent.expr2, intent.lhs, intent.rhs) if part
    )
    if source_trig_calls > len(_TRIG_CALL.findall(intent_text)):
        leftovers.append("unconsumed trigonometric term")
    if _GRAPH_REQUEST.search(text) and _ROOT_OUTPUT_REQUEST.search(text):
        # A graph intent has no typed roots result and a roots intent has no
        # graph result. Never certify whichever extractor happened to run first.
        leftovers.append("multiple requested function outputs")
    if intent.kind == "equation" and _NONDEFAULT_DOMAIN.search(text):
        # Equation intents currently solve over their default real domain.
        # A sign or number-set restriction must not be silently discarded.
        leftovers.append("unconsumed equation domain")
    return ConsumptionAudit(complete=not leftovers, leftovers=tuple(leftovers))


def _prior_math_request(prefix: str) -> bool:
    """Distinguish a second operation from prose such as "graph theory"."""
    if re.search(r"[=+\-*/^<>≤≥]", prefix) or re.search(r"\d", prefix):
        return True
    return (
        re.search(
            r"\b(?:solve|simplify|evaluate|calculate|compute|differentiate|integrate|"
            r"factor|expand|plot|find|determine|convert|compare)\b",
            prefix,
            re.IGNORECASE,
        )
        is not None
    )


def request_consumption_complete(text: str, intent: MathIntent) -> bool:
    return audit_math_request(text, intent).complete
