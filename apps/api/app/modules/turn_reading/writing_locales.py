# ruff: noqa: RUF001, RUF002, RUF003 - Turkish ı and Cyrillic letters are the words matched
"""Draft requests and draft changes in the app's seven other languages.

English has its own patterns in ``writing_kind`` and ``writing``. Here a draft
request is a writing verb and a draft noun: the verb first in Spanish, French,
Portuguese and Russian ("escribe un correo a mi jefe…"), last in Turkish, Amharic
and Hindi ("patronuma bir e-posta yaz", "ለአለቃዬ ኢሜይል ጻፍልኝ", "मेरे बॉस को एक ईमेल
लिखो"). A change to the draft before ("más corto", "en inglés", "daha kısa yap",
"और छोटा करो") is one of a short list of edits. Language names stay in every language
the user may say them in ("en alemán"), whether or not the app offers it.
"""

from __future__ import annotations

import re

from app.core.validation import unify_devanagari
from app.services.text_normalize import collapse_ws

_POLITE_WORD = (
    r"(?:por favor|s'il (?:te|vous) pla[iî]t|stp|пожалуйста|lütfen|"
    r"እባክ(?:ህ|ሽ|ዎ)|कृपया|प्लीज़?)"
)
_POLITE = rf"(?:{_POLITE_WORD}[,\s]+)?"

# Verbs that write or send, opening a request; "can you write"; "help me write".
_VERB_FIRST = (
    r"(?:"
    # Spanish
    r"escr[ií]b(?:e|eme|ele|eles)|red[aá]ct(?:a|ame)|m[aá]nd(?:a|ame|ale)|env[ií](?:a|ame|ale)|"
    r"(?:me )?(?:puedes|podr[ií]as) (?:escribir|redactar|mandar|enviar)|"
    r"ay[uú]dame a (?:escribir|redactar)|"
    # French
    r"[ée]cris(?:-moi|-lui|-leur)?|r[ée]dige(?:-moi|-lui)?|envoie(?:-moi|-lui)?|"
    r"(?:peux-tu|tu peux|pourrais-tu|pouvez-vous) (?:m'|lui )?(?:[ée]crire|r[ée]diger|envoyer)|"
    r"aide-moi [àa] (?:[ée]crire|r[ée]diger)|"
    # Portuguese
    r"escrev(?:e|a)(?:-me)?|redija|mand(?:a|e)|envi(?:a|e)|"
    r"(?:voc[eê] )?(?:pode|podes) (?:escrever|redigir|mandar|enviar)|"
    r"(?:me ajuda|ajuda-me) a escrever|"
    # Russian
    r"напиши(?:те)?(?: мне)?|составь(?:те)?|отправь(?:те)?|(?:можешь|можете|помоги) написать"
    r")"
)
# Turkish and Amharic close the request with the verb.
_VERB_LAST = (
    r"(?:"
    r"yaz(?:ar m[ıi]s[ıi]n|abilir misin|[ıi]n|sana)?|haz[ıi]rla(?:r m[ıi]s[ıi]n)?|g[öo]nder|"
    r"[ጻፃ][ፍፊፉ](?:ልኝ)?|አዘጋጅ(?:ልኝ)?|አዘጋጂ(?:ልኝ)?"
    r")"
)

# Draft nouns, by the fence they become. "Texto" is a text of any kind in
# Spanish and Portuguese, so only French counts it as a message. Turkish and
# Amharic nouns take only the object ending: "e-postanın özetini yaz" is a summary.
_NOUNS = {
    "email": (
        r"(?:correo(?: electr[oó]nico)?|e-?mail|mail|courriel|письмо|имейл|мейл|"
        r"e-?posta(?:y[ıi]|lar[ıi]?)?|ኢ-?ሜይ?ል(?:ሉን|ን)?|ደብዳቤ(?:ውን|ን)?|ईमेल|ई-मेल|मेल)"
    ),
    "message": (
        r"(?:mensaje(?: de texto)?|message|sms|whatsapp|texto|"
        r"mensagem|сообщение|смс|mesaj(?:[ıi]|lar[ıi]?)?|መል[እዕ]ክት(?:ቱን|ን)?|मैसेज|मेसेज|संदेश)"
    ),
    "social": (
        r"(?:publicaci[oó]n|publication|publica[çc][ãa]o|post|tuit|"
        r"tweet|pie de foto|l[ée]gende|legenda|пост|твит|"
        r"g[öo]nderi(?:yi|si)?|payla[şs][ıi]m(?:[ıi])?|ፖስት(?:ን)?|पोस्ट|ट्वीट|कैप्शन|"
        r"linkedin|instagram|facebook|tiktok)"
    ),
}
_SPANISH_PORTUGUESE_TEXT = re.compile(r"^(?:escr[ií]b|red[aá]ct|m[aá]nd|env[ií]|escrev|redij)")

