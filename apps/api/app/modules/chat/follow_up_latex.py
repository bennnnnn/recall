# ruff: noqa: RUF001, RUF002 -- the characters a LaTeX command names (times, theta, ell).
"""A follow-up question reads as plain text: a command that names a character is that character.

The model writes its follow-ups from a reply typeset in LaTeX and copies the source: "What
if $\\theta$ was $45^\\text{\\textdegree}$ instead?" (2026-11-08) showed it on the chip. A
command that names one character becomes it (θ, °, ×, ≤), a text group its words and a
spacing command a space, so a maths span made only of those is text. A span that still needs
typesetting (``$\\frac{1}{2}$``, ``$1.6\\text{ m/s}^2$``) stays as written for the phone to
draw, and so does one with no command at all (``$v_f$``, ``$x^2$``). Only maths is read:
prose and code that talk about LaTeX keep their backslashes.
"""

from __future__ import annotations

import re

_GREEK = dict(
    zip(
        (
            "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi "
            "rho sigma tau upsilon phi chi psi omega Gamma Delta Theta Lambda Xi Pi Sigma "
            "Upsilon Phi Psi Omega varepsilon vartheta varphi varrho varsigma varpi"
        ).split(),
        "αβγδεζηθικλμνξοπρστυφχψωΓΔΘΛΞΠΣΥΦΨΩεϑφϱςϖ",
        strict=True,
    )
)
# Commands that name one character, as a reader writes it.
_SYMBOLS = {
    **_GREEK,
    "times": "×",
    "cdot": "·",
    "div": "÷",
    "pm": "±",
    "mp": "∓",
    "le": "≤",
    "leq": "≤",
    "ge": "≥",
    "geq": "≥",
    "ne": "≠",
    "neq": "≠",
    "approx": "≈",
    "infty": "∞",
    "to": "→",
    "rightarrow": "→",
    "degree": "°",
    "textdegree": "°",
    "circ": "°",
    "ell": "ℓ",
    "hbar": "ℏ",
}
# A degree written as a power (``45^\\circ``, ``45^{\\textdegree}``) is the degree sign.
_DEGREE = re.compile(r"\^\s*(?:\{\s*)?(?:\\(?:circ|textdegree|degree)(?![A-Za-z])|°)(?:\s*\})?")
_TEXT_GROUP = re.compile(r"\\(?:text|textrm|mathrm|operatorname|mbox)\s*\{([^{}]*)\}")
_SPACING = re.compile(r"\\(?:quad|qquad|[,;: ])")
_COMMAND = re.compile(r"\\([A-Za-z]+)(?![A-Za-z])")
_MATH_SPAN = re.compile(r"\$([^$\n]+)\$")
# An inline code span, kept whole (its backticks included) when the question is split on it.
_CODE_SPAN = re.compile(r"(`+[^`\n]*`+)")
# What only maths can draw: a script, a group, or a command with no character of its own.
_TYPESET = re.compile(r"[\\^_{}]")


def _fold(tex: str) -> str:
    text = tex
    for _ in range(3):  # a text group in a text group
        text = _TEXT_GROUP.sub(r"\1", text)
    text = _DEGREE.sub("°", text)
    text = _SPACING.sub(" ", text).replace("\\%", "%")
    return _COMMAND.sub(lambda m: _SYMBOLS.get(m.group(1), m.group(0)), text)


def plain_follow_up(question: str) -> str:
    """``question`` with each maths span that needs no typesetting once its commands are
    the characters they name written as text. Only maths is read: prose and code about LaTeX
    ("How do I write \\alpha in LaTeX?", ```\\text{}```) keep every backslash."""
    if "\\" not in question:
        return question

    def span(match: re.Match[str]) -> str:
        # A span the phone must still typeset stays as written: it draws every command.
        if "\\" not in match.group(1):
            return match.group(0)
        folded = _fold(match.group(1)).strip()
        return match.group(0) if _TYPESET.search(folded) else folded

    pieces = _CODE_SPAN.split(question)
    # The split keeps each code span at an odd index; only the prose around them holds maths.
    plain = (piece if at % 2 else _MATH_SPAN.sub(span, piece) for at, piece in enumerate(pieces))
    return re.sub(r"[ \t]{2,}", " ", "".join(plain))
