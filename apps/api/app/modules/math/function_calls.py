"""The functions a maths message applies, and whether a reading kept every one.

A reader that does not know a function name peels it off as an English word and solves what
is left: "solve floor(x) = 3" was read as (x) = 3 and certified x = 3, and "solve
sign(sin(x)) = 1 for 0 <= x <= 2pi" as sin(x) = 1, certified x = π/2. Both answers are
wrong (3 ≤ x < 4, and 0 < x < π). Whatever drops the name, the question solved is no
longer the one asked, so a reading that lost a written function is no reading at all.

``written_functions`` names each function the message applies, as a call (``floor(x)``,
``foo(x)``) or in words (``the floor of x``, ``x mod 3``). ``unread_functions`` says which
of them a reading's own text does not hold. A one- or two-letter name before a bracket is
function notation or a product (``f(x)``, ``ab(x+1)``) and is read elsewhere; a request
verb (``solve(``, ``factor(``) names the operation, not a function.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Iterator
from typing import TYPE_CHECKING, Any

from app.modules.math.function_names import (
    HYPERBOLIC,
    MATH_FUNCTION_NAMES,
    TRIG,
    names_longest_first,
)

if TYPE_CHECKING:
    from app.modules.math.schemas import MathIntent

# Each name a message may write, and the one name it is counted under.
_CANONICAL: dict[str, str] = {
    **{name: name for name in (*TRIG, *HYPERBOLIC)},
    **{f"a{name}": f"a{name}" for name in (*TRIG, *HYPERBOLIC)},
    **{f"arc{name}": f"a{name}" for name in (*TRIG, *HYPERBOLIC)},
    "log": "log", "ln": "log", "lg": "log",
    "exp": "exp", "sqrt": "sqrt", "cbrt": "cbrt", "root": "root",
    "abs": "abs",
    "floor": "floor", "ceil": "ceiling", "ceiling": "ceiling",
    "sign": "sign", "sgn": "sign", "signum": "sign",
    "frac": "frac", "round": "round", "trunc": "trunc",
    "mod": "mod", "modulo": "mod",
    "max": "max", "min": "min",
    "gcd": "gcd", "hcf": "gcd", "gcf": "gcd", "lcm": "lcm",
    "heaviside": "heaviside", "piecewise": "piecewise",
    "factorial": "factorial", "gamma": "gamma",
    "ncr": "choose", "choose": "choose", "binomial": "choose", "binom": "choose",
    "comb": "choose", "npr": "permute", "perm": "permute",
    "det": "det", "re": "re", "im": "im", "arg": "arg", "conjugate": "conjugate",
    "sum": "sum", "mean": "mean", "median": "median", "mode": "mode",
    "var": "variance", "variance": "variance", "std": "stdev", "stdev": "stdev",
}  # fmt: skip
# How a reading may spell each one: SymPy's name, a symbol, or the operation it names.
_SPELLINGS: dict[str, tuple[str, ...]] = {
    **{f"a{name}": (f"a{name}", f"arc{name}") for name in (*TRIG, *HYPERBOLIC)},
    # A reciprocal is read through its partner: where sec(x) is undefined, cos(x) = 0.
    "sec": (r"sec", r"cos"),
    "csc": (r"csc", r"sin"),
    "cot": (r"cot", r"tan", r"cos"),
    "log": (r"log", r"ln", r"lg"),
    "exp": (r"exp", r"(?<![A-Za-z])[eE]\s*(?:\^|\*\*)"),
    "sqrt": (r"sqrt", r"root", r"√"),
    "cbrt": (r"cbrt", r"root", r"∛", r"1\s*/\s*3"),
    "root": (r"root", r"sqrt", r"cbrt"),
    "abs": (r"abs", r"\|"),
    "ceiling": (r"ceil(?:ing)?", r"⌈"),
    "floor": (r"floor", r"⌊"),
    "sign": (r"sign", r"sgn"),
    "mod": (r"mod", r"%"),
    "gcd": (r"gcd", r"hcf", r"gcf"),
    "choose": (r"ncr", r"choose", r"binom(?:ial)?", r"comb(?:ination)?s?"),
    "permute": (r"npr", r"perm(?:utation)?s?"),
    "factorial": (r"factorial", r"!"),
    "det": (r"det(?:erminant)?",),
    "mean": (r"mean", r"average"),
    "variance": (r"var(?:iance)?",),
    "stdev": (r"std", r"stdev", r"standard_deviation"),
}
# Names a reading must hold verbatim: TRIG, the inverse names, and anything unlisted.
_KNOWN = names_longest_first(tuple(_CANONICAL))
# The verb or object of the request, written against a bracket: ``Solve(2x+1=5)``.
_REQUEST_WORDS = frozenset(
    {
        "solve", "simplify", "evaluate", "calculate", "compute", "find", "determine",
        "factor", "factorise", "factorize", "expand", "differentiate", "derive",
        "derivative", "integrate", "integral", "limit", "lim", "graph", "plot", "sketch",
        "draw", "show", "check", "verify", "convert", "what", "whats", "is", "of", "and",
        "or", "the", "for", "if", "then", "where", "when", "with", "let", "given", "answer",
        "equation", "expression", "inequality", "system", "value", "values", "point",
        "points", "interval", "domain", "range", "area", "at", "to", "in", "on",
    }
)  # fmt: skip
# A name's own letters before a bracket. Whitespace is allowed only after a name the readers
# already know (``sin (x)``), so "the sign (positive or negative)" stays prose.
_CALL = re.compile(r"(?<![A-Za-z_\\])([A-Za-z]{2,})(\s*)\(")
_ROUND_WORDS = r"floor|ceiling|signum|integer\s+part|fractional\s+part|greatest\s+integer"
# What a function said in words is applied to: a variable, a bracket or a bare number. "The
# floor of a room" and "the floor of 5 m by 4 m" are no operand.
_OPERAND = r"(?=(?![aAI]\b)[a-z]\b|\(|-?\d+(?:\.\d+)?\s*(?:$|[-=+*/<>)?.,]))"
# The function said in words, applied to an operand: "the floor of x", "x mod 3".
_SAID = re.compile(
    rf"\b(?P<said>{_ROUND_WORDS})\s+(?:function\s+of|function|of)\s+{_OPERAND}"
    r"|(?:\w|\))\s*\b(?P<mod>mod|modulo)\b\s*(?=\w|\()",
    re.IGNORECASE,
)
_SAID_CANONICAL = {
    "floor": "floor",
    "ceiling": "ceiling",
    "signum": "sign",
    "integer part": "floor",
    "greatest integer": "floor",
    "fractional part": "frac",
}


def _call_name(run: str, spaced: bool) -> str | None:
    """The function a letter run before ``(`` names, or None for notation or a verb."""
    lowered = run.lower()
    if lowered in _CANONICAL:
        return _CANONICAL[lowered]
    if spaced:
        return None
    # ``2xsin(x)`` reaches here as ``xsin``: the name is the run's known tail.
    for name in _KNOWN:
        if len(name) >= 3 and lowered.endswith(name):
            return _CANONICAL[name]
    if len(lowered) < 3 or lowered in _REQUEST_WORDS:
        return None
    return lowered


# LaTeX and the brackets of a step function, as the call each one writes.
_LATEX_NAME = re.compile(r"\\operatorname\s*\{\s*([A-Za-z]+)\s*\}|\\([A-Za-z]+)(?=\s*\()")
_FLOOR_MARK = re.compile(r"⌊|\\lfloor\b")
_CEILING_MARK = re.compile(r"⌈|\\lceil\b")


def _latex_call(match: re.Match[str]) -> str:
    """A named operator, or a known function's command; ``\\left(`` stays LaTeX."""
    if match.group(1):
        return match.group(1)
    return match.group(2) if match.group(2).lower() in _CANONICAL else match.group(0)


def _plain_calls(text: str) -> str:
    """``\\operatorname{sgn}(x)`` as ``sgn(x)``, ``\\lfloor x \\rfloor`` as ``floor( x``."""
    text = _LATEX_NAME.sub(_latex_call, text)
    text = _FLOOR_MARK.sub(" floor(", text)
    return _CEILING_MARK.sub(" ceiling(", text)


def written_functions(text: str) -> Counter[str]:
    """Each function the message applies, by its one name, with how often it is applied."""
    found: Counter[str] = Counter()
    text = _plain_calls(text)
    for match in _CALL.finditer(text):
        spaced = bool(match.group(2))
        if spaced and match.group(1).lower() not in MATH_FUNCTION_NAMES:
            continue
        name = _call_name(match.group(1), spaced)
        if name is not None:
            found[name] += 1
    for match in _SAID.finditer(text):
        if match.group("mod"):
            found["mod"] += 1
        else:
            said = re.sub(r"\s+", " ", match.group("said").lower())
            found[_SAID_CANONICAL[said]] += 1
    return found


def _spelling(name: str) -> re.Pattern[str]:
    spellings = _SPELLINGS.get(name, (re.escape(name),))
    return re.compile(
        rf"(?<![Aa])(?:{'|'.join(spellings)})(?![a-z])"
        if name not in {"abs", "factorial", "exp"}
        else "|".join(spellings),
        re.IGNORECASE,
    )


def unread_functions(text: str, reading_parts: Iterable[str]) -> tuple[str, ...]:
    """The written functions a reading's text holds fewer times than the message applies them."""
    written = written_functions(text)
    if not written:
        return ()
    reading = " ".join(reading_parts)
    return tuple(
        sorted(
            name for name, count in written.items() if len(_spelling(name).findall(reading)) < count
        )
    )


def functions_dropped(text: str, intent: MathIntent) -> bool:
    """Whether the reading lost a function the text applies.

    "solve floor(x) = 3" was read as (x) = 3 and certified x = 3: a function the reader
    peeled off as a word leaves a different question."""
    return bool(unread_functions(text, _reading_text(intent.model_dump())))


def _reading_text(value: Any) -> Iterator[str]:
    """Every piece of text a reading holds: its sides, expressions and operation names."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _reading_text(item)
    elif isinstance(value, list | tuple):
        for item in value:
            yield from _reading_text(item)
