# ruff: noqa: RUF001, RUF002, RUF003 - Turkish dotless i, Cyrillic and maths signs are the words matched
"""Picture requests in the app's eight other languages, read the way English ones are.

"Zeichne eine Katze mit Hut", "dibuja un gato", "нарисуй кошку", "bir kedi çiz" drew
nothing: every rule in ``gen_intent.py`` reads English words. ``gen_intent`` asks here only
when no English rule matched, so an English message reads as it always did. The word
lists are ``gen_intent_languages.py``.

Each language keeps the English shapes: "draw" and its object ("draw me a cat"), and
"create", "generate" or "make" with a picture noun ("generate an image of a lion"). The
subject stays in the user's words. A second request after the picture ("… und erkläre
auch, was ein schwarzes Loch ist") is not part of it: the whole line draws nothing, and
``split_picture_request`` gives the planner the two parts, as English "and also" does.

Matching is linear token scans, as in ``gen_intent``: no ``\\s+`` / ``.+`` regex on user
chat text.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import pairwise

from app.modules.images.gen_intent_languages import (
    ALSO,
    ARTICLES,
    ASK_PAIRS,
    ASK_QUESTIONS,
    ASK_VERBS,
    CONNECTORS,
    VERB_FIRST,
    VERB_LAST,
    VerbFirst,
    VerbLast,
)
from app.services.text_normalize import straighten_apostrophes

_WORDS = re.compile(r"\S+")
# Punctuation around a word, Spanish "¿¡", French and German quotes, Ethiopic stops.
_EDGES = '.,!?;:"()[]{}¿¡«»“”„…።፣፤፥፦፧፨'
_SENTENCE_ENDS = tuple(".!?;:።፧")
# "d'un", "l'image", "un'immagine", "s'il", "qu'est-ce": the elided word is its own token.
_ELISIONS = frozenset(
    {
        "d'",
        "l'",
        "m'",
        "t'",
        "s'",
        "j'",
        "n'",
        "c'",
        "qu'",
        "un'",
        "dell'",
        "all'",
        "dall'",
        "nell'",
        "sull'",
        "quest'",
        "cos'",
    }
)
# "dessine-moi", "peux-tu", "desenhe-me": the pronoun after the hyphen is its own token.
_HYPHEN_CLITICS = frozenset({"moi", "toi", "nous", "vous", "tu", "me", "te", "lo", "la", "il"})
# "y = x^2", "1/x", "H2O": maths or chemistry, which those subjects draw.
_MATHS_MARKS = frozenset("=^√∫×÷<>")
_MAX_MODIFIERS = 3
_SHORT_WORDS = 12
_SHORT_CHARS = 80
_MAX_CHARS = 500
# Said before the second request's verb: "y también me explique", "und bitte erkläre".
_ASK_LEADS = frozenset({"me", "mir", "moi", "mi", "мне", "bana", "bitte", "please", "lütfen"})
_MAX_FILLERS = 4


@dataclass(frozen=True)
class _Token:
    start: int
    end: int
    word: str


def _fold(piece: str) -> str:
    word = piece.lower().strip(_EDGES)
    return word if word.endswith("'") else word.strip("'")


def _pieces(text: str, start: int, end: int) -> Iterable[tuple[int, int]]:
    word = text[start:end].lower()
    quote = word.find("'")
    if 0 < quote < len(word) - 1 and word[: quote + 1].strip(_EDGES) in _ELISIONS:
        yield start, start + quote + 1
        yield from _pieces(text, start + quote + 1, end)
        return
    hyphen = word.rfind("-")
    if 0 < hyphen < len(word) - 1 and word[hyphen + 1 :].strip(_EDGES) in _HYPHEN_CLITICS:
        yield from _pieces(text, start, start + hyphen)
        yield start + hyphen + 1, end
        return
    yield start, end


def _tokens(text: str) -> list[_Token]:
    out: list[_Token] = []
    for match in _WORDS.finditer(text):
        for start, end in _pieces(text, *match.span()):
            word = _fold(text[start:end])
            if word:
                out.append(_Token(start, end, word))
    return out


def _phrase_at(phrases: tuple[tuple[str, ...], ...], tokens: list[_Token], i: int) -> int:
    """How many tokens a phrase from ``phrases`` covers at ``i`` (the longest), else 0."""
    best = 0
    for phrase in phrases:
        n = len(phrase)
        if n > best and tuple(t.word for t in tokens[i : i + n]) == phrase:
            best = n
    return best


def _subject_text(text: str, tokens: list[_Token], prefix: str = "") -> str | None:
    if not tokens:
        return None
    start = tokens[0].start
    if prefix and len(tokens) == 1 and tokens[0].word.startswith(prefix):
        # Amharic "የድመት ምስል": the picture of a cat draws "ድመት".
        start += len(prefix)
    subject = text[start : tokens[-1].end].strip().rstrip(_EDGES).strip()
    return subject if len(subject) >= 2 else None


def _has_maths(text: str) -> bool:
    if any(char in _MATHS_MARKS for char in text):
        return True
    for word in text.split():
        has_digit = any(char.isdigit() for char in word)
        if has_digit and any(char in "+*/" for char in word):
            return True
        # A formula: an element symbol then its count ("H2O", "CO2").
        if any(a.isupper() and b.isdigit() for a, b in pairwise(word)):
            return True
    return False


def _no_picture(
    words: list[str],
    *,
    not_words: frozenset[str],
    not_stems: tuple[str, ...],
    not_endings: tuple[str, ...] = (),
    not_pairs: frozenset[tuple[str, str]] = frozenset(),
    prefix: str = "",
) -> bool:
    """A word the app draws itself or that is no picture: "eine Tabelle", "график"."""
    for word in words:
        bare = word.removeprefix(prefix) if prefix else word
        if word in not_words or bare.startswith(not_stems) or word.endswith(not_endings):
            return True
    return any(
        first == a and second.startswith(b)
        for first, second in pairwise(words)
        for a, b in not_pairs
    )


def _points_back(
    words: list[str],
    pronouns: frozenset[str],
    determiners: frozenset[str],
    again: tuple[tuple[str, ...], ...],
) -> bool:
    """ "Zeichne das nochmal", "dibuja eso", "tekrar çiz": the chat names what to draw."""
    if words[0] in pronouns:
        return True
    tokens = [_Token(0, 0, word) for word in words]
    if _phrase_at(again, tokens, 0):
        return True
    return words[0] in determiners and (len(words) == 1 or _phrase_at(again, tokens, 1) > 0)


def _subject_checks(lang: VerbFirst, words: list[str]) -> bool:
    return not (
        _points_back(words, lang.pronouns, lang.determiners, lang.again)
        or words[-1] in lang.particles
        or _no_picture(
            words,
            not_words=lang.not_words,
            not_stems=lang.not_stems,
            not_endings=lang.not_endings,
            not_pairs=lang.not_pairs,
        )
    )


def _skip_fillers(lang: VerbFirst, tokens: list[_Token], i: int, end: int) -> tuple[int, bool]:
    """Past "bitte", "mal", "mir" after the verb; True when a "me" word was among them."""
    me = False
    for _ in range(_MAX_FILLERS):
        if i >= end:
            break
        polite = _phrase_at(lang.polite, tokens, i)
        if polite:
            i += polite
        elif tokens[i].word in lang.me:
            i, me = i + 1, True
        elif tokens[i].word in lang.fillers:
            i += 1
        else:
            break
    return i, me


def _verb_first_verb(
    lang: VerbFirst, tokens: list[_Token], i: int, end: int
) -> tuple[str, bool, int, int] | None:
    """The verb's family ("draw" or "create"), whether it said "me", and the object's span."""
    me = False
    if lang.me_first and i < end and tokens[i].word in lang.me:
        i, me = i + 1, True
    lead = _phrase_at(lang.can_you, tokens, i)
    if lead:
        i += lead
        i, said_me = _skip_fillers(lang, tokens, i, end)
        me = me or said_me
        at = end - 1 if lang.infinitive_last else i
        if at < i or at >= end:
            return None
        verb = tokens[at].word
        if lang.infinitive_last:
            end -= 1
        else:
            i, said_me = _skip_fillers(lang, tokens, i + 1, end)
            me = me or said_me
        family = (
            "draw"
            if verb in lang.draw_infinitives
            else "create"
            if verb in lang.create_infinitives
            else None
        )
        if family is None:
            return None
        # "dibujarme", "disegnarmi": the infinitive carries the "me".
        return family, me or verb.endswith(("me", "rmi")), i, end
    if i >= end:
        return None
    verb = tokens[i].word
    if verb in lang.draw or verb in lang.needs_me:
        family = "draw"
    elif verb in lang.draw_me:
        family, me = "draw", True
    elif verb in lang.create:
        family = "create"
    elif verb in lang.create_me:
        family, me = "create", True
    else:
        return None
    i, said_me = _skip_fillers(lang, tokens, i + 1, end)
    if verb in lang.needs_me and not said_me:
        return None
    return family, me or said_me, i, end


def _without_closing_polite(polite: tuple[tuple[str, ...], ...], tokens: list[_Token]) -> int:
    """Where the request ends before a closing "bitte" or "por favor"."""
    end = len(tokens)
    for size in (2, 1):
        if end >= size and _phrase_at(polite, tokens, end - size) == size:
            return end - size
    return end


def _read_verb_first(lang: VerbFirst, text: str, tokens: list[_Token]) -> str | None:
    end = _without_closing_polite(lang.polite, tokens)
    read = _verb_first_verb(lang, tokens, _phrase_at(lang.polite, tokens, 0), end)
    if read is None:
        return None
    family, me, i, end = read
    if i < end and tokens[i].word in lang.reflexive:
        return None
    j = i + 1 if i < end and tokens[i].word in ARTICLES else i
    k = j
    while k < end and k - j < _MAX_MODIFIERS and tokens[k].word not in lang.nouns:
        k += 1
    after = tokens[k + 1].word if k + 1 < end else ""
    # As in English, words before the noun describe the picture only when "of" follows
    # it ("ein realistisches Bild von einem Löwen"); else they were the subject.
    if k < end and tokens[k].word in lang.nouns and (k == j or not lang.of or after in lang.of):
        start = k + 2 if after in lang.of else k + 1
        bounded = False
    elif family == "create":
        return None
    else:
        start, bounded = j, not me
    subject = tokens[start:end]
    if not subject or any(t.word in lang.nouns for t in subject[:1]):
        return None
    if bounded and (len(subject) > _SHORT_WORDS or len(text.strip()) > _SHORT_CHARS):
        return None
    if not _subject_checks(lang, [t.word for t in subject]):
        return None
    return _subject_text(text, subject)


def _verb_last_verb(lang: VerbLast, tokens: list[_Token], end: int) -> tuple[str, bool, int] | None:
    """The closing verb's family, whether a bare "draw" needs a picture noun, and the end."""
    if end >= 2 and tokens[end - 1].word in lang.question:
        verb, end = tokens[end - 2].word, end - 2
        if verb in lang.asked_draw:
            return "draw", False, end
        return ("create", True, end) if verb in lang.asked_create else None
    if not end:
        return None
    verb = tokens[end - 1].word
    if verb in lang.draw:
        return "draw", False, end - 1
    if verb in lang.bare_draw:
        return "draw", True, end - 1
    return ("create", True, end - 1) if verb in lang.create else None


