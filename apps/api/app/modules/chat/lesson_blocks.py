# ruff: noqa: RUF001
"""A reply as Markdown blocks: each fence whole, and each run of prose lines between blank lines.

The lesson passes move whole blocks (a title after the opening hook, a practice card last),
so a fence is never split and a paragraph never loses a line.
"""

from __future__ import annotations

import re

from app.services.md_fence_scan import line_fences

QUESTION_MARKS = ("?", "？", "፧")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s")
_LIST_ITEM = re.compile(r"^\s{0,3}(?:\d{1,2}[.)]|[-*+])\s")


def blocks(text: str) -> list[str]:
    """``text`` as blocks, in order; a heading line is a block of its own."""
    lines = text.split("\n")
    owners = line_fences(text)
    found: list[str] = []
    current: list[str] = []
    fence = None

    def flush() -> None:
        if current:
            found.append("\n".join(current))
            current.clear()

    for line, owner in zip(lines, owners, strict=True):
        if owner is not None:
            if owner is not fence:
                flush()
                fence = owner
            current.append(line)
            continue
        if fence is not None:
            flush()
            fence = None
        if not line.strip():
            flush()
        elif is_heading(line):
            flush()
            found.append(line)
        else:
            current.append(line)
    flush()
    return found


def joined(parts: list[str]) -> str:
    return "\n\n".join(part.strip("\n") for part in parts if part.strip())


def is_fence(block: str) -> bool:
    return block.lstrip().startswith(("```", "~~~"))


def is_heading(block: str) -> bool:
    return bool(_HEADING.match(block))


def is_list(block: str) -> bool:
    return bool(_LIST_ITEM.match(block))


def is_question(block: str) -> bool:
    """A prose block that asks the reader something."""
    return not (is_fence(block) or is_heading(block)) and any(m in block for m in QUESTION_MARKS)


def is_paragraph(block: str) -> bool:
    return not (is_fence(block) or is_heading(block) or is_list(block))
