"""A follow-up that scales one given of the problem before it, said the ways students say it.

"what if the mass doubles", "what if the cliff was twice as high", "with three times the
force", "what if I halve the speed", "if the speed was increased by a factor of 3": each
holds one factor and what it scales. That is the noun the line names when it names a
quantity ("the speed was twice as high" is the speed, the adjective only says which way),
or the quantity an unambiguous adjective stands for when the line's subject is the
problem's object or a pronoun ("the cliff was twice as high" is the height). Only "is",
"was" and the like carry the adjective, or for a speed the motion it belongs to ("it was
thrown twice as fast"): "it accelerated twice as fast" or "it landed twice as far" says
something else and is not read. A line with two scalings or a negation is not one scaled
given. Which given the reading names is the subject's rewriter's call
(``GivenRewriter.scaled``).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from app.services.law_binding.givens import Given


@dataclass(frozen=True)
class Scaling:
    """One scaled given as a line says it: the factor, the noun the line names ("mass",
    "cliff", "speed of sound"), and the quantity its adjective stands for ("height")."""

    factor: float
    noun: str | None
    adjective: str | None


_LEAD = r"(?:(?:and|but|so|ok(?:ay)?|now|then|please|can you|could you)[ ,]+)*"
_IF = r"(?:(?:(?:what )?if|suppose(?: that)?|say|what about|how about) )?"
# The words that may open a factor before a named quantity: "with", "what if I", "it had".
_OPENING = (
    r"(?:(?:(?:what )?if|suppose|say|what about|how about|make|making|with|at|using|it|she"
    r"|he|they)(?: [a-z']+){0,5} )?"
)
_ARTICLE = r"(?:the|its|her|his|their|this|that)"
_NOUN = r"(?P<noun>[a-z]+(?: [a-z]+){0,2}?)"
# "the cliff was", "it's", "the ball were": a subject and the verb that carries an adjective.
_COPULA = r"(?:'s| is| was| were| be| are| had been| has been| became| becomes| got| gets)"
_SUBJECT = rf"(?:(?:it|she|he|they)|{_ARTICLE} {_NOUN}){_COPULA}"
# The motion a speed belongs to: "it was thrown twice as fast".
_MOTION = (
    r"(?P<motion>thrown|kicked|launched|fired|shot|moving|travelling|traveling|going|running"
    r"|driving|driven)"
)
_MADE = rf"(?:make|making) (?:it|{_ARTICLE} (?P<made>[a-z]+(?: [a-z]+){{0,2}}?))"
_CARRIER = rf"(?:{_SUBJECT}(?: {_MOTION})? |{_MADE} )?"
_COUNT = r"(?:\d+(?:\.\d+)?|two|three|four|five|ten)"
# "twice", "3 times", "3x": a multiple, as before "as high" or "higher".
_MULTIPLE = rf"(?:twice|thrice|{_COUNT} times|\d+(?:\.\d+)?x)"
_TAIL = r"(?: (?:instead|then|now|as before|than before|than that|than it was))?"
_NAME = r"(?P<noun>[a-z][a-z ]{0,30}?)"

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

# "twice as high", "the cliff was twice as high", "half as heavy as before".
_AS_ADJECTIVE = re.compile(
    _LEAD + _IF + _CARRIER + rf"(?P<factor>{_MULTIPLE}|half) as (?P<word>[a-z]+)"
    r"(?: as (?:before|that|it was|the first(?: one)?))?" + _TAIL,
    re.IGNORECASE,
)
# "3 times higher", "what if the mass was 3 times higher".
_COMPARATIVE = re.compile(
    _LEAD + _IF + _CARRIER + rf"(?P<factor>{_MULTIPLE}) (?P<word>more massive|[a-z]+)" + _TAIL,
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


def scaled_given(line: str) -> Scaling | None:
    """``what if the mass doubles`` → the mass, times 2; ``what if the cliff was twice as high`` →
    the cliff, its height times 2. None unless the line scales one thing by one sensible factor."""
    text = " ".join(line.split())
    if len(_SCALE_WORD.findall(text)) != 1 or _NEGATION.search(text):
        return None
    for pattern, words in ((_AS_ADJECTIVE, _ADJECTIVES), (_COMPARATIVE, _COMPARATIVES)):
        match = pattern.fullmatch(text)
        if match is None:
            continue
        adjective = words.get(match.group("word").lower())
        if adjective is None:
            continue
        # A motion carries a speed only: "it was thrown twice as high" says where it went.
        if match.group("motion") and adjective != "speed":
            return None
        noun = match.group("noun") or match.group("made")
        return _reading(match.group("factor"), noun, adjective)
    for pattern in (_OF_NAME, _NAME_THEN, _CUT_NAME):
        match = pattern.fullmatch(text)
        if match is not None:
            noun = match.group("noun")
            if noun.lower().strip() in _PRONOUNS:
                return None
            return _reading(match.group("factor"), noun, None)
    return None


def _reading(written: str, noun: str | None, adjective: str | None) -> Scaling | None:
    factor = _factor(written.lower())
    if factor is None or factor == 1.0 or not 0.0 < factor <= _LARGEST:
        return None
    return Scaling(factor, None if noun is None else " ".join(noun.lower().split()), adjective)


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
    if written in {"cut", "cuts"}:
        return 0.5
    for word, factor in _WORD_FACTORS.items():
        if written.startswith(word):
            return factor
    return None


_ARTICLES = frozenset({"the", "a", "an", "its", "her", "his", "their", "this", "that"})


def _mentions(prior: str, phrase: str) -> bool:
    """True when every word of ``phrase`` but its articles is a word of the problem."""
    words = set(re.findall(r"[a-z]+", prior.lower()))
    wanted = [word for word in re.findall(r"[a-z]+", phrase.lower()) if word not in _ARTICLES]
    return bool(wanted) and all(word in words for word in wanted)


def scaled_name(
    prior: str, scaling: Scaling, is_quantity: Callable[[str], bool]
) -> tuple[str, bool] | None:
    """The quantity a scaling names in ``prior``, and whether only an adjective named it,
    with no noun ("twice as far" may be the answer's distance, "the cliff" says whose).

    A named quantity wins over the adjective ("the mass was 3 times higher" is the mass); a
    named object of the problem takes its adjective's quantity ("the cliff was twice as
    high"); "the speed of sound" is the problem's speed only when the problem has sound in
    it. Anything else, an object the problem never had included, names nothing."""
    noun = scaling.noun
    if noun is None:
        return None if scaling.adjective is None else (scaling.adjective, True)
    head, _, owner = noun.partition(" of ")
    if owner and not _mentions(prior, owner):
        return None
    if is_quantity(head):
        return head, False
    if scaling.adjective is not None and _mentions(prior, head):
        return scaling.adjective, False
    return None


# A name that says which end of a change it is: "the initial speed", "the final velocity".
_ROLE_WORDS = {
    "initial": "initial",
    "initially": "initial",
    "starting": "initial",
    "start": "initial",
    "launch": "initial",
    "final": "final",
    "end": "final",
    "ending": "final",
}
# The words before a value that say which end it is: "moving at 10 m/s", "reaches 30 m/s".
_ROLE_CUES = re.compile(
    r"\b(?P<initial>initial(?:ly)?|starts?|starting|started|from|launched|thrown|kicked"
    r"|fired|moving|travell?ing|going)\b"
    r"|\b(?P<final>final(?:ly)?|reach(?:es|ed|ing)?|until|to|ends?|ending|ended)\b",
    re.IGNORECASE,
)
_CUE_REACH = 40


def plays_role(prior: str, given: Given, name: str) -> bool:
    """False when ``name`` says initial or final and the words before ``given`` say the
    other end, or neither: "the initial speed" is never the 30 m/s a car "reaches"."""
    role = next(
        (_ROLE_WORDS[word] for word in re.findall(r"[a-z]+", name.lower()) if word in _ROLE_WORDS),
        None,
    )
    if role is None:
        return True
    head = prior[max(0, given.start - _CUE_REACH) : given.start]
    head = re.split(r"[.?!]\s", head)[-1]
    cues = list(_ROLE_CUES.finditer(head))
    return bool(cues) and cues[-1].lastgroup == role
