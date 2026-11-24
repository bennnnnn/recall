"""A decimal given for an exact value, written right: "√65/8 cm (approximately 0.999 cm)".

The working check (``working_check``) holds a step's arithmetic; this holds the decimal a
reply puts beside an exact value it worked out, a few words apart, to that value at the
same places.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from app.modules.chat.tex_arithmetic import is_unit_word, log_readings, plain_arithmetic
from app.modules.chat.working_check import DECIMAL, RELATION, is_off
from app.modules.chat.working_numbers import shown_like, shown_number
from app.services.md_fence_scan import iter_fences

# "$\frac{\sqrt{65}}{8}$ cm (approximately 0.999 cm)", "**$2\sqrt{30}$ cm** (approx. $10.95$ cm)":
# an exact value and the decimal a reply gives for it, a few words apart.
_APPROXIMATED = re.compile(
    r"\$(?P<exact>[^$\n]{1,200})\$(?P<gap>[^$\n()~≈]{0,30}?)\(?"
    r"(?:approx(?:imately|\.)?|≈|~)[\s*$]*(?P<number>-?\d+(?:\.\d+)?)"
)


def corrected_approximations(reply: str) -> str:
    """``reply`` with each decimal given for an exact value it misstates written correctly, to
    the same places: "√65/8 cm (approximately 0.999 cm)" is 1.008 (live, 2026-11-21), and
    "2(√10 + √13 + √17) (approximately 19.13)" is 21.78. Only an exact value of plain numbers
    is held, never a side that carries a rounded decimal itself."""

    def fix(match: re.Match[str]) -> str:
        exact_tex = RELATION.split(match.group("exact"))[-1].strip()
        plain = plain_arithmetic(exact_tex)
        if plain is None or DECIMAL.search(plain) is not None:
            return match.group(0)
        if _another_unit(match) or not _units_only(match.group("gap")):
            return match.group(0)
        shown = shown_number(match.group("number"), coarse=True)
        readings = log_readings(plain)
        if shown is None or not readings:
            return match.group(0)
        # A log with no base is base 10 or e: the reading nearest the decimal is the one meant
        # ("log 2 (approximately 0.693)" is ln 2; review, #2576).
        value = min(readings, key=lambda reading: abs(reading - shown[0]))
        if not is_off(value, shown[0], shown[1]):
            return match.group(0)
        start = match.start("number") - match.start()
        end = match.end("number") - match.start()
        whole = match.group(0)
        return whole[:start] + shown_like(value, match.group("number")) + whole[end:]

    return _outside_fences(reply, lambda text: _APPROXIMATED.sub(fix, text))


# What follows an approximated number: a unit ("70.7 cm", "$10.95$ \\text{cm}"), or a mark that
# makes it another number than its digits ("1.67 \\times 10^{-4}", "8%", "30°", "1,224.74"), or a
# fraction, ratio or range of which it is only the start ("22/7", "3:1", "2-3", "2 to 3").
_UNIT_AFTER = re.compile(
    r"[ \t$]*(?:\\[,; ][ \t]*)?"
    r"(?:\\(?:text|mathrm)\s*\{\s*([^{}\s]{1,12})\s*\}|([A-Za-zµμΩ]+)|(\\times|\u00d7|\*\s*10\b|e[-+]?\d|"
    r"\\?%|°|\^|\\circ|\\deg|,\d|[ \t]*[/:\u2013-][ \t]*\d|[ \t]+to[ \t]+\d))"
)
_WORD = re.compile(r"[A-Za-zµμΩ°]+")


def _another_unit(match: re.Match[str]) -> bool:
    """The decimal is not the exact value's own, written to places: given in a unit the exact
    value is not written in ("√2/2 m (approximately 70.7 cm)", "1/3 hr (approximately 20
    minutes)"), or in powers of ten, a percent or degrees (review, #2520)."""
    after = _UNIT_AFTER.match(match.string, match.end())
    if after is None:
        return False
    if after.group(3) is not None:
        return True
    unit = after.group(1) or after.group(2)
    return unit is not None and unit not in _WORD.findall(match.group("exact") + match.group("gap"))


def _units_only(gap: str) -> bool:
    """Between the exact value and its decimal only a unit and marks: "$√65/8$ cm (approx.",
    never words ("$√3$, the height is approximately 8.66" names another value)."""
    return all(
        is_unit_word(word) or word.lower() in _GAP_WORDS
        for word in re.findall(r"[A-Za-zµμΩ]+", gap)
    )


# Words a unitless or an area's value is written with: "19.13 units", "8 square cm".
_GAP_WORDS = frozenset({"units", "unit", "square", "sq", "cubic"})


def _outside_fences(text: str, change: Callable[[str], str]) -> str:
    """``change`` applied to the text between fences, every fence as written."""
    pieces: list[str] = []
    cursor = 0
    for fence in iter_fences(text):
        pieces.extend([change(text[cursor : fence.start]), text[fence.start : fence.end]])
        cursor = fence.end
    pieces.append(change(text[cursor:]))
    return "".join(pieces)
