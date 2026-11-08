"""The line a search hit shows: a message's words as a reader sees them, cut around the match.

Messages are stored as the markdown the phone draws, so a snippet cut from the raw body
showed its marks (``…taught by **Ms. Okafor**.``), and a cut through a pair left half of it
that no client could draw. The body is read as plain text first and cut after, here, so
every client gets the same line.

Maths is the one thing left for the client to read: its TeX shown as written was source on
screen (``…$t$ = time Required $a$…``), and only a client's own maths reader turns it into
what its screen draws. Every formula (inline, display, a ``math`` fence, an answer card's
value) is kept whole as one ``$...$`` span, never cut through, and a dollar that is not
maths because it sits in code is written ``\\$``. The phone shows each span as one line of
symbols (``features/search/model/snippetText.ts``).

A card's fence (a calculator, a chart, a scene: a JSON body) is not words, and is left
out; any other fence keeps its body, as code reads as itself, also code that opens with a
bracket (an ini section, a JS object, a list comprehension). Every pattern is bounded,
so a long or hostile body is read in linear time.
"""

from __future__ import annotations

import json
import re

from app.services.answer_fence import (
    ANSWER_FENCE_LANGS,
    CHEMISTRY_NOTATION_LINE,
    answer_header_and_value,
)
from app.services.md_fence_scan import iter_fences
from app.services.text_normalize import collapse_ws

# How far a cut moves to land between words; a longer word is cut where it falls.
_WORD_REACH = 15
# How far one inline mark may reach: past it the mark is not a pair, and the text stays.
_SPAN = 300

_IMAGE = re.compile(rf"!\[([^\]\n]{{0,{_SPAN}}})\]\([^)\n]{{0,{_SPAN}}}\)")
_LINK = re.compile(rf"\[([^\]\n]{{1,{_SPAN}}})\]\([^)\n]{{0,{_SPAN}}}\)")
_CODE = re.compile(rf"`([^`\n]{{1,{_SPAN}}})`")
_STRONG = re.compile(rf"(\*\*|__)(?=\S)([^\n]{{1,{_SPAN}}}?)(?<=\S)\1")
_STRIKE = re.compile(rf"~~(?=\S)([^~\n]{{1,{_SPAN}}}?)(?<=\S)~~")
# One star or underscore: not inside a word (snake_case, 2*3*4 stay as they are).
_EMPHASIS = re.compile(rf"(?<![\w*])\*(?=[^\s*])([^*\n]{{1,{_SPAN}}}?)(?<=[^\s*])\*(?![\w*])")
_UNDERSCORE = re.compile(rf"(?<![\w_])_(?=[^\s_])([^_\n]{{1,{_SPAN}}}?)(?<=[^\s_])_(?![\w_])")
_LINE_BREAK_TAG = re.compile(r"<br\s{0,4}/?>", re.IGNORECASE)
# The tags a reply writes for looks; ``List<String>`` in prose is not one.
_TAG = re.compile(
    r"</?(?:b|i|u|s|em|strong|small|mark|kbd|code|sub|sup|del|ins|span|div|p)"
    r"(?:\s[^<>\n]{0,200})?/?>",
    re.IGNORECASE,
)
_ESCAPE = re.compile(r"\\([\\`*_{}\[\]()#+\-.!|~>])")
# Escaped ASCII marks ride in the private-use area while the pairs are read.
_HIDDEN = 0xE000
_SHOW_HIDDEN = {_HIDDEN + code: chr(code) for code in range(128)}
_MATH_DELIMITER = re.compile(r"\$\$|\\[()\[\]]")

# The longest formula a hit shows; a longer one is "…", so the line stays short.
_FORMULA = 2_000
# A formula with explicit delimiters, over lines for display maths. A body stops at the
# next opener and holds no backtick (code), so each opener scans only to the next one.
_DELIMITED_MATH = re.compile(
    r"\$\$((?:[^$\\`]|\\[^`])+?)\$\$"
    r"|\\\[((?:[^\\`]|\\[^\]\[`])+?)\\\]"
    r"|\\\(((?:[^\\`]|\\[^)(`])+?)\\\)"
)
# Inline ``$...$`` as pandoc reads it: the opener before a non-space, the closer after one
# and not before a digit, so "$5 and $10" stays two prices. A body stops at the next dollar.
_INLINE_MATH = re.compile(r"(?<!\\)\$(?=[^\s$])(?:[^$\\\n]|\\.)+?(?<=[^\s\\])\$(?!\d)")
# An answer card's value that is TeX, not words ("12 cm", "5 cups of flour" are words).
_TEX = re.compile(r"\\[A-Za-z]|[\^_{}]")
_COMMAND = re.compile(r"\\[A-Za-z]+")
_UNESCAPED_DOLLAR = re.compile(r"(?<!\\)\$")
# Where a formula waits while the marks around it are read (outside the escapes' range).
_HELD = "\ue100"
_HELD_END = "\ue101"
_HELD_FORMULA = re.compile(f"{_HELD}(\\d{{1,6}}){_HELD_END}")
# Where a code span waits while the formulas around it are found: inside backticks, so no
# formula's body reaches across it.
_HELD_CODE = "\ue102"
_HELD_CODE_SPAN = re.compile(f"`{_HELD_CODE}(\\d{{1,6}})`")
_MATH_FENCE_LANGS = frozenset({"math", "latex", "tex"})
# Fences whose body is the model's prose, maths and marks included (the phone's callouts).
_PROSE_FENCE_LANGS = frozenset(
    {"tip", "note", "warning", "info", "important", "callout", "quote", "blockquote"}
)

