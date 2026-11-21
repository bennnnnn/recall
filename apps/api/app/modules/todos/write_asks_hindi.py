"""Which Hindi messages ask to add or change a to-do: request forms only, never a question.

A Hindi verb's infinitive is also a plain statement's: "माँ को दवा याद दिलाना मेरी ज़िम्मेदारी
है" (reminding mom is my job), "मैं उसे remind करना भूल गया" (I forgot to remind him). So
the imperatives ask anywhere ("याद दिलाओ", "याद दिलाइए", "टू-डू में दूध जोड़ो"), and an
infinitive asks only when it closes the sentence, as a request does ("मुझे कल 9 बजे दवाई लेने
की याद दिलाना"). A question ("?", "कैसे", "क्या", "क्यों") is never one: "आईफ़ोन पर रिमाइंडर
कैसे हटाएं?" asks how. The words are written with a dotted letter as its letter and its dot
(``unify_devanagari``), as the message reaching here is.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

# Imperatives and polite requests: a request wherever they stand.
_REMIND = (
    "याद दिलाओ", "याद दिलाइए", "याद दिलाइये", "याद दिलाइएगा", "याद दिलाइयेगा", "याद दिला दो",
    "याद दिला दीजिए", "याद दिला दीजिये", "याद दिला दीजिएगा", "रिमाइंडर लगाओ", "रिमाइंडर लगा दो",
    "रिमाइंडर लगाइए", "रिमाइंडर लगा दीजिए", "रिमाइंडर सेट करो", "रिमाइंडर सेट कर दो",
    "रिमाइंडर सेट कीजिए", "remind करो", "remind कर दो", "रिमाइंड करो", "रिमाइंड कर दो",
    "रिमाइंड कीजिए",
)  # fmt: skip
# Infinitives, a request only as the sentence's last words.
_REMIND_LAST = (
    "याद दिलाना", "याद दिला देना", "याद करा देना", "रिमाइंडर लगा देना", "रिमाइंडर सेट कर देना",
    "remind करना", "remind कर देना", "रिमाइंड करना", "रिमाइंड कर देना",
)  # fmt: skip
_ADD_OR_CHANGE = (
    "जोड़ो", "जोड़ें", "जोड़िए", "जोड़िये", "जोड़ दो", "जोड़ दें", "जोड़ दीजिए", "डालो", "डाल दो",
    "हटाओ", "हटाएं", "हटाइए", "हटा दो", "हटा दें", "हटा दीजिए", "मिटाओ", "मिटा दो", "बदलो",
    "बदलें", "बदलिए", "बदल दो", "बदल दें", "बदल दीजिए", "लिख लो",
)  # fmt: skip
# Whole words: "मेरी लिस्टिंग" (my listing) is no list.
_TODO_TARGET = (
    "टू-डू", "टूडू", "टू-डूज़", "रिमाइंडर", "रिमाइंडरों", "रिमाइंडर्स", "मेरी सूची", "मेरी लिस्ट",
    "काम की सूची", "कामों की सूची",
)  # fmt: skip
# A word's letters, vowel signs included (``\w`` leaves them out); not the danda.
_IN_WORD = r"[\w'\-\u0900-\u0963\u0966-\u097f]"
_QUESTION = re.compile(f"\\?|(?<!{_IN_WORD})(?:कैसे|क्या|क्यों|कौन|किसे|किसको)(?!{_IN_WORD})")


def _words(phrases: Iterable[str], tail: str = "") -> re.Pattern[str]:
    body = "|".join(re.escape(phrase) for phrase in phrases)
    return re.compile(f"(?<!{_IN_WORD})(?:{body})(?!{_IN_WORD}){tail}")


_REMIND_RE = _words(_REMIND)
_REMIND_LAST_RE = _words(_REMIND_LAST, r"[\s.!।]*$")
_ADD_OR_CHANGE_RE = _words(_ADD_OR_CHANGE)
_TODO_TARGET_RE = _words(_TODO_TARGET)


def asks_in_hindi(folded: str) -> bool:
    """True when ``folded`` (collapsed, casefolded, Devanagari unified) asks in Hindi to
    add, change or delete a to-do."""
    if _QUESTION.search(folded):
        return False
    if _REMIND_RE.search(folded) or _REMIND_LAST_RE.search(folded):
        return True
    return bool(_ADD_OR_CHANGE_RE.search(folded) and _TODO_TARGET_RE.search(folded))
