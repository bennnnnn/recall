"""Shared lexical, cue, numeric, and unit extraction helpers."""

from __future__ import annotations

import logging
import re

from app.services.text_match import word_index

logger = logging.getLogger(__name__)

_NUMBER = r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"

_LENGTH_UNIT_PATTERN = (
    r"kilometers?|km|centimeters?|cm|millimeters?|mm|"
    r"nanometers?|nm|micrometers?|micrometres?|um|µm|"
    r"miles?|mi|meters?|metres?|m|feet|ft|yards?|yd|inches?|in"
)

_VELOCITY_UNIT_PATTERN = r"m/s|km/h|mph|cm/s|mm/s|miles\s+per\s+hour"

_G_DEFAULT = 9.81

_ELECTRON_MASS = 9.1093837015e-31

_ELEMENTARY_CHARGE = 1.602176634e-19

_VALUE_UNIT_RE = re.compile(
    rf"({_NUMBER})\s*"
    r"(m/s\^?2|m/s2|m/s|m\^?2/s\^?2|km/h|mph|miles\s+per\s+hour|cm/s|mm/s|"
    r"kilometers?|centimeters?|millimeters?|"
    r"miles?|minutes?|milliseconds?|seconds?|hours?|"
    r"meters?|metres?|inches?|yards?|feet|"
    r"km|cm|mm|mi|ft|yd|in|"
    r"kg|mg|lb|lbs|oz|"
    r"N|J|W|Pa|Hz|"
    r"s|ms|sec|min|hr|h|"
    r"deg|degrees|°|rad|radians)?"
    r"(?![A-Za-z0-9/^])",
    re.IGNORECASE,
)


def _has_cue_either_case(
    cleaned: str,
    cues: tuple[str, ...],
    regexes: tuple[re.Pattern[str], ...] = (),
) -> bool:
    """`_has_cue`, but the regexes see the text as written as well as lowered.

    A few cue regexes mean the SI symbols `V` and `A` and are case-sensitive on
    purpose - "12 V and 3 A" is a circuit, "12 v cards and 3 a piece" is not.
    Handing them only lowercased text silently disables them, which is exactly
    what the pre-filter did: `needs_symbolic` dropped questions the extractor
    would have answered, because the extractor saw the original casing and the
    pre-filter did not. The two have to see the same thing.
    """
    lower = cleaned.lower()
    if any(cue in lower for cue in cues):
        return True
    return any(rx.search(cleaned) or rx.search(lower) for rx in regexes)


def _has_cue(
    lower: str,
    cues: tuple[str, ...],
    regexes: tuple[re.Pattern[str], ...] = (),
) -> bool:
    """Cue match: plain substrings, plus regexes for cues that need a boundary.

    Most cues are safe as substrings ("net force"). A few are not: "find f"
    sits inside "find factors", and "KE" inside "take". Those are expressed as
    regexes instead of widening the tuple.
    """
    if any(cue in lower for cue in cues):
        return True
    return any(rx.search(lower) for rx in regexes)


def _find_value_with_unit(text: str, keywords: tuple[str, ...]) -> tuple[float, str] | None:
    """Find the first number near a keyword (e.g. "height of 20m", "20m high").

    Returns (value, unit) where unit is "" if no unit was found. The unit is
    not validated here — the solver runs it through Pint.
    """
    lower = text.lower()
    for kw in keywords:
        idx = lower.find(kw)
        if idx == -1:
            continue
        # Search a window after the keyword for a number (the common case:
        # "height of 20m", "velocity 15 m/s"). Also search a small window
        # *before* the keyword ("20m high", "15 m/s initial velocity").
        after = text[idx + len(kw) : idx + len(kw) + 40]
        m = _VALUE_UNIT_RE.match(after.strip())
        if m:
            val = float(m.group(1))
            unit = (m.group(2) or "").strip()
            return val, unit
        before = text[max(0, idx - 40) : idx]
        m = _VALUE_UNIT_RE.search(before)
        if m:
            val = float(m.group(1))
            unit = (m.group(2) or "").strip()
            return val, unit
    return None


def _find_value_after_keyword(text: str, keywords: tuple[str, ...]) -> tuple[float, str] | None:
    """Number immediately after a keyword — never the window before it.

    ``What`` / a preceding height must not bind as v0.
    """
    lower = text.lower()
    for kw in keywords:
        idx = lower.find(kw)
        if idx == -1:
            continue
        after = text[idx + len(kw) : idx + len(kw) + 40]
        m = _VALUE_UNIT_RE.match(after.strip())
        if m:
            return float(m.group(1)), (m.group(2) or "").strip()
    return None