_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+")
_QUOTE = re.compile(r"^\s{0,3}(?:>\s?)+")
_BULLET = re.compile(r"^\s{0,12}[-*+]\s+(?:\[[ xX]\]\s+)?")
_RULE = re.compile(r"^\s{0,3}([-*_])(?:\s{0,2}\1){2,}\s*$")
_TABLE_SEPARATOR = re.compile(
    r"^\s{0,12}\|?\s{0,12}:?-{3,}:?\s{0,12}(?:\|\s{0,12}:?-{3,}:?\s{0,12})*\|?\s{0,12}$"
)


def reader_text(markdown: str) -> str:
    """The message as one line of the words a reader sees, its markdown marks gone.

    Each formula stays TeX, whole, between ``$`` marks.
    """
    pieces: list[str] = []
    cursor = 0
    for fence in iter_fences(markdown):
        pieces.append(_prose_text(markdown[cursor : fence.start]))
        pieces.append(_fence_text(fence.lang, markdown[fence.body_start : fence.body_end]))
        cursor = fence.end
    pieces.append(_prose_text(markdown[cursor:]))
    return collapse_ws(" ".join(pieces))


def _fence_text(lang: str, body: str) -> str:
    if lang in _MATH_FENCE_LANGS:
        return _formula(body)
    if lang in _PROSE_FENCE_LANGS or lang.startswith("callout-"):
        return _prose_text(body)
    if lang in ANSWER_FENCE_LANGS:
        # The card's protocol lines (``verified: true``) are not words a reader sees.
        headers, value = answer_header_and_value(body)
        if CHEMISTRY_NOTATION_LINE in headers:
            return _code_text(value)
        has_maths = "$" in value or "\\(" in value
        return _formula(value) if _TEX.search(value) and not has_maths else _prose_text(value)
    return "" if _is_card_data(body) else _code_text(body)


def _formula(tex: str) -> str:
    """TeX as one ``$...$`` span on one line; a formula too long to show is "…"."""
    tex = collapse_ws(_UNESCAPED_DOLLAR.sub("", tex)).rstrip("\\ ")
    if len(tex) > _FORMULA:
        return "…"
    return f"${tex}$" if tex else ""


def _code_text(code: str) -> str:
    # A dollar in code (``$HOME``) is not maths: escaped, no client pairs it.
    return _UNESCAPED_DOLLAR.sub(r"\\$", code)


def _is_card_data(body: str) -> bool:
    """A JSON object or list: a card's data, not code a reader reads."""
    stripped = body.strip()
    if not stripped.startswith(("{", "[")):
        return False
    try:
        return isinstance(json.loads(stripped), (dict, list))
    except ValueError:
        return False


def snippet(content: str, query: str, max_len: int = 120) -> str:
    """A short line of the message's readable text around the first match of ``query``.

    A match only in the marks (or in a card) shows the message's opening words instead.
    The cut lands between words where one is near, so no word is shown in part.
    """
    text = reader_text(content)
    formulas = [(found.start(), found.end()) for found in _INLINE_MATH.finditer(text)]
    idx = _visible_match(text, query, formulas)
    if idx == -1:
        if len(text) <= max_len:
            return text
        return _trim_end(text, max_len, formulas) + "…"
    start = max(0, idx - 40)
    end = min(len(text), idx + len(query) + 80)
    if start > 0 and text[start - 1] != " ":
        space = text.find(" ", start, min(idx, start + _WORD_REACH))
        if space != -1:
            start = space + 1
    if end < len(text) and text[end] != " ":
        space = text.rfind(" ", max(idx + len(query), end - _WORD_REACH), end)
        if space != -1:
            end = space
    start, end = _clear_of_formulas(formulas, start, end, idx, idx + len(query))
    cut = text[start:end].strip()
    if start > 0:
        cut = "…" + cut
    if end < len(text):
        cut += "…"
    return cut


