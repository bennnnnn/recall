"""A wrong number in the working the model wrote, put right, and the lines built on it after.

``working_check.wrong_steps`` finds each step whose number is not its value. The first one
is written again to its value, to the places it was shown with ("t = 4.85" for 4.828 is
"t = 4.83"), and the number it got wrong goes on being right after it:

- each later line that uses it in a calculation ("x = 20.48(4.85)") takes the right one;
- each later line that says the same name is it ("**Time: $t \\approx 4.85$ s**"), or the
  number alone (``$4.85\\ \\text{s}$``), takes it too, and a sentence that gives it with
  the same unit ("lands after 4.85 s");
- then the working is read again, so a result worked from the right number ("x = 99.3"
  from 20.48 * 4.83) is put right in turn, and so on to the answer.

Only the exact digits of the wrong number are carried, and only when they appear nowhere
before the slip, in the question or the reply: the same digits there are a given or
another value. A number written as the result of another calculation is that calculation's,
and is left for the next read to judge. A number of fewer than three figures and no decimal
point ("12") is too common to be sure of, so only its own line is put right. Code, inline
code and every fence (a server's answer card among them) are never touched.

A step that cannot be put right in place (another exact form, "\\sqrt{11375} = 25\\sqrt{73}")
stops the walk: the lines after it may depend on it, so they are left as written and the
note names it (``working_check.working_note``).
"""

from __future__ import annotations

import re

from app.modules.chat.tex_arithmetic import (
    masked,
    math_statement_spans,
    plain_arithmetic,
    prose_only,
)
from app.modules.chat.working_check import (
    NAME,
    OPERATOR,
    Fix,
    WrongStep,
    shown_like,
    shown_number,
    statement_parts,
    wrong_steps,
)

# Each put-right step re-reads the working; a reply has only so many lines.
_MAX_FIXES = 12
# A unit written after a number: \text{s}, \mathrm{m/s}, or a bare symbol.
_UNIT_INNER = re.compile(r"\\(?:text|mathrm|textrm|rm)\s*\{\s*([^{}]+?)\s*\}")


def corrected_working(reply: str, question: str = "") -> str:
    """``reply`` with each wrong number in its working put right, in reading order, and the
    lines built on it with it (the module docstring)."""
    text = reply
    for _ in range(_MAX_FIXES):
        steps = wrong_steps(text)
        if not steps or not steps[0].fixes:
            return text
        fixed = _put_right(text, steps[0], question)
        if fixed == text:
            return text
        text = fixed
    return text


def _put_right(text: str, step: WrongStep, question: str) -> str:
    """``text`` with ``step``'s numbers written to their values, each carried on after it;
    ``text`` as it was when a number cannot be carried safely (``_carries``)."""
    original = text
    for fix in sorted(step.fixes, key=lambda fix: fix.start, reverse=True):
        right = _written(fix)
        before, after = text[: fix.start], text[fix.end :]
        mode = _carries(fix, right, before, question)
        if mode != _NONE:
            unit = _unit_after(after) if step.name and mode == _ALL else ""
            carried = _carried(after, fix, right, step.name, unit, everywhere=mode == _ALL)
            if carried is None:
                return original
            after = carried
        text = before + right + after
    return text


# How far a wrong number is carried: everywhere it is the slip's, only where a line says it
# again (a short number, "38", may be another value's in a calculation), or nowhere (the
# same digits were written before the slip: a given's, or another value's).
_ALL, _RESTATED, _NONE = "all", "restated", "none"


def _written(fix: Fix) -> str:
    """The fix's value written the way the wrong number was: its places, its minus sign."""
    right = shown_like(fix.value, fix.number)
    return right.replace("-", "\u2212", 1) if fix.number.startswith("\u2212") else right


def _standalone(number: str) -> re.Pattern[str]:
    """``number`` as a whole number, never the digits of another (4.85 in 14.85 or 4.851)."""
    return re.compile(rf"(?<![\d.,]){re.escape(number.lstrip('-\u2212'))}(?![\d]|[.,]\d)")


def _carries(fix: Fix, right: str, before: str, question: str) -> str:
    """How far the wrong number is sure to be the slip's own after it: nowhere when it was
    written before it (or in the question), or when the right one turns its sign; only where
    it is said again when it is short (no decimal point, under three figures); else
    everywhere."""
    pattern = _standalone(fix.number)
    signs = (fix.number.startswith(("-", "\u2212")), right.startswith(("-", "\u2212")))
    if pattern.search(before) or pattern.search(question) or signs[0] != signs[1]:
        return _NONE
    digits = fix.number.lstrip("-\u2212").replace(",", "")
    return _ALL if "." in digits or len(digits) >= 3 else _RESTATED


def _unit_after(after: str) -> str:
    """The unit written right after the fixed number, as a word: "s" for ``\\ \\text{s}``."""
    head = after[:40].split("$", 1)[0]
    match = _UNIT_INNER.match(re.sub(r"^(?:\s|\\[,; ])*", "", head))
    return match.group(1).strip() if match else ""


def _carried(
    after: str, fix: Fix, right: str, name: str, unit: str, *, everywhere: bool
) -> str | None:
    """``after`` with each use of the wrong number in a calculation, each restatement of
    it, and each sentence giving it with ``unit``, written as ``right``. Not
    ``everywhere``: only the restatements, and None when the number appears anywhere else
    after it, whose line would then disagree with the one put right."""
    edits: list[tuple[int, int]] = []
    pattern = _standalone(fix.number)
    for segment, _follows, at in math_statement_spans(after):
        parts, starts = statement_parts(segment, at)
        for index, start in enumerate(starts):
            if _carry_into(parts, index, name, fix.number, operands=everywhere):
                found = pattern.finditer(parts[index].strip())
                edits += [(start + match.start(), start + match.end()) for match in found]
    if unit:
        prose = prose_only(after)
        word = re.compile(rf"{pattern.pattern}(?=(?:\s|\*\*)*{re.escape(unit)}\b)")
        edits += [match.span() for match in word.finditer(prose)]
    if not everywhere and len(set(edits)) < len(pattern.findall(masked(after))):
        return None
    for start, end in sorted(set(edits), reverse=True):
        after = after[:start] + right.lstrip("-\u2212") + after[end:]
    return after


def _carry_into(parts: list[str], index: int, name: str, number: str, *, operands: bool) -> bool:
    """The wrong number in ``parts[index]`` is the slip's: an operand of a calculation (when
    ``operands``), the same name said to be it, or the number alone; never the result of
    another calculation, nor another name's value."""
    part = parts[index].strip()
    plain = plain_arithmetic(part)
    if plain is None:
        return False
    if OPERATOR.search(plain.lstrip("-+")) is not None:
        return operands
    if index == 0:
        return len(parts) == 1
    earlier = plain_arithmetic(parts[index - 1].strip())
    if earlier is not None and OPERATOR.search(earlier.lstrip("-+")) is not None:
        return False
    head = parts[0].strip()
    if earlier is not None:
        # "4.85 = 4.85": the number said again.
        return shown_number(earlier) is not None and earlier == plain_arithmetic(number)
    return bool(name) and NAME.fullmatch(head.replace(" ", "")) is not None and head == name
