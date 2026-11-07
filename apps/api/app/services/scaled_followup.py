"""A follow-up that scales one given of the problem before it, said the ways students say it.

"what if the mass doubles", "what if the cliff was twice as high", "with three times the
force", "what if I halve the speed", "if the speed was increased by a factor of 3": each
names one quantity and one factor. The quantity is a noun the line names, or the one an
unambiguous adjective stands for ("twice as fast" is the speed; "twice as long" may be a
time or a length and is not read). A line with two scalings, a negation, or a pronoun in
place of the quantity is not one scaled given.
"""

from __future__ import annotations

import re

_LEAD = r"(?:(?:and|but|so|ok(?:ay)?|now|then|please|can you|could you)[ ,]+)*"
# The words that may open the change: "what if the cliff was", "with", "make it".
_OPENING = (
    r"(?:(?:(?:what )?if|suppose|say|what about|how about|make|making|with|at|using|it|she"
    r"|he|they)(?: [a-z']+){0,5} )?"
)
_COUNT = r"(?:\d+(?:\.\d+)?|two|three|four|five|ten)"
# "twice", "3 times", "3x": a multiple, as before "as high" or "higher".
_MULTIPLE = rf"(?:twice|thrice|{_COUNT} times|\d+(?:\.\d+)?x)"
_TAIL = r"(?: (?:instead|then|now|as before|than before|than that|than it was))?"
_NAME = r"(?P<name>[a-z][a-z ]{0,30}?)"

_ADJECTIVES = {
    "high": "height",
    "tall": "height",
    "deep": "height",
    "fast": "speed",
    "quick": "speed",
    "quickly": "speed",
    "heavy": "mass",
    "massive": "mass",
    "far": "distance",
}
_COMPARATIVES = {
    "higher": "height",
    "taller": "height",
    "deeper": "height",
    "faster": "speed",
    "quicker": "speed",
    "heavier": "mass",
    "more massive": "mass",
    "farther": "distance",
    "further": "distance",
}

# "twice as high", "half as heavy as before".
_AS_ADJECTIVE = re.compile(
    _LEAD + _OPENING + rf"(?P<factor>{_MULTIPLE}|half) as (?P<word>[a-z]+)"
    r"(?: as (?:before|that|it was|the first(?: one)?))?" + _TAIL,
    re.IGNORECASE,
)
# "3 times higher", "twice heavier".
_COMPARATIVE = re.compile(
    _LEAD + _OPENING + rf"(?P<factor>{_MULTIPLE}) (?P<word>more massive|[a-z]+)" + _TAIL,
    re.IGNORECASE,
)
# "with twice the mass", "double the height", "what if I halve the speed".
_OF_NAME = re.compile(
    _LEAD + _OPENING + rf"(?P<factor>{_MULTIPLE}|double[d]?|triple[d]?|quadruple[d]?"
    r"|half|halve[d]?) (?:the |its |her |his |their )" + _NAME + _TAIL,
    re.IGNORECASE,
)
# "what if the mass doubles", "the voltage is cut in half", "increased by a factor of 3".
_SCALED_BY = (
    r"(?:doubled|doubles|double|halved|halves|tripled|triples|quadrupled|quadruples"
    r"|cut in half|cut by half|reduced by half"
    rf"|(?:multiplied|divided) by {_COUNT}"
    rf"|(?:increased|multiplied|scaled(?: up)?|raised) by a factor of {_COUNT}"
    rf"|(?:decreased|reduced|divided|lowered|scaled down) by a factor of {_COUNT})"
)
_NAME_THEN = re.compile(
    _LEAD + r"(?:(?:(?:what )?if|suppose(?: that)?|say) )?(?:the |its |her |his |their )?"
    rf"{_NAME} (?:(?:is|was|were|gets|got|has been|had been|is being) )?"
    rf"(?P<factor>{_SCALED_BY})" + _TAIL,
    re.IGNORECASE,
)
# "what if I cut the mass in half".
_CUT_NAME = re.compile(
    _LEAD + _OPENING + rf"(?P<factor>cut|cuts) (?:the |its |her |his |their ){_NAME}"
    r" (?:in|by) half" + _TAIL,
    re.IGNORECASE,
)

# Every word that scales: two of them are two changes, not one scaled given.
_SCALE_WORD = re.compile(
    r"\b(?:(?:multiplied|divided) by a factor|twice|thrice|double[sd]?|triple[sd]?"
    r"|quadruple[sd]?|half|halve[sd]?|times|factor|multiplied|divided|\d+(?:\.\d+)?x)\b",
    re.IGNORECASE,
)
_NEGATION = re.compile(r"\b(?:not|never|no)\b|n't\b", re.IGNORECASE)
_PRONOUNS = frozenset({"it", "she", "he", "they", "this", "that", "i", "we", "you", "one"})
_WORD_COUNTS = {"two": 2.0, "three": 3.0, "four": 4.0, "five": 5.0, "ten": 10.0}
_WORD_FACTORS = {"twice": 2.0, "double": 2.0, "thrice": 3.0, "triple": 3.0, "quadruple": 4.0}
_LARGEST = 100.0


def scaled_given(line: str) -> tuple[str, float] | None:
    """``what if the mass doubles`` → ``("mass", 2.0)``; ``twice as fast`` → ``("speed", 2.0)``.

    None unless the line scales exactly one quantity by one sensible factor."""
    text = " ".join(line.split())
    if len(_SCALE_WORD.findall(text)) != 1 or _NEGATION.search(text):
        return None
    for pattern, words in ((_AS_ADJECTIVE, _ADJECTIVES), (_COMPARATIVE, _COMPARATIVES)):
        match = pattern.fullmatch(text)
        if match is not None:
            name = words.get(match.group("word").lower())
            if name is not None:
                return _reading(name, match.group("factor"))
    for pattern in (_OF_NAME, _NAME_THEN, _CUT_NAME):
        match = pattern.fullmatch(text)
        if match is not None:
            name = match.group("name").lower().split(" of ")[0].strip()
            if name in _PRONOUNS:
                return None
            return _reading(name, match.group("factor"))
    return None


def _reading(name: str, written: str) -> tuple[str, float] | None:
    factor = _factor(written.lower())
    if factor is None or factor == 1.0 or not 0.0 < factor <= _LARGEST:
        return None
    return name, factor


def _factor(written: str) -> float | None:
    """The factor a scaling says: "3 times" → 3, "halved" → 0.5, "divided by 4" → 0.25."""
    if "half" in written or written.startswith("halv"):
        return 0.5
    count = re.search(r"\d+(?:\.\d+)?|\b(?:two|three|four|five|ten)\b", written)
    if count is not None:
        number = _WORD_COUNTS.get(count.group()) or float(count.group())
        if re.search(r"\b(?:decreased|reduced|divided|lowered|down)\b", written):
            return None if number == 0 else 1.0 / number
        return number
    if written == "cut" or written == "cuts":
        return 0.5
    for word, factor in _WORD_FACTORS.items():
        if written.startswith(word):
            return factor
    return None