def _read_verb_last(lang: VerbLast, text: str, tokens: list[_Token]) -> str | None:
    end = len(tokens)
    while end and tokens[end - 1].word in lang.polite:
        end -= 1
    read = _verb_last_verb(lang, tokens, end)
    if read is None:
        return None
    _family, needs_noun, end = read
    i, me = 0, False
    while i < end and (tokens[i].word in lang.polite or tokens[i].word in lang.me):
        me = me or tokens[i].word in lang.me
        i += 1
    if i < end and tokens[i].word in lang.article:
        i += 1
    if end - 1 >= i and tokens[end - 1].word in lang.nouns:
        end, bounded = end - 1, False
    elif needs_noun:
        return None
    else:
        bounded = not me
    subject = tokens[i:end]
    if not subject:
        return None
    if bounded and (len(subject) > _SHORT_WORDS or len(text.strip()) > _SHORT_CHARS):
        return None
    words = [t.word for t in subject]
    if _points_back(words, lang.pronouns, frozenset(), lang.again) or _no_picture(
        words,
        not_words=lang.not_words,
        not_stems=lang.not_stems,
        not_pairs=lang.not_pairs,
        prefix=lang.of_prefix,
    ):
        return None
    return _subject_text(text, subject, lang.of_prefix)


def _read_in(text: str, tokens: list[_Token]) -> tuple[str, str] | None:
    """The picture's subject when the whole of ``text`` asks for one, and the language."""
    if not tokens or _has_maths(text):
        return None
    for first in VERB_FIRST:
        subject = _read_verb_first(first, text, tokens)
        if subject:
            return subject, first.code
    for last in VERB_LAST:
        subject = _read_verb_last(last, text, tokens)
        if subject:
            return subject, last.code
    return None


