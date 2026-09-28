"""Shared readers for the closed school-physics templates."""

from __future__ import annotations

import re

from app.models.schemas.physics import PhysicsIntent
from app.modules.physics.extractors.common import _NUMBER

_OHM = r"ohms?|\u03a9"
_AMP = r"A|amps?|amperes?"
_HENRY = r"mH|millihenrys?|millihenries|H|henrys?|henries"
_FARAD = r"mF|uF|µF|nF|pF|F|farads?|microfarads?"
_HERTZ = r"Hz|hertz|kHz|kilohertz"
_WEBER = r"Wb|webers?"
_TESLA = r"T|tesla|teslas|mT|millitesla"
# A following viscosity unit is not a pressure. ``Pa*s`` must not bind as pascals.
_PRESSURE = r"Pa(?!\s*[*·]?\s*s)|pascals?|kPa|kilopascals?|MPa|megapascals?"
_SECOND = r"seconds?|secs?|s"
_VOLUME = r"m\^?3|cm\^?3|litres?|liters?"


def _intent(
    kind: str,
    operation: str,
    params: dict[str, float],
    units: dict[str, str],
) -> PhysicsIntent:
    return PhysicsIntent(
        kind=kind,  # type: ignore[arg-type]
        physics_op=operation,  # type: ignore[arg-type]
        physics_params=params,
        physics_units=units,
        operation="solve",
    )


def _numbers_before(pattern: str, text: str) -> list[float]:
    found = re.search(pattern, text, re.IGNORECASE)
    if found is None:
        return []
    return [float(value) for value in re.findall(_NUMBER, found.group(1))]


def _sum_directed(text: str, verb: str, label: str) -> float | None:
    grouped = _numbers_before(
        rf"((?:{_NUMBER}\s*(?:{_AMP})(?:\s*(?:,|and)\s*)?)+)\s*(?:{verb})",
        text,
    )
    labeled = _numbers_before(
        rf"\b{label}(?:\s+currents?)?(?:\s+of)?\s+"
        rf"((?:{_NUMBER}\s*(?:{_AMP})(?:\s*(?:,|and)\s*)?)+)",
        text,
    )
    values = grouped or labeled
    if not values:
        return None
    return float(sum(values))


def _henry_unit(raw: str) -> str:
    if raw.lower().startswith("m"):
        return "millihenry"
    return "henry"


def _keyword_spans(text: str, keywords: tuple[str, ...]) -> list[tuple[int, int]]:
    """Whole-word hits only. ``in`` must not match the start of ``inductor``."""
    lower = text.lower()
    spans: list[tuple[int, int]] = []
    for keyword in keywords:
        spans.extend(
            (found.start(), found.end())
            for found in re.finditer(rf"\b{re.escape(keyword.lower())}\b", lower)
        )
    return spans


def _one(
    text: str,
    unit: str,
    keywords: tuple[str, ...] = (),
    *,
    require_keyword: bool = False,
) -> tuple[float, str] | None:
    matches = list(
        re.finditer(
            rf"({_NUMBER})\s*({unit})(?![A-Za-z0-9/^])",
            text,
            re.IGNORECASE,
        )
    )
    if not matches:
        return None
    spans = _keyword_spans(text, keywords)
    if keywords and require_keyword and not spans:
        return None
    match = matches[0]
    if spans:

        def distance(candidate: re.Match[str]) -> int:
            distances: list[int] = []
            for start, end in spans:
                if candidate.end() <= start:
                    distances.append(start - candidate.end())
                elif end <= candidate.start():
                    distances.append(candidate.start() - end)
                else:
                    distances.append(0)
            return min(distances)

        match = min(matches, key=distance)
    return float(match.group(1)), match.group(2)


def _has_word(text: str, words: tuple[str, ...]) -> bool:
    return any(re.search(rf"\b{re.escape(word)}\b", text) for word in words)


def _turns(text: str, lower: str) -> float | None:
    match = re.search(rf"({_NUMBER})\s*(?:turns?|coils?)", text, re.IGNORECASE)
    if match is not None:
        return float(match.group(1))
    if re.search(r"\b(?:a|one|single)\s+(?:loop|turn|coil)\b", lower):
        return 1.0
    return None


def _kelvin(text: str, keywords: tuple[str, ...]) -> tuple[float, str] | None:
    """Temperature named by the words that follow it, not the nearer neighbor.

    ``300 K and a cold reservoir at 250 K`` sits closer to the word ``cold``
    than ``250 K`` does, so a nearest-either-side search would swap the reservoirs.
    """
    for _start, end in _keyword_spans(text, keywords):
        window = text[end : end + 48]
        found = re.search(
            rf"({_NUMBER})\s*(K|kelvins?)(?![A-Za-z0-9/^])",
            window,
            re.IGNORECASE,
        )
        if found is not None:
            return float(found.group(1)), found.group(2)
    return None
