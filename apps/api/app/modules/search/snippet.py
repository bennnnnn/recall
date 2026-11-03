"""The line a search hit shows: a message's words as a reader sees them, cut around the match.

Messages are stored as the markdown the phone draws, so a snippet cut from the raw body
showed its marks (``…taught by **Ms. Okafor**.``), and a cut through a pair left half of it
that no client could draw. The body is read as plain text first and cut after, here, so
every client (the phone's drawer, the web) gets the same readable line.

A card's fence (a calculator, a chart, a scene: a JSON body) is not words, and is left
out; any other fence keeps its body, as code reads as itself, also code that opens with a
bracket (an ini section, a JS object, a list comprehension). Every pattern is bounded,
so a long or hostile body is read in linear time.
"""

from __future__ import annotations

import json
import re

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

_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+")
_QUOTE = re.compile(r"^\s{0,3}(?:>\s?)+")
_BULLET = re.compile(r"^\s{0,12}[-*+]\s+(?:\[[ xX]\]\s+)?")
_RULE = re.compile(r"^\s{0,3}([-*_])(?:\s{0,2}\1){2,}\s*$")
_TABLE_SEPARATOR = re.compile(
    r"^\s{0,12}\|?\s{0,12}:?-{3,}:?\s{0,12}(?:\|\s{0,12}:?-{3,}:?\s{0,12})*\|?\s{0,12}$"
)


def reader_text(markdown: str) -> str:
    """The message as one line of the words a reader sees, its markdown marks gone."""
    pieces: list[str] = []
    cursor = 0
    for fence in iter_fences(markdown):
        pieces.append(_prose_text(markdown[cursor : fence.start]))
        body = markdown[fence.body_start : fence.body_end]
        if not _is_card_data(body):
            pieces.append(body)
        cursor = fence.end
    pieces.append(_prose_text(markdown[cursor:]))
    return collapse_ws(" ".join(pieces))


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
    idx = text.lower().find(query.lower())
    if idx == -1:
        if len(text) <= max_len:
            return text
        return _trim_end(text, max_len) + "…"
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
    cut = text[start:end].strip()
    if start > 0:
        cut = "…" + cut
    if end < len(text):
        cut += "…"
    return cut


def _trim_end(text: str, max_len: int) -> str:
    space = text.rfind(" ", max_len - _WORD_REACH, max_len)
    return text[: space if space != -1 else max_len].rstrip()


def _prose_text(prose: str) -> str:
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
    return "".join(piece if index % 2 else _marks_text(piece) for index, piece in enumerate(pieces))


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
