"""The user's name now and then, not in every reply.

In the owner's Greeting chat (2026-11-15) "bini" was in 94 of 100 replies, each line of an
emergency included ("Bini, call 911 now"): once a reply named them, the free plan's model
named them in the next. A prompt line asking for the name rarely made it worse (review,
2026-11-15: a first "my head hurts" got the name 9 of 9, against 3 of 9 without it). So when one of the last two replies already called the user by
name, this one does not: the name goes from where it addresses them, and only there:

- opening the reply: "Bini, call 911 now";
- after a greeting or a short reaction: "Hey bini!", "Sorry, bini, that's fair";
- closing a sentence after a comma: "Great question, bini!";
- set off by commas inside a sentence, after a lowercase word: "That's a lot to take in,
  Bini, and it makes sense". Replayed, the 80-message "Friend getting married" chat
  (2026-11-19) still had the name in 49 replies, nearly all this way; "Invite Anna, Bini,
  and Carl" names a list, after a capital, and stays.

The name is matched as the profile spells it or capitalised, never in another case: "Use 8
GB, max." keeps its "max" for a user named Max. A sentence about them ("Call Bini.",
"Invite Anna, Bini, and Carl."), a draft's salutation ("Dear Bini,", "Hi Bini, thanks"),
a list item, a quote, a table row, inline code and a fence stay, and so does every name in a
reply to a message about the name ("what's my name?" answered "Bini, of course!").
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.models.orm import User
from app.modules.chat.markdown_regions import map_prose_outside_fences
from app.modules.turn_reading.conversation import is_social_opener

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
        # "That's a lot to take in, Bini, and …": between commas after a lowercase word.
        # "I told my sister, Bini, and Carl" names a list: kept.
        re.compile(
            rf"(?P<w>\b[a-z][\w']*),[ \t]+{n},(?=[ \t])(?![ \t]+(?:and|or)[ \t]+(?!I\b)[A-Z])"
        ),
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


def _short_closing(name: str) -> re.Pattern[str]:
    """In a few words back: the name closing a sentence with an emoji or nothing after it,
    after a lowercase word or the sentence's first ("Got it, Sam 👍", "Night, Sam 🌙",
    "Anytime, Sam"). A name after a capital stays: "Just Anna, Sam" names two people
    (review, #2526)."""
    n = rf"(?:{_spellings(name)})\b"
    return re.compile(
        rf"(?P<w>(?:^|(?<=[.!?][ \t]))[A-Z][\w']*|\b[a-z][\w']*),[ \t]+{n}"
        rf"(?=[ \t]*$|[ \t]+[^\w\s*,;:'\"(\[&+-])",
        re.MULTILINE,
    )


def without_name(text: str, name: str, *, short: bool = False) -> str:
    """``text`` with ``name`` gone from where it addresses the reader; ``short``: a few words
    answering a few words, where it closes a sentence with no stop too."""
    opening, after_greeting, greeting, closing, inside = _patterns(name)
    short_closing = _short_closing(name) if short else None
    text = opening.sub(lambda m: f"{m['lead']}{m['next'].upper()}", text, count=1)

    def line_without(line: str) -> str:
        if _KEPT_LINE.match(line):
            return line
        if short_closing is not None:
            # Inside prose only: a fence's "id, Sam" is data (review, #2526).
            line = short_closing.sub(r"\g<w>", line)
        line = greeting.sub(r"\g<g>", after_greeting.sub(r"\g<g>", line))
        return inside.sub(r"\g<w>,", closing.sub("", line))

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


def _sparable_name(user: User | None, asked: str) -> str | None:
    """The user's name when a reply may be held to it at all: never in a reply to a message
    about the name, or one that says it."""
    name = first_name(user)
    if name is None or _ABOUT_THE_NAME.search(asked) or name in asked:
        return None
    return name


@dataclass(frozen=True)
class NameSpare:
    """What the finalize pass will decide for this turn's name, known before the reply: the
    name, whether the message is a few words (then a short reply spares it too) and whether
    one of the last two replies used it (then every reply does)."""

    name: str
    short_message: bool
    named_lately: bool


def name_to_spare(user: User | None, asked: str, recent: Sequence[Any]) -> NameSpare | None:
    """The name a streaming reply may leave out of its opening (``OpeningNameHold``), or
    ``None`` when the finalize pass keeps it whatever the reply says."""
    name = _sparable_name(user, asked)
    if name is None:
        return None
    spare = NameSpare(name, _a_short_message(asked), named_lately(name, recent))
    return spare if spare.short_message or spare.named_lately else None


def spare_name_pass(state: FinalizeState) -> str:
    """The finalize pass: no name in a reply when one of the last two used it, nor in a few
    words answering a few words."""
    asked = state.ctx.user_message_content or ""
    name = _sparable_name(state.ctx.user, asked)
    if state.server_text or name is None:
        return state.text
    short = _a_short_exchange(asked, state.text)
    if not short and not named_lately(name, state.ctx.recent_messages or []):
        return state.text
    return without_name(state.text, name, short=short)


class OpeningNameHold:
    """The streaming reply's opening, held until it is clear what the finalize pass makes of
    a name the turn may spare ("Hi Bini!", "Bini, here's…"), then sent as it will be saved.

    The finalize pass took the name out only once the reply had streamed, so the phone showed
    "Hi Bini" and then swapped in "Hi" (the owner, 2026-11-23). Only finished words count (a
    token may end inside the name: "Bi", "ni"). With no name in the first few words, the
    opening passes unchanged. With the name in it, it is held to the end of its sentence, or,
    after a message of a few words, until the reply is past a short one or ends: the finalize
    pass's rule turns on the whole reply's length. Then everything passes straight through; a
    name further in is still the finalize pass's.
    """

    _WORDS = 4
    _MAX_CHARS = 400
    _SENTENCE_END = re.compile(r"[.!?\n]")

    def __init__(self, spare: NameSpare) -> None:
        self._spare = spare
        self._word = re.compile(rf"(?:{_spellings(spare.name)})\b")
        self._held = ""
        self._open = True

    def feed(self, token: str) -> str:
        if not self._open:
            return token
        self._held += token
        if len(self._held) >= self._MAX_CHARS:
            return self._release(short=False)
        return self._release(short=False) if self._settled() else ""

    def flush(self) -> str:
        if not self._open:
            return ""
        short = self._spare.short_message and len(self._held.split()) <= _SHORT_REPLY_WORDS
        return self._release(short=short)

    def _settled(self) -> bool:
        held = self._held
        cut = max(held.rfind(" "), held.rfind("\n"), held.rfind("\t")) + 1
        done, tail = held[:cut], held[cut:]
        named = self._word.search(held)
        if named is None:
            last = tail.strip("*_,;:.!?\"'()").lower()
            maybe_name = bool(last) and self._spare.name.lower().startswith(last)
            return len(done.split()) > self._WORDS and not maybe_name
        if self._spare.short_message:
            return len(done.split()) > _SHORT_REPLY_WORDS
        return self._SENTENCE_END.search(done, named.end()) is not None

    def _release(self, *, short: bool) -> str:
        self._open = False
        if not short and not self._spare.named_lately:
            return self._held
        return without_name(self._held, self._spare.name, short=short)


# "ok" answered "Got it, Sam 👍", "thanks" "Anytime, Sam!", "night" "Night, Sam 🌙": in 100
# texted chats (2026-11-21) a few words back named the user in most of them. A friend says
# "anytime 😊"; a greeting may still answer with the name ("Hey Sam!").
_SHORT_MESSAGE_WORDS = 4
_SHORT_REPLY_WORDS = 30


def _a_short_message(asked: str) -> bool:
    """A few words, no greeting."""
    return len(asked.split()) <= _SHORT_MESSAGE_WORDS and not is_social_opener(asked)


def _a_short_exchange(asked: str, reply: str) -> bool:
    """A few words answered in a few words, the message no greeting."""
    return _a_short_message(asked) and len(reply.split()) <= _SHORT_REPLY_WORDS
