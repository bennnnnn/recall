"""Shared number and word scans for school arithmetic extractors."""

from __future__ import annotations

import math
import re

from app.modules.math import match as mtm
from app.services.text_match import word_index

_PROB_NUMBER = r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)"


_LABELED_NUMBER = r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)"


def _count_char(text: str, needle: str) -> int:
    count = 0
    for char in text:
        if char == needle:
            count += 1
    return count


def _has_any_word(lower: str, words: tuple[str, ...]) -> bool:
    return any(word_index(lower, word) != -1 for word in words)


def _finite_match_value(match: re.Match[str]) -> float | None:
    try:
        value = float(match.group(0))
    except ValueError:
        return None
    if not math.isfinite(value):
        return None
    return value


def _number_immediately_before(text: str, idx: int) -> re.Match[str] | None:
    end = idx
    while end > 0 and text[end - 1].isspace():
        end -= 1
    found = None
    for match in mtm._NUM.finditer(text[:end]):
        found = match
    if found is None or found.end() != end:
        return None
    return found


def _colon_ratio_parts(text: str) -> tuple[list[float], list[tuple[int, int]]] | None:
    """First ``a:b`` / ``a:b:c`` group. Linear scan, no nested regex."""
    search_from = 0
    length = len(text)
    while search_from < length:
        match = mtm._NUM.search(text, search_from)
        if match is None:
            return None
        cursor = match.end()
        while cursor < length and text[cursor].isspace():
            cursor += 1
        if cursor >= length or text[cursor] != ":":
            search_from = match.end()
            continue
        values = [_finite_match_value(match)]
        spans = [(match.start(), match.end())]
        if values[0] is None:
            search_from = match.end()
            continue
        cursor += 1
        while True:
            while cursor < length and text[cursor].isspace():
                cursor += 1
            nxt = mtm._NUM.match(text, cursor)
            if nxt is None:
                break
            parsed = _finite_match_value(nxt)
            if parsed is None:
                break
            values.append(parsed)
            spans.append((nxt.start(), nxt.end()))
            cursor = nxt.end()
            while cursor < length and text[cursor].isspace():
                cursor += 1
            if cursor < length and text[cursor] == ":":
                cursor += 1
                continue
            break
        finite_parts = [part for part in values if part is not None]
        if len(finite_parts) >= 2:
            return finite_parts, spans
        search_from = match.end()
    return None
