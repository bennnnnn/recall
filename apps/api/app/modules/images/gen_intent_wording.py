# ruff: noqa: RUF001, RUF003 - Turkish dotless i, Cyrillic and Ethiopic are the words matched
"""A draw-me line that is the thing asked about, not a request for a picture.

"Traduce al inglés: dibújame un gato", "¿Cómo se dice en inglés? Dibújame un gato",
"«Dibújame un cordero»: ¿quién lo dijo?" ask about the words "dibújame un gato": their
translation, their meaning, who said them. English's planner keeps such a line whole and
draws nothing: a quote is never cut, "translate …:" keeps the message one request, and a
first clause that points ("Is this sentence correct?", "How do you say this in Spanish?")
keeps it whole. The other languages often drop the pronoun ("¿Cómo se dice en inglés?",
"Как сказать по-английски?"), so the words that ask about wording are listed as well.

``gen_intent_parts`` draws none of these: a line with a quote mark is no request, a line
with a colon is never cut in two, and a picture is not cut off beside a request that asks
about wording, meaning, spelling, pronunciation, grammar, translation or attribution, or
points at the line ("esta frase", "das", "это"). The lists only ever stop a picture, so a
word too many costs a picture the user asked for, never one they did not.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.images.gen_intent_local import Token

# Any of these makes the line a quotation: «Dibújame un cordero», „Zeichne mir …“, "…".
QUOTE_MARKS = frozenset('"«»‹›„“”‟「」『』〝〞＂')
# A single quote opens a quotation at the start of a word ("'Dibújame un gato': …"); inside
# a word it is an apostrophe ("d'un", "un'immagine", "Fransa'nın").
_SINGLE_QUOTES = ("'", "‘", "’", "‚", "‛")
_BEFORE_QUOTE = "¿¡([{—–-"
# What follows a colon is the content asked about: "Traduce al inglés: …", "ተርጉም፦ …".
COLONS = frozenset(":፥፦：")


def quoted(text: str) -> bool:
    """``text`` quotes something: a quote mark, or a word that opens with a single quote."""
    if not QUOTE_MARKS.isdisjoint(text):
        return True
    return any(chunk.lstrip(_BEFORE_QUOTE).startswith(_SINGLE_QUOTES) for chunk in text.split())


def has_colon(text: str) -> bool:
    """A colon other than one between digits ("10:30", "3:4")."""
    if COLONS.isdisjoint(text):
        return False
    last = len(text) - 1
    return any(
        char in COLONS
        and not (char == ":" and 0 < i < last and text[i - 1].isdigit() and text[i + 1].isdigit())
        for i, char in enumerate(text)
    )


def _w(text: str) -> frozenset[str]:
    return frozenset(text.split())


# A word starting with one of these asks about wording: translate, mean, spell, pronounce,
# grammar and its terms, word, sentence, language, correct, accent, capitals, rhyme, repeat,
# conjugate, tense, the opposite, how it sounds or reads, a quote, and who wrote it or which
# book, film, song or poem it is from. Turkish, Russian "по-" and Amharic language names
# name only the language ("İngilizce", "по-английски"), so they are here too.
_STEMS = tuple(
    """
    translat pronounc spell grammar grammatic meaning synonym antonym rhym quotation
    sentence phrase wording language vocabular conjugat plural singular paraphras rephras
    reword proofread uppercase lowercase
    traduc tradúc signific ortograf gramátic gramatic pronunci deletre sinónim sinonim
    antónim antonim palabra frase oración oracion idioma lengua escrit correc corrig correg
    incorrect acent tilde mayúscul mayuscul minúscul minuscul sílab silab letra rimar repit
    repet conjug sustantiv adjetiv cita pretérit
    tradui signifi orthograph grammai prononc épel epel langue accent majuscul minuscul
    syllab lettre répèt répét pluriel singulier citation imparfait
    übersetz ubersetz uebersetz bedeut rechtschreib grammatik aussprach aussprech
    ausgesproch buchstab satz sätze satze wort wörter sprache richtig korrekt korrigier
    falsch fehler akzent großschreib grossschreib kleinschreib silbe reim wiederhol
    nachsprech konjugier zitat zitier vergangenheit präteritum
    tradu parol lingua corrett corregg sbagliat errore errori maiuscol minuscol sillab
    letter ripet coniug singolare plurale citazion passato
    soletr sinônim antônim palavra língua corret correç corrij errad maiúscul citaç citac
    passado
    перев сказа значит значени означа называ произнос произнош ударени орфограф граммат
    правописан пишется написан слов фраз предложени язык по-англ по-исп по-фран по-нем
    по-итал по-порт по-рус по-тур по-кит по-яп по-араб правильн исправ ошибк ошибок
    синоним антоним рифм повтор спряг спряж глагол существительн прилагательн множествен
    единствен прошедш цитат букв слог говорит
    çevir çeviri tercüme anlam telaffuz okunuş okunur yazıl yazım dilbilgi gramer kelime
    sözcük söz cümle deyim atasöz ingilizce ispanyolca fransızca almanca italyanca
    portekizce rusça türkçe amharca çince japonca arapça latince doğru yanlış düzelt hata
    kafiye uyak tekrarla hece harf fiil sıfat çoğul tekil geçmiş alıntı söylen söyledi
    verbal imperativ subjuntiv indicativ infinitiv gerundi particip impératif subjonctif
    konjunktiv congiuntiv повелительн инфинитив причаст деепричаст sujet subjekt soggett
    sujeit подлежащ özne complement pronom местоимени zamir adverb advérbi avverbi
    preposici préposition präposition preposizion preposiç предлог edat
    contrari contrári contraire gegenteil противополож opposite zıt expres exprim esprim
    ausdruck ausdrück ausgedrückt выраж ifade kulağa читает
    autor auteur author автор yazar book libro livre buch livro книг kitap kitab película
    pelicula film movie canción cancion chanson lied canzone canção cancao песн şarkı song
    poem poème poesía poesia poet poète dichter gedicht стих поэт şiir şair escribió
    escribio написал yazdı yazmış yazıyor
    """.split()
)
# Whole words: forms of "say", "written", "word", "error".
_WORDS = _w(
    """
    say said says mean means meant written quote quoted correct incorrect wrong repeat word
    words verb verbs noun nouns tense error errors mistake mistakes
    dice dicen decir dijo dijiste dicho diría digo pasado verbo verbos rima rimas error
    errores
    dit dit-on dire disait dirait écrit ecrit écrite ecrite mot mots sens passé passe rime
    rimes verbe verbes erreur erreurs
    sagt sagen gesagt heißt heisst schreibt geschrieben spricht verb verben stammt
    dicono detto disse dici scrive scritto scritta rime
    dizer dito diz-se escreve-se escreveu escrito escrita erro erros
    верно
    denir deniyor demek dil dili dilde dilinde diline dilin
    wrote suena suenan suona suonano sonne sonnent klingt звучит soa soam tono tone тон
    """
)
# A language's name after "in", "into", "to": "en inglés", "ins Englische", "на английский".
# Alone it is often a people's or a country's adjective: "la Revolución Francesa",
# "deutsche Geschichte", "a French recipe".
_LANGUAGE_STEMS = tuple(
    """
    english spanish french italian portuguese russian turkish amharic chinese japanese
    arabic latin
    inglés ingles español espanol castellan francés frances italian portugués portugues
    portuguê amáric amaric japonés japones árabe arabe latín
    anglais espagnol français francais allemand italien portugais chinois japonais amhariq
    englisch spanisch französisch franzosisch franzoesisch italienisch portugiesisch
    russisch türkisch turkisch amharisch chinesisch japanisch arabisch latein
    spagnol tedesc portoghes giappones arabo
    inglês espanhol francês chinês latim
    английск испанск французск немецк итальянск португальск русск турецк амхарск китайск
    японск арабск латин
    """.split()
)
_LANGUAGE_WORDS = _w(
    """
    german alemán aleman chino ruso turco russe turc deutsch deutsche deutschen cinese russo
    alemão alemao
    """
)
_INTO = _w(
    """
    in into to from en al a del de el auf ins aus im vom em para pro do da o l' le lo il
    dal dall' all' allo nel nell' на с со из в по
    """
)
# Two words: "se dice", "quer dizer", "sagt man".
_PAIRS = frozenset(
    {
        ("se", "escribe"),
        ("se", "dice"),
        ("se", "diz"),
        ("se", "escreve"),
        ("si", "dice"),
        ("si", "scrive"),
        ("on", "dit"),
        ("quer", "dizer"),
        ("sagt", "man"),
        ("se", "lee"),
        ("se", "lit"),
        ("si", "legge"),
        ("se", "lê"),
        ("liest", "man"),
    }
)
# Amharic joins "in", "of", "to" to the word ("በእንግሊዝኛ"), so these are found inside it.
_AMHARIC = (
    "ርጉም ይባላል ማለት ቃል ቃላት ዓረፍተ አረፍተ ሰዋሰው ፊደል አጻጻፍ አፃፃፍ ተጽፏ ተፅፏ ተጻፈ ተፃፈ "
    "አነባበብ አጠራር ይነበባል ቋንቋ እንግሊዝኛ ስፓኒሽ ፈረንሳይኛ ጀርመንኛ ጣሊያንኛ ፖርቱጋልኛ "
    "ሩሲያኛ ቱርክኛ አማርኛ ቻይንኛ ዓረብኛ አረብኛ ትክክል ስህተት ተሳሳ ጥቅስ ተናገ ድገም ድገሚ "
    "ይጻፋል ይፃፋል ጻፈ ፃፈ ይላል ደራሲ መጽሐፍ መፅሐፍ ፊልም ዘፈን ግጥም"
).split()
# Words that point at the line or at something earlier: "esta frase", "eso", "это".
POINTERS = _w(
    """
    this that these those it
    esto eso esta este estas estos esa ese esas esos aquello aquella aquel así asi ello
    ça ca cela ceci cette cet ces ainsi
    dies dieser diese dieses diesen diesem folgendes folgende folgenden
    questo questa questi queste quello quella quelli ciò cio così cosi
    isso isto aquilo essa esse essas esses nesta neste nessa nesse desta deste dessa desse
    assim
    это этого этом этому эту этот эта эти этих этой следующее
    bu şu bunu şunu bunun şunun buna şuna bunlar şunlar böyle şöyle
    ይህ ይሄ ይህን ይሄን ይህንን ያ ያንን እንደዚህ በዚህ የዚህ
    here there aquí aqui ahí allí alli ici là qua lì aí здесь тут там burada şurada orada
    እዚህ እዚያ
    """
)
# German "da", "hier", "dort" point too; in French "hier" is "yesterday", "dort" "sleeps".
_GERMAN_POINTERS = _w("da hier dort")
_ETHIOPIC = ("ሀ", "፿")
_ENDS = tuple(".!?,;:…")


def _german_das(text: str, tokens: Sequence[Token], i: int) -> bool:
    """German "das" points ("Wie sagt man das?") unless a capitalised noun follows it
    ("das Subjekt"): the article."""
    raw = text[tokens[i].start : tokens[i].end]
    if raw.endswith(_ENDS) or i + 1 >= len(tokens):
        return True
    return not text[tokens[i + 1].start : tokens[i + 1].end][:1].isupper()


def about_wording(text: str, tokens: Sequence[Token], lang: str) -> bool:
    """``tokens`` (a request of ``text``) ask about wording or point at the line: "Traduce
    al inglés", "¿Cómo se dice?", "Ist dieser Satz richtig?", "Что значит эта фраза?".
    ``lang`` is the picture's language ("das" is German's pointer, Portuguese "of the")."""
    words = [token.word.replace("̇", "") for token in tokens]
    for i, word in enumerate(words):
        if word in _WORDS or word in POINTERS or word.startswith(_STEMS):
            return True
        named = word in _LANGUAGE_WORDS or word.startswith(_LANGUAGE_STEMS)
        if named and i > 0 and words[i - 1] in _INTO:
            return True
        if tuple(words[i : i + 2]) in _PAIRS:
            return True
        if _ETHIOPIC[0] <= word[:1] <= _ETHIOPIC[1] and any(piece in word for piece in _AMHARIC):
            return True
        if lang == "de" and (
            word in _GERMAN_POINTERS or (word == "das" and _german_das(text, tokens, i))
        ):
            return True
    return False
