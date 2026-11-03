"""How a student states a result as theirs, and asks whether it is right.

One grammar for every subject. Physics read "I calculated", "my result is", "my teacher
says" and "is that ok?"; the maths readers knew "I got / found / have" and "is that
right" only, so "I calculated x = 6, is that ok?" was a claim to physics and not to
maths, and chemistry read none and declined the whole question (code-health audit
DUP-08). Each subject keeps its own value reader: physics a quantity with its unit,
maths ``var = value``, chemistry none (the model compares, beside the verified answer).

Live (2026-11-02): after four mole problems, "My answers: 1) 1 mol 2) 110 g 3) 4.5 x 10^23
molecules 4) 2 mol. Did I get them right?" was read as a new calculation. The grammar knew
one answer ("my answer is", "did I get it right"), not a list of them ("my answers:", "my
results are", "did I get them right", "are these right"). A message that only states
results to check asks for no new value (``question_part`` is empty of numbers): the reply
compares each one with the right one instead of working the problems again.
"""

from __future__ import annotations

import re

# Not "get" or "have": "I have a 2 kg ball" states a given. The maths readers add them
# where a ``var = value`` must follow.
_OWN_VERBS = (
    r"got|calculated|computed|worked\s+(?:it\s+)?out|found|obtained|reckon|"
    r"estimated|came\s+up\s+with|ended\s+up\s+with|wrote|answered|"
    r"think\s+(?:it'?s|it\s+is|the\s+answer\s+is)"
)
_OWN_RESULT = (
    r"my\s+(?:final\s+)?(?:answers?|results?|values?|working|workings|calculations?|solutions?)"
)
_SOMEONE_ELSE = (
    r"(?:my|a|the|our)\s+(?:friend|teacher|book|textbook|classmate|tutor|answer\s+key|"
    r"answer\s+sheet|mark\s+scheme)\s+(?:says?|said|thinks?|thought|got|gets|claims?|"
    r"reckons?)"
)

# The lead-in that makes the value after it a stated result (regex source, no anchor).
CLAIM_LEAD = (
    rf"\b(?:i|we)\s+(?:{_OWN_VERBS})\b"
    # "My answers: 1) 1 mol 2) 110 g" lists them after a colon.
    rf"|\b{_OWN_RESULT}(?:\s*:|\s+(?:is|are|was|were|says|gives|gave|came\s+to|comes\s+to)\b)"
    rf"|\b{_SOMEONE_ELSE}\b"
)
STATED = re.compile(CLAIM_LEAD, re.IGNORECASE)
# A lead-in naming the student's own result, not someone else's ("my friend says").
OWN = re.compile(rf"(?:i|we|{_OWN_RESULT})\b", re.IGNORECASE)

