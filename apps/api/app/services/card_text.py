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
  maths is drawn on the phone (``lib/math/answerLayout.ts``);
- ``card_maths``: a value that is all maths loses its ``$`` marks, as a verified card holds
  TeX alone, and a unit's power is written after the unit, as the server writes it
  (``\\mathrm{cm}^{2}``): a triangle's parts came as ``$A = 54\\,\\mathrm{cm²}$`` beside
  ``\\mathrm{cm^2}`` (2026-11-06).

A line in words is no card at all (``wordy``): a paragraph, or a sentence its maths only
illustrates (``sentence_answer``).
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
    its words as text and its number in maths. Anything else is returned as it is: several
    values joined ("Work = 5 J, Power = 2 W") stay one text, never half converted."""
    if "$" in value or "\\" in value or value.count("=") != 1:
        return value
    name, _, written = value.rpartition("=")
    match = _VALUE.fullmatch(written.strip())
    if match is None or _NAME_WORD.search(name) is None:
        return value
    number = match.group("number").replace("−", "-")
    if match.group("power"):
        number += rf" \times 10^{{{match.group('power').replace('−', '-')}}}"
    return f"{name.rstrip()} = ${number}{_unit(match.group('unit') or '')}$"


_WHOLE_MATH = re.compile(r"\$(?!\$)([^$\n]+)\$")
# "\mathrm{cm^2}", "\mathrm{cm^{3}}", "\mathrm{cm²}": a power written inside the unit.
_POWER_INSIDE = re.compile(r"\\mathrm\{([A-Za-zµΩ/]+)(?:\^\{?([23])\}?|([²³]))\}")
_SUPERSCRIPT = {"²": "2", "³": "3"}


def card_maths(value: str) -> str:
    """A card's value as the server writes one: no ``$`` around a value that is all maths,
    and a unit's power after the unit."""
    whole = _WHOLE_MATH.fullmatch(value.strip())
    value = whole.group(1).strip() if whole else value
    return _POWER_INSIDE.sub(
        lambda m: rf"\mathrm{{{m.group(1)}}}^{{{m.group(2) or _SUPERSCRIPT[m.group(3)]}}}", value
    )


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


_WORD = re.compile(r"[A-Za-z]{3,}")
# A line that states a relation, inside its maths or around it, states a value.
_RELATION = re.compile(
    r"[=\u2248<>\u2264\u2265\u2260]|\\(?:approx|leq?|geq?|neq?|lt|gt|equiv|sim|propto)(?![A-Za-z])"
)
# A word of a sentence, in any script (three letters or more).
_LETTERS = re.compile(r"[^\W\d_]{3,}")


def _relations(text: str) -> str:
    """``≈`` and ``\\approx`` read as ``=``: an approximate value is still a value."""
    return text.replace("\\approx", "=").replace("\u2248", "=")


def wordy(value: str) -> bool:
    """Words, not a value a card holds: a paragraph (over twenty words outside its maths and
    no equation), or a sentence its maths only illustrates (``sentence_answer``)."""
    if len(value) > 2000:
        return True
    prose = _relations(_MATH.sub(" ", value))  # 2000 characters at most: read once
    if "=" not in prose and len(_WORD.findall(prose)) > 20:
        return True
    return sentence_answer(value)


def sentence_answer(value: str) -> bool:
    """A sentence its maths only illustrates, which no card holds: "A line from $(-3, -5)$ to
    $(3, 7)$ — slope $2$, $y$-intercept $1$." filled one (2026-11-13). Read by its shape: no
    relation anywhere (``=``, ``≈``, ``<``, inside the maths or around it), four words or more
    (of three letters) outside the maths, two of them after the first maths. A line that
    states a value keeps its card: an equation ("The area is $A = 24$ cm²", "Sum of the angles
    $= 180°$"), a value with its unit after a lead ("The speed is about $4.2$ m/s"), a short
    answer in words ("Sodium chloride"). Twin: the phone's ``isAnswerValue``."""
    if _RELATION.search(value):
        return False
    first = _MATH.search(value)
    after = value if first is None else value[first.end() :]
    words = len(_LETTERS.findall(_MATH.sub(" ", value)))
    return words >= 4 and len(_LETTERS.findall(_MATH.sub(" ", after))) >= 2
