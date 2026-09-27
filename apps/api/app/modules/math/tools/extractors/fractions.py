"""Closed whole-request grammars for primary-school fraction procedures."""

from __future__ import annotations

import re

from app.models.schemas.math import MathIntent
from app.modules.math.response_intent import strip_math_response_wrappers
from app.modules.math.tools.lesson import lesson_math_text
from app.services.text_normalize import collapse_ws

_F = r"\d+\s*/\s*\d+"
_SIMPLE = re.compile(rf"^(?:simplify|reduce)\s+(?P<a>{_F})$", re.IGNORECASE)
_BINARY = re.compile(
    rf"^(?P<a>{_F})\s*(?P<op>\+|-|\*|\u00d7|x|\u00f7|divided\s+by)\s*(?P<b>{_F})$",
    re.IGNORECASE,
)
_OF_QUANTITY = re.compile(
    rf"^(?:find\s+)?(?P<a>{_F})\s+of\s+(?P<quantity>\d+(?:\.\d+)?)$",
    re.IGNORECASE,
)
_MIXED_TO_IMPROPER = re.compile(
    rf"^(?:convert\s+)?(?P<whole>\d+)\s+(?P<a>{_F})\s+(?:to|into)\s+(?:an?\s+)?improper\s+fraction$",
    re.IGNORECASE,
)
_IMPROPER_TO_MIXED = re.compile(
    rf"^(?:convert\s+)?(?P<a>{_F})\s+(?:to|into)\s+(?:a\s+)?mixed\s+(?:number|fraction)$",
    re.IGNORECASE,
)
_EQUIVALENT = re.compile(
    rf"^(?:find\s+)?(?:an?\s+)?equivalent\s+fraction\s+(?:to|for)\s+(?P<a>{_F})\s+"
    r"with\s+denominator\s+(?P<target>\d+)$",
    re.IGNORECASE,
)
_COMPARE = re.compile(
    rf"^(?:compare|which\s+is\s+(?:larger|greater|smaller|less),?)\s+(?P<a>{_F})\s+"
    rf"(?:and|or)\s+(?P<b>{_F})$",
    re.IGNORECASE,
)


def _compact_fraction(value: str) -> str:
    return value.replace(" ", "")


def _fraction_body(text: str) -> str:
    body = lesson_math_text(strip_math_response_wrappers(text)).strip(" :?.!")
    return collapse_ws(body)


def extract_fraction_intent(text: str) -> MathIntent | None:
    """Extract only when the complete remaining request is one fraction task."""
    body = _fraction_body(text)
    if not body:
        return None
    match = _SIMPLE.fullmatch(body)
    if match:
        operand = _compact_fraction(match["a"])
        return MathIntent(
            kind="arithmetic",
            school_op="fraction_simplify",
            fraction_operands=[operand],
            expr=operand,
            operation="solve",
        )
    match = _BINARY.fullmatch(body)
    if match:
        left, right = _compact_fraction(match["a"]), _compact_fraction(match["b"])
        op = match["op"].lower()
        operation = {
            "+": "fraction_add",
            "-": "fraction_subtract",
            "*": "fraction_multiply",
            "\u00d7": "fraction_multiply",
            "x": "fraction_multiply",
            "\u00f7": "fraction_divide",
            "divided by": "fraction_divide",
        }[op]
        return MathIntent(
            kind="arithmetic",
            school_op=operation,
            fraction_operands=[left, right],
            expr=f"{left}{match['op']}{right}",
            operation="solve",
        )
    match = _OF_QUANTITY.fullmatch(body)
    if match:
        fraction = _compact_fraction(match["a"])
        quantity = match["quantity"]
        return MathIntent(
            kind="arithmetic",
            school_op="fraction_of_quantity",
            fraction_operands=[fraction, quantity],
            expr=f"{fraction} of {quantity}",
            operation="solve",
        )
    match = _MIXED_TO_IMPROPER.fullmatch(body)
    if match:
        fraction = _compact_fraction(match["a"])
        return MathIntent(
            kind="arithmetic",
            school_op="fraction_mixed_to_improper",
            fraction_operands=[match["whole"], fraction],
            expr=f"{match['whole']} {fraction}",
            operation="solve",
        )
    match = _IMPROPER_TO_MIXED.fullmatch(body)
    if match:
        operand = _compact_fraction(match["a"])
        return MathIntent(
            kind="arithmetic",
            school_op="fraction_improper_to_mixed",
            fraction_operands=[operand],
            expr=operand,
            operation="solve",
        )
    match = _EQUIVALENT.fullmatch(body)
    if match:
        operand = _compact_fraction(match["a"])
        return MathIntent(
            kind="arithmetic",
            school_op="fraction_equivalent",
            fraction_operands=[operand],
            fraction_target=int(match["target"]),
            expr=operand,
            operation="solve",
        )
    match = _COMPARE.fullmatch(body)
    if match:
        left, right = _compact_fraction(match["a"]), _compact_fraction(match["b"])
        return MathIntent(
            kind="arithmetic",
            school_op="fraction_compare",
            fraction_operands=[left, right],
            expr=f"{left} ? {right}",
            operation="solve",
        )
    return None