# The check a student asks of a stated value (regex source, no anchor).
# What the check is of: one result or several ("did I get them right?", "are these ok?").
_CHECKED = (
    r"(?:it|this|that|they|them|these|those|everything|my\s+\w+"
    r"|(?:all|both|each|any)(?:\s+of\s+(?:them|these|those|my\s+\w+))?)"
)
CHECK = (
    r"(?:(?:am|are)\s+(?:i|we)\s+(?:right|correct)"
    rf"|(?:is|are)\s+{_CHECKED}\s+(?:all\s+)?(?:right|correct|ok|okay)"
    rf"|did\s+(?:i|we)\s+get\s+{_CHECKED}\s+(?:all\s+)?(?:right|correct)"
    rf"|(?:can\s+you\s+)?check\s+{_CHECKED}"
    r"|(?:is\s+(?:that|this)\s+)?(?:right|correct))"
)
# A sentence that is only that check: "Am I right?", "Is that correct?".
CHECK_ONLY = re.compile(rf"^\s*(?:{CHECK}|yes\s+or\s+no)\s*(?:[?.!]+\s*)?$", re.IGNORECASE)
# The check glued to the end of a claim: "I got 4 m/s^2, correct?".
TRAILING_CHECK = re.compile(rf"(?:,|\b|\B(?<!\s))\s*{CHECK}\s*(?=[?.!]|$)", re.IGNORECASE)
# A question word before the lead-in makes it part of a question: "how far do I get".
QUESTION_WORD = re.compile(
    r"\b(?:how|what|when|where|which|why|do|does|did|can|could|will|would|should)\b",
    re.IGNORECASE,
)
# A sentence, not split at a decimal point ("29.2 g") or at a list's number on its own
# line ("1. 1 mol"): a list of results is one claim.
_SENTENCE = re.compile(r"(?:^[ \t]*\d{1,2}\.(?=[ \t])|[^.?!]|\.(?=\d))+[.?!]*", re.MULTILINE)
_DIGIT = re.compile(r"\d")
# A lead-in that names a result, or someone else's: a claim even with no check asked.
_NAMES_A_RESULT = re.compile(rf"\b{_OWN_RESULT}\b|\b{_SOMEONE_ELSE}\b", re.IGNORECASE)
_ASKS_CHECK = re.compile(CHECK, re.IGNORECASE)
# A sentence that asks for nothing: thanks, a please, an okay.
_COURTESY = re.compile(
    r"^(?:thanks?(?:\s+(?:a\s+lot|so\s+much))?|thank\s+you(?:\s+(?:so|very)\s+much)?|thx|ty|"
    r"please|pls|plz|ok(?:ay)?|cool|great|cheers|lol)\W*$",
    re.IGNORECASE,
)


def _claim_sentences(text: str) -> list[str]:
    """The sentences stating a result to check.

    "I got 29.2 g, am I right?" and "My answer is 29.2 g." are claims; "I found 2.5 g of
    a white solid." with no check asked states a given.
    """
    sentences = [sentence for sentence in _SENTENCE.findall(text) if sentence.strip()]
    check_asked = _ASKS_CHECK.search(text) is not None
    claims: list[str] = []
    for sentence in sentences:
        lead = STATED.search(sentence)
        if lead is None or QUESTION_WORD.search(sentence, 0, lead.start()) is not None:
            continue
        if _DIGIT.search(sentence, lead.end()) is None:
            continue
        if check_asked or _NAMES_A_RESULT.search(lead.group()) is not None:
            claims.append(sentence)
    return claims


def question_part(text: str) -> str:
    """The text without the sentences that state a result to check, or only check; empty
    when that is all it says ("My answers: 1) 1 mol 2) 110 g. Did I get them right?")."""
    claims = set(_claim_sentences(text))
    kept = [
        sentence.strip()
        for sentence in _SENTENCE.findall(text)
        if sentence.strip() and sentence not in claims and CHECK_ONLY.match(sentence) is None
    ]
    return " ".join(kept)


def without_stated_results(text: str) -> str:
    """The question without the sentences that state a result to check, or only check.

    "How many grams are in 0.5 mol of NaCl? I got 29.2 g, am I right?" is solved as its
    first sentence; the stated 29.2 g is not a given.
    """
    return question_part(text) or text


def only_checks_stated_results(text: str) -> bool:
    """The text states results to check and asks for no new value. "My answers: 1) 1 mol
    2) 110 g. Right?" asks only the check; "How many grams in 0.5 mol of NaCl? I got
    29.2 g, am I right?" and "What is the molar mass of water? I got 18 g/mol, right?" still
    ask their question. With no check asked, anything else it says is a question of its
    own: in "My values are 3 and 4. What is their sum?" the values are givens, not answers
    to mark."""
    if not has_stated_result(text):
        return False
    rest = question_part(text)
    if not rest:
        return True
    return _ASKS_CHECK.search(text) is not None and not _asks_something(rest)


def _asks_something(text: str) -> bool:
    """A sentence beside the claims asks for something of its own ("What is the molar
    mass of water?", "Show the working.", "Explain why."), unless it is only a courtesy:
    "Thanks!", "Please.", "ok"."""
    return any(
        _COURTESY.match(sentence.strip()) is None
        for sentence in _SENTENCE.findall(text)
        if sentence.strip()
    )


def has_stated_result(text: str) -> bool:
    """The text states a result for checking."""
    return bool(_claim_sentences(text))
