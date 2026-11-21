# ruff: noqa: RUF001 - Turkish dotless i and Cyrillic are the words matched
"""Picture requests in the app's other languages: the few shapes ``gen_intent_local`` reads.

Only two unmistakable shapes draw in Spanish, French, Portuguese, Russian, Turkish, Amharic
and Hindi:

- "draw me": a draw verb addressed to the assistant with "me" ("dibújame", "¿me
  dibujas …?", "dessine-moi", "me desenhe", "нарисуй мне", "bana … çiz", "… ሳልልኝ",
  "मेरे लिए … ड्रा करो", "मेरे लिए … का चित्र बनाओ");
- "create a picture of": create or generate, a picture noun, then "of" ("crea una
  imagen de", "… resmi oluştur", "создай картинку …", "… की तस्वीर बनाओ").

Everything else ("Dibuja un gato", "बिल्ली बनाओ", "फूल का चित्र बनाइए") is answered in
words, as on main.

A shape is written as slots: "a|b ?c d" is "a" or "b", then an optional "c", then "d";
"_" joins the words of one choice ("peux_tu").
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product


def _w(words: str) -> frozenset[str]:
    return frozenset(words.split())


def _phrases(words: str) -> tuple[tuple[str, ...], ...]:
    """ "por_favor porfa": one phrase per word, "_" joining its words."""
    return tuple(tuple(phrase.split("_")) for phrase in words.split())


def _expand(pattern: str) -> frozenset[tuple[str, ...]]:
    """Every word sequence ``pattern`` writes ("me puedes|podrías dibujar")."""
    slots: list[list[tuple[str, ...]]] = []
    for slot in pattern.split():
        choices = [tuple(choice.split("_")) for choice in slot.lstrip("?").split("|")]
        slots.append([*choices, ()] if slot.startswith("?") else choices)
    return frozenset(tuple(word for part in seq for word in part) for seq in product(*slots))


@dataclass(frozen=True)
class Shape:
    """A request: one of ``leads``, the subject, then one of ``tails`` (``()`` is none)."""

    leads: frozenset[tuple[str, ...]]
    tails: frozenset[tuple[str, ...]]
    # Amharic "የድመት ምስል ፍጠር": "of" is the subject's first letter.
    of_prefix: str = ""
    # Their lengths, longest first: a set lookup per length, not a scan of every phrase.
    lead_sizes: tuple[int, ...] = ()
    tail_sizes: tuple[int, ...] = ()
    # The subject must name a new thing with one of these: Hindi has no article, so a bare
    # "फूल का चित्र बनाइए" is the textbook's figure of the flower, and "एक फूल" a new one.
    new_thing: frozenset[str] = frozenset()


def _shape(lead: str = "", tail: str = "", of_prefix: str = "", new_thing: str = "") -> Shape:
    leads = _expand(lead) if lead else frozenset({()})
    tails = _expand(tail) if tail else frozenset({()})
    lead_sizes, tail_sizes = (
        tuple(sorted({len(seq) for seq in seqs}, reverse=True)) for seqs in (leads, tails)
    )
    return Shape(leads, tails, of_prefix, lead_sizes, tail_sizes, _w(new_thing))


@dataclass(frozen=True)
class Language:
    code: str
    shapes: tuple[Shape, ...]
    polite: tuple[tuple[str, ...], ...] = ()
    # Said between the lead and the subject: "dibújame por favor …".
    fillers: frozenset[str] = frozenset()
    # A subject that points back ("eso", "das"): only the chat could name it.
    pronouns: frozenset[str] = frozenset()
    # A definite subject ("la pirámide alimenticia", "l'anatomie de l'œil") is a school
    # figure or a known thing far more often than a picture to invent: "un dragón" draws.
    definite: frozenset[str] = frozenset()
    # Turkish marks a definite object by its ending ("sistemini", "kediyi"): "bir kedi".
    definite_endings: tuple[str, ...] = ()
    again: tuple[tuple[str, ...], ...] = ()


# Spanish.
_ES_ME = "dibújame|dibujame|dibújeme|dibujeme|píntame|pintame"
_ES_YOU = "dibujas|dibujarías|dibujarias|pintas"
_ES_CAN = "puedes|podrías|podrias|puede|podría|podria|podés"
_ES_TO_ME = "dibujarme|pintarme"
_ES_TO = "dibujar|pintar"
_ES_CREATE = "crea|genera|haz|cree|genere|haga|créame|creame|genérame|generame|hazme|hágame|hagame"
_ES_TO_CREATE = "crear|generar|hacer|crearme|generarme|hacerme"
_ES_PICTURE = "?una|un imagen|ilustración|ilustracion|dibujo de"

SPANISH = Language(
    "es",
    shapes=(
        _shape(_ES_ME),
        _shape(f"me {_ES_YOU}"),
        _shape(f"?me {_ES_CAN} {_ES_TO_ME}"),
        _shape(f"me {_ES_CAN} {_ES_TO}"),
        _shape(f"{_ES_CREATE} {_ES_PICTURE}"),
        _shape(f"?me {_ES_CAN} {_ES_TO_CREATE} {_ES_PICTURE}"),
    ),
    polite=_phrases("por_favor porfa porfavor"),
    pronouns=_w("eso esto ello aquello ese esa este esta estos estas esos esas mí lo"),
    definite=_w("el la los las le al del"),
    again=_phrases("otra_vez de_nuevo nuevamente"),
)

# French: "dessine-moi" is "dessine" then "moi" (gen_intent_local splits the clitic).
_FR_DRAW = "dessine|dessinez|peins|peignez"
_FR_YOU = "dessines|dessinerais|dessinez|dessineriez|peins"
_FR_CAN = (
    "peux_tu|pouvez_vous|pourrais_tu|pourriez_vous|tu_peux|vous_pouvez|tu_pourrais|vous_pourriez"
)
_FR_CREATE = "crée|créez|cree|creez|génère|générez|genere|generez"
_FR_TO_CREATE = "créer|creer|générer|generer"
_FR_PICTURE = "une|un image|illustration|dessin de|d'"

FRENCH = Language(
    "fr",
    shapes=(
        _shape(f"{_FR_DRAW} moi"),
        _shape(f"tu|vous me {_FR_YOU}"),
        _shape(f"{_FR_CAN} me dessiner|peindre"),
        _shape(f"{_FR_CREATE} ?moi {_FR_PICTURE}"),
        _shape(f"{_FR_CAN} ?me {_FR_TO_CREATE} {_FR_PICTURE}"),
    ),
    polite=_phrases("s'_il_te_plaît s'_il_te_plait s'_il_vous_plaît s'_il_vous_plait stp svp"),
    pronouns=_w("ça ca cela ceci ce cet cette ces moi"),
    definite=_w("le la les l' du des au aux"),
    again=_phrases("encore à_nouveau a_nouveau de_nouveau"),
)

# Portuguese: "desenha-me" is "desenha" then "me".
_PT_DRAW = "desenha|desenhe|desenhas"
_PT_CAN = (
    "pode|podes|poderia|consegue|você_pode|voce_pode|você_poderia|voce_poderia|"
    "você_consegue|voce_consegue|tu_podes"
)
_PT_CREATE = "crie|cria|gere|gera"
_PT_PICTURE = "uma|um imagem|ilustração|ilustracao|desenho de"

PORTUGUESE = Language(
    "pt",
    shapes=(
        _shape(f"{_PT_DRAW} me"),
        _shape(f"?você|voce|tu me {_PT_DRAW}"),
        _shape(f"{_PT_CAN} me desenhar"),
        _shape(f"{_PT_CAN} desenhar me"),
        _shape(f"{_PT_CREATE} ?me {_PT_PICTURE}"),
        _shape(f"{_PT_CAN} ?me criar|gerar {_PT_PICTURE}"),
    ),
    polite=_phrases("por_favor pfv"),
    pronouns=_w("isso isto aquilo este esta esse essa aquele aquela estes estas esses essas mim"),
    definite=_w("o a os as do da dos das ao"),
    again=_phrases("de_novo outra_vez novamente"),
)

# Russian: "создай картинку льва" names the subject without an "of".
_RU_DRAW = "нарисуй|нарисуйте|нарисуешь|нарисуете"
_RU_CAN = "можешь|можете|ты_можешь|вы_можете"
_RU_CREATE = "создай|создайте|сгенерируй|сгенерируйте"
_RU_PICTURE = "изображение|картинку|рисунок|иллюстрацию"

RUSSIAN = Language(
    "ru",
    shapes=(
        _shape(f"{_RU_DRAW} мне|нам"),
        _shape(f"{_RU_CAN} нарисовать мне|нам"),
        _shape(f"{_RU_CAN} мне|нам нарисовать"),
        _shape(f"{_RU_CREATE} ?мне|нам {_RU_PICTURE}"),
        _shape(f"{_RU_CAN} ?мне|нам создать|сгенерировать {_RU_PICTURE}"),
    ),
    polite=_phrases("пожалуйста плиз пж"),
    pronouns=_w("это этого эту этот эти его её ее их то того тот ту меня"),
    again=_phrases("ещё_раз еще_раз снова опять заново"),
)

# Turkish closes with its verb: "Bana bir kedi çiz", "Bir aslan resmi oluştur".
_TR_DRAW = (
    "çiz|çizin|çizsene|çizer_misin|çizer_misiniz|çizebilir_misin|çizebilir_misiniz|"
    "çizermisin|çizebilirmisin"
)
_TR_CREATE = (
    "oluştur|oluşturun|oluştursana|üret|üretin|oluşturur_musun|oluşturabilir_misin|"
    "üretir_misin|üretebilir_misin"
)

TURKISH = Language(
    "tr",
    shapes=(
        _shape("bana|bize", _TR_DRAW),
        _shape("?bana|bize", f"resmi|resmini|görseli|görselini {_TR_CREATE}"),
    ),
    polite=_phrases("lütfen lutfen"),
    pronouns=_w("bunu onu şunu bunları onları şunları bu şu o"),
    definite_endings=("nı", "ni", "nu", "nü", "yı", "yi", "yu", "yü"),
    again=_phrases("tekrar yine yeniden"),
)

# Amharic: "ድመት ሳልልኝ" (draw me a cat); bare "ሳል" is also "a cough" and draws nothing.
_AM_DRAW = "ሳልልኝ|ሣልልኝ|ሳይልኝ|ሣይልኝ|ሳሉልኝ|ሣሉልኝ"
_AM_CREATE = "ፍጠርልኝ|ፍጠሪልኝ|ፍጠሩልኝ|ፍጠር|ፍጠሪ|ፍጠሩ"
_AM_PICTURE = "ምስል|ስዕል|ሥዕል|ስእል"

AMHARIC = Language(
    "am",
    shapes=(
        _shape(tail=f"{_AM_PICTURE} {_AM_DRAW}", of_prefix="የ"),
        _shape(tail=f"{_AM_PICTURE} {_AM_CREATE}", of_prefix="የ"),
        _shape(tail=_AM_DRAW),
    ),
    polite=_phrases("እባክህ እባክሽ እባካችሁ እባክዎ እባክዎን"),
    pronouns=_w("ይህን ይሄን ያንን እሱን እሷን እነሱን"),
    again=_phrases("እንደገና"),
)

# Hindi has no article, and "चित्र बनाइए" (draw the figure) is how a textbook asks for a
# diagram, as "Dibuja" is in Spanish. So, as there, only the unmistakable shapes draw:
# - addressed, "for me": "मेरे लिए एक काली बिल्ली ड्रा करो", "मेरे लिए शेर का चित्र बना दो";
# - "create an image of", a picture noun no textbook asks for: "ड्रैगन की तस्वीर बनाइए",
#   "पहाड़ों की पेंटिंग बनाइए";
# - the figure noun or the draw verb with a new thing, "एक": "एक बिल्ली का चित्र बनाओ".
# A bare "फूल का चित्र बनाइए" or "बिल्ली ड्रा करो" is answered in words. "बनाओ" without a
# picture word draws nothing: it also cooks ("मेरे लिए चाय बनाओ"), builds and makes plans.
_HI_MAKE = (
    "बनाओ|बनाइए|बनाइये|बनाएँ|बनाएं|बना_दो|बना_दीजिए|बना_दीजिये|बना_दें|बना_देना|बनाकर_दो|बनाकर_दिखाओ"
)
_HI_DRAW = "ड्रा_करो|ड्रा_कीजिए|ड्रा_कीजिये|ड्रा_करें|ड्रा_कर_दो|स्केच_करो|स्केच_कीजिए"
_HI_IMAGE = "तस्वीर|तसवीर|इमेज|छवि|पेंटिंग"
_HI_FIGURE = "चित्र|ड्राइंग"
_HI_FOR_ME = "मेरे_लिए|मेरे_लिये|हमारे_लिए|मुझे"
_HI_OF = "का|की|के"

HINDI = Language(
    "hi",
    shapes=(
        _shape(_HI_FOR_ME, f"{_HI_OF} {_HI_IMAGE}|{_HI_FIGURE} {_HI_MAKE}|{_HI_DRAW}"),
        _shape(_HI_FOR_ME, _HI_DRAW),
        _shape(tail=f"{_HI_OF} {_HI_IMAGE} {_HI_MAKE}|{_HI_DRAW}"),
        _shape(tail=f"{_HI_OF} {_HI_FIGURE} {_HI_MAKE}|{_HI_DRAW}", new_thing="एक"),
        _shape(tail=_HI_DRAW, new_thing="एक"),
    ),
    polite=_phrases("कृपया प्लीज़ प्लीज जरा ज़रा"),
    pronouns=_w("इसे उसे इन्हें उन्हें यह वह ये वो इसको उसको इसका उसका"),
    again=_phrases("फिर_से दोबारा एक_बार_फिर फिर"),
)

LANGUAGES: tuple[Language, ...] = (
    SPANISH,
    FRENCH,
    PORTUGUESE,
    RUSSIAN,
    TURKISH,
    AMHARIC,
    HINDI,
)

# Dropped before the subject ("dibújame un gato" draws "gato").
ARTICLES = _w("un una une um uma bir एक")

# "Dibújame también un gato", "मेरे लिए भी …": "also" after the lead.
ALSO = _w(
    "also también además aussi également também tambem além disso ayrıca также тоже ещё еще "
    "እንዲሁም ደግሞ ደግሞም भी"
)