_ANY_NOUN = "|".join(f"(?P<{kind}>{noun})" for kind, noun in _NOUNS.items())
_ARTICLE = r"(?:(?:un|una|uno|une|um|uma)\s+|un')?"
# Up to three words between the verb and the noun (a recipient: "escribe a mi casero
# un mensaje"), never "of": "escribe un resumen de este correo".
_GAP = r"(?:\s+(?!(?:de|del|du|des|do|da|о|об|про)\b)\S+){0,3}?"
_VERB_THEN_NOUN = re.compile(rf"^{_POLITE}{_VERB_FIRST}\b{_GAP}\s+{_ARTICLE}(?:{_ANY_NOUN})(?!\w)")
_NOUN_THEN_VERB = re.compile(
    rf"(?:^|\s)(?:{_ANY_NOUN})(?:\s+\S+){{0,2}}?\s+{_VERB_LAST}(?:\s+{_POLITE_WORD})?"
    r"[\s.!?።]*$"
)
# Hindi closes on its verb too ("मेरे बॉस को एक ईमेल लिखो"), and its "of" (का, की, के) or "in"
# between them makes the noun something else's: "इस ईमेल का सारांश लिखो" is a summary.
_HI_WRITE = (
    r"(?:लिखो|लिखिए|लिखिये|लिखें|लिख\s+दो|लिख\s+दें|लिख\s+दीजिए|लिखकर\s+दो|तैयार\s+करो|"
    r"तैयार\s+कीजिए|ड्राफ़्ट\s+करो|भेजो)"
)
_HI_NOT_BETWEEN = r"(?:का|की|के|में|पर|से|को)(?!\S)"
_HINDI_REQUEST = re.compile(
    rf"(?:^|\s)(?:{_ANY_NOUN})(?!\S)(?:\s+(?!{_HI_NOT_BETWEEN})\S+){{0,2}}?\s+{_HI_WRITE}"
    # What it says may follow the verb: "… ईमेल लिखो कि मैं कल नहीं आऊँगा".
    r"(?=[\s.!?।]*$|\s+(?:कि|जिसमें|जिसमे|जो)\s)"
)
# A request with nothing past the verb, the noun and a short recipient
# ("escribe un correo a mi jefe", "напиши письмо начальнику") asks what to say.
_BARE_EXTRA_WORDS = 3


# Hindi's article and postpositions around a recipient: "मेरे बॉस के लिए एक ईमेल लिखो" names
# only the boss.
_BARE_FILLERS = frozenset({"एक", "को", "के", "लिए"})


def _folded(text: str) -> str:
    # Turkish İ lowercases to i and a combining dot; the dot breaks "ingilizce".
    folded = collapse_ws(unify_devanagari(text)).lower().replace("\u0307", "")
    return folded.lstrip("¿¡")


def _draft_match(text: str) -> re.Match[str] | None:
    folded = _folded(text)
    for pattern in (_VERB_THEN_NOUN, _NOUN_THEN_VERB, _HINDI_REQUEST):
        match = pattern.search(folded)
        if match is not None:
            return match
    return None


def locale_draft_kind(text: str) -> str | None:
    """ "email", "message" or "social" for a draft request in a non-English locale."""
    match = _draft_match(text)
    if match is None:
        return None
    if match.group("message") == "texto":
        start = _folded(text).removeprefix("por favor").lstrip(" ,")
        if _SPANISH_PORTUGUESE_TEXT.match(start):
            return None
    return next(kind for kind in _NOUNS if match.group(kind))


def is_bare_locale_draft(text: str) -> bool:
    """True when the request names the draft and a recipient but not what it says."""
    match = _draft_match(text)
    if match is None:
        return False
    folded = _folded(text)
    rest = f"{folded[: match.start()]} {folded[match.end() :]}"
    words = [word for word in rest.strip(" .!?¿¡,።।").split() if word not in _BARE_FILLERS]
    return len(words) <= _BARE_EXTRA_WORDS


