"""The functions a maths message applies, and whether a reading kept every one.

A reader that does not know a function name peels it off as an English word and solves what
is left: "solve floor(x) = 3" was read as (x) = 3 and certified x = 3, and "solve
sign(sin(x)) = 1 for 0 <= x <= 2pi" as sin(x) = 1, certified x = π/2. Both answers are
wrong (3 ≤ x < 4, and 0 < x < π). Whatever drops the name, the question solved is no
longer the one asked, so a reading that lost a written function is no reading at all.

``written_functions`` names each function the message applies: a call (``floor(x)``,
``foo(x)``, ``ln|x|``, ``Γ(x)``), absolute-value bars, a remainder (``x mod 3``,
``x % 3``), a congruence in an unknown (``2x ≡ 3 mod 5``) or a function said in words
(``the floor of x``). ``unread_functions`` says which of them a reading's own text does
not hold. The names and their spellings are ``function_table.py``. A one- or two-letter
Latin name before a bracket is function notation or a product (``f(x)``, ``ab(x+1)``) and
is read elsewhere, as is ``π(r + 1)``; a request verb (``solve(``) names the operation.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Iterator
from functools import cache
from typing import TYPE_CHECKING, Any

from app.modules.math.function_names import MATH_FUNCTION_NAMES, names_longest_first
from app.modules.math.function_table import BY_NAME, REQUEST_WORDS, WRITTEN

if TYPE_CHECKING:
    from app.modules.math.schemas import MathIntent

_KNOWN = names_longest_first(tuple(WRITTEN))
# A name's own letters before a bracket or an absolute-value bar. Whitespace is allowed only
# after a name the readers already know (``sin (x)``): "the sign (positive or negative)" is prose.
_CALL = re.compile(r"(?<![^\W\d]|\\)([^\W\d_]+)(\s*)([(|])")
# π before a bracket multiplies (``π(r + 1)``).
_MULTIPLYING_LETTERS = frozenset("πΠ")
# What a function said in words is applied to: a variable, a bracket or a bare number. "The
# floor of a room" and "the floor of 5 m by 4 m" are no operand.
_OPERAND = r"(?=(?![aAI]\b)[a-z]\b|\(|-?\d+(?:\.\d+)?\s*(?:$|[-=+*/<>)?.,]))"
_ROUND_WORDS = r"floor|ceiling|signum|integer\s+part|fractional\s+part|greatest\s+integer"
# The function said in words, applied to an operand: "the floor of x", "x mod 3", "x % 3".
# A percentage is followed by a word or nothing ("15% of 80"), a remainder by an operand.
_SAID = re.compile(
    rf"\b(?P<said>{_ROUND_WORDS})\s+(?:function\s+of|function|of)\s+{_OPERAND}"
    r"|(?:\w|\))\s*\b(?P<mod>mod|modulo)\b\s*(?=\w|\()"
    r"|(?<=[\w)])\s*(?P<percent>%)\s*(?=\d|\(|[^\W\d_](?![^\W\d_]))",
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
# A congruence in an unknown: a lone letter on the left of ``≡`` (``17 ≡ 2 mod 5`` is a check).
_CONGRUENCE = re.compile(r"(?<![^\W\d_])[a-z](?![^\W\d_])[^≡\n.,;]*?(?:≡|\\equiv\b)", re.IGNORECASE)
# LaTeX and the brackets of a step function, as the call each one writes.
_LATEX_NAME = re.compile(r"\\operatorname\s*\{\s*([A-Za-z]+)\s*\}|\\([A-Za-z]+)(?=\s*\()")
_FLOOR_MARK = re.compile(r"⌊|\\lfloor\b")
_CEILING_MARK = re.compile(r"⌈|\\lceil\b")
_LETTER_BEFORE = r"(?<![^\W\d_])"
_LETTER_AFTER = r"(?![^\W\d_])"


def _letter_name(letter: str) -> str:
    """``φ`` is ``phi``: a reading may write a Greek letter out."""
    words = unicodedata.name(letter, "").split()
    return words[-1].lower() if words else letter


def _call_name(run: str, spaced: bool, bar: bool) -> str | None:
    """The function a letter run before ``(`` or ``|`` names, or None for notation or a verb."""
    lowered = run.lower()
    if lowered in WRITTEN:
        return WRITTEN[lowered].name
    if len(run) == 1:
        # ``Γ(x)``, ``ζ(s)``, ``φ(n)``: a Greek letter applied is a function; a Latin one is
        # notation (``f(x)``).
        if run.isascii() or run in _MULTIPLYING_LETTERS or spaced or bar:
            return None
        return run
    if spaced or bar:
        return None
    # ``2xsin(x)`` reaches here as ``xsin``: the name is the run's known tail.
    for name in _KNOWN:
        if len(name) >= 3 and lowered.endswith(name):
            return WRITTEN[name].name
    if len(lowered) < 3 or lowered in REQUEST_WORDS:
        return None
    return lowered


def _latex_call(match: re.Match[str]) -> str:
    """A named operator, or a known function's command; ``\\left(`` stays LaTeX."""
    if match.group(1):
        return match.group(1)
    return match.group(2) if match.group(2).lower() in WRITTEN else match.group(0)


def _plain_calls(text: str) -> str:
    """``\\operatorname{sgn}(x)`` as ``sgn(x)``, ``\\lfloor x \\rfloor`` as ``floor( x``."""
    text = _LATEX_NAME.sub(_latex_call, text)
    text = _FLOOR_MARK.sub(" floor(", text)
    return _CEILING_MARK.sub(" ceiling(", text)


def _bar_pairs(text: str) -> int:
    """Absolute values written with bars: two bars each (``\\left|x\\right|`` too)."""
    return text.count("|") // 2


def written_functions(text: str) -> Counter[str]:
    """Each function the message applies, by its one name, with how often it is applied."""
    found: Counter[str] = Counter()
    text = _plain_calls(text)
    # Where each counted call's name starts: "mod(17, 5)" is a call, and the said form must
    # not count its "mod" again.
    called: set[int] = set()
    for match in _CALL.finditer(text):
        run, spaced, bar = match.group(1), bool(match.group(2)), match.group(3) == "|"
        if not run.isalpha() or (spaced and run.lower() not in MATH_FUNCTION_NAMES):
            continue
        name = _call_name(run, spaced, bar)
        if name is not None:
            found[name] += 1
            called.add(match.start(1))
    if bars := _bar_pairs(text):
        found["abs"] += bars
    for match in _SAID.finditer(text):
        if match.group("mod") and match.start("mod") in called:
            continue
        if match.group("mod") or match.group("percent"):
            found["mod"] += 1
        else:
            said = re.sub(r"\s+", " ", match.group("said").lower())
            found[_SAID_CANONICAL[said]] += 1
    if congruences := len(_CONGRUENCE.findall(text)):
        found["congruence"] += congruences
    return found


def _whole_word(spelling: str) -> str:
    """A spelling that starts or ends with a letter may not run into another letter."""
    before = _LETTER_BEFORE if spelling[0].isalpha() else ""
    after = _LETTER_AFTER if spelling.rstrip("?s")[-1:].isalpha() else ""
    return f"{before}(?:{spelling}){after}"


@cache
def _spelling(name: str) -> re.Pattern[str]:
    """Each way a reading may write ``name``, as whole words: ``sin`` is not in ``arcsin``."""
    function = BY_NAME.get(name)
    if function is not None:
        spellings = (*(re.escape(written) for written in function.written), *function.read_as)
        return re.compile("|".join(_whole_word(spelling) for spelling in spellings), re.IGNORECASE)
    if len(name) == 1:
        # A Greek letter is a function only where a reading still applies it: ``φ(``, ``phi(``.
        letters = f"{re.escape(name)}|{re.escape(_letter_name(name))}"
        return re.compile(rf"{_LETTER_BEFORE}(?:{letters})\s*\(", re.IGNORECASE)
    return re.compile(_whole_word(re.escape(name)), re.IGNORECASE)


def _read_count(name: str, reading: str) -> int:
    count = len(_spelling(name).findall(reading))
    return count + _bar_pairs(reading) if name == "abs" else count


def unread_functions(text: str, reading_parts: Iterable[str]) -> tuple[str, ...]:
    """The written functions a reading's text holds fewer times than the message applies them."""
    written = written_functions(text)
    if not written:
        return ()
    reading = " ".join(reading_parts)
    return tuple(
        sorted(name for name, count in written.items() if _read_count(name, reading) < count)
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
