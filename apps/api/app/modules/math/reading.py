"""What the scanner read, in the notation a student writes.

The read-back is the student's check that the camera saw the problem. It is
the full transcription (Mathpix text, or the vision model's ``source_text``),
not an equation rebuilt from a parse: a rebuilt equation silently drops what
the parse did not keep, such as a printed ``x ∈ ℤ``. Tapping Solve sends this
text through the ordinary chat pipeline, which reads every symbol below.
"""

from __future__ import annotations

import re

_DELIMITERS = re.compile(r"\\[()\[\]]|\$+")
_LABEL = re.compile(r"^\s*(?:(?:Q|question\s*)?\d+\s*[.):]\s*)?(?:\(?[a-hivx]{1,3}\)\s*)?", re.I)
_BRACED = r"\{([^{}]*)\}"
_FRAC = re.compile(r"\\[dt]?frac\s*" + _BRACED + r"\s*" + _BRACED)
_SQRT_INDEX = re.compile(r"\\sqrt\s*\[\s*([^\]]+?)\s*\]\s*" + _BRACED)
_SQRT = re.compile(r"\\sqrt\s*" + _BRACED)
_TEXT = re.compile(r"\\(?:text|mathrm|mathbf|mathit|operatorname)\s*" + _BRACED)
_BLACKBOARD = {"R": "ℝ", "Z": "ℤ", "N": "ℕ", "Q": "ℚ", "C": "ℂ"}
_MATHBB = re.compile(r"\\mathbb\s*\{([RZNQC])\}")
_SCRIPT = re.compile(r"([\^_])\s*" + _BRACED)
_SYMBOLS = (
    ("\\leq", "≤"),
    ("\\geq", "≥"),
    ("\\neq", "≠"),
    ("\\le", "≤"),
    ("\\ge", "≥"),
    ("\\ne", "≠"),
    ("\\cdot", "·"),
    ("\\times", "×"),
    ("\\div", "÷"),
    ("\\pm", "±"),
    ("\\mp", "∓"),
    ("\\infty", "∞"),
    ("\\notin", "∉"),
    ("\\in", "∈"),
    ("\\pi", "π"),
    ("\\theta", "θ"),
    ("\\alpha", "α"),
    ("\\beta", "β"),
    ("\\lambda", "λ"),
    ("\\degree", "°"),
    ("^\\circ", "°"),
    ("^{\\circ}", "°"),
)
_SPACES = re.compile(r"\\(?:quad|qquad|[,;:! ])")
_SIZING = re.compile(r"\\(?:left|right)\s*[.]|\\(?:left|right|big|Big|bigg|Bigg)(?![A-Za-z])\s*")
_NAMED = re.compile(r"\\(arcsin|arccos|arctan|sin|cos|tan|sec|csc|cot|log|ln|exp|lim)(?![A-Za-z])")
_INTEGRAL = re.compile(r"\\int(?![A-Za-z])")
_ARRAY = re.compile(
    r"\\(?:begin|end)\s*\{(?:array|cases|aligned|align\*?|gathered)\}(?:\{[^{}]*\})?"
)
_IMPLICIT_TIMES = re.compile(r"(\d)\s*\*\s*(?=[A-Za-z(])")
_ABS_CALL = re.compile(r"\bAbs\(([^()]*)\)")
_SQRT_CALL = re.compile(r"\bsqrt\(")
_SIMPLE = re.compile(r"[A-Za-z0-9.]+")


def _fraction(match: re.Match[str]) -> str:
    """``\\frac{1}{2}x`` is ``(1/2)x``; a fraction standing alone needs no brackets."""
    top, bottom = match.group(1).strip(), match.group(2).strip()
    top = top if _SIMPLE.fullmatch(top) else f"({top})"
    bottom = bottom if _SIMPLE.fullmatch(bottom) else f"({bottom})"
    before = match.string[: match.start()].rstrip()[-1:]
    after = match.string[match.end() :].lstrip()[:1]
    glued = (before and (before.isalnum() or before in ")^_")) or (
        after and (after.isalnum() or after in "(\\")
    )
    return f"({top}/{bottom})" if glued else f"{top}/{bottom}"


def _root(match: re.Match[str]) -> str:
    index, body = match.group(1), match.group(2).strip()
    glyph = {"3": "∛", "4": "∜"}.get(index)
    return f"{glyph}({body})" if glyph else f"({body})^(1/{index})"


def _script(match: re.Match[str]) -> str:
    mark, body = match.group(1), match.group(2).strip()
    return f"{mark}{body}" if _SIMPLE.fullmatch(body) else f"{mark}({body})"


def student_reading(source: str) -> str:
    """``\\frac{1}{2}x+3=7`` → ``(1/2)x+3=7``; ``Abs(2x-1)`` → ``|2x-1|``."""
    text = _DELIMITERS.sub(" ", source)
    text = _ARRAY.sub("", text)
    text = text.replace("\\\\", "\n").replace("&", "")
    text = _SIZING.sub("", text)
    text = _TEXT.sub(r"\1", text)
    text = _MATHBB.sub(lambda m: _BLACKBOARD[m.group(1)], text)
    for _ in range(4):
        before = text
        text = _FRAC.sub(_fraction, text)
        text = _SQRT_INDEX.sub(_root, text)
        text = _SQRT.sub(lambda m: f"√({m.group(1).strip()})", text)
        if text == before:
            break
    for latex, glyph in _SYMBOLS:
        text = re.sub(re.escape(latex) + r"(?![A-Za-z])", glyph, text)
    text = _SPACES.sub(" ", text)
    text = _NAMED.sub(r"\1", text)
    text = _INTEGRAL.sub("∫", text)
    text = _SCRIPT.sub(_script, text)
    text = text.replace("\\{", "").replace("\\}", "").replace("{", "").replace("}", "")
    text = text.replace("**", "^")
    text = _IMPLICIT_TIMES.sub(r"\1", text)
    text = _ABS_CALL.sub(r"|\1|", text)
    text = _SQRT_CALL.sub("√(", text)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    if lines:
        lines[0] = _LABEL.sub("", lines[0], count=1).strip()
    return "\n".join(line for line in lines if line)
