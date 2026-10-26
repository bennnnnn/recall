# ruff: noqa: RUF001, RUF002, RUF003 - Turkish dotless i and Cyrillic are the words matched
"""Whether a picture subject asked in another language names a thing to draw.

An allow-list, not a block-list: "Dibújame un gato con sombrero" draws because its head
noun, "gato", is a concrete thing on the language's list; "Dibújame un cuadro
comparativo", "Zeichne mir einen Grundriss", "Нарисуй мне сказку" are answered in words
because "cuadro", "Grundriss" and "сказку" are not. An unusual subject is simply
answered, as on main.

The head noun is where each language puts it:

- Spanish, French, Italian, Portuguese, German and Russian name it first, after a size,
  a look or a number ("un pequeño gato", "einen süßen Hund", "маленького щенка"); what
  follows it ("con sombrero", "mit Hut", "в шляпе") is free, unless the topic lists
  block a word of it (``gen_intent_topics``: "un gato con una tabla de multiplicar").
- Turkish and Amharic close the subject with it ("şapkalı bir kedi", "ኮፍያ ያደረገች ድመት").

The word lists are ``gen_intent_drawable_romance`` and ``gen_intent_drawable_other``.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable
from dataclasses import dataclass

from app.modules.images import gen_intent_drawable_other as other
from app.modules.images import gen_intent_drawable_romance as romance

_HEAD_LAST = frozenset({"tr", "am"})
_LONGEST_NAME = 4
# A German compound's first part has at least this many letters ("Feuerdrache").
_MIN_COMPOUND_LEAD = 3

# German adjectives before the noun inflect ("kleine", "süßen", "großer", "buntes").
_DE_ADJECTIVE = ("e", "en", "er", "es", "em")
# Russian adjectives before the noun ("белого", "маленькую", "красивые"); "-ние"/"-тие"
# nouns ("строение", "событие") are no adjectives.
_RU_ADJECTIVE = tuple("ый ий ой ая яя ое ее ые ие ую юю ого его ых их ым им".split())
_RU_NOT_ADJECTIVE = tuple("ение ание яние тие вие".split())
_RU_ENDINGS = {
    "а": "а у ы и е ой ам ами ах -",
    "я": "я ю и е ей ь ям ями",
    "ь": "ь я и ей ю ем ям",
    "й": "й я и ев ю ем",
    "о": "о а у ом е -",
    "е": "е я а ю ем",
}
_RU_HARD = "- а у ы и ов ей ом е ам ами ах"
_RU_SOFT_ENDS = frozenset("аяьйое")
_RU_FIXED_ENDS = frozenset("иуыюэ")
_TR_VOWELS = "aıoueiöü"
_TR_BACK = frozenset("aıou")
_TR_POSSESSIVE = {"a": "ı", "ı": "ı", "o": "u", "u": "u", "e": "i", "i": "i", "ö": "ü", "ü": "ü"}
_TR_SOFT = {"p": "b", "ç": "c", "t": "d", "k": "ğ"}


def fold(word: str) -> str:
    """Lowercase, no accents, so "leon" is "león" and "kopek" is "köpek"; Cyrillic keeps its
    letters (only "ё" is "е"), Ethiopic is as typed."""
    out: list[str] = []
    for char in word.lower():
        if "Ѐ" <= char <= "ӿ" or "ሀ" <= char <= "፿":
            out.append("е" if char == "ё" else char)
        else:
            out.append(unicodedata.normalize("NFD", char)[0])
    return "".join(out).replace("ı", "i").replace("ß", "ss")


def _listed(entry: str) -> list[str]:
    """ "gato+s" → gato, gatos; "león/leones" → both; "Hund+e+en" → Hund, Hunde, Hunden."""
    out: list[str] = []
    for form in entry.split("/"):
        base, *endings = form.split("+")
        out += [base, *(base + ending for ending in endings)]
    return out


def _russian(word: str) -> list[str]:
    """The case and plural forms of a Russian nominative: "кошка" → "кошку", "кошки" …"""
    last = word[-1]
    if last in _RU_FIXED_ENDS:
        return [word]
    stem, endings = (word[:-1], _RU_ENDINGS[last]) if last in _RU_SOFT_ENDS else (word, _RU_HARD)
    return [stem + ending.strip("-") for ending in endings.split()]


def _turkish(word: str) -> list[str]:
    """A Turkish noun, its plural and its compound form: "gemi", "gemiler", "gemisi"."""
    vowels = [char for char in word if char in _TR_VOWELS]
    if not vowels:
        return [word]
    back = vowels[-1] in _TR_BACK
    plural = word + ("lar" if back else "ler")
    mark = _TR_POSSESSIVE[vowels[-1]]
    forms = [word, plural, plural + ("ı" if back else "i")]
    if word[-1] in _TR_VOWELS:
        return [*forms, word + "s" + mark]
    forms.append(word + mark)
    if word[-1] in _TR_SOFT and len(vowels) > 1:
        forms.append(word[:-1] + _TR_SOFT[word[-1]] + mark)
    return forms


@dataclass(frozen=True)
class Nouns:
    words: frozenset[str]
    names: frozenset[tuple[str, ...]]
    # Said before the head: "pequeño", "zwei", "очень".
    before: frozenset[str] = frozenset()
    # German compounds end with these ("Feuerdrache"), except ``not_compounds``.
    compounds: tuple[str, ...] = ()
    not_compounds: frozenset[str] = frozenset()
    # Each entry as written: Turkish "ayı" (a bear) is no definite "-yı" object.
    entries: frozenset[str] = frozenset()

    def has(self, word: str, *, last_part: bool) -> bool:
        if word in self.words:
            return True
        if "-" in word:
            parts = [part for part in word.split("-") if part]
            return bool(parts) and parts[-1 if last_part else 0] in self.words
        return (
            word.endswith(self.compounds)
            and word not in self.not_compounds
            and any(
                word.endswith(end) and len(word) - len(end) >= _MIN_COMPOUND_LEAD
                for end in self.compounds
            )
        )


def _nouns(
    text: str,
    before: str = "",
    forms: Callable[[str], list[str]] | None = None,
    not_compounds: str = "",
) -> Nouns:
    """The language's nouns; ``forms`` makes the inflected forms of each entry's first."""
    words: set[str] = set()
    names: set[tuple[str, ...]] = set()
    compounds: set[str] = set()
    entries: set[str] = set()
    for entry in text.split():
        marked = entry.startswith("*")
        for index, form in enumerate(_listed(entry.lstrip("*"))):
            *lead, last = form.split("_")
            made = {fold(word) for word in (forms(last) if forms and not index else [last])}
            entries.add(fold(form))
            if lead:
                names.update((*map(fold, lead), made_word) for made_word in made)
            else:
                words.update(made)
            if marked:
                compounds.update(made)
    return Nouns(
        frozenset(words),
        frozenset(names),
        frozenset(map(fold, before.split())),
        tuple(sorted(compounds)),
        frozenset(map(fold, not_compounds.split())),
        frozenset(entries),
    )


NOUNS: dict[str, Nouns] = {
    "es": _nouns(romance.SPANISH, romance.SPANISH_BEFORE),
    "fr": _nouns(romance.FRENCH, romance.FRENCH_BEFORE),
    "it": _nouns(romance.ITALIAN, romance.ITALIAN_BEFORE),
    "pt": _nouns(romance.PORTUGUESE, romance.PORTUGUESE_BEFORE),
    "de": _nouns(other.GERMAN, other.GERMAN_BEFORE, not_compounds=other.GERMAN_NOT_COMPOUNDS),
    "ru": _nouns(other.RUSSIAN, other.RUSSIAN_BEFORE, forms=_russian),
    "tr": _nouns(other.TURKISH, forms=_turkish),
    "am": _nouns(other.AMHARIC),
}


def _name_at(nouns: Nouns, words: list[str], start: int, *, last_part: bool) -> bool:
    if nouns.has(words[start], last_part=last_part):
        return True
    return any(
        tuple(words[start : start + size]) in nouns.names
        for size in range(2, min(_LONGEST_NAME, len(words) - start) + 1)
    )


def _before_head(code: str, nouns: Nouns, word: str, typed: str, *, cased: bool) -> bool:
    """``word`` may come before the head noun: a size, a look, a number."""
    if word in nouns.before:
        return True
    if code == "de":
        # Whoever writes "Hund" capitalised writes nouns so: "Tabelle" is a noun.
        return not (cased and typed[:1].isupper()) and word.endswith(_DE_ADJECTIVE)
    if code == "ru":
        return word.endswith(_RU_ADJECTIVE) and not word.endswith(_RU_NOT_ADJECTIVE)
    return False


def is_entry(code: str, word: str) -> bool:
    """``word`` is a noun of ``code``'s list as written there: "ayı", not "ayıyı"."""
    return fold(word) in NOUNS[code].entries


def names_drawable(code: str, words: list[str], typed: list[str]) -> bool:
    """True when the subject ``words`` (``typed`` as written) has a listed head noun."""
    nouns = NOUNS[code]
    folded = [fold(word) for word in words]
    if not folded:
        return False
    if code in _HEAD_LAST:
        start = max(0, len(folded) - _LONGEST_NAME)
        return nouns.has(folded[-1], last_part=True) or any(
            tuple(folded[index:]) in nouns.names for index in range(start, len(folded) - 1)
        )
    cased = any(word[:1].isupper() for word in typed)
    for index, word in enumerate(folded):
        if _name_at(nouns, folded, index, last_part=code == "de"):
            return True
        if not _before_head(code, nouns, word, typed[index], cased=cased):
            return False
    return False
