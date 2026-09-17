"""Canonicalize complete numeric literals before heuristic physics extraction.

This is lexical normalization, not calculation: units and the user's stored
message stay unchanged. Refuse malformed or oversized tokens rather than let
an extractor consume a suffix (``.5`` as ``5``, or ``2e1`` as ``1``).
"""

from __future__ import annotations

import math
import re
from decimal import Decimal, InvalidOperation

_START = re.compile(r"(?<![\w.])(?=[+-]?(?:\d|\.\d))")
_LITERAL = re.compile(r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?")
# Legacy keyword scanners inspect 40-character windows. Never expand a
# literal beyond that window and thereby make a prefix look like the value.
_MAX_LITERAL_CHARS = 36
_MAX_INPUT_CHARS = 12_000


def normalize_physics_numbers(text: str) -> str | None:
    """Return equivalent decimal spellings, or None for an unsafe token.

    Signed decimals, leading-dot decimals, and scientific notation are
    supported. Ambiguous thousands separators, incomplete exponents, and
    repeated decimal points fail closed. Decimal bounds are checked before
    expansion so an exponent cannot allocate an unbounded string.
    """
    if len(text) > _MAX_INPUT_CHARS:
        return None
    text = text.replace("\u2212", "-")
    if re.search(
        r"[A-Za-z_]\.\d|(?<!\w)[+-]{2,}(?=\d|\.\d)"
        r"|(?<!\w)[+-]\s+(?=\d|\.\d)|\d\s*/\s*[+-]?(?:\d|\.)",
        text,
    ):
        return None
    pieces: list[str] = []
    end = 0
    for start in _START.finditer(text):
        if start.start() < end:
            continue
        match = _LITERAL.match(text, start.start())
        if match is None:
            return None
        token = match.group()
        tail = text[match.end() :]
        if re.match(r"(?:\.[.\d]|[,_]\d|[eE](?:[+\-\d]|\b))", tail):
            return None
        if len(token) > 128:
            return None
        try:
            value = Decimal(token)
            if not value.is_finite() or (value and abs(value.adjusted()) > 36):
                return None
            decimal = "0" if value.is_zero() else format(value, "f")
        except (InvalidOperation, ValueError, OverflowError):
            return None
        if "." in decimal:
            decimal = decimal.rstrip("0").rstrip(".")
        if decimal in {"-0", "+0"}:
            decimal = "0"
        if len(decimal) > _MAX_LITERAL_CHARS:
            return None
        number = float(value)
        if not math.isfinite(number) or (value != 0 and number == 0):
            return None
        pieces.extend((text[end : start.start()], decimal))
        end = match.end()
    pieces.append(text[end:])
    return "".join(pieces)


def numeric_spans(text: str) -> list[tuple[int, int]]:
    """Complete literal spans in already-normalized solver input."""
    spans: list[tuple[int, int]] = []
    for start in _START.finditer(text):
        if spans and start.start() < spans[-1][1]:
            continue
        match = _LITERAL.match(text, start.start())
        if match is not None:
            spans.append(match.span())
    return spans