def _visible_match(text: str, query: str, formulas: list[tuple[int, int]]) -> int:
    """Where ``query`` first shows: never inside a TeX command's name ("time" in ``\\times``)."""
    hidden = [
        (command.start(), command.end())
        for first, last in formulas
        for command in _COMMAND.finditer(text, first, last)
    ]
    lower, needle = text.lower(), query.lower()
    idx = lower.find(needle)
    while idx != -1 and any(start < idx + len(needle) and idx < end for start, end in hidden):
        idx = lower.find(needle, idx + 1)
    return idx


def _trim_end(text: str, max_len: int, formulas: list[tuple[int, int]]) -> str:
    space = text.rfind(" ", max_len - _WORD_REACH, max_len)
    end = space if space != -1 else max_len
    for first, last in formulas:
        if first < end < last:
            end = first
    return text[:end].rstrip()


def _clear_of_formulas(
    formulas: list[tuple[int, int]], start: int, end: int, match: int, match_end: int
) -> tuple[int, int]:
    """Edges moved off any formula they cut: the matched one is kept whole, another left out."""
    for first, last in formulas:
        holds_match = first < match_end and match < last
        if first < start < last:
            start = first if holds_match else last
        if first < end < last:
            end = last if holds_match else first
    return start, end


def _prose_text(prose: str) -> str:
    # Display maths may run over lines: each formula is one span on one line first. Code
    # spans wait aside meanwhile, so `\\(x\\)` in code stays code.
    spans: list[str] = []

    def hold(found: re.Match[str]) -> str:
        spans.append(found.group())
        return f"`{_HELD_CODE}{len(spans) - 1}`"

    def put_back(held: re.Match[str]) -> str:
        index = int(held.group(1))
        return spans[index] if index < len(spans) else held.group()

    prose = _DELIMITED_MATH.sub(
        lambda found: _formula(next(g for g in found.groups() if g)), _CODE.sub(hold, prose)
    )
    prose = _HELD_CODE_SPAN.sub(put_back, prose)
    return " ".join(_line_text(line) for line in prose.split("\n"))


def _line_text(line: str) -> str:
    if _RULE.match(line) or _TABLE_SEPARATOR.match(line):
        return ""
    line = _HEADING.sub("", line)
    line = _QUOTE.sub("", line)
    line = _BULLET.sub("", line)
    stripped = line.strip()
    if len(stripped) > 1 and stripped.startswith("|") and stripped.endswith("|"):
        line = " · ".join(cell.strip() for cell in stripped[1:-1].split("|"))
    return _inline_text(line)


def _inline_text(line: str) -> str:
    # Odd pieces are code spans: their text is shown as written, marks and all.
    pieces = _CODE.split(line)
    return "".join(
        _code_text(piece) if index % 2 else _prose_marks_text(piece)
        for index, piece in enumerate(pieces)
    )


def _prose_marks_text(prose: str) -> str:
    # A formula's ``_`` and ``*`` are TeX, not marks: each waits behind a placeholder while
    # the marks are read, so a pair around it (``**$x = 3$**``) still goes.
    formulas: list[str] = []

    def hold(found: re.Match[str]) -> str:
        formula = found.group()
        formulas.append(formula if len(formula) <= _FORMULA + 2 else "…")
        return f"{_HELD}{len(formulas) - 1}{_HELD_END}"

    def put_back(held: re.Match[str]) -> str:
        index = int(held.group(1))
        # A message that itself holds the placeholder's characters keeps them as written.
        return formulas[index] if index < len(formulas) else held.group()

    return _HELD_FORMULA.sub(put_back, _marks_text(_INLINE_MATH.sub(hold, prose)))


def _marks_text(line: str) -> str:
    # An escaped mark (``\\*``) is the character itself: hidden from the pairs, shown after.
    line = _MATH_DELIMITER.sub("", line)
    line = _ESCAPE.sub(lambda match: chr(_HIDDEN + ord(match.group(1))), line)
    line = _IMAGE.sub(r"\1", line)
    line = _LINK.sub(r"\1", line)
    line = _STRONG.sub(r"\2", line)
    line = _STRIKE.sub(r"\1", line)
    line = _EMPHASIS.sub(r"\1", line)
    line = _UNDERSCORE.sub(r"\1", line)
    line = _LINE_BREAK_TAG.sub(" ", line)
    line = _TAG.sub("", line)
    return line.translate(_SHOW_HIDDEN)
