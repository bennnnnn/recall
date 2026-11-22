# ruff: noqa: RUF001 -- a card's minus is read as either sign a reply writes.
"""An unchecked answer card held to the working's last line above it.

A model that ends its working on an expression it never works out ("$\\text{total} = 5 +
20$", "$D = 4 - 12$") does that last sum in its head, and sometimes misses it: the card
said ``total = 37`` and ``D = -7`` (live, 2026-11-22), with the closing line repeating the
card's number. The working check (``working_check.wrong_steps``) reads only the
equalities the working writes, so that last step, from the expression to the card, was
never read.

The card is that step: its value must be the expression's. When it is not, and the
expression is the working's own (each of its numbers written in the question or earlier in
the reply, or the line restating the line before it with the same value), the card takes the expression's
value, written to the card's own places (the working ends unrounded, the card rounds
once), and every repeat of the wrong value after the card follows it, so the card and the
closing summary never disagree. When the expression is not held by the working, which of
the two slipped is unknown: the reply keeps both and a note names the step.

Only a card no solver checked, holding one value, is read; only when nothing but
headings stands between the working's last line and the card; and only when the line
names what the card does (or nothing). A whole card next to a fractional value (4 buses
for 3.75) is a count rounded as the question needs, never a slip.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from app.modules.chat.tex_arithmetic import (
    INLINE_MATH,
    UNIT_GROUP,
    evaluate,
    is_unit_word,
    math_statements,
    plain_arithmetic,
)
from app.modules.chat.working_check import (
    NAME,
    OPERATOR,
    RELATION,
    shown_like,
    slip,
    wrong_steps,
)
from app.services.answer_fence import (
    ANSWER_FENCE_LANGS,
    VERIFIED_ANSWER_MARKER,
    answer_header_and_value,
)
from app.services.md_fence_scan import iter_fences

# A line that is a bold heading alone: "**Answer**", "**Answer (b)**".
_BOLD_LINE = re.compile(r"\*\*[^*\n]+\*\*")
_UPRIGHT = re.compile(r"\\(?:text|mathrm|operatorname|textrm)\s*\{([^{}]*)\}")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


@dataclass(frozen=True)
class CardSlip:
    """The card at ``body_start:body_end`` shows ``shown`` where its working makes ``value``."""

    body_start: int
    body_end: int
    expression: str
    shown: str
    value: float
    # The expression is the working's own, and the card is the reply's last: the text after
    # it is the closing summary, not another part's working.
    held: bool


def _name(tex: str) -> str:
    """A name as written, its upright wrapper and spaces off: ``\\text{total}`` is total."""
    return re.sub(r"[\s{}]", "", _UPRIGHT.sub(r"\1", tex))


def _card_value(body: str) -> tuple[str, str, bool] | None:
    """An unchecked card's symbol (or ""), its one value's TeX, and whether it says "≈"."""
    headers, value = answer_header_and_value(body)
    if not value or "\n" in value or VERIFIED_ANSWER_MARKER in headers:
        return None
    value = value.strip("*$ ")
    parts, relations = RELATION.split(value), RELATION.findall(value)
    if len(parts) > 2:
        return None
    symbol, number = (parts[0].strip(), parts[1].strip()) if relations else ("", value)
    return symbol, number, bool(relations) and relations[0] != "="


def _only_headings(between: str) -> bool:
    """Nothing but blank lines and bold headings between the working and the card."""
    return all(
        not line.strip() or _BOLD_LINE.fullmatch(line.strip()) for line in between.split("\n")
    )


def _held(statements: list[str], expression: str, value: float, earlier: str, name: str) -> bool:
    """The expression is the working's own: the line before it worked the same name to the
    same value ("D = 2^2 - 4(3)(1)" then "D = 4 - 12"), or each of its numbers is written
    earlier in the reply ("part = 20" before "5 + 20")."""
    if len(statements) >= 2 and name:
        before = RELATION.split(statements[-2])
        last = plain_arithmetic(before[-1].strip())
        same = evaluate(last) if last is not None else None
        if (
            len(before) > 1
            and _name(before[0]) == name
            and same is not None
            and math.isclose(same, value, rel_tol=1e-9, abs_tol=1e-12)
        ):
            return True
    written = set(_NUMBER.findall(earlier))
    return all(number in written for number in _NUMBER.findall(expression))


def _counted(value: float, shown: str) -> bool:
    """A whole card beside a fractional value: a count rounded up or down as asked."""
    plain = plain_arithmetic(shown)
    number = evaluate(plain) if plain is not None else None
    return (
        number is not None
        and number == int(number)
        and number in (math.floor(value), math.ceil(value))
        and value != int(value)
    )


def card_slips(text: str, question: str = "") -> list[CardSlip]:
    """Each unchecked card whose one value is not the working's last expression's; a
    number of the ``question`` is one the working holds."""
    found: list[CardSlip] = []
    previous = 0
    fences = list(iter_fences(text))
    last_card = max(
        (fence.start for fence in fences if fence.closed and fence.lang in ANSWER_FENCE_LANGS),
        default=-1,
    )
    for fence in fences:
        above, start = text[previous : fence.start], previous
        previous = fence.end
        if not fence.closed or fence.lang not in ANSWER_FENCE_LANGS:
            continue
        card = _card_value(text[fence.body_start : fence.body_end])
        lines = list(INLINE_MATH.finditer(above))
        if card is None or not lines or not _only_headings(above[lines[-1].end() :]):
            continue
        if not _own_line(above, lines[-1].start()):
            continue
        statements = list(math_statements(above))
        if not statements:
            continue
        parts = RELATION.split(statements[-1])
        expression_tex = parts[-1].strip()
        expression = plain_arithmetic(expression_tex)
        if expression is None or OPERATOR.search(expression.lstrip("-+")) is None:
            continue
        name = _name(parts[0]) if len(parts) > 1 else ""
        symbol, shown_tex, approximate = card
        if name and _name(symbol) != name and not (not symbol and NAME.fullmatch(name)):
            continue
        shown = plain_arithmetic(shown_tex)
        value = evaluate(expression)
        if shown is None or value is None or _counted(value, shown_tex):
            continue
        step = slip(expression_tex, shown_tex, expression, shown, approximate, {})
        if step is None:
            continue
        earlier = f"{question}\n{text[: start + lines[-1].start()]}"
        held = (
            fence.start == last_card
            and _plain_number(shown_tex) is not None
            and not wrong_steps(text)
            and _held(statements, expression_tex, value, earlier, name or _name(symbol))
        )
        found.append(
            CardSlip(fence.body_start, fence.body_end, expression_tex, shown_tex, value, held)
        )
    return found


# The number a card writes, as written: "-7", "1,200", "3.85" (its unit after it left off).
_WRITTEN_NUMBER = re.compile(r"[-−]?\d{1,3}(?:,\d{3})+(?:\.\d+)?|[-−]?\d+(?:\.\d+)?")
# A list marker or a space: what may stand before the working's last line on its line.
_LINE_LEAD = re.compile(r"[ \t]*(?:(?:[-*+]|\d{1,3}[.)])[ \t]+)?")
_SPACING = re.compile(r"\\[,;: !]|\s")


def _own_line(above: str, at: int) -> bool:
    """The working's last maths stands on a line of its own: "Divide $100$ by $2 + 3$" is a
    sentence that goes on to work more out (review, #2536)."""
    lead = above[above.rfind("\n", 0, at) + 1 : at]
    return _LINE_LEAD.fullmatch(lead) is not None


def _plain_number(shown: str) -> str | None:
    """The card's value when it is one plain number, a unit after it or none; never one in
    powers of ten, a fraction or a multiple of pi, whose leading digits are no value
    ("6 \\times 10^3", "7/2", "8\\pi": review, #2536)."""
    written = _WRITTEN_NUMBER.match(shown)
    if written is None:
        return None
    rest = _SPACING.sub("", UNIT_GROUP.sub("", shown[written.end() :]))
    return written.group(0) if not rest or (rest.isalpha() and is_unit_word(rest)) else None


def _repeats(numbers: set[str]) -> re.Pattern[str]:
    """The card's wrong number written again in prose or maths, in any of its ``numbers``
    spellings ("1200", "1,200"), never inside another number."""
    spellings = sorted(numbers, key=len, reverse=True)
    sign = "[-−]" if any(number.startswith(("-", "−")) for number in spellings) else ""
    lead = r"(?<![\d.,])" if sign else r"(?<![\d.,\-−])"
    digits = "|".join(re.escape(number.lstrip("-−")) for number in spellings)
    return re.compile(rf"{lead}{sign}(?:{digits})(?![\d]|[.,]\d)")


def held_cards(text: str, question: str = "") -> tuple[str, str | None]:
    """``text`` with each card its own working contradicts set to the working's value, and
    the wrong value said again after it set the same; a note for a slip whose side is
    unknown (the module docstring)."""
    note: str | None = None
    for found in reversed(card_slips(text, question)):
        if not found.held:
            right = shown_like(found.value, found.shown)
            note = note or f"Check the answer: ${found.expression} = {right}$, not ${found.shown}$."
            continue
        # The number alone, as the card wrote it: its unit stays, and is the prose's own.
        number = _plain_number(found.shown) or found.shown
        said = shown_like(found.value, number)
        body = text[found.body_start : found.body_end]
        at = body.rfind(found.shown)
        body = body[:at] + said + body[at + len(number) :]
        wrong = _repeats({number, plain_arithmetic(number) or number})
        closing = _closing_end(text, found.body_end)
        earlier = wrong.search(text[: found.body_start]) is not None
        tail = _said_again(text[found.body_end : closing], wrong, said, dropped=earlier)
        text = text[: found.body_start] + body + tail + text[closing:]
    return text, note


def _closing_end(text: str, after: int) -> int:
    """Where the closing lines after a card end: the next fence (a picture, a table's code,
    another card), or the reply's end."""
    later = [fence.start for fence in iter_fences(text) if fence.start >= after]
    return min(later, default=len(text))


# A line that is no sentence of the closing summary: a table row, a heading, a quote.
_NOT_PROSE = ("|", "#", ">")


def _said_again(closing: str, wrong: re.Pattern[str], said: str, *, dropped: bool) -> str:
    """The closing lines with the card's wrong value said as the right one. When the working
    also wrote that value (a given, a step), which mention is the card's is unknown, so the
    lines saying it go. A table row, a heading or a quote is left as written (review, #2536)."""
    lines: list[str] = []
    for line in closing.split("\n"):
        if line.lstrip().startswith(_NOT_PROSE) or not wrong.search(line):
            lines.append(line)
        elif not dropped:
            lines.append(wrong.sub(said, line))
    return "\n".join(lines)
