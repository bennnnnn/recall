# ruff: noqa: RUF001 - accented and dotless letters are part of the words matched below
"""Which language a text played aloud is written in, when it plainly is one.

Listen picks its voice model by the language of the text it plays, not the app's: a reply can
be in another language than the app (a Spanish answer in an English app). The phone sends a
reply in clips of about 150 characters, the first a "lead"; the lead's language is kept for
the reply (``clip_language``), so one reply is never read in two voices because a later clip
holds only numbers or a name.

A language is named only on plain evidence, else None and the any-language model reads it:

* another script (Cyrillic, Ethiopic, Devanagari) when nearly every letter is of it;
* a Latin-script language when its own common words make up a real share of the text, far
  ahead of every other language's, and no letter of another script is in it.

Each word is in one list only, and a common word another listed language (English
included) also writes is in none: "de", "que", "a", "no", "mais", "das", "dos" and "les" are
in several languages, so in no list. One exception, Spanish "y": French writes it only in
"il y a", which counts as French, and a Spanish text without it often has too few listed
words. Italian, German and
Turkish are listed only so that a text in one of them is never read as Spanish, French or
Portuguese.

Letters used as symbols are no script: Greek (θ, Ω, µ in a formula) and the signs that are
letters to Unicode (º, ª, Ω as the ohm sign).
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

from app.services.text_normalize import straighten_apostrophes

# A reply whose lead could not be told: every clip of it goes to the any-language model.
UNSURE = ""

_WORD = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)?")
_SCRIPTS = {"CYRILLIC": "ru", "ETHIOPIC": "am", "DEVANAGARI": "hi"}
# Letters a reply writes as symbols, by the first word of their Unicode name: "θ = 30°",
# "R = 10 Ω", "el 1º de mayo", "5 µm" are still one language's text.
_SYMBOL_SCRIPTS = frozenset(
    {"GREEK", "MASCULINE", "FEMININE", "MICRO", "OHM", "KELVIN", "ANGSTROM"}
)
# Letters of one script are at least this share of a text before it is of that script: a
# stray symbol (θ in "θ = 30°") is let through, a word of another language is not.
_ONE_SCRIPT = 0.97
# A language's own words are at least this share of the text's words, and more than this
# many times the next language's.
_SHARE = 0.12
_LEAD = 3
_MIN_WORDS = 2

_WORDS: dict[str, frozenset[str]] = {
    "en": frozenset(
        """the and is are of to you your it its this that these those with what how why which
        who they them their we our she not would should could have had does did from by at if
        but there here then than just about into more some any when where been being i'm
        it's don't can't let's you're that's here's there's isn't doesn't""".split()
    ),
    "es": frozenset(
        """el los las y están muy pero también cuando hay puede puedes usted tú más qué cómo
        dónde aquí ahora hola gracias tiene tienes hacer puedo mucho ya ellos yo esa ese eso
        esto estos nuestro nuestra hace estoy eres pueden entonces aunque cuál según después
        siempre""".split()
    ),
    "fr": frozenset(
        """des et est une elle ils elles nous vous je pas pour avec dans au aux cette ces sont
        être avoir très bonjour merci c'est n'est leur votre notre aussi donc ça peut fait
        comme qu'il qu'on j'ai d'un d'une sur""".split()
    ),
    "pt": frozenset(
        """não é são você vocês com uma na nas em ao aos pela também isso isto muito mas seu
        sua ele ela eles elas então foi tem têm estão olá obrigado obrigada pode podem fazer
        aqui onde já nós essa esse ainda assim agora coisa""".split()
    ),
    "it": frozenset(
        """della delle degli gli nel nella sono è per che questo questa anche molto ciao
        grazie alla perché più può essere hai ho""".split()
    ),
    "de": frozenset(
        """der die und ist nicht ein eine mit für auf sie ich wir auch sind zu den dem von
        werden kann haben wird oder aber wenn wie""".split()
    ),
    "tr": frozenset(
        """bir bu için ile çok gibi daha olarak var değil ben sen merhaba şey olan kadar nasıl
        neden evet hayır sonra şimdi bunu ise""".split()
    ),
}
# Letters only one of these languages writes: each word holding one is that language's.
_LETTERS = (("ñ", "es"), ("ãõ", "pt"), ("œ", "fr"), ("ışğ", "tr"), ("ß", "de"))


def _script(char: str) -> str:
    """The script of a letter: "LATIN", "CYRILLIC", …, or "" for one with no name."""
    name = unicodedata.name(char, "")
    return name.split(" ", 1)[0] if name else ""


def _letter_scripts(text: str) -> Counter[str]:
    """How many letters of each script ``text`` holds, letters used as symbols left out."""
    scripts = (_script(char) for char in text if char.isalpha())
    return Counter(script for script in scripts if script not in _SYMBOL_SCRIPTS)


def script_of_language(language: str) -> str:
    """The script a language of the app is written in."""
    return next((script for script, code in _SCRIPTS.items() if code == language), "LATIN")


def one_script(text: str) -> str | None:
    """The script nearly every letter of ``text`` is in; None for a mix or no letters."""
    scripts = _letter_scripts(text)
    total = sum(scripts.values())
    if not total:
        return None
    script, count = scripts.most_common(1)[0]
    return script if count >= _ONE_SCRIPT * total else None


def _latin_language(text: str) -> str | None:
    words = [word.casefold() for word in _WORD.findall(straighten_apostrophes(text))]
    if len(words) < _MIN_WORDS:
        return None
    hits: Counter[str] = Counter()
    for index, word in enumerate(words):
        if word == "y" and index and words[index - 1] == "il":
            hits["fr"] += 1  # "il y a"
            continue
        for language, vocabulary in _WORDS.items():
            if word in vocabulary:
                hits[language] += 1
        for letters, language in _LETTERS:
            if any(letter in word for letter in letters):
                hits[language] += 1
    hits["es"] += text.count("¿") + text.count("¡")
    ranked = hits.most_common(2)
    if not ranked:
        return None
    language, count = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else 0
    if count < _MIN_WORDS or count < _SHARE * len(words) or count <= _LEAD * runner_up:
        return None
    return language


def text_language(text: str) -> str | None:
    """The language ``text`` is plainly written in (an ISO 639-1 code), or None."""
    script = one_script(text)
    if script is None:
        return None
    if script != "LATIN":
        return _SCRIPTS.get(script)
    return _latin_language(text)


def clip_language(text: str, reply_language: str | None) -> str | None:
    """The language one clip of a reply is read in.

    ``reply_language`` is what the reply's lead clip was read as: None when there is no
    record of it (a reply in one clip, or the record expired), ``UNSURE`` when the lead could
    not be told. A clip follows its reply's language unless it says otherwise itself: it
    reads as another language, or holds letters of another script. Then it, alone, goes to
    the any-language model.
    """
    own = text_language(text)
    if reply_language is None:
        return own
    if reply_language == UNSURE:
        return None
    if own == reply_language:
        return own
    if own is None and set(_letter_scripts(text)) <= {script_of_language(reply_language)}:
        return reply_language
    return None
