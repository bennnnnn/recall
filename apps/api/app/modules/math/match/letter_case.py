"""A capital ``X`` or ``Y`` typed as the unknown reads as ``x`` or ``y``.

The phone's keyboard capitalises a letter after a shift, so "How many solutions does
$4X^2 + 4 = 6$ have?" arrives with ``X``. The readers that name the axes (the vertex of
``y = …``, the value of ``f(x)``, the remainder on division by ``x - 2``, how many
solutions an equation has) read ``x`` and ``y`` only, and each passed on the capital,
so the turn went to the model unverified (2026-11-10). Folding the letter once, before
any reader runs, gives every reader the line it was written for.

Only a lone ``X`` or ``Y`` is folded, and only where the line writes it as algebra
(``4X``, ``X^2``, ``f(X)``, ``$X``). A line that also uses the lower-case letter as
algebra, alone or in a product (``xy = 6``, ``ax``, ``dx``), or another lone capital as
maths (``P(X = 2)``, ``E(X)``: a random variable), keeps its letters, and so do names and
prose ("Malcolm X", "X-rays", "Ctrl+Shift+X").
"""

from __future__ import annotations

import re

# Not inside a word or a name with digits (``SpaceX``, ``9800X3D``).
_LONE = r"(?<![A-Za-z]){letter}(?![A-Za-z0-9])"
# The unknown may also stand after a letter coefficient: ``kX``, ``2aX``.
_LONE_UNKNOWN = r"(?:(?<![A-Za-z])|(?<=(?<![A-Za-z])[a-z]))[XY](?![A-Za-z0-9])"
# Written as algebra: after a coefficient, a closing bracket, a ``$``, an operator that
# binds it or a bracket against what it follows (``f(X)``, ``$(X+1)``, not "Twitter
# (X)"), or before a power or an argument.
_AFTER = r"(?:(?<=[\d)}$*/^{])|(?<=\S\()|(?<=^\())"
_BEFORE = r"(?=[\^(²³])"
_LONE_FOLDED = re.compile(_LONE_UNKNOWN)
_ALGEBRA_FOLDED = re.compile(
    rf"{_AFTER}{_LONE.format(letter='[XY]')}|{_LONE.format(letter='[XY]')}{_BEFORE}"
)
# A run of letters, and what follows it ("x-intercepts" is a word, not the letter x).
_LETTER_RUN = re.compile(r"[A-Za-z]+(?P<hyphen>-[A-Za-z])?")
# Short words with an x or a y in them, not a product of letters.
_SHORT_WORDS = frozenset({"by", "my", "ex", "ox", "oy", "ye", "yo", "ya", "ay", "xo"})
_OTHER_CAPITAL = re.compile(
    rf"{_AFTER}{_LONE.format(letter='[A-WZ]')}|{_LONE.format(letter='[A-WZ]')}{_BEFORE}"
)


def fold_capital_unknowns(text: str) -> str:
    """``How many solutions does $4X^2 + 4 = 6$ have?`` → ``… $4x^2 + 4 = 6$ …``."""
    if not _ALGEBRA_FOLDED.search(text):
        return text
    used = {match.group(0).lower() for match in _LONE_FOLDED.finditer(text)}
    if used & _lower_case_algebra(text):
        # ``x`` and ``X`` in one line may be two letters: "If xy = 12 and X = 3Y".
        return text
    if _OTHER_CAPITAL.search(text):
        return text
    return _LONE_FOLDED.sub(lambda match: match.group(0).lower(), text)


def _lower_case_algebra(text: str) -> set[str]:
    """The lower-case x and y the line writes as algebra: alone (``x``), in a product of
    letters (``xy``, ``2ax``, ``dx``, ``xyz``), never inside a word ("box", "yes", "why")."""
    letters: set[str] = set()
    for match in _LETTER_RUN.finditer(text):
        run = match.group(0).removesuffix(match.group("hyphen") or "")
        if match.group("hyphen") or run.lower() in _SHORT_WORDS:
            continue
        if len(run) <= 2 or set(run) <= set("xyz"):
            letters |= set(run) & {"x", "y"}
    return letters
