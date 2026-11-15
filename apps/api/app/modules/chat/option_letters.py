"""Lettered options in a reply: one plain style, and the question they answer.

A trivia game in the owner's Greeting chat (2026-11-15) wrote its options "🅰️ Roman
Empire", "🅱️ Greek Empire", "🅲 Ottoman Empire". U+1F170 and U+1F171 have colour emoji
forms, U+1F172 and the letters after it have none, so C drew as a plain glyph beside two
coloured ones; at "A few" emoji the emoji pass took the variation mark and the space with
it ("🅰Roman Empire"); and Markdown joins lines a single break apart, so the phone ran the
options together on one row. A run of two or more lettered options, A first, in any style a
model writes ("🅰️", "A)", "A.", "(A)", "**A.**", "- A)"), becomes "A) England", one
paragraph each, the same on both platforms.

The same reading tells the pick note which question a typed "A" answers
(``prompt_constants.list_reference``): the line just before the options, ending on "?".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.modules.chat.markdown_regions import map_prose_outside_fences
from app.services.md_fence_scan import line_fences

if TYPE_CHECKING:
    from app.modules.chat.finalize_passes import FinalizeState

# 🅰 to 🆉 (U+1F170 to U+1F189), a variation mark or not; or a plain capital A to H.
_SQUARED_A = 0x1F170
_OPTION = re.compile(
    r"^(?P<indent>[ \t]{0,3})(?:[-*+•][ \t]+)?(?P<open>\*\*)?"
    r"(?:(?P<squared>[\U0001f170-\U0001f189])️?[ \t]*"
    r"|(?:\((?P<wrapped>[A-H])\)|(?P<letter>[A-H])[.)])(?P<close>\*\*)?[ \t]+)"
    r"(?P<text>\S.*?)[ \t]*$"
)
_MARKUP = re.compile(r"\*\*|__|[*_`]")
# What may close a question line: markup, emoji, spaces.
_QUESTION_END = re.compile(r"\?[^\w\n]*$")
# The options close a question only when little comes after them ("Type A, B, or C. 🎯").
_AFTER_LINES = 2
_AFTER_CHARS = 200
# Only the reply's end is read for a question, as the pick note reads it.
_TAIL_CHARS = 2_000


@dataclass(frozen=True)
class Option:
    letter: str
    # As the reply wrote it, its markup kept ("**Roman Empire**", "$x_1$").
    text: str

    @property
    def plain(self) -> str:
        return _MARKUP.sub("", self.text).strip() or self.text


@dataclass(frozen=True)
class OptionQuestion:
    """A question a reply asked with lettered options under it."""

    question: str
    options: tuple[Option, ...]


def _option(line: str) -> tuple[str, Option] | None:
    """The indent and option a line holds, or None."""
    match = _OPTION.match(line)
    if match is None:
        return None
    squared = match["squared"]
    letter = chr(ord("A") + ord(squared) - _SQUARED_A) if squared else None
    letter = letter or match["wrapped"] or match["letter"]
    text = match["text"]
    if match["open"] and not match["close"] and not squared:
        # "**A) England**": the bold wraps the whole option.
        text = text.removesuffix("**").rstrip()
    elif match["open"] and squared:
        # "**🅰️ England**".
        text = text.removesuffix("**").rstrip()
    return match["indent"], Option(letter, text)


def _runs(lines: list[str]) -> list[tuple[int, int, list[Option]]]:
    """Each run of two or more options lettered A, B, C … in order: its first and last line
    and its options. Blank lines may sit between them."""
    runs: list[tuple[int, int, list[Option]]] = []
    start, end = -1, -1
    options: list[Option] = []
    for index, line in enumerate([*lines, "end"]):
        if not line.strip() and options:
            continue
        found = _option(line)
        expected = chr(ord("A") + len(options))
        if found is not None and found[1].letter == expected:
            start = index if not options else start
            end, options = index, [*options, found[1]]
            continue
        if len(options) >= 2:
            runs.append((start, end, options))
        options = []
        if found is not None and found[1].letter == "A":
            start, end, options = index, index, [found[1]]
    return runs


def plain_option_letters(text: str) -> str:
    """``text`` with each run of lettered options written "A) …", a paragraph each."""

    def rewrite(prose: str) -> str:
        lines = prose.split("\n")
        runs = _runs(lines)
        if not runs:
            return prose
        out: list[str] = []
        last = 0
        for start, end, options in runs:
            out += lines[last:start]
            if out and out[-1].strip():
                out.append("")
            indent = (_option(lines[start]) or ("", None))[0]
            for number, option in enumerate(options):
                out += [""] if number else []
                out.append(f"{indent}{option.letter}) {option.text}")
            if end + 1 < len(lines) and lines[end + 1].strip():
                out.append("")
            last = end + 1
        return "\n".join([*out, *lines[last:]])

    return map_prose_outside_fences(text, rewrite)


def asked_options(reply: str) -> OptionQuestion | None:
    """The question ``reply`` ends on with lettered options under it, or None.

    The line just before the options asks it ("**Which river runs through Paris?**"); a
    lettered outline under no question ("A) Plan the route") asks nothing."""
    tail = reply.rstrip()[-_TAIL_CHARS:]
    # A fenced card's or code's lines ask nothing.
    owners = line_fences(tail)
    lines = [
        "" if owner is not None else line
        for line, owner in zip(tail.split("\n"), owners, strict=False)
    ]
    runs = _runs(lines)
    if not runs:
        return None
    start, end, options = runs[-1]
    after = [line for line in lines[end + 1 :] if line.strip()]
    if len(after) > _AFTER_LINES or sum(map(len, after)) > _AFTER_CHARS:
        return None
    above = next((line for line in reversed(lines[:start]) if line.strip()), "")
    if not _QUESTION_END.search(above):
        return None
    # The question ends at its mark: "Which planet is closest to the Sun? 🪐".
    question = _MARKUP.sub("", above)
    question = question[: question.rfind("?") + 1].strip()
    # "Here's your first question: Which empire …?" asks the part after its colon.
    question = question.rpartition(": ")[2] if ": " in question else question
    return OptionQuestion(question.strip(), tuple(options))


def plain_options_pass(state: FinalizeState) -> str:
    """The finalize pass: a model reply's lettered options in one plain style."""
    if state.server_text:
        return state.text
    return plain_option_letters(state.text)
