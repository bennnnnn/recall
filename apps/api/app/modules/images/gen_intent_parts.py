# ruff: noqa: RUF002, RUF003 - Turkish dotless i and Cyrillic are the words matched
"""A picture asked in another language, alone or beside a second request.

"Zeichne mir eine Katze und erkläre auch, was ein schwarzes Loch ist" and "Explica qué
es un agujero negro y dibújame un gato" are two requests each, as "draw a cat and also
explain …" and "explain … and also draw a cat" are in English. The planner's clause rules read
English, so it asks here for the two parts; the whole line draws nothing.

A cut is made only where a second request plainly starts: after "and", "also" or a
sentence, with a verb that asks for an answer ("explain", "tell me") or a question word,
or a picture request after a request ("… und zeichne mir auch eine Katze"). Each picture
part is one of the narrow shapes ``gen_intent_local`` reads ("Dibújame un gato", not
"Dibuja un gato").
"""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.images.gen_intent_languages import (
    ALSO,
    ASK_LAST,
    ASK_PAIRS,
    ASK_QUESTIONS,
    ASK_VERBS,
    CONNECTORS,
)
from app.modules.images.gen_intent_local import (
    CLOSERS,
    OPENERS,
    PICTURE_VERBS,
    SENTENCE_ENDS,
    Token,
    read_picture,
    tokens_of,
)
from app.services.text_normalize import straighten_apostrophes

_MAX_CHARS = 500
# Said between "and" and the request's verb: "und bitte erkläre", "y por favor dibújame".
_POLITE = frozenset({"bitte", "please", "lütfen", "пожалуйста", "por", "favor", "per"})
# … and before an answer verb: "y también me explique". A picture keeps its "me".
_LEADS = _POLITE | {"me", "mir", "moi", "mi", "мне", "bana"}
_QUESTION_MARKS = ("?", "፧")
# Cuts tried for a Turkish or Amharic picture asked second (its verb closes the line).
_SECOND_TRIES = 3


@dataclass(frozen=True)
class Part:
    """One request of the message, in the user's words; ``picture`` for the drawing."""

    text: str
    picture: bool


def _joined(words: list[str], start: int, leads: frozenset[str] = _LEADS) -> int:
    """Past the "and also" and "please" that join a request to the one before."""
    while start < len(words) and (
        words[start] in CONNECTORS or words[start] in ALSO or words[start] in leads
    ):
        start += 1
    return start


def _asks(words: list[str], start: int) -> bool:
    """``words[start:]`` is a request for an answer: "erkläre auch, was …", "… açıkla"."""
    start = _joined(words, start)
    if start >= len(words):
        return False
    first = words[start]
    if first in ASK_VERBS or first in ASK_QUESTIONS or tuple(words[start : start + 2]) in ASK_PAIRS:
        return True
    # Turkish and Amharic close a request with its verb ("… ne olduğunu açıkla").
    return words[-1] in ASK_LAST


def _opens_request(words: list[str], text: str) -> bool:
    """The part before a picture asked second is a request: a question or "explain …"."""
    if text.rstrip().endswith(_QUESTION_MARKS):
        return True
    start = _joined(words, 0)
    if start >= len(words):
        return False
    first = words[start]
    if first in ASK_VERBS or first in ASK_QUESTIONS or tuple(words[start : start + 2]) in ASK_PAIRS:
        return True
    return words[-1] in ASK_LAST


def _cut_here(text: str, tokens: list[Token], index: int) -> bool:
    """A request may start at ``tokens[index]``: after "and", "also" or a sentence, or an
    answer or picture verb after a comma ("Нарисуй мне кошку, объясни …")."""
    word = tokens[index].word
    if word in CONNECTORS or word in ALSO:
        return True
    before = text[tokens[index - 1].end - 1]
    if before in SENTENCE_ENDS:
        return True
    # Turkish and Amharic close the request with its verb: "Bana bir kedi çiz, … açıkla".
    asks_last = tokens[-1].word in ASK_LAST
    return before in ",፣" and (word in ASK_VERBS or word in OPENERS or asks_last)


def _picture_first(text: str, tokens: list[Token], words: list[str], index: int) -> bool:
    head = text[: tokens[index - 1].end]
    return _asks(words, index) and read_picture(head, tokens[:index]) is not None


def _picture_second(text: str, tokens: list[Token], words: list[str], index: int) -> str | None:
    """The picture request that starts at ``index``, after a request of its own."""
    start = _joined(words, index, _POLITE)
    if start >= len(words) or not _opens_request(words[:index], text[: tokens[index - 1].end]):
        return None
    tail = text[tokens[start].start :].strip()
    tail_tokens = tokens_of(tail)
    if read_picture(tail, tail_tokens) is None or _split(tail, tail_tokens, second=False):
        return None
    return tail


def _split(text: str, tokens: list[Token], *, second: bool = True) -> tuple[Part, Part] | None:
    words = [t.word for t in tokens]
    if not any(word in PICTURE_VERBS for word in words):
        return None
    tries = _SECOND_TRIES
    for index in range(1, len(tokens)):
        if not _cut_here(text, tokens, index):
            continue
        head = text[: tokens[index - 1].end].strip().rstrip(",፣ ")
        if _picture_first(text, tokens, words, index):
            asked = _joined(words, index)
            rest = text[tokens[min(asked, len(tokens) - 1)].start :].strip()
            return Part(head, picture=True), Part(rest, picture=False)
        start = _joined(words, index, _POLITE)
        opens = start < len(words) and words[start] in OPENERS
        # "… und kannst du mir eine Katze zeichnen?", "… ve bana bir kedi çiz": the picture
        # closes the line, so every cut could start it.
        closes = not opens and words[-1] in CLOSERS and tries > 0
        if second and (opens or closes):
            tries -= closes
            picture = _picture_second(text, tokens, words, index)
            if picture:
                return Part(head, picture=False), Part(picture, picture=True)
    return None


def _candidate(text: str) -> tuple[str, list[Token]] | None:
    trimmed = straighten_apostrophes(text.strip())
    if not trimmed or len(trimmed) > _MAX_CHARS:
        return None
    return trimmed, tokens_of(trimmed)


def extract_other_language_prompt(text: str) -> str | None:
    """The picture ``text`` asks for in Spanish, French, German, Italian, Portuguese,
    Russian, Turkish or Amharic, in the user's words; None when it asks for none, or
    asks for something more beside it."""
    read = _candidate(text)
    if read is None:
        return None
    trimmed, tokens = read
    found = read_picture(trimmed, tokens)
    if found is None or _split(trimmed, tokens) is not None:
        return None
    return found[0]


def picture_and_request(text: str) -> tuple[Part, Part] | None:
    """A picture asked in another language beside a second request: the parts, in order.
    "Dibújame un gato y explica qué es un agujero negro" is two, as English "draw me a cat
    and also explain …" is; no English cut divides it, so the planner asks here."""
    read = _candidate(text)
    return _split(*read) if read is not None else None


def picture_language(text: str, prefer: str | None = None) -> str | None:
    """The language a picture request was read in ("de" for "Zeichne mir eine Katze"); None
    for English or no picture. ``prefer`` (the app's language) breaks a tie."""
    read = _candidate(text)
    found = read_picture(*read, prefer=prefer) if read is not None else None
    return found[1] if found else None
