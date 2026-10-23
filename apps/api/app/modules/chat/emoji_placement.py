"""Emoji where the user's setting puts them (``users.emoji_use``, Settings → Emoji).

The prompt says where, and a model does not always listen: at "A few", "what are the
benefits of drinking water" ended every list line with an emoji ("…the fuel for that
system 🌡️") instead of leading its label, and 🌊 opened the reply. The setting is kept
here:

- ``off``: no emoji, unless the user wrote one (then the reply may mirror it).
- ``some``: one emoji may lead a heading, a list item or a bold label line; one written
  later in such a line moves to its front, and any in a sentence goes.
- ``more``: as written.

Fences (code, cards, the clarify card's options), inline code and table rows are never
touched, nor is a lesson (its 🐍 and 🎉 are the lesson's own) or server text.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import TYPE_CHECKING

from app.modules.chat.prompt_constants.routing import EMOJI
from app.services.md_fence_scan import line_fences
from app.services.response_tone import DEFAULT_EMOJI_USE

if TYPE_CHECKING:
    from app.modules.chat.finalize_passes import FinalizeState

# A heading, a list item or a bold label paragraph: its marker, then the text it leads.
_LABELLED = re.compile(r"^(?P<lead>\s*(?:#{1,6}\s+|(?:[-*+]|\d{1,3}[.)])\s+)?)(?P<body>.*)$")
_BOLD_START = re.compile(r"^(?:\*\*|__)")
_INLINE_CODE = re.compile(r"(`+)[^`]*?\1")
# "### Lesson 2: Loops": a lesson keeps the emoji its own rules give it.
_LESSON = re.compile(r"^#{1,6}\s.*\bLesson\s+\d", re.MULTILINE)


def _outside_code(text: str, change: Callable[[str], str]) -> str:
    """``change`` applied to ``text`` between inline code spans, never inside one."""
    parts: list[str] = []
    last = 0
    for span in _INLINE_CODE.finditer(text):
        parts.append(change(text[last : span.start()]))
        parts.append(span.group(0))
        last = span.end()
    parts.append(change(text[last:]))
    return "".join(parts)


# An emoji with the spaces after it: "🧠 Brain" leaves "Brain", "**🧠 Brain**" "**Brain**".
_EMOJI_AND_SPACE = re.compile(rf"(?:{EMOJI.pattern})[ \t]*")
# A space left before a closing bold marker ("**Brain power **") or punctuation.
_SPACE_BEFORE_CLOSE = re.compile(r"[ \t]+(\*\*|__)(?=[\s.,;:!?)]|$)|[ \t]+(?=[.,;:!?)])")


# An emoji used as a sentence break: "Hey bini 👋 How's it going?" lost its 👋 and read
# "Hey bini How's it going?". Between a word and a capitalised word it becomes a full
# stop, unless the word leads into the next ("to 🇫🇷 France") or it is a flag.
_LEADS_ON = frozenset(
    {
        "to", "in", "at", "on", "of", "from", "for", "with", "by", "about", "like", "the",
        "a", "an", "my", "your", "our", "their", "his", "her", "its", "and", "or", "i",
    }
)  # fmt: skip
_FLAG = re.compile(r"[\U0001f1e6-\U0001f1ff]")
# The same letters as the phone's twin, whose regex has no Unicode classes.
_LAST_WORD = re.compile(r"([A-Za-z0-9\u00c0-\u024f']+)[ \t]*$")
_NEXT_WORD = re.compile(r"[A-Z][a-z']")


def _drop_emoji(part: str) -> str:
    """``part`` without its emoji; one that broke two sentences becomes a full stop."""
    out = ""
    last = 0
    for match in _EMOJI_AND_SPACE.finditer(part):
        before = out + part[last : match.start()]
        word = _LAST_WORD.search(before)
        breaks = (
            word is not None
            and word.group(1).lower() not in _LEADS_ON
            and _FLAG.search(match.group(0)) is None
            and _NEXT_WORD.match(part, match.end()) is not None
        )
        out = f"{before.rstrip(' \t')}. " if breaks else before
        last = match.end()
    return out + part[last:]


def _without_emoji(line: str) -> str:
    """``line`` with no emoji outside inline code; its indent and list marker kept."""
    indent = line[: len(line) - len(line.lstrip())]
    body = _outside_code(line[len(indent) :], _drop_emoji)
    body = _SPACE_BEFORE_CLOSE.sub(lambda m: m.group(1) or "", body)
    return f"{indent}{body}".rstrip()


def _first_emoji(text: str) -> str | None:
    """The first emoji outside inline code; a lone joiner or variation mark is none."""
    runs = EMOJI.findall(_INLINE_CODE.sub(" ", text))
    return next((run for run in runs if run.strip("\ufe0f\u200d")), None)


def _leading_emoji(line: str) -> str:
    """``line`` with at most one emoji, at the front of its label."""
    match = _LABELLED.match(line)
    if match is None:
        return _without_emoji(line)
    lead, body = match.group("lead"), match.group("body")
    labelled = bool(lead.strip()) or _BOLD_START.match(body) is not None
    emoji = _first_emoji(body)
    if not labelled or emoji is None:
        return _without_emoji(line)
    rest = _without_emoji(body)
    return f"{lead}{emoji} {rest}" if rest else line


def place_emoji(text: str, level: str | None, *, user_wrote_emoji: bool) -> str:
    """``text`` with its emoji where ``level`` puts them."""
    level = level if level in {"off", "some", "more"} else DEFAULT_EMOJI_USE
    if level == "more" or (level == "off" and user_wrote_emoji) or not EMOJI.search(text):
        return text
    if level == "some" and _LESSON.search(text):
        return text
    lines = text.split("\n")
    owners = line_fences(text)
    for index, line in enumerate(lines):
        if owners[index] is not None or line.lstrip().startswith("|") or not EMOJI.search(line):
            continue
        lines[index] = _without_emoji(line) if level == "off" else _leading_emoji(line)
    return "\n".join(lines)


def place_reply_emoji(state: FinalizeState) -> str:
    """The finalize pass: a model reply's emoji follow the user's setting."""
    if state.server_text or state.ctx.user is None:
        return state.text
    user_wrote_emoji = EMOJI.search(state.ctx.user_message_content or "") is not None
    return place_emoji(state.text, state.ctx.user.emoji_use, user_wrote_emoji=user_wrote_emoji)
