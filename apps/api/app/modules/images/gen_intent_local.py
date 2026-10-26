# ruff: noqa: RUF001 - Turkish dotless i, Cyrillic and maths signs are the words matched
"""One picture request in the app's eight other languages, read the way English ones are.

"Zeichne eine Katze mit Hut", "dibuja un gato", "нарисуй кошку", "bir kedi çiz" drew
nothing: every rule in ``gen_intent.py`` reads English words. ``gen_intent_parts`` asks here
only when no English rule matched, so an English message reads as it always did. The
words are ``gen_intent_languages.py``; what a picture may not be about (an example, a
homework, a molecule, what English declines) is ``gen_intent_topics.py``.

Each language keeps the English shapes: "draw" and its object ("draw me a cat"), and
"create", "generate" or "make" with a picture noun ("generate an image of a lion"). The
subject stays in the user's words. Matching is linear token scans, as in ``gen_intent``:
no ``\\s+`` / ``.+`` regex on user chat text.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import pairwise

from app.modules.chemistry.request import extract_compound_name
from app.modules.images.gen_intent_languages import (
    ALSO,
    ARTICLES,
    VERB_FIRST,
    VERB_LAST,
    VerbFirst,
    VerbLast,
)
from app.modules.images.gen_intent_topics import TOPICS

_WORDS = re.compile(r"\S+")
# Punctuation around a word, Spanish "¿¡", French and German quotes, Ethiopic stops.
_EDGES = '.,!?;:"()[]{}¿¡«»“”„…።፣፤፥፦፧፨'
SENTENCE_ENDS = tuple(".!?;:።፧")
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
_MAX_FILLERS = 4
# Read for a verb another language shares ("pinta", "ilustra"): the declined reading wins.
_DECLINED = ""


@dataclass(frozen=True)
class Token:
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


def tokens_of(text: str) -> list[Token]:
    """The words of ``text`` with where each sits, lowercase, elisions and clitics apart."""
    out: list[Token] = []
    for match in _WORDS.finditer(text):
        for start, end in _pieces(text, *match.span()):
            word = _fold(text[start:end])
            if word:
                out.append(Token(start, end, word))
    return out


def phrase_at(phrases: tuple[tuple[str, ...], ...], tokens: list[Token], i: int) -> int:
    """How many tokens a phrase from ``phrases`` covers at ``i`` (the longest), else 0."""
    best = 0
    for phrase in phrases:
        n = len(phrase)
        if n > best and tuple(t.word for t in tokens[i : i + n]) == phrase:
            best = n
    return best


def _subject_text(text: str, tokens: list[Token], prefix: str = "") -> str | None:
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


# Every language's: "Pinta isso" (Portuguese read with Spanish words) points back too.
_PRONOUNS = frozenset(
    {word for lang in VERB_FIRST for word in lang.pronouns}
    | {word for lang in VERB_LAST for word in lang.pronouns}
)
_DETERMINERS = frozenset(word for lang in VERB_FIRST for word in lang.determiners)
_AGAIN = tuple(phrase for lang in VERB_FIRST for phrase in lang.again) + tuple(
    phrase for lang in VERB_LAST for phrase in lang.again
)


# After "das", "la", "le" these say how to change the last picture, not what to draw:
# "Zeichne das größer", "Dessine-la plus grande", "Dessine le en bleu", "Dibuja la más …".
_CHANGES = frozenset(
    "plus moins en más mas menos mayor menor più meno mais maior em in im noch etwas viel "
    "nochmal mit avec con com aussi también auch anche tan so così tão très muy molto sehr "
    "bem bien".split()
)


def _points_back(words: list[str], *, cased: list[str] | None = None) -> bool:
    """ "Zeichne das nochmal", "dibuja eso", "Pinte isso de novo", "Zeichne das größer":
    the chat names what to draw, as English "draw it again" and "draw that bigger" leave
    to the thread. ``cased`` (German, as typed): a lowercase "…er" after "das" is a
    comparative ("größer"), not a noun."""
    if words[0] in _PRONOUNS:
        return True
    tokens = [Token(0, 0, word) for word in words]
    if phrase_at(_AGAIN, tokens, 0):
        return True
    if words[0] not in _DETERMINERS:
        return False
    if len(words) == 1 or phrase_at(_AGAIN, tokens, 1) > 0 or words[1] in _CHANGES:
        return True
    return cased is not None and cased[1][:1].islower() and words[1].endswith("er")


def _before_purpose(words: list[str], purpose: frozenset[str], *, leads: bool = False) -> list[str]:
    """The words the picture is of: "un gato para mi proyecto" is a cat ("for my project"
    says what it is for, as English "draw a cat for my notes"). Turkish says it first."""
    for index, word in enumerate(words):
        if word in purpose:
            return words[index + 1 :] if leads else words[:index]
    return words


def _subject_checks(lang: VerbFirst, words: list[str], typed: list[str]) -> bool:
    drawn = _before_purpose(words, lang.purpose)
    return not (
        _points_back(words, cased=typed if lang.code == "de" else None)
        # "Male mir aus, wie es wäre", "zeichne das Gespräch auf": a separable verb.
        or words[0] in lang.particles
        or words[-1] in lang.particles
        or TOPICS[lang.code].names_one(drawn)
    )


def _skip_fillers(lang: VerbFirst, tokens: list[Token], i: int, end: int) -> tuple[int, bool]:
    """Past "bitte", "mal", "mir" after the verb; True when a "me" word was among them."""
    me = False
    for _ in range(_MAX_FILLERS):
        if i >= end:
            break
        polite = phrase_at(lang.polite, tokens, i)
        if polite:
            i += polite
        elif tokens[i].word in lang.me:
            i, me = i + 1, True
        elif tokens[i].word in lang.fillers or tokens[i].word in ALSO:
            # "… und zeichne auch eine Katze".
            i += 1
        else:
            break
    return i, me


def _verb_first_verb(
    lang: VerbFirst, tokens: list[Token], i: int, end: int
) -> tuple[str, bool, int, int] | None:
    """The verb's family ("draw" or "create"), whether it said "me", and the object's span."""
    me = False
    if lang.me_first and i < end and tokens[i].word in lang.me:
        i, me = i + 1, True
    lead = phrase_at(lang.can_you, tokens, i)
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
    if verb in lang.draw or verb in lang.needs_me or verb in lang.needs_article:
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
    if verb in lang.needs_article and not said_me:
        follows = tokens[i].word if i < end else ""
        if (
            follows not in ARTICLES
            and follows not in lang.determiners
            and follows not in lang.nouns
        ):
            return None
    return family, me or said_me, i, end


def _without_closing_polite(polite: tuple[tuple[str, ...], ...], tokens: list[Token]) -> int:
    """Where the request ends before a closing "bitte" or "por favor"."""
    end = len(tokens)
    for size in (2, 1):
        if end >= size and phrase_at(polite, tokens, end - size) == size:
            return end - size
    return end


def _read_verb_first(lang: VerbFirst, text: str, tokens: list[Token]) -> str | None:
    """The subject; None when the verb is not this language's, ``_DECLINED`` when it is
    and the request is no picture."""
    end = _without_closing_polite(lang.polite, tokens)
    read = _verb_first_verb(lang, tokens, phrase_at(lang.polite, tokens, 0), end)
    if read is None:
        return None
    family, me, i, end = read
    if i < end and tokens[i].word in lang.reflexive:
        return _DECLINED
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
    # Not this language's shape (another may read it): no subject, or too long.
    if not subject or any(t.word in lang.nouns for t in subject[:1]):
        return None
    if bounded and (len(subject) > _SHORT_WORDS or len(text.strip()) > _SHORT_CHARS):
        return None
    typed = [text[t.start : t.end] for t in subject]
    if not _subject_checks(lang, [t.word for t in subject], typed):
        return _DECLINED
    return _subject_text(text, subject) or _DECLINED


def _verb_last_verb(lang: VerbLast, tokens: list[Token], end: int) -> tuple[str, bool, int] | None:
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


def _read_verb_last(lang: VerbLast, text: str, tokens: list[Token]) -> str | None:
    end = len(tokens)
    while end and tokens[end - 1].word in lang.polite:
        end -= 1
    read = _verb_last_verb(lang, tokens, end)
    after = _afterthought(lang, text, tokens, end) if read is None else []
    if after:
        read = ("draw", False, end - len(after) - 1)
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
    words = [t.word for t in subject + after]
    drawn = _before_purpose(words, lang.purpose, leads=True)
    if _points_back(words) or TOPICS[lang.code].names_one(
        [word.removeprefix(lang.of_prefix) for word in drawn]
    ):
        return _DECLINED
    drawn_text = _subject_text(text, subject, lang.of_prefix)
    if drawn_text and after:
        drawn_text = f"{drawn_text}, {_subject_text(text, after)}"
    return drawn_text or _DECLINED


_AFTERTHOUGHT_WORDS = 5


def _afterthought(lang: VerbLast, text: str, tokens: list[Token], end: int) -> list[Token]:
    """ "Bir kedi çiz, yaz mevsiminde": a few words after the verb and its comma still
    describe the picture. The words after the comma, or none."""
    for verb in range(max(0, end - _AFTERTHOUGHT_WORDS - 1), end - 1):
        if tokens[verb].word in lang.draw and text[tokens[verb].end - 1] == ",":
            return tokens[verb + 1 : end]
    return []


def read_picture(
    text: str, tokens: list[Token], prefer: str | None = None
) -> tuple[str, str] | None:
    """The subject and language when the whole of ``text`` asks for one picture.

    A verb two languages share ("pinta", "ilustre" are Spanish and Portuguese) is read
    with each: if either declines, nothing is drawn; else ``prefer`` (the app's language)
    names it, then the first.
    """
    if not tokens or _has_maths(text):
        return None
    found: list[tuple[str, str]] = []
    readings = [(lang.code, _read_verb_first(lang, text, tokens)) for lang in VERB_FIRST]
    readings += [(lang.code, _read_verb_last(lang, text, tokens)) for lang in VERB_LAST]
    for code, subject in readings:
        if subject == _DECLINED:
            return None
        if subject is not None:
            found.append((subject, code))
    if not found:
        return None
    subject, code = next(
        (pick for pick in found if pick[1] == _worded_in(tokens)),
        next((pick for pick in found if pick[1] == prefer), found[0]),
    )
    # "Zeichne Ethanol": a compound the chemistry card draws, as for "draw ethanol".
    if extract_compound_name(f"draw {subject}") is not None:
        return None
    return subject, code


# Words only one of Spanish and Portuguese writes: "Pinte um gato" is Portuguese, whatever
# the app's language; the two share "pinta", "pinte", "ilustra", "ilustre".
_ONLY_IN = {
    "pt": frozenset("um uma uns umas você voce não nao é também isso isto desenhe explique "
                    "os do dos em com meu minha seu sua".split()),
    "es": frozenset("un una unos unas el los las del con mi su eso esto explica qué y "
                    "dibuja".split()),
}  # fmt: skip


def _worded_in(tokens: list[Token]) -> str | None:
    words = {t.word for t in tokens}
    marked = [code for code, only in _ONLY_IN.items() if words & only]
    return marked[0] if len(marked) == 1 else None


def _verbs(*groups: Iterable[str]) -> frozenset[str]:
    return frozenset(word for group in groups for word in group)


# Every word a picture request turns on: a message with none of them asks for no picture.
PICTURE_VERBS = _verbs(
    *(
        lang.draw | lang.create | lang.draw_me | lang.create_me | lang.needs_me
        for lang in VERB_FIRST
    ),
    *(lang.needs_article | lang.draw_infinitives | lang.create_infinitives for lang in VERB_FIRST),
    *(
        lang.draw | lang.create | lang.bare_draw | lang.asked_draw | lang.asked_create
        for lang in VERB_LAST
    ),
)