def _find_value_with_specific_unit(
    text: str,
    unit_pattern: str,
    keywords: tuple[str, ...] = (),
    *,
    require_keyword: bool = False,
) -> tuple[float, str] | None:
    """Find a number followed by a specific unit (e.g. "20 N", "5 kg").

    When keywords are present in the text, prefer the unit-bearing value
    nearest one of them; otherwise use the first matching value. This avoids
    binding an earlier unrelated quantity to the requested mass/force/etc.

    ``require_keyword`` (projectile h0): if none of the keywords appear, return
    None instead of the first unlabeled length (``wall is 15 m away``).
    Kinematics unlabeled ``free fall 20 m`` still binds.
    """
    matches = list(
        re.finditer(
            rf"({_NUMBER})\s*({unit_pattern})(?![A-Za-z0-9/^])",
            text,
            re.IGNORECASE,
        )
    )
    if not matches:
        return None

    match = matches[0]
    if keywords:
        lower = text.lower()
        keyword_spans: list[tuple[int, int]] = []
        for keyword in keywords:
            start = 0
            while (idx := lower.find(keyword.lower(), start)) != -1:
                keyword_spans.append((idx, idx + len(keyword)))
                start = idx + len(keyword)
        if require_keyword and not keyword_spans:
            return None
        if keyword_spans:

            def distance_to_keyword(candidate: re.Match[str]) -> int:
                distances: list[int] = []
                for start, end in keyword_spans:
                    if candidate.end() <= start:
                        distances.append(start - candidate.end())
                    elif end <= candidate.start():
                        distances.append(candidate.start() - end)
                    else:
                        distances.append(0)
                return min(distances)

            match = min(matches, key=distance_to_keyword)
        elif require_keyword:
            return None

    return float(match.group(1)), match.group(2)


def _detect_gravity(text: str) -> float:
    """If the user named a gravity value, use it; else default 9.81 m/s^2."""
    lower = text.lower()
    # "g = 1.6", "gravity = 1.62", "g = 1.6 m/s^2"
    m = re.search(r"\bg\s*=\s*(-?\d+(?:\.\d+)?)", lower)
    if m:
        return float(m.group(1))
    m = re.search(r"\bgravity\s*(?:of|is|=)?\s*(-?\d+(?:\.\d+)?)", lower)
    if m:
        return float(m.group(1))
    if word_index(lower, "moon") != -1:
        return 1.62
    if word_index(lower, "mars") != -1:
        return 3.71
    return _G_DEFAULT


_PARAM_ASSIGN_RE = re.compile(
    r"\b(?:gravity|theta|angle|h_?0|v_?0|omega|mu|rho|delta|"
    r"[mqxv]_?[12]|[hFmgMRIcRx])\s*=\s*(?=-?\d)",
    re.IGNORECASE,
)

_T_ASSIGN_RE = re.compile(r"\bt\s*=\s*(?=-?\d)", re.IGNORECASE)

_NAMED_FORMULA_RE = re.compile(
    r"\b(?:using|from|with)\s+E\s*=\s*m\s*c(?:\^?2|²)\b",
    re.IGNORECASE,
)


def _strip_param_assignments(text: str) -> str:
    """Remove textbook labels such as ``h0 =``, ``m1 =``, ``x_2 =`` and
    ``g =`` so has_equation does not mistake a list of givens for algebra.
    The number and unit stay for the quantity scanners.

    Do not strip ``t`` / ``v`` / ``a`` / ``d`` — those are often the unknown
    (``find v when t = 1 s``) and stripping them silently solves the wrong op.
    """
    return _PARAM_ASSIGN_RE.sub("", _NAMED_FORMULA_RE.sub("", text))


def _ordered_values(text: str, unit_pattern: str) -> list[tuple[float, str]]:
    """Every number carrying one of these units, left to right.

    Collisions need two masses and two velocities *in the order written* —
    "a 2 kg ball at 3 m/s hits a 1 kg ball at rest" binds m1=2, v1=3, m2=1.
    The keyword-nearest search the other extractors use cannot express that.
    """
    return [
        (float(m.group(1)), m.group(2))
        for m in re.finditer(
            rf"({_NUMBER})\s*({unit_pattern})(?![A-Za-z0-9/^])",
            text,
            re.IGNORECASE,
        )
    ]


def _positioned_values(text: str, unit_pattern: str) -> list[tuple[int, float, str]]:
    """Like ``_ordered_values`` but keeps each match's offset.

    Torque balance needs to know *which* force a distance belongs to, which
    written order alone cannot say.
    """
    return [
        (m.start(), float(m.group(1)), m.group(2))
        for m in re.finditer(
            rf"({_NUMBER})\s*({unit_pattern})(?![A-Za-z0-9/^])",
            text,
            re.IGNORECASE,
        )
    ]
