"""A follow-up that scales one given of the problem before it, said the ways students say it.

"what if the mass doubles", "what if the cliff was twice as high", "with three times the
force", "what if I halve the speed", "if the speed was increased by a factor of 3": each
holds one factor and what it scales. That is the noun the line names when it names a
quantity ("the speed was twice as high" is the speed, the adjective only says which way),
or the quantity an unambiguous adjective stands for when the line's subject is an object
of the problem ("the cliff was twice as high" is the cliff's height). A pronoun with an
adjective or a quantity ("it was twice as heavy", "it had twice the mass") may be any body
of the problem and is not read; the one exception is a throw ("it was thrown twice as
fast"), which the problem's own "thrown at" names. Nor is a verb other than "is" or "was"
("it accelerated twice as fast", "it landed twice as far"), two scalings, or a negation.
Which given a reading names, and whether its object owns it, is the rewriter's call
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
    "cliff", "speed of sound"), the quantity its adjective stands for ("height"), and the
    object said to have it ("the car had twice the mass": "car")."""

    factor: float
    noun: str | None
    adjective: str | None
    owner: str | None = None
    # "it was thrown twice as fast": the throw that names the speed.
    thrown: str | None = None


_LEAD = r"(?:(?:and|but|so|ok(?:ay)?|now|then|please|can you|could you)[ ,]+)*"
_IF = r"(?:(?:(?:what )?if|suppose(?: that)?|say|what about|how about) )?"
_ARTICLE = r"(?:the|its|her|his|their|this|that)"
_NOUN = r"(?P<noun>[a-z]+(?: [a-z]+){0,2}?)"
# Who has the factor before a named quantity, and how: "what if the car had", "it rolled
# at", "I", "with". "I double the mass" is an agent; "we had twice the mass" an owner.
_WHO = rf"(?P<who>it|she|he|they|i|we|you|{_ARTICLE} [a-z]+(?: [a-z]+){{0,2}}?)"
_OPENING = (
    rf"{_IF}(?:{_WHO}(?: (?P<verb>[a-z']+(?: [a-z']+){{0,2}}?))? )?"
    r"(?:(?:with|at|using|from|to|for) )?"
)
_AGENTS = frozenset({"i", "we", "you"})
_THROWS = frozenset({"thrown", "kicked", "launched"})
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
        noun = match.group("noun") or match.group("made")
        motion = (match.group("motion") or "").lower()
        if noun is None:
            # A pronoun or nothing: only a throw says which body ("it was thrown twice
            # as fast"); "it was twice as heavy" may be the driver or the car.
            if motion in _THROWS and adjective == "speed":
                return _reading(match.group("factor"), None, adjective, thrown=motion)
            return None
        # "the truck was going twice as fast": a motion is no object beside a value.
        if motion:
            return None
        return _reading(match.group("factor"), noun, adjective)
    for pattern in (_OF_NAME, _NAME_THEN, _CUT_NAME):
        match = pattern.fullmatch(text)
        if match is not None:
            noun = match.group("noun")
            if noun.lower().strip() in _PRONOUNS:
                return None
            return _reading(match.group("factor"), noun, None, _owner(match))
    return None


def _owner(match: re.Match[str]) -> str | None:
    """The object a factor's opening says has the quantity: "the car" in "the car had
    twice the mass"; none for "it", "with" or an agent ("I double the mass"). "we" or "I"
    having it is no body of the problem: "?" stands for an owner nothing can match."""
    who = (match.groupdict().get("who") or "").lower()
    if not who:
        return None
    # "it had twice the mass" may be any body of the problem; "we had" is none of them.
    if who in {"it", "she", "he", "they"}:
        return "?"
    if who in _AGENTS:
        return "?" if match.groupdict().get("verb") else None
    return who


def _reading(
    written: str,
    noun: str | None,
    adjective: str | None,
    owner: str | None = None,
    thrown: str | None = None,
) -> Scaling | None:
    factor = _factor(written.lower())
    if factor is None or factor == 1.0 or not 0.0 < factor <= _LARGEST:
        return None
    noun = None if noun is None else " ".join(noun.lower().split())
    return Scaling(factor, noun, adjective, owner, thrown)


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


def _words(text: str) -> list[str]:
    return [word for word in re.findall(r"[a-z]+", text.lower()) if word not in _ARTICLES]


def _mentions(prior: str, phrase: str) -> bool:
    """True when every word of ``phrase`` but its articles is a word of the problem."""
    words = set(re.findall(r"[a-z]+", prior.lower()))
    wanted = _words(phrase)
    return bool(wanted) and all(word in words for word in wanted)


