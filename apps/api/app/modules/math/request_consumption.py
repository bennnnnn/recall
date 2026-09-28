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
_STATISTIC_NAME = (
    r"(?:z[-\s]?score|arithmetic\s+mean|mean|median|mode|range|variance|"
    r"standard\s+deviation|stdev)"
)
_MULTIPLE_REQUESTED_STATISTICS = re.compile(
    r"\b(?:find|calculate|compute|determine|give|what\s+(?:is|are))\b"
    rf"[^.?!]{{0,50}}\b{_STATISTIC_NAME}\b[^.?!]{{0,30}}\b(?:and|plus)\b"
    rf"[^.?!]{{0,30}}\b{_STATISTIC_NAME}\b",
    re.IGNORECASE,
)
_LABELED_Z_SCORE_OPERAND = re.compile(
    r"\b(?:mean(?:\s+score)?|standard\s+deviation|std(?:\s+dev)?|stdev)"
    r"(?:\s+is|\s*=)?\s+[+-]?(?:\d+(?:\.\d+)?|\.\d+)\b",
    re.IGNORECASE,
)
_GRAPH_REQUEST = re.compile(r"\b(?:graph|plot|sketch)\b", re.IGNORECASE)
_ROOT_OUTPUT_REQUEST = re.compile(
    r"\b(?:roots|zeros)\b"
    r"|\b(?:find|tell\s+me|give|determine|calculate|compute|what\s+is)\b"
    r"[^.?!]{0,40}\b(?:the|a|its)?\s*(?:root|zero)\b",
    re.IGNORECASE,
)
_NAMED_RADICAL = re.compile(
    r"\b(?:square|cube|fourth|fifth|sixth|seventh|eighth|n(?:th)?|"
    r"[2-9](?:nd|rd|th))\s+root\b",
    re.IGNORECASE,
)
_NUMBER_SET_DOMAIN = (
    r"(?:(?:integers?|natural\s+numbers?|rationals?(?:\s+numbers?)?|"
    r"complex(?:\s+numbers?)?)\b|[\u2124\u2115\u211A\u2102]|"
    r"\\mathbb\s*\{\s*[ZNQC]\s*\})"
)
_REAL_NUMBER_SET = r"(?:\u211D|\\mathbb\s*\{\s*R\s*\})"
_DOMAIN_ADJECTIVE = (
    r"(?:positive|negative|non[-\s]?negative|non[-\s]?positive|non[-\s]?zero|"
    r"odd|even|prime|composite)"
)
_DOMAIN_CUE = (
    r"(?:(?:for|where|also|with|and|if)\b|"
    r"(?:assuming|given|provided)(?:\s+that)?\b|subject\s+to\b|[,;])"
)
_EQUALITY_DOMAIN_CUE = r"(?:where\b|(?:assuming|given|provided)(?:\s+that)?\b|subject\s+to\b)"
_NONDEFAULT_DOMAIN = re.compile(
    rf"\b(?:in|over)\s+(?:the\s+)?{_NUMBER_SET_DOMAIN}"
    rf"|[a-z]\s*(?:∈|\\in\b)\s*(?!{_REAL_NUMBER_SET}(?:$|[\s,;.:)\]]))"
    rf"|{_DOMAIN_CUE}\s+[a-z]\s+in\s*[\[(]"
    rf"|{_DOMAIN_CUE}\s+[a-z]\s*(?:!=|≠|[<>≤≥])"
    rf"|{_DOMAIN_CUE}\s+[a-z]\s+(?:(?:must\s+(?:not\s+)?(?:be|equal)|is|are|"
    r"was|were|equals?|cannot\s+(?:be|equal)|being|belongs?\s+to|lies?\s+in)\b)"
    rf"|{_DOMAIN_CUE}\s+[a-z]\s+"
    rf"(?:{_DOMAIN_ADJECTIVE}|(?:an?\s+)?{_NUMBER_SET_DOMAIN})"
    rf"|{_DOMAIN_CUE}\s+(?:an?\s+)?(?:{_DOMAIN_ADJECTIVE}|{_NUMBER_SET_DOMAIN})"
    r"\s+[a-z]\b",
    re.IGNORECASE,
)
_LINKED_EQUALITY_DOMAIN = re.compile(
    rf"{_EQUALITY_DOMAIN_CUE}\s+[a-z]\s*={{1,2}}(?!=)",
    re.IGNORECASE,
)
_DOMAIN_BLIND_KINDS = frozenset(
    {"equation", "system", "inequality", "calculus", "limit", "graph", "graph_pair"}
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
    statistics_text = (
        _LABELED_Z_SCORE_OPERAND.sub("", text) if intent.school_op == "z_score" else text
    )
    additional = _ADDITIONAL_OPERATION.search(text)
    if additional is not None and _prior_math_request(text[: additional.start()]):
        leftovers.append("additional requested operation")
    if _MEAN_AND_SPREAD.search(statistics_text):
        # MathIntent currently represents one statistics operation. Until a
        # typed multi-stat result exists, declining is the only atomic answer.
        leftovers.append("additional requested statistic")
    if _MULTIPLE_REQUESTED_STATISTICS.search(statistics_text):
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
    root_request_text = _NAMED_RADICAL.sub("", text)
    if _GRAPH_REQUEST.search(text) and _ROOT_OUTPUT_REQUEST.search(root_request_text):
        # A graph intent has no typed roots result and a roots intent has no
        # graph result. Never certify whichever extractor happened to run first.
        leftovers.append("multiple requested function outputs")
    has_unrepresented_domain = bool(_NONDEFAULT_DOMAIN.search(text))
    if _LINKED_EQUALITY_DOMAIN.search(text):
        has_unrepresented_domain = True
    if intent.kind in _DOMAIN_BLIND_KINDS and has_unrepresented_domain:
        # These symbolic intents currently use their default real domain and
        # cannot encode an extra sign or number-set assumption. Never certify
        # a partial interpretation that silently discards that restriction.
        leftovers.append("unconsumed symbolic domain")
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
