"""Lines that each open with a bold lead stay separate lines.

A model lists options one per line with single breaks ("🇨🇭 **Switzerland — best for
quality of life** (…)", then "🇩🇪 **Germany — …**"), and Markdown joins single breaks into
one paragraph, so the options ran together. A run of two or more such lines becomes one
paragraph each. A lead may follow emoji or flags; list items, headings, quotes, tables and
indented lines are left alone (twin: apps/mobile/lib/markdown/leadLines.ts).

A worked reply's headings start their own paragraph too, whatever line is above them. A
model wrote its sections with single breaks ("$3x - 5 < 2x + 4$" then "**Required**"), and
the phone showed "3x - 5 < 2x + 4 **Required** Solve for x. **Solution**" on one row
(2026-11-13). In a reply that heads a line **Given** or **Required**, a heading is a
section's, a part's or a numbered move's bold title ("**1. Subtract 2x** — subtraction
property") or a bold run that is the whole line, whatever its first letter (a formula's
name, "**pOH from pH**", a bold value). A bold label with words after it on its line
("**Speed:** 3 m/s") and a display formula's lines stay as they are.
"""

from __future__ import annotations

import re
import unicodedata

from app.modules.chat.markdown_regions import display_math_lines, map_prose_outside_fences
from app.services.workout import (
    ANSWER,
    FORMULA,
    GIVEN,
    REQUIRED_HEADINGS,
    REQUIRED_PATTERN,
    SOLUTION,
    STEPS,
    SUBSTITUTION,
)

# What may come before the bold lead: emoji, flags, their modifiers and joiners, spaces.
_PREFIX_CATEGORIES = frozenset({"So", "Sk", "Mn", "Cf"})
_MAX_PREFIX = 16

# A line that makes a reply worked, as the phone reads one (``isWorkedReply``).
_WORKED_LINE = re.compile(rf"^\*\*(?:{GIVEN}|{REQUIRED_PATTERN}):?\*\*")
_BOLD_HEAD = re.compile(r"^\*\*(?P<title>[^*\n]+)\*\*(?P<rest>.*)$")
_SECTIONS = frozenset({GIVEN, *REQUIRED_HEADINGS, SOLUTION, FORMULA, SUBSTITUTION, STEPS, ANSWER})
# "Answer (a)", "1. Subtract 4", "2) Divide", "(b) Speed", "Part (c): Time", "d) Distance".
_TITLE = re.compile(
    rf"{ANSWER} \([a-h]\)|\d+[.)]\s.*|(?:part\s+(?:\([a-h]\)|[a-h])|\([a-h]\)|[a-h]\))\s*[.:]?\s*\S.*",
    re.IGNORECASE,
)


def _opens_with_bold_lead(line: str) -> bool:
    """``**Lead**`` (or ``🇨🇭 **Lead**``) at the start of an unindented line."""
    start = line.find("**")
    if start < 0 or start > _MAX_PREFIX or line[:1] == " ":
        return False
    if any(
        char != " " and unicodedata.category(char) not in _PREFIX_CATEGORIES
        for char in line[:start]
    ):
        return False
    close = line.find("**", start + 2)
    return close > start + 2


def _heading(line: str) -> bool:
    """A worked reply's heading: a bold run that is the whole line, whatever its first
    letter ("**pOH from pH**", "**de Broglie relation**"), or a section's, a part's or a
    numbered move's bold title with words after it. A bold word with other text on its line
    is that line's."""
    bold = _BOLD_HEAD.match(line)
    if bold is None:
        return False
    if bold.group("rest").strip() in ("", ":"):
        return True
    title = bold.group("title").strip().removesuffix(":").strip()
    return title in _SECTIONS or _TITLE.fullmatch(title) is not None


def _separate(prose: str, worked: bool) -> str:
    lines = prose.split("\n")
    # A line of a display formula is the formula's, never a heading.
    display = display_math_lines(lines)
    out: list[str] = []
    for index, line in enumerate(lines):
        above = lines[index - 1] if index else ""
        breaks = (_opens_with_bold_lead(line) and _opens_with_bold_lead(above)) or (
            worked and above.strip() and _heading(line)
        )
        if breaks and not display[index]:
            out.append("")
        out.append(line)
    return "\n".join(out)


def _worked(text: str) -> bool:
    """A reply that heads a line outside its fences **Given** or **Required**."""
    found = False

    def read(prose: str) -> str:
        nonlocal found
        found = found or any(_WORKED_LINE.match(line) for line in prose.split("\n"))
        return prose

    if "**" in text:
        map_prose_outside_fences(text, read)
    return found


def separate_lead_lines(text: str) -> str:
    """Each line of a run of bold-lead lines, and each heading of a worked reply, becomes
    its own paragraph."""
    worked = _worked(text)
    return map_prose_outside_fences(text, lambda prose: _separate(prose, worked))
