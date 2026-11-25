# ruff: noqa: RUF001 - accented and dotless letters are part of the words matched below
"""Which language a text played aloud is written in, when it plainly is one.

Listen picks its voice model by the language of the text it plays, not the app's: a reply can
be in another language than the app (a Spanish answer in an English app). The phone sends a
reply in clips of about 150 characters, the first a "lead"; the lead's language is kept for
the reply (``clip_language``), so one reply is never read in two voices because a later clip
holds only numbers or a name.

A language is named only on plain evidence, else None and the any-language model reads it:

* another script (Cyrillic, Ethiopic, Devanagari) when nearly every letter (97%) is of it;
* a Latin-script language when every letter is Latin and its own common words make up a
  real share of the text, far ahead of every other language's.

A clip too short or too plain to tell ("Divide both sides by 3.") plays in its reply's
language, or the app's, when nothing in it says otherwise (``clip_language``).

Each word is in one list only, and a word another listed language writes in everyday text,
English above all, is in none: "de", "que", "a", "no", "mais", "das", "dos" and "les" are in
several of these languages; "per", "pour", "die", "den", "ben", "hay", "est", "et" (et al.),
"au" (au pair), "ho", "ciao", "mit", "von", "sen" and "na" (sodium) are English words too,
and "Los Angeles", "Las Vegas", "São Paulo" and "Notre-Dame" are English text. A single
letter is never a word here ("y" is Spanish "and", and a variable in "x + y = 5"), and a web
address's parts are not words (the "com" of example.com is not Portuguese "with"). Italian,
German and Turkish are listed only so that a text in one of them is never read as Spanish,
French or Portuguese.

Letters used as symbols are no script: Greek (θ, Ω, µ in a formula) and the signs that are
letters to Unicode (º, ª, Ω as the ohm sign, the modifier letters of a pronunciation).
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

from app.services.text_normalize import straighten_apostrophes

# A reply whose lead could not be told: every clip of it goes to the any-language model.
UNSURE = ""

_WORD = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)?")
# A dot inside a token makes it a web address or a file name ("example.com", "main.py"): no
# words of a language. Matched token by token, so no input can make it backtrack.
_DOTTED = re.compile(r"\w\.\w")
_SCRIPTS = {"CYRILLIC": "ru", "ETHIOPIC": "am", "DEVANAGARI": "hi"}
# Letters a reply writes as symbols, by the first word of their Unicode name: "θ = 30°",
# "R = 10 Ω", "el 1º de mayo", "5 µm" are still one language's text.
_SYMBOL_SCRIPTS = frozenset(
    {"GREEK", "MASCULINE", "FEMININE", "MICRO", "OHM", "KELVIN", "ANGSTROM", "MODIFIER"}
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
        """el están muy pero también cuando puede puedes usted tú más qué cómo dónde aquí
        ahora hola gracias tiene tienes hacer puedo ya ellos esa ese eso esto estos nuestro
        nuestra hace estoy eres pueden entonces aunque cuál según después siempre ejemplo
        primero nosotros ustedes luego mismo mejor bueno necesitas""".split()
    ),
    "fr": frozenset(
        """des une ils elles nous vous je avec dans aux cette ces sont être avoir très bonjour
        merci c'est n'est leur votre aussi donc ça peut comme qu'il qu'on j'ai d'un d'une voici
        beaucoup toujours cela alors déjà même où chez quelque parce""".split()
    ),
    "pt": frozenset(
        """não é você vocês com uma ao aos pela também isso isto muito mas seu sua ele ela
        eles elas então foi tem têm estão olá obrigado obrigada pode podem fazer aqui onde já
        nós essa esse ainda assim agora coisa""".split()
    ),
    "it": frozenset(
        """della delle degli gli nel nella sono è questo questa anche grazie perché più può
        essere""".split()
    ),
    "de": frozenset(
        """der und ist nicht ein eine für sie ich wir auch sind zu werden kann haben wird oder
        aber wenn wie""".split()
    ),
    "tr": frozenset(
        """bir için ile çok gibi daha olarak değil merhaba şey olan kadar nasıl neden evet
        hayır sonra şimdi bunu""".split()
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


def _latin_hits(text: str) -> tuple[list[str], Counter[str]]:
    """``text``'s words, and how many of them each listed language's own words are."""
    tokens = straighten_apostrophes(text).split()
    plain = " ".join(token for token in tokens if not _DOTTED.search(token))
    words = [word.casefold() for word in _WORD.findall(plain) if len(word) > 1]
    hits: Counter[str] = Counter()
    for word in words:
        for language, vocabulary in _WORDS.items():
            if word in vocabulary:
                hits[language] += 1
        for letters, language in _LETTERS:
            if any(letter in word for letter in letters):
                hits[language] += 1
    hits["es"] += text.count("¿") + text.count("¡")
    return words, +hits


def _latin_language(text: str) -> str | None:
    words, hits = _latin_hits(text)
    if len(words) < _MIN_WORDS:
        return None
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
    # A Latin-script language only when every letter is Latin: "water is 水 in Chinese" is no
    # text Kokoro's English voice reads.
    if set(_letter_scripts(text)) != {"LATIN"}:
        return None
    return _latin_language(text)


def _app_code(locale: str | None) -> str | None:
    """The language code of the app's locale ("en-US" -> "en"), or None."""
    code = (locale or "").strip().lower().replace("_", "-").split("-", 1)[0]
    return code if len(code) == 2 and code.isalpha() else None


def _uncontested(text: str, language: str) -> bool:
    """``text`` can be ``language``'s: every letter is of its script and, in Latin script, no
    word of another listed language is in it. Plain English such as "Divide both sides by 3."
    names too few listed words to be read as English, yet nothing says it is anything else."""
    if not set(_letter_scripts(text)) <= {script_of_language(language)}:
        return False
    if script_of_language(language) != "LATIN":
        return True
    _words, hits = _latin_hits(text)
    return not set(hits) - {language}


def clip_language(
    text: str, reply_language: str | None, app_language: str | None = None
) -> str | None:
    """The language one clip of a reply is read in.

    ``reply_language`` is what the reply's lead clip played in: None when there is no record
    of it (the lead itself, a reply in one clip, or the record expired), ``UNSURE`` when the
    any-language model played the lead, which keeps the whole reply on it. ``app_language``
    is the app's locale, the phone's ``language``.

    A clip that plainly reads as a language is read in it (a rest clip only when that is its
    reply's language). One whose words are too few to tell follows its reply's language, or
    with no record the app's, when nothing in it says otherwise (``_uncontested``): no word
    of another listed language, no letter of another script. Else it goes, alone, to the
    any-language model.
    """
    if reply_language == UNSURE:
        return None
    own = text_language(text)
    if own is not None:
        return own if reply_language in (None, own) else None
    expected = reply_language or _app_code(app_language)
    if expected and _uncontested(text, expected):
        return expected
    return None