def _read(text: str, tokens: list[_Token]) -> str | None:
    read = _read_in(text, tokens)
    return read[0] if read else None


def _asks_something(tokens: list[_Token]) -> bool:
    """The rest is a request of its own: "erkläre auch, was …", "kara deliği açıkla"."""
    words = [t.word for t in tokens]
    while words and (words[0] in CONNECTORS or words[0] in ALSO or words[0] in _ASK_LEADS):
        words = words[1:]
    if not words:
        return False
    first = words[0]
    if first in ASK_VERBS or first in ASK_QUESTIONS or tuple(words[:2]) in ASK_PAIRS:
        return True
    # Turkish and Amharic close a request with its verb ("… açıkla", "… አስረዳኝ").
    return words[-1] in ASK_VERBS or words[-1] in ASK_QUESTIONS


def _split_at(text: str, tokens: list[_Token], index: int) -> bool:
    """A second request may start at ``tokens[index]``: after "and", "also" or a sentence,
    or a verb after a comma ("Нарисуй кошку, объясни …")."""
    word = tokens[index].word
    if word in CONNECTORS or word in ALSO:
        return True
    before = text[tokens[index - 1].end - 1]
    if before in _SENTENCE_ENDS:
        return True
    return before in ",፣" and word in ASK_VERBS


