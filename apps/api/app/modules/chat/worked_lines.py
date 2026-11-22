"""A line of a ```worked block's working: its maths, and the words a model wrote around it.

A maths field is drawn as one formula, so words in it were set as italic maths, run
together and mixed with source: "$Group terms: (x^2 - 8x) + (y^2 + 6y) = 11$", "$s =
\\frac{P}{n} where n=6$", "$13 + c > 8 \\implies c > -5 (always$ true for positive
length)", "$L = 2h, where$ h = \\sqrt{R^2 - x^2}$$" (hard geometry round, 2026-11-21). The
words are read off the line by where they stand, never by what they say:

- a label before a colon ("Group terms:", "Check perimeter:") or a run of two words or more
  before the maths ("Tangent slope m_t = -1"), or one word that opens a sentence ("Let",
  "So", "Then");
- a clause after the maths that a joining word opens (", where …", " since …", " so …");
- words in brackets at the line's end ("(always true for positive length)").

The maths is drawn as maths and the words beside it as the line's note
(``services.workout.math_line``). A line holding ``$…$`` of its own is a sentence with its
maths marked, and is shown as one (``worked_prose.prose_maths``).
"""

from __future__ import annotations

import re

# "Group terms: …": words, then a colon and the maths.
_LABEL = re.compile(r"^(?P<words>[A-Za-z][A-Za-z' -]{1,40}?)\s*:\s+(?P<rest>\S.*)$")
# Two words or more before the maths: "Tangent slope m_t = -1".
_LEAD_WORDS = re.compile(r"^(?P<words>(?:[A-Za-z][a-z]{2,}\s+){2,})(?P<rest>\S.*)$")
# One word that opens a sentence before the maths.
_OPENER = re.compile(
    r"^(?P<words>(?:let|so|thus|hence|then|therefore|now|using|solving|substituting|"
    r"rearranging|simplifying|similarly|finally)),?\s+(?P<rest>\S.*)$",
    re.IGNORECASE,
)
# A clause the maths runs into: ", where n = 6", " since x > 0".
_CLAUSE = re.compile(
    r"(?:,\s*|\s+)(?=(?:where|since|because|which|so|so that|hence|thus|giving|i\.e\.|let)"
    r"\s)",
)
# Words in brackets at the end of the line: "(always true for positive length)".
_BRACKETED_WORDS = re.compile(r"\s*\((?P<words>[A-Za-z][^()\\$]*)\)\s*$")
_WORD = re.compile(r"[A-Za-z]{3,}")
# Signs a model typed for maths a renderer draws otherwise.
_TYPED_SIGNS = ((" -> ", r" \Rightarrow "), ("->", r"\Rightarrow "), ("==", "="))
# A space typed after a comma between two equations, "R = r, \ h = 2r": each equation is a
# row of its own, and the space opened the second ("$\ h = 2r$").
_SPACED_COMMA = re.compile(r",\s*(?:\\[ ,;:!]\s*|\\q?quad\s*)+")


def _depth_zero(text: str, at: int) -> bool:
    """``at`` is outside every brace group of ``text``."""
    depth = 0
    for char in text[:at]:
        if char == "{":
            depth += 1
        elif char == "}":
            depth = max(0, depth - 1)
    return depth == 0


def _words_before(tex: str) -> tuple[str, str]:
    for pattern in (_LABEL, _OPENER, _LEAD_WORDS):
        found = pattern.match(tex)
        if found is not None and "\\" not in found["words"] and _WORD.search(found["words"]):
            return found["words"].strip(" :,"), found["rest"].strip()
    return "", tex


def _words_after(tex: str) -> tuple[str, str]:
    for found in _CLAUSE.finditer(tex):
        if found.start() > 0 and _depth_zero(tex, found.start()):
            return tex[: found.start()].strip(), tex[found.end() :].strip()
    bracketed = _BRACKETED_WORDS.search(tex)
    if bracketed is not None and len(_WORD.findall(bracketed["words"])) >= 2:
        return tex[: bracketed.start()].strip(), bracketed["words"].strip()
    return tex, ""


# Maths the model marked inside the field, "$h = \\sqrt{R^2 - x^2}$": never a price's "$0.90",
# whose sign comes before a digit.
_MARKED = re.compile(r"(?<!\\)\$(?![\d\s.])[^$]+(?<!\\)\$")


def marks_maths(tex: str) -> bool:
    """The field holds ``$…$`` of its own: words with their maths marked, a sentence."""
    return _MARKED.search(tex) is not None


# Pi typed as its name, and a star typed for a product: "A = pi*(6)^2", "36*pi".
_TYPED_PI = re.compile(r"(?<![A-Za-z\\])pi(?![A-Za-z])")
_STAR_BEFORE_SYMBOL = re.compile(r"(?<=[\dA-Za-z)}])\s*\*\s*(?=\\pi\b|[A-Za-z(])")
_STAR = re.compile(r"(?<=[\w)}])\s*\*\s*(?=[\w(\\{])")


# A calculator's power of ten, "1e-3", "8.854e-12": as maths writes it, 8.854 \times 10^{-12}.
_CALCULATOR_POWER = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)[eE]\+?(-?)0*(\d+)(?![\w.])")


def typed_signs(tex: str) -> str:
    """``->`` as an arrow, ``==`` as ``=``, ``pi`` as π, ``*`` as a product and ``1e-3`` as a
    power of ten: what the model typed, as maths draws it."""
    for typed, drawn in _TYPED_SIGNS:
        tex = tex.replace(typed, drawn)
    tex = _TYPED_PI.sub(r"\\pi ", tex).replace("\\pi )", "\\pi)").replace("\\pi  ", "\\pi ")
    tex = _STAR.sub(r" \\times ", _STAR_BEFORE_SYMBOL.sub(" ", tex)) if "*" in tex else tex
    tex = _CALCULATOR_POWER.sub(r"\1 \\times 10^{\2\3}", tex)
    return _SPACED_COMMA.sub(", ", tex).strip()


def split_line(tex: str) -> tuple[str, str, str]:
    """``tex`` as (words before its maths, its maths, words after it); ("", tex, "") when it
    is all maths. A side left with no maths keeps the line whole."""
    before, rest = _words_before(tex.strip())
    maths, after = _words_after(rest)
    if not maths or not any(char.isdigit() or not char.isalpha() for char in maths):
        return "", tex.strip(), ""
    return before, maths, after
