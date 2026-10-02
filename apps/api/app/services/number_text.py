# ruff: noqa: RUF001, RUF002, RUF003 -- the point of this module is the Unicode times and minus signs.
"""Read a number written in scientific notation as one literal.

People write one number many ways: ``2 × 10^-6``, ``2x10^-6``, ``2*10**-6``,
``2·10⁻⁶``, ``2 \\times 10^{-6}``, ``−3``. A scanner that only knows ``2e-6``
reads the first of those as two numbers, the 2 and the -6, and binds whichever
one sits next to a unit: "a charge of 2 × 10^-6 C" became a charge of -6 C.
Folding the notation into ``2e-6`` first means a coefficient and its exponent
are never mistaken for two quantities.

Subject-neutral and lexical: nothing is calculated, and text that is not a
power of ten is left exactly as written.
"""

from __future__ import annotations

import re

_MINUS_SIGNS = "−–"  # − (minus sign) and – (en dash, OCR and phones)
_SUPERSCRIPTS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺", "0123456789-+")

# Thin spaces and the LaTeX spacing commands people paste from a typeset page.
_GAP = r"(?:\s|\\[,;:! ])*"
_TIMES = r"(?:[x×X*·⋅]|\\times|\\cdot)"
_SIGNED = rf"[-+{_MINUS_SIGNS}]?\s*\d{{1,3}}"
_EXPONENT = (
    rf"(?:\^|\*\*){_GAP}"
    rf"(?:\{{\s*(?P<braced>{_SIGNED})\s*\}}|\(\s*(?P<paren>{_SIGNED})\s*\)|(?P<plain>{_SIGNED}))"
    r"|(?P<sup>[⁻⁺]?[⁰¹²³⁴⁵⁶⁷⁸⁹]{1,3})"
)
_MANTISSA = rf"[-+{_MINUS_SIGNS}]?(?:\d{{1,3}}(?:,\d{{3}})+|\d+)(?:\.\d+)?"

# A literal starts after a non-number: "x10^5" is a variable times 10^5, and
# the "000" of "6,000" is not a mantissa of its own.
_SCIENTIFIC = re.compile(
    rf"(?<![\w.,^])(?:(?P<mantissa>{_MANTISSA}){_GAP}{_TIMES}{_GAP})?"
    rf"10{_GAP}(?:{_EXPONENT})(?![\d.])"
)


def _sign(text: str) -> str:
    text = re.sub(r"\s+", "", text)
    for minus in _MINUS_SIGNS:
        text = text.replace(minus, "-")
    return text


def _literal(match: re.Match[str]) -> str:
    raw_exponent = (
        match.group("braced")
        or match.group("paren")
        or match.group("plain")
        or match.group("sup").translate(_SUPERSCRIPTS)
    )
    exponent = int(_sign(raw_exponent))
    mantissa = _sign(match.group("mantissa") or "1").replace(",", "")
    return f"{mantissa}e{exponent}"


def read_scientific_numbers(text: str) -> str:
    """Rewrite every ``a × 10^n`` (or a bare ``10^n``) as ``aEn``.

    ``2 × 10^-6`` → ``2e-6``; ``10^8`` → ``1e8``; ``1.6 \\times 10^{-19}`` →
    ``1.6e-19``. Exponents have at most three digits; anything else stays.
    """
    if "10" not in text:
        return text
    return _SCIENTIFIC.sub(_literal, text)
