"""The model's own scenes and structures never ship: only the server draws them.

A ```simulation scene is solver-sampled; a ```chem_scene, ```molecule or ```molecule3d is
drawn from a chemistry solve, RDKit or PubChem (``answer_fence.SERVER_DRAWN_LANGS``). Moved
out of ``services.answer_fence`` (the answer-card protocol): chat's finalize is its one owner.
Each is found as the phone's markdown finds a fence, then as the lenient scan does: a fence
either reads as one goes.
"""

from __future__ import annotations

import re

from app.services.answer_fence import SERVER_DRAWN_LANGS, normalize_owned_fences
from app.services.md_fence_scan import Fence, map_closed_fences, read_fence_marker

_DIAGRAM_FAIL_NOTE = "*Could not render that diagram.*"


def strip_model_drawn_fences(text: str, langs: tuple[str, ...] = SERVER_DRAWN_LANGS) -> str:
    """``text`` without the server-drawn fences of ``langs`` a model wrote, in any spelling,
    and without one it left open.

    Every turn's chemistry pass and SMILES drawing run later and add the server's own.
    """
    lower = text.lower()
    if not any(lang in lower for lang in langs):
        return text
    # As the phone reads them first: put in one spelling, a quoted fence leaves its quote.
    stripped = normalize_owned_fences(_without_phone_fences(text, langs), langs)
    for lang in langs:
        stripped = map_closed_fences(stripped, lang, lambda _body: "")
    if stripped == text:
        return text
    cleaned = re.sub(r"\n{3,}", "\n\n", stripped).strip()
    return cleaned or _DIAGRAM_FAIL_NOTE


def drop_open_fences(text: str, langs: tuple[str, ...]) -> str:
    """``text`` without a fence of ``langs`` the model left open, as the phone's dropFences
    drops one. The close-fences pass runs after every check and would close it whole: an
    unclosed ```molecule3d shipped as a drawing, an unclosed ```smiles with its caption
    (review, 2026-11-13). One in a quote goes to the quote's end, the rest staying."""
    spans = [(f.start, f.end) for f in phone_fences(text) if not f.closed and f.lang in langs]
    for start, end in reversed(spans):
        before, after = text[:start].rstrip(), text[end:].lstrip("\n")
        text = f"{before}\n\n{after}" if before and after else before or after
    return text


def _without_phone_fences(text: str, langs: tuple[str, ...]) -> str:
    """``text`` without every fence of ``langs`` the phone reads, closed or left open."""
    pieces: list[str] = []
    cursor = 0
    for fence in phone_fences(text):
        if fence.lang in langs:
            pieces.append(text[cursor : fence.start])
            cursor = fence.end
    return "".join(pieces) + text[cursor:] if pieces else text


# A list item's first line: what a deeper indent below it continues (CommonMark).
_LIST_ITEM = re.compile(r"^ {0,3}(?:[-*+]|\d{1,9}[.)])[ \t]+\S")


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _quote_depth(line: str) -> int:
    """How many quotes the line is in: the ``>`` markers before its text."""
    return line[: len(line) - len(line.lstrip(" \t>"))].count(">")


def _code_line(lines: list[str], index: int) -> bool:
    """A line indented four spaces past any list item it continues: an indented code block,
    whose "```smiles" is text the phone shows, never a fence."""
    line = lines[index]
    if _indent(line) < 4:
        return False
    for before in reversed(lines[:index]):
        if before.strip() and _indent(before) < _indent(line):
            return _LIST_ITEM.match(before) is None
    return True


def phone_fences(text: str) -> list[Fence]:
    """The fences the phone's markdown reads (react-native-markdown-display, CommonMark): in a
    quote or a list item too, never an indented code block's "```" line, its language the
    info string's first word ("```chem_scene |" is a chem_scene), and closed only by a bare
    run of the opener's character at least as long. Inside one, "```python" or "``` done" is
    its content, so a fence they do not close runs to the end, or, in a quote, to the quote's
    end (review, 2026-11-13)."""
    fences: list[Fence] = []
    lines = text.split("\n")
    opener = None
    start = body_start = offset = 0
    for index, line in enumerate(lines):
        after = min(offset + len(line) + 1, len(text))
        marker = read_fence_marker(line, lenient=True)
        if opener is not None and _quote_depth(line) < _quote_depth(opener.prefix):
            # The quote ended, and the fence in it with it.
            fences.append(Fence(start, body_start, offset, offset, opener, closed=False))
            opener = None
        if opener is not None:
            if marker is not None and marker.closes(opener):
                fences.append(Fence(start, body_start, offset, after, opener, closed=True))
                opener = None
        elif marker is not None and not _code_line(lines, index):
            opener, start, body_start = marker, offset, after
        offset = after
    if opener is not None:
        fences.append(Fence(start, body_start, len(text), len(text), opener, closed=False))
    return fences
