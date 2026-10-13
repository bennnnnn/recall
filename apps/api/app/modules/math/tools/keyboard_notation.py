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
_RADIAN_RE = re.compile(r"\s*\\mathrm\{rad\}")
_DERIVATIVE_FRAC_RE = re.compile(r"\\frac\{(?:d|\\partial)")


def _group_end(tex: str, start: int) -> int | None:
    """Index after the ``{…}`` group opening at ``start``."""
    if start >= len(tex) or tex[start] != "{":
        return None
    depth = 0
    for index in range(start, len(tex)):
        if tex[index] == "{":
            depth += 1
        elif tex[index] == "}":
            depth -= 1
            if depth == 0:
                return index + 1
    return None


def _times_beside_fractions(tex: str) -> str:
    """``44\\frac{2}{2}4`` is 44 * 2/2 * 4: a number beside a fraction multiplies.

    Unread, it went to the model, which guessed ``44 + 2 / 2 + 4`` and answered 50.
    """
    out: list[str] = []
    index = 0
    while index < len(tex):
        if not tex.startswith("\\frac", index):
            out.append(tex[index])
            index += 1
            continue
        numerator_end = _group_end(tex, index + len("\\frac"))
        end = _group_end(tex, numerator_end) if numerator_end is not None else None
        if end is None:
            out.append(tex[index])
            index += 1
            continue
        before = "".join(out).rstrip()
        if before and (before[-1].isdigit() or before[-1] == ")"):
            out.append("\\cdot ")
        out.append(tex[index:end])
        after = tex[end:].lstrip()
        if (
            after
            and (after[0].isdigit() or after[0] == "(")
            and not _DERIVATIVE_FRAC_RE.match(tex, index)
        ):
            out.append("\\cdot ")
        index = end
    return "".join(out)


def _template_to_words(tex: str) -> str:
    tex = _times_beside_fractions(tex.strip())
    tex = _DEGREE_RE.sub("°", tex)
    tex = _RADIAN_RE.sub(" rad", tex)
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

    if "$" not in text or ("\\" not in text and "{" not in text):
        return text

    def plain(match: re.Match[str]) -> str:
        words = _template_to_words(match.group(1))
        return _normalize_latex_to_sympy(words).strip()

    return _SPAN_RE.sub(plain, text)