def _words_of(*groups: Iterable[str]) -> frozenset[str]:
    return frozenset(word for group in groups for word in group)


# Words a picture request can open with, or close with (Turkish, Amharic, German "…
# zeichnen?"): a message with none of them is never cut for a picture.
_OPENERS = _words_of(
    *(
        lang.draw | lang.create | lang.draw_me | lang.create_me | lang.needs_me
        for lang in VERB_FIRST
    ),
    *(lang.draw_infinitives | lang.create_infinitives | lang.me for lang in VERB_FIRST),
    *(phrase[0] for lang in VERB_FIRST for phrase in (*lang.can_you, *lang.polite)),
)
_CLOSERS = _words_of(
    *(lang.draw_infinitives | lang.create_infinitives for lang in VERB_FIRST),
    *(
        lang.draw | lang.create | lang.bare_draw | lang.asked_draw | lang.asked_create
        for lang in VERB_LAST
    ),
)
_OPENING_WORDS = 3


def _could_hold_a_picture(tokens: list[_Token]) -> bool:
    return any(t.word in _OPENERS for t in tokens[:_OPENING_WORDS]) or any(
        t.word in _CLOSERS for t in tokens
    )


def _split(text: str, tokens: list[_Token]) -> tuple[str, str] | None:
    if not _could_hold_a_picture(tokens):
        return None
    for index in range(1, len(tokens)):
        if not _split_at(text, tokens, index):
            continue
        rest = tokens[index:]
        if not _asks_something(rest):
            continue
        head = text[: tokens[index - 1].end]
        if _read(head, tokens[:index]):
            asked = [t for t in rest if t.word not in CONNECTORS and t.word not in ALSO]
            return head.strip().rstrip(",፣ "), text[asked[0].start :].strip() if asked else ""
    return None


def _candidate(text: str) -> tuple[str, list[_Token]] | None:
    trimmed = straighten_apostrophes(text.strip())
    if not trimmed or len(trimmed) > _MAX_CHARS:
        return None
    return trimmed, _tokens(trimmed)


def extract_other_language_prompt(text: str) -> str | None:
    """The picture ``text`` asks for in Spanish, French, German, Italian, Portuguese,
    Russian, Turkish or Amharic, in the user's words; None when it asks for none, or
    asks for something more beside it."""
    read = _candidate(text)
    if read is None:
        return None
    trimmed, tokens = read
    subject = _read(trimmed, tokens)
    if subject is None or _split(trimmed, tokens) is not None:
        return None
    return subject


def split_picture_request(text: str) -> tuple[str, str] | None:
    """ "Zeichne eine Katze und erkläre auch, was ein schwarzes Loch ist" → the picture
    request and the request after it, for a message no English cut divides."""
    read = _candidate(text)
    if read is None:
        return None
    trimmed, tokens = read
    return _split(trimmed, tokens)


def other_language_of(text: str) -> str | None:
    """The language a picture request was read in ("de" for "Zeichne eine Katze")."""
    read = _candidate(text)
    if read is None:
        return None
    found = _read_in(*read)
    return found[1] if found else None