def scaled_name(
    prior: str, scaling: Scaling, is_quantity: Callable[[str], bool]
) -> tuple[str, str | None] | None:
    """The quantity a scaling names in ``prior``, and the object that must own its given.

    A named quantity wins over the adjective ("the mass was 3 times higher" is the mass); a
    named object takes its adjective's quantity and must own it ("the cliff was twice as
    high"); "the mass of the car" and "the car had twice the mass" are the car's mass. A
    throw is the speed it was thrown at. An owner the problem never mentions ("the earth",
    "we") or a pronoun ("it had twice the mass") names nothing."""
    noun = scaling.noun
    if noun is None:
        return ("speed", None) if scaling.thrown else None
    owner = scaling.owner
    head, _, of_owner = noun.partition(" of ")
    if of_owner:
        if owner is not None:
            return None
        owner = of_owner
    if is_quantity(head):
        name = head
    elif scaling.adjective is not None and owner is None:
        name, owner = scaling.adjective, head
    else:
        return None
    if owner is not None and not _mentions(prior, owner):
        return None
    return name, owner


_UNIT_AFTER = r"[ \t]*{unit}"
# The one word that may stand between a value and its object: "1.2 m high table".
_BESIDE = frozenset({"high", "tall", "deep", "long", "wide", "heavy"})


def _clause_before(prior: str, given: Given) -> list[str]:
    return _words(re.split(r"[.?!,;]", prior[: given.start])[-1])


def owns(prior: str, given: Given, owner: str, name: str = "") -> bool:
    """True only when ``owner`` is written right beside the given: its value, its unit, at
    most one word of size ("high", "tall", ...), then the owner ("80 m cliff", "1.2 m high
    table"); or the owner just before "of" and the value ("a load of 50 kg", "a car of mass
    900 kg"). "A 70 kg driver in a car" is the driver's, never the car's."""
    wanted = _words(owner)
    if not wanted:
        return False
    end = given.end
    unit = re.match(_UNIT_AFTER.format(unit=re.escape(given.unit)), prior[end:], re.IGNORECASE)
    if unit is not None:
        end += unit.end()
    after = _words(re.split(r"[.?!,;]", prior[end:], maxsplit=1)[0])
    size = 1 if after and after[0] in _BESIDE else 0
    if after[size : size + len(wanted)] == wanted:
        return True
    before = _clause_before(prior, given)
    named = _words(name)[-1:]
    for lead in (["of"], ["of", *named] if named else None):
        if lead and before[-len(lead) :] == lead:
            if before[-len(lead) - len(wanted) : -len(lead)] == wanted:
                return True
    return False


# "Two 5 kg masses", "each 4 ohm resistor": a value that is more than one body's.
_COUNTED = frozenset({"two", "three", "four", "both", "each", "pair"})


def counted(prior: str, given: Given) -> bool:
    """True when a count stands right before the value: doubling "the mass" of "two 5 kg
    masses" may be one of them or both."""
    before = _clause_before(prior, given)
    return bool(before) and (before[-1] in _COUNTED or before[-2:] == ["pair", "of"])


def thrown_at(prior: str, given: Given, throw: str) -> bool:
    """True when the problem itself throws at this value: "thrown upward at 20 m/s"."""
    head = re.split(r"[.?!,;]", prior[: given.start])[-1]
    stem = throw[:-1] if throw.endswith("n") else throw[:-2]  # thrown → throw, kicked → kick
    return re.search(rf"\b{stem}[a-z]*(?: [a-z]+){{0,2}} at[ \t]*$", head, re.I) is not None


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
# The words directly before a value that say which end it is: "from 10 m/s", "launched at
# 10 m/s", "reaches 30 m/s", "a final speed of 30 m/s". Nothing else counts: "moving at"
# and "rolls off at" say no end.
_INITIAL_CUE = re.compile(
    r"(?:\bfrom|\binitially(?: at)?|\bstart(?:s|ing)? at"
    r"|\b(?:launched|thrown|fired|kicked|shot|projected)(?: up(?:ward)?| horizontally"
    r"| vertically(?: upward)?)? at"
    r"|\b(?:initial|starting|launch) (?:speed|velocity) (?:of|is|was))[ \t]*$",
    re.IGNORECASE,
)
_FINAL_CUE = re.compile(
    r"(?:\bto|\breach(?:es|ed)?|\buntil it reaches"
    r"|\bfinal (?:speed|velocity) (?:of|is|was))[ \t]*$",
    re.IGNORECASE,
)


def plays_role(prior: str, given: Given, name: str) -> bool:
    """False when ``name`` says initial or final and the words directly before ``given``
    do not say that end alone: "the initial speed" is never the 30 m/s a car "reaches",
    nor the 30 m/s it "is going" with no word for which end."""
    role = next((_ROLE_WORDS[word] for word in _words(name) if word in _ROLE_WORDS), None)
    if role is None:
        return True
    head = re.split(r"[.?!,;]", prior[: given.start])[-1]
    initial = _INITIAL_CUE.search(head) is not None
    final = _FINAL_CUE.search(head) is not None
    if initial == final:
        return False
    return (role == "initial") == initial