# Short edits to the draft before: shorter, longer, a tone, a language, add or remove.
_LANGUAGES = (
    r"(?:ingl[eéê]s|espa[ñn]ol|franc[eéê]s|alem[aá]n|italiano|portugu[eéê]s|ruso|turco|"
    r"am[aá]rico|"
    r"anglais|espagnol|allemand|italien|portugais|russe|turc|amharique|"
    r"englisch|spanisch|franz[öo]sisch|italienisch|portugiesisch|russisch|t[üu]rkisch|amharisch|"
    r"deutsch|inglese|spagnolo|francese|tedesco|portoghese|russo|amarico|espanhol|alem[ãa]o|"
    r"английск\w*|испанск\w*|французск\w*|немецк\w*|итальянск\w*|турецк\w*|амхарск\w*|русск\w*)"
)
_TONES = (
    r"(?:cort[oa]|breve|larg[oa]|formal|informal|amable|educad[oa]|cordial|seri[oa]|sencill[oa]|"
    r"simple|c[aá]lid[oa]|profesional|casual|direct[oa]|"
    r"court(?:e)?|long(?:ue)?|formel(?:le)?|poli(?:e)?|amical(?:e)?|chaleureu(?:x|se)|"
    r"professionnel(?:le)?|d[ée]contract[ée]|bref|br[eè]ve|"
    r"curt[oa]|long[oa]|gentil|simples|profissional|calorosa?)"
)
# "Ok", "now", "perfect," and "can you (make it)" before the edit.
_CHANGE_LEAD = (
    r"(?:(?:ahora|ok|vale|bien|perfecto|gracias|maintenant|parfait|merci|d'accord|"
    r"agora|perfeito|obrigad[oa]|теперь|хорошо|спасибо|şimdi|tamam|"
    r"teşekkürler|አሁን|अब|ठीक है|बढ़िया|धन्यवाद|और|y|et|e|и)[,!.]?\s+)*"
    + _POLITE
    + r"(?:(?:me )?(?:puedes|podr[ií]as)\s+|"
    r"(?:peux-tu|tu peux|pourrais-tu|pouvez-vous)\s+(?:le |la )?(?:rendre\s+|faire\s+)?|"
    r"(?:इसे|इसको)\s+|"
    r"(?:voc[eê] )?(?:pode|podes)\s+(?:deixar\s+|fazer\s+)?|"
    r"(?:можешь|можете)\s+(?:сделать\s+)?)?"
)
_LOCALE_DRAFT_CHANGE = re.compile(
    r"^" + _CHANGE_LEAD + r"(?:"
    # Spanish
    r"(?:hazlo|hacerlo|ponlo|ponerlo|d[ée]jalo|dejarlo|escr[ií]belo|reescr[ií]belo|"
    r"red[aá]ctalo)\b|"
    r"(?:un poco |mucho )?(?:m[aá]s|menos) " + _TONES + r"\b|"
    r"(?:ac[oó]rtalo|acortarlo|al[aá]rgalo|res[uú]melo|trad[uú]celo|trad[uú]cela|traducirlo)\b|"
    r"(?:a[ñn]ade|agrega|quita|elimina|cambia|pon|incluye|menciona|dile|saca|borra)\b|"
    r"otra (?:versi[oó]n|opci[oó]n)|"
    # French
    r"(?:un peu )?(?:plus|moins) " + _TONES + r"\b|"
    r"(?:raccourcis|rallonge|simplifie|reformule|r[ée][ée]cris|refais|tradui[st])"
    r"(?:-le|-la)?\b|"
    r"(?:ajoute|enl[eè]ve|retire|supprime|change|mets|pr[ée]cise|mentionne)\b|"
    r"une autre version|"
    # Portuguese
    r"(?:um pouco |bem )?mais " + _TONES + r"\b|"
    r"(?:encurt[ae]|resum[ae]|reescrev[ae]|refa[zç]a?|simplifi(?:ca|que))(?:-o|-a)?\b|"
    r"traduz(?:a|ir)?(?:-o|-a)?\b|"
    r"(?:adicion[ae]|acrescent[ae]|tir[ae]|remov[ae]|mud[ae]|coloc[ae]|p[õo]e|ponha|"
    r"inclu[ia]|mencion[ae])\b|outra vers[ãa]o|"
    # In another language: "en inglés", "em inglês", "на английском".
    r"(?:en|em|на) " + _LANGUAGES + r"\b|"
    # Russian
    r"(?:сделай|напиши|перепиши)(?: (?:его|её|ее|это))? (?:покороче|короче|подлиннее|длиннее|"
    r"формальнее|официальнее|вежливее|дружелюбнее|проще|теплее|мягче)\b|"
    r"(?:покороче|короче|подлиннее|длиннее|формальнее|официальнее|вежливее|дружелюбнее|"
    r"проще|теплее|мягче|перепиши|сократи|переведи)\b|"
    r"(?:добавь|убери|удали|измени|поменяй|допиши)\b|(?:другой|ещё один|еще один) вариант|"
    # Turkish
    r"(?:biraz )?daha (?:k[ıi]sa|uzun|resmi|samimi|kibar|nazik|sade|basit|profesyonel|"
    r"s[ıi]cak)\b|"
    r"(?:k[ıi]salt|uzat|sadele[şs]tir|yeniden yaz|tekrar yaz|[çc]evir)\w*|"
    r"(?:ingilizce|ispanyolca|frans[ıi]zca|almanca|italyanca|portekizce|rus[çc]a|t[üu]rk[çc]e|"
    r"amharca)(?:'?y[ae])?\b|"
    r"ba[şs]ka bir (?:versiyon|s[üu]r[üu]m)|"
    # Amharic
    r"አሳጥረው|አሳጥሪው|አጠር አድ\w*|ረዘም አድ\w*|ተርጉ\w*|በእንግሊዝኛ|በአማርኛ|ወደ \S+ ተርጉ\w*|"
    r"ጨምር\w*|ጨምሪ\w*|ቀይረው|ቀይሪው|አስተካክለው|አስተካክይው|"
    # Hindi: "और छोटा करो", "थोड़ा औपचारिक बना दो", "अंग्रेज़ी में लिखो", "अनुवाद करो". Its vowel
    # signs are no ``\w``, so a word ends at a space or a stop, not at ``\b``.
    r"(?:(?:थोड़ा|थोड़ी|और|ज़्यादा|बहुत)\s+)*(?:छोटा|छोटी|लंबा|लंबी|औपचारिक|अनौपचारिक|विनम्र|"
    r"सरल|आसान|दोस्ताना|पेशेवर|प्रोफ़ेशनल|सीधा|गर्मजोशी\s+भरा)\s+"
    r"(?:करो|कर\s+दो|कीजिए|करें|बनाओ|बना\s+दो|बनाइए)(?![^\s.!?।,])|"
    r"(?:अंग्रेज़ी|अंग्रेजी|हिंदी|हिन्दी|स्पेनिश|फ्रेंच|फ़्रेंच|जर्मन|रूसी|पुर्तगाली)\s+में"
    r"(?:\s+(?:लिखो|लिखिए|लिख\s+दो|करो|कर\s+दो|अनुवाद\s+करो))?(?![^\s.!?।,])|"
    r"(?:इसका\s+)?अनुवाद\s+(?:करो|कीजिए|कर\s+दो)(?![^\s.!?।,])|"
    r"(?:दोबारा|फिर\s+से)\s+लिखो(?![^\s.!?।,])|दूसरा\s+(?:वर्ज़न|विकल्प)(?![^\s.!?।,])"
    r")"
)
# Turkish and Amharic end on the edit: "pazartesi döneceğimi de ekle", "ስሜን ጨምርበት".
_VERB_FINAL_CHANGE = re.compile(
    r"(?:^|\s)(?:(?:ekle|[çc][ıi]kar|sil|de[ğg]i[şs]tir|k[ıi]salt|uzat|[çc]evir|yeniden yaz)"
    r"(?:ir misin|[ıi]r m[ıi]s[ıi]n|abilir misin|[ıi]n)?"
    r"|(?:ጨምር|ጨምሪ|አሳጥር|አሳጥሪ|ቀይር|ቀይሪ|አስተካክል|አስተካክይ|ተርጉም|ተርጉሚ)\w*"
    # Hindi: "कि मैं सोमवार को लौटूँगा, यह भी जोड़ो", "आख़िरी लाइन हटा दो".
    r"|(?:जोड़ो|जोड़ें|जोड़िए|जोड़\s+दो|जोड़\s+दें|हटाओ|हटाएं|हटाइए|हटा\s+दो|बदलो|बदलें|बदलिए|"
    r"बदल\s+दो))"
    r"[\s.!?።।]*$"
)
# "¿Qué es más largo, el Nilo o el Amazonas?" is a question, not an edit.
_QUESTION_LEAD = re.compile(
    r"^[¿¡]?(?:qu[ée]|cu[aá]l|c[oó]mo|por qu[ée]|quoi|qu'est|quel(?:le)?|comment|pourquoi|"
    r"qual|o que|por que|"
    r"что|как|почему|какой|ne|nas[ıi]l|neden|hangi|ምን|እንዴት|ለምን)\b"
    r"|^(?:क्या|कैसे|क्यों|कौन\S*)(?!\S)"
)
_CHANGE_MAX_WORDS = 10


def is_locale_draft_change(text: str) -> bool:
    """True for a short edit to the draft before, in a non-English locale."""
    folded = _folded(text)
    if not folded or len(folded.split()) > _CHANGE_MAX_WORDS:
        return False
    if "?" in folded and _QUESTION_LEAD.match(folded):
        return False
    if _LOCALE_DRAFT_CHANGE.match(folded) is not None:
        return True
    return _VERB_FINAL_CHANGE.search(folded) is not None
