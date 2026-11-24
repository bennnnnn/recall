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
and is left for the next read to judge. A number of under three significant figures ("38",
"0.5") is too common to be sure of in a calculation (the ½ of a kinetic energy), so it is
carried only to the lines that say it again, and when a calculation after it uses the same
digits nothing is changed and the step is named. When the digits are still written after
the slip once carried (after a given with the same digits, or in display maths), the
corrected step is named too: those lines may depend on it. Code, inline code and every
fence (a server's answer card among them) are never touched.

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
    statement_parts,
    step_note,
    wrong_steps,
)
from app.modules.chat.working_numbers import shown_like, shown_number

# Each put-right step re-reads the working; a reply has only so many lines.
_MAX_FIXES = 12
# A unit written after a number: \text{s}, \mathrm{m/s}.
_UNIT_INNER = re.compile(r"\\(?:text|mathrm|textrm|rm)\s*\{([^{}]*)\}")
# Display maths: the carry reads inline maths only, so a wrong number there stays.
_DISPLAY = re.compile(r"\$\$.*?\$\$", re.DOTALL)
# How far a wrong number is carried: everywhere it is the slip's, only where a line says it
# again (a number of under three figures, "38" or "0.5", may be another value's in a
# calculation: the ½ of a kinetic energy; review, #2576), or nowhere (the same digits were
# written before the slip: a given's, or another value's).
_ALL, _RESTATED, _NONE = "all", "restated", "none"


def put_right(reply: str, question: str = "") -> tuple[str, str | None]:
    """``reply`` with each wrong number in its working put right, in reading order, and the
    lines built on it with it (the module docstring); and a note for a slip whose number is
    still written after it once carried (after a given with its digits, or in display
    maths): those lines may depend on it."""
    text, note = reply, None
    for _ in range(_MAX_FIXES):
        steps = wrong_steps(text, question)
        if not steps or not steps[0].fixes:
            break
        fixed, complete = _put_right(text, steps[0], question)
        if fixed == text:
            break
        if not complete and note is None:
            note = step_note(steps[0])
        text = fixed
    return text, note


def _put_right(text: str, step: WrongStep, question: str) -> tuple[str, bool]:
    """``text`` with ``step``'s numbers written to their values, each carried on after it,
    and whether every later use was carried; ``text`` as it was when a number cannot be
    carried safely (``_carries``)."""
    edits: list[tuple[int, int, str]] = []
    complete = True
    for fix in step.fixes:
        right = _written(fix)
        edits.append((fix.start, fix.end, right))
        mode = _carries(fix, right, text[: fix.start], question)
        later = _later_uses(text, fix)
        if mode == _NONE:
            complete = complete and not later
            continue
        carried = _carry_edits(text, fix, step.name, mode)
        left_over = later - {start for start, _end in carried}
        if mode == _RESTATED and left_over:
            return text, False
        complete = complete and not (left_over & _display_starts(text))
        edits += [(start, end, right.lstrip("-\u2212")) for start, end in carried]
    for start, end, written in sorted(set(edits), reverse=True):
        text = text[:start] + written + text[end:]
    return text, complete


def _written(fix: Fix) -> str:
    """The fix's value written the way the wrong number was: its places, its minus sign."""
    right = shown_like(fix.value, fix.number)
    return right.replace("-", "\u2212", 1) if fix.number.startswith("\u2212") else right


def _standalone(number: str) -> re.Pattern[str]:
    """``number`` as a whole number, never the digits of another (4.85 in 14.85 or 4.851)."""
    digits = re.escape(number.lstrip("-\u2212"))
    return re.compile(rf"(?<![\d.,]){digits}(?![\d]|[.,]\d)")


def _figures(number: str) -> int:
    """Significant figures as written: 4.85 has 3, 0.5 has 1, 100 has 1, 1,500 has 2."""
    digits = number.lstrip("-\u2212").replace(",", "")
    whole = "." not in digits
    digits = digits.replace(".", "").lstrip("0")
    return len(digits.rstrip("0") if whole else digits)


def _carries(fix: Fix, right: str, before: str, question: str) -> str:
    """How far the wrong number is sure to be the slip's own after it: nowhere when it was
    written before it (or in the question), or when the right one turns its sign; only where
    it is said again when it has under three figures; else everywhere."""
    pattern = _standalone(fix.number)
    signs = (fix.number.startswith(("-", "\u2212")), right.startswith(("-", "\u2212")))
    if pattern.search(before) or pattern.search(question) or signs[0] != signs[1]:
        return _NONE
    return _ALL if _figures(fix.number) >= _CARRIED_FIGURES else _RESTATED


_CARRIED_FIGURES = 3


def _later_uses(text: str, fix: Fix) -> set[int]:
    """Where the wrong number is written after the fix, outside fences and inline code."""
    shown = masked(text)
    return {match.start() for match in _standalone(fix.number).finditer(shown, fix.end)}


def _display_starts(text: str) -> set[int]:
    return {index for block in _DISPLAY.finditer(masked(text)) for index in range(*block.span())}


def _unit_after(after: str) -> str:
    """The unit written right after the fixed number, as a word: "s" for ``\\ \\text{s}``."""
    head = re.sub(r"^(?:\s|\\[,; ])*", "", after[:40].split("$", 1)[0])
    match = _UNIT_INNER.match(head)
    return match.group(1).strip() if match else ""


def _carry_edits(text: str, fix: Fix, name: str, mode: str) -> list[tuple[int, int]]:
    """Where, after the fix, the wrong number is the slip's: each use in a calculation
    (``_ALL`` only), each restatement of it, and each sentence giving it with its unit.
    The maths is read in the whole reply, so the slip's own closing ``$`` is never taken
    for an opening one (review, #2576)."""
    edits: list[tuple[int, int]] = []
    pattern = _standalone(fix.number)
    everywhere = mode == _ALL
    for segment, _follows, at in math_statement_spans(text):
        if at < fix.end:
            continue
        parts, starts = statement_parts(segment, at)
        for index, start in enumerate(starts):
            if _carry_into(parts, index, name, fix.number, operands=everywhere):
                found = pattern.finditer(parts[index].strip())
                edits += [(start + match.start(), start + match.end()) for match in found]
    unit = _unit_after(text[fix.end :]) if name and everywhere else ""
    if unit:
        word = re.compile(rf"{pattern.pattern}(?=(?:\s|\*\*)*{re.escape(unit)}\b)")
        edits += [match.span() for match in word.finditer(prose_only(text), fix.end)]
    return edits


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
