"""An emoji fits its line: the same one closing a sentence reply after reply goes.

At "Lots" an 80-message chat about a girlfriend's mother (2026-11-19) ended the opening line
of 58 replies on 💛, whatever the line said. The prompt now says each emoji fits its line and
is never the same one reply after reply as a sign-off, and replayed, one run of the chat still
put 💛 in 40 of 80: once a reply ended a sentence on it, the next ones copied it. Dropped only
when both of the last two replies had it, one run kept it in 24, alternating. So, as the name
pass spares the user's name (``name_use``), when one of the last two replies ended a sentence
on an emoji, this one does not end a sentence on that same emoji. Every other emoji stays, and so does this one where it leads a heading, a list
item or a label (where "Lots" asks for one), or sits in a fence, inline code or a table row.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from app.modules.chat.markdown_regions import map_prose_outside_fences
from app.modules.turn_reading.routing import EMOJI

if TYPE_CHECKING:
    from app.modules.chat.finalize_passes import FinalizeState

# The replies looked back on: a sign-off at most once in three replies.
_LOOK_BACK = 2
# An emoji closing a sentence or a line: after a word or punctuation, before a line end or
# the next sentence. One that leads a line (a heading's or a list item's) is never matched.
_CLOSING = re.compile(rf"(?<=\S)(?P<gap>[ \t]*)(?P<emoji>{EMOJI.pattern})(?=[ \t]*(?:\n|$|[A-Z*]))")
_KEPT_LINE = re.compile(r"^\s*\|")
# "### Lesson 2: Loops": a lesson keeps the emoji its own rules give it (``emoji_placement``).
_LESSON = re.compile(r"^#{1,6}\s.*\bLesson\s+\d", re.MULTILINE)
_CODE = re.compile(r"(`+)[^`]*?\1")
# What may stand before an emoji that leads its line: a heading or list marker, bold.
_LABEL_LEAD = re.compile(r"\s*(?:#{1,6}\s+|(?:[-*+]|\d{1,3}[.)])\s+)?(?:\*\*|__)?\s*")


def _closes(line: str, match: re.Match[str]) -> bool:
    """The match ends a sentence, not leads a heading, a list item or a label."""
    return _LABEL_LEAD.fullmatch(line[: match.start("emoji")]) is None


def closing_emoji(text: str) -> set[str]:
    """The emoji ``text`` ends a sentence or a line on, outside fences, code and tables."""
    found: set[str] = set()

    def collect(prose: str) -> str:
        for line in prose.split("\n"):
            if not _KEPT_LINE.match(line):
                bare = _CODE.sub("", line)
                found.update(m["emoji"] for m in _CLOSING.finditer(bare) if _closes(bare, m))
        return prose

    map_prose_outside_fences(text, collect)
    return found


def _recent_replies(recent: Sequence[Any]) -> list[str]:
    return [
        content
        for message in reversed(recent)
        if getattr(message, "role", None) == "assistant"
        and isinstance(content := getattr(message, "content", None), str)
    ][:_LOOK_BACK]


def without_closing(text: str, repeated: set[str]) -> str:
    """``text`` with each emoji in ``repeated`` gone from where it closes a sentence."""

    def line_without(line: str) -> str:
        if _KEPT_LINE.match(line) or _CODE.search(line):
            return line

        def drop(match: re.Match[str]) -> str:
            gone = match["emoji"] in repeated and _closes(line, match)
            return "" if gone else match.group(0)

        return _CLOSING.sub(drop, line)

    return map_prose_outside_fences(
        text, lambda prose: "\n".join(line_without(line) for line in prose.split("\n"))
    )


def repeated_emoji_pass(state: FinalizeState) -> str:
    """The finalize pass: no sign-off emoji that one of the last two replies signed off on."""
    if state.server_text or _LESSON.search(state.text):
        return state.text
    replies = _recent_replies(state.ctx.recent_messages or [])
    repeated = set().union(*(closing_emoji(reply) for reply in replies))
    if not repeated:
        return state.text
    return without_closing(state.text, repeated)
