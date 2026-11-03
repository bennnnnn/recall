# ruff: noqa: RUF001, RUF003 -- units are read as written: ×, µ, Ω, °, ², ⁻.
"""A model's own answer line as an answer card draws it.

The card draws its value as maths: every letter outside a ``\\text{}`` is a symbol in the
maths italic, and markdown is not read there. So a line the model wrote for a reader,
``(a) Work input = **1.2J**`` (a scanned lever, 2026-11-03), came out as italic letters
with its asterisks showing. Before a model's line becomes a card:

- ``without_emphasis``: markdown emphasis (``**bold**``, ``__bold__``, ``*it*``, ``_it_``)
  is dropped outside its maths, and bold inside it (``$x = **3**$``), so no mark reaches a
  value drawn as maths;
- ``named_value``: a quantity named in words keeps its words as text and puts only its
  value in maths, ``Work input = $1.2\\,\\mathrm{J}$``, the way a card holding words and
  maths is drawn on the phone (``lib/math/answerLayout.ts``).
"""

from __future__ import annotations

import re

_MATH = re.compile(r"\$\$.*?\$\$|\$[^$\n]*\$|\\\(.*?\\\)|\\\[.*?\\\]", re.DOTALL)
_STRONG = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*|__(?=\S)(.+?)(?<=\S)__")
_EMPHASIS = re.compile(
    r"(?<![\w*])\*(?=\S)([^*\n]+?)(?<=\S)\*(?![\w*])|(?<!\w)_(?=\S)([^_\n]+?)(?<=\S)_(?!\w)"
)
# "1.2J", "100%", "4.5 × 10^23 molecules", "25 °C": a number and its unit, nothing else.
_VALUE = re.compile(
    r"(?P<number>[-−]?\d+(?:[.,]\d+)?)"
    r"(?:\s*(?:×|x|\*)\s*10\^\{?(?P<power>[-−]?\d+)\}?)?"
    r"\s*(?P<unit>[A-Za-zµΩ°%][A-Za-zµΩ°%/·²³⁻¹]*(?:\s[A-Za-z][A-Za-z/²³]*)?)?\.?"
)
_NAME_WORD = re.compile(r"[A-Za-z]{3,}")


def without_emphasis(text: str) -> str:
    """``text`` without markdown emphasis: around words or maths (``**$x = 3$**``), and bold
    inside maths too, since "**" means nothing in TeX."""
    spans: list[str] = []

    def hold(span: re.Match[str]) -> str:
        spans.append(_STRONG.sub(lambda match: match.group(1) or match.group(2), span.group(0)))
        return f"\x00{len(spans) - 1}\x00"

    plain = _plain(_MATH.sub(hold, text))
    return re.sub("\x00(\\d+)\x00", lambda match: spans[int(match.group(1))], plain)


def _plain(prose: str) -> str:
    prose = _STRONG.sub(lambda match: match.group(1) or match.group(2), prose)
    return _EMPHASIS.sub(lambda match: match.group(1) or match.group(2), prose)


def named_value(value: str) -> str:
    """``Work input = 1.2J`` → ``Work input = $1.2\\,\\mathrm{J}$``: a value named in words,
    its words as text and its number in maths. Anything else is returned as it is."""
    if "$" in value or "\\" in value or "=" not in value:
        return value
    name, _, written = value.rpartition("=")
    match = _VALUE.fullmatch(written.strip())
    if match is None or _NAME_WORD.search(name) is None:
        return value
    number = match.group("number").replace("−", "-")
    if match.group("power"):
        number += rf" \times 10^{{{match.group('power').replace('−', '-')}}}"
    return f"{name.rstrip()} = ${number}{_unit(match.group('unit') or '')}$"


def _unit(unit: str) -> str:
    unit = unit.strip()
    if not unit:
        return ""
    if unit == "%":
        return r"\,\%"
    if unit.startswith("°") and len(unit) > 1:
        return rf"\,^\circ\mathrm{{{unit[1:]}}}"
    if unit == "°":
        return r"^\circ"
    return rf"\,\text{{{unit}}}" if " " in unit else rf"\,\mathrm{{{unit}}}"
