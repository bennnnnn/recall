"""The phone's math keyboard types LaTeX the extractors were not written for.

``$\\int_{0}^{1}x^{2}\\,dx$``, ``$\\frac{d}{dx}x^{3}$``, ``$\\binom{5}{2}$`` and
``$\\sin(30^{\\circ})$`` went to the model unverified, while "integrate x^2 from
0 to 1", "d/dx x^3", "C(5,2)" and "sin(30°)" were solved. Each ``$…$`` span is
rewritten into that plain notation, and the extractors get one more try.
"""

from __future__ import annotations

import re

_SPAN_RE = re.compile(r"\$([^$]+)\$")

_INT_BOUNDS_RE = re.compile(
    r"\\int_\{([^{}]*)\}\^\{([^{}]*)\}\s*(.+?)\s*(?:\\,)?\s*d\{?([a-z])\}?\s*$"
)
_INT_RE = re.compile(r"\\int\s*(.+?)\s*(?:\\,)?\s*d\{?([a-z])\}?\s*$")
_SECOND_DERIVATIVE_RE = re.compile(r"^\\frac\{d\^\{?2\}?\}\{d\{?([a-z])\}?\^\{?2\}?\}\s*(.+)$")
_DERIVATIVE_RE = re.compile(r"^\\frac\{d\}\{d\{?([a-z])\}?\}\s*(.+)$")
_BINOM_RE = re.compile(r"\\binom\{([^{}]+)\}\{([^{}]+)\}")
_DEGREE_RE = re.compile(r"\^\{\\circ\}")


def _template_to_words(tex: str) -> str:
    tex = tex.strip()
    tex = _DEGREE_RE.sub("°", tex)
    tex = _BINOM_RE.sub(r"C(\1,\2)", tex)
    match = _INT_BOUNDS_RE.search(tex)
    if match:
        lower, upper, body, _var = match.groups()
        return f"{tex[: match.start()]}integrate {body} from {lower} to {upper}"
    match = _INT_RE.search(tex)
    if match:
        body, var = match.groups()
        return f"{tex[: match.start()]}integrate {body} d{var}"
    match = _SECOND_DERIVATIVE_RE.match(tex)
    if match:
        return f"second derivative of {match.group(2)}"
    match = _DERIVATIVE_RE.match(tex)
    if match:
        var, body = match.groups()
        return f"d/d{var} {body}"
    return tex


def keyboard_math_to_plain(text: str) -> str:
    """Each ``$…$`` span in the plain notation the extractors read."""
    from app.modules.math.solve.parse import _normalize_latex_to_sympy

    if "$" not in text or "\\" not in text:
        return text

    def plain(match: re.Match[str]) -> str:
        words = _template_to_words(match.group(1))
        return _normalize_latex_to_sympy(words).strip()

    return _SPAN_RE.sub(plain, text)
