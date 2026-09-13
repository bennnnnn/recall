"""Literal coordinate/vector operands and bounded whole-request matching."""

from __future__ import annotations

import math

from app.services.math_text_match.scan import word_index

_OPERATIONS = ("distance", "midpoint", "slope", "magnitude", "norm", "dot", "cross")
_REQUESTS = (
    ("distance between ", "(", ")", 2, "coord"),
    ("midpoint of ", "(", ")", 2, "coord"),
    ("midpoint between ", "(", ")", 2, "coord"),
    ("slope of the line through ", "(", ")", 2, "coord"),
    ("slope between ", "(", ")", 2, "coord"),
    ("magnitude of ", "<", ">", 1, "vector"),
    ("norm of ", "<", ">", 1, "vector"),
    ("dot product of ", "<", ">", 2, "vector"),
    ("cross product of ", "<", ">", 2, "vector"),
)


def has_coordinate_vector_request(text: str) -> bool:
    lower = text.lower()
    return any(word_index(lower, op) != -1 for op in _OPERATIONS) or "how far" in lower


def _take_tuple(text: str, opener: str, closer: str) -> tuple[list[float], str] | None:
    if not text.startswith(opener):
        return None
    end = text.find(closer, 1)
    if end < 0:
        return None
    parts = text[1:end].split(",")
    if not 2 <= len(parts) <= 3 or any(not part.strip() or len(part) > 64 for part in parts):
        return None
    try:
        values = [float(part.strip()) for part in parts]
    except (ValueError, OverflowError):
        return None
    if not all(math.isfinite(value) for value in values):
        return None
    return values, text[end + 1 :]


def literal_math_tuples(text: str, opener: str, closer: str) -> list[list[float]] | None:
    """Read every tuple; malformed/extra operands must not be silently skipped."""
    if len(text) > 2000:
        return None
    values: list[list[float]] = []
    rest = text
    while rest:
        start = rest.find(opener)
        if start < 0:
            return None if closer in rest else values
        if closer in rest[:start]:
            return None
        parsed = _take_tuple(rest[start:], opener, closer)
        if parsed is None:
            return None
        value, rest = parsed
        values.append(value)
    return values


def is_closed_coordinate_vector_request(text: str) -> bool:
    if len(text) > 1000:
        return False
    request = " ".join(text.lower().split()).rstrip(".?")
    for prefix in ("please ", "can you ", "could you "):
        if request.startswith(prefix):
            request = request[len(prefix) :]
            break
    for prefix in ("find ", "compute ", "calculate ", "determine ", "what is ", "what's "):
        if request.startswith(prefix):
            request = request[len(prefix) :]
            break
    if request.startswith("the "):
        request = request[4:]
    for prefix, opener, closer, count, kind in _REQUESTS:
        if not request.startswith(prefix):
            continue
        rest = request[len(prefix) :]
        operands: list[list[float]] = []
        for index in range(count):
            if index:
                if not rest.startswith(" and "):
                    return False
                rest = rest[5:]
            parsed = _take_tuple(rest, opener, closer)
            if parsed is None:
                return False
            operand, rest = parsed
            operands.append(operand)
        if rest.strip() or len({len(operand) for operand in operands}) != 1:
            return False
        dimension = len(operands[0])
        return dimension == 2 if kind == "coord" else True
    return False
