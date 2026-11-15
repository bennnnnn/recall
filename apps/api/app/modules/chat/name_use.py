"""The user's name now and then, not in every reply.

In the owner's Greeting chat (2026-11-15) "bini" was in 94 of 100 replies, each line of an
emergency included ("Bini, call 911 now"): once a reply named them, the free plan's model
named them in the next. A prompt line asking for the name rarely made it worse (review,
2026-11-15: a first "my head hurts" got the name 9 of 9, against 3 of 9 without it). So when one of the last two replies already called the user by
name, this one does not: the name goes from where it addresses them, and only there:

- opening the reply: "Bini, call 911 now";
- after a greeting or a short reaction: "Hey bini!", "Sorry, bini, that's fair";
- closing a sentence after a comma: "Great question, bini!".

The name is matched as the profile spells it or capitalised, never in another case: "Use 8
GB, max." keeps its "max" for a user named Max. A sentence about them ("Call Bini.",
"Invite Anna, Bini, and Carl."), a draft's salutation ("Dear Bini,", "Hi Bini, thanks"),
a list item, a quote, a table row, inline code and a fence stay, and so does every name in a
reply to a message about the name ("what's my name?" answered "Bini, of course!").
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any

from app.models.orm import User
from app.modules.chat.markdown_regions import map_prose_outside_fences

if TYPE_CHECKING:
    from app.modules.chat.finalize_passes import FinalizeState

# The replies looked back on: the name at most once in three replies.
_LOOK_BACK = 2
# The words a reply addresses someone after: a greeting or a short reaction.
_GREETINGS = (
    "hey|hi|hello|thanks|thank you|sorry|okay|ok|alright|all right|great|sure|yes|no|oh|ha|"
    "haha|well|good|welcome|congrats|congratulations|nice|wow|phew|got it|deal|done"
)
# Lines whose names are kept: a list item, a quote, a table row, a draft's salutation.
_KEPT_LINE = re.compile(r"^\s*(?:[-*+•]\s|\d{1,3}[.)]\s|>|\|)")
_ABOUT_THE_NAME = re.compile(r"\bnames?\b", re.IGNORECASE)


def _spellings(name: str) -> str:
    forms = dict.fromkeys([name, name[:1].upper() + name[1:]])
    return "|".join(map(re.escape, forms))


def _patterns(name: str) -> tuple[re.Pattern[str], ...]:
    n = rf"(?:{_spellings(name)})\b"
    greet = rf"(?i:\b(?:{_GREETINGS}))"
    return (
        # "**Bini, call 911**" opening the reply: the next word takes the capital. A capital
        # after the comma may start a list of names ("Bini, Anna and Carl are…"): kept.
        re.compile(rf"\A(?P<lead>\s*(?:\*\*)?){n},[ \t]+(?P<next>[^\s*A-Z])"),
        # "Sorry, bini, that's fair", "Hi, Bini!", "Alright, Bini — round two".
        re.compile(rf"(?P<g>{greet}),[ \t]+{n}(?=[ \t]*[,.!?\u2014\u2013])"),
        # "Hey bini!": the greeting then the name, no comma (that is "Hi Bini," a draft's).
        re.compile(rf"(?P<g>{greet})[ \t]+{n}(?=[.!?])"),
        # "Great question, bini!": closing its sentence.
        re.compile(rf"(?<=\S),[ \t]+{n}(?=[.!?](?:\*\*)?(?:\s|$))"),
    )


def _code_spans(text: str) -> list[tuple[int, int]]:
    """Inline code spans: a run of backticks to the next run of the same length. Scanned once,
    as a regex with a backreference read a long run of backticks again for each start
    (CodeQL, #2459)."""
    spans: list[tuple[int, int]] = []
    at = text.find("`")
    while at >= 0:
        end = at
        while end < len(text) and text[end] == "`":
            end += 1
        fence = text[at:end]
        close = text.find(fence, end)
        # The closing run must be exactly as long: not part of a longer one.
        while close >= 0 and close + len(fence) < len(text) and text[close + len(fence)] == "`":
            close = text.find(fence, close + len(fence) + 1)
        if close < 0:
            break
        spans.append((at, close + len(fence)))
        at = text.find("`", close + len(fence))
    return spans


def _outside_code(text: str, change: Callable[[str], str]) -> str:
    parts: list[str] = []
    last = 0
    for start, end in _code_spans(text):
        parts += [change(text[last:start]), text[start:end]]
        last = end
    return "".join([*parts, change(text[last:])])


def without_name(text: str, name: str) -> str:
    """``text`` with ``name`` gone from where it addresses the reader."""
    opening, after_greeting, greeting, closing = _patterns(name)
    text = opening.sub(lambda m: f"{m['lead']}{m['next'].upper()}", text, count=1)

    def line_without(line: str) -> str:
        if _KEPT_LINE.match(line):
            return line
        line = greeting.sub(r"\g<g>", after_greeting.sub(r"\g<g>", line))
        return closing.sub("", line)

    def rewrite(prose: str) -> str:
        return "\n".join(_outside_code(line, line_without) for line in prose.split("\n"))

    return map_prose_outside_fences(text, rewrite)


def named_lately(name: str, recent: Sequence[Any]) -> bool:
    """One of the last ``_LOOK_BACK`` replies called the user by ``name``."""
    word = re.compile(rf"(?:{_spellings(name)})\b")
    replies = [
        content
        for message in reversed(recent)
        if getattr(message, "role", None) == "assistant"
        and isinstance(content := getattr(message, "content", None), str)
    ][:_LOOK_BACK]
    return any(word.search(reply) for reply in replies)


def first_name(user: User | None) -> str | None:
    name = ((user.name if user is not None else None) or "").strip().split()
    return name[0] if name and len(name[0]) >= 2 else None


def spare_name_pass(state: FinalizeState) -> str:
    """The finalize pass: no name in a reply when one of the last two used it."""
    name = first_name(state.ctx.user)
    asked = state.ctx.user_message_content or ""
    if state.server_text or name is None or _ABOUT_THE_NAME.search(asked) or name in asked:
        return state.text
    if not named_lately(name, state.ctx.recent_messages or []):
        return state.text
    return without_name(state.text, name)
