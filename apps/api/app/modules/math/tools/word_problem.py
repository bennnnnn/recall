"""Algebra word problems: a cheap gate, one structured translation, a number guard.

"Maria is three times as old as her son; together they are 48" has no
equation for the regex extractors to find. When the gate below fires and no
extractor matched, one bounded call on the fast alias translates the problem
into unknowns and equations (``WordProblemSetup``). Before SymPy sees it,
every number in those equations must be one the problem states, in digits or
in words, so a translation cannot smuggle in a value the student never gave.
SymPy then has to find exactly one solution in the stated domain
(``solve/word_problem.py``); otherwise the turn keeps its normal path.
"""

from __future__ import annotations

import logging
import re
from fractions import Fraction

from app.core.config import Settings
from app.gateways import litellm_gateway
from app.models.schemas.math import MathIntent
from app.models.schemas.math.word_problem import WordProblemSetup

logger = logging.getLogger(__name__)

_MIN_CHARS = 25
_MAX_CHARS = 600

_QUESTION = re.compile(
    r"\?|\b(?:find|determine|calculate|work\s+out|what\s+(?:is|are|was|were)"
    r"|how\s+(?:many|much|old|long|far|fast|tall|wide))\b",
    re.IGNORECASE,
)
_RELATION = re.compile(
    r"\b(?:times\s+as|twice|double|triple|thrice|half|more\s+than|less\s+than|fewer\s+than"
    r"|greater\s+than|older|younger|sum|total|together|altogether|combined|difference"
    r"|product|consecutive|each|per|costs?|paid|spent|earns?|left|remain(?:s|ing)?|shared?"
    r"|split|equally|ages?|years\s+old|numbers?|integers?|percent)\b|%",
    re.IGNORECASE,
)
_DIGITS = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?|\.\d+")
_NUMBER_WORDS: dict[str, tuple[int, ...]] = {
    "zero": (0,),
    "one": (1,),
    "two": (2,),
    "three": (3,),
    "four": (4,),
    "five": (5,),
    "six": (6,),
    "seven": (7,),
    "eight": (8,),
    "nine": (9,),
    "ten": (10,),
    "eleven": (11,),
    "twelve": (12,),
    "thirteen": (13,),
    "fourteen": (14,),
    "fifteen": (15,),
    "sixteen": (16,),
    "seventeen": (17,),
    "eighteen": (18,),
    "nineteen": (19,),
    "twenty": (20,),
    "thirty": (30,),
    "forty": (40,),
    "fifty": (50,),
    "sixty": (60,),
    "seventy": (70,),
    "eighty": (80,),
    "ninety": (90,),
    "hundred": (100,),
    "thousand": (1000,),
    "twice": (2,),
    "double": (2,),
    "triple": (3,),
    "thrice": (3,),
    "half": (2,),
    "halves": (2,),
    "third": (3,),
    "thirds": (3,),
    "quarter": (4,),
    "quarters": (4,),
    "fourth": (4,),
    "fifth": (5,),
    "dozen": (12,),
    "percent": (100,),
    "consecutive": (1, 2, 3, 4, 6),
    "even": (2,),
    "odd": (2,),
}
_FRACTION_WORDS = frozenset(
    {"half", "halves", "third", "thirds", "quarter", "quarters", "fourth", "fifth"}
)
_WORD = re.compile(r"[a-z]+")

_PROMPT = """Translate the word problem into equations for a symbolic solver.

Return JSON only:
{"found": true,
 "unknowns": [{"symbol": "s", "meaning": "the son's age now", "unit": "years"}],
 "equations": [{"equation": "m = 3*s", "source": "Maria is three times as old as her son"}],
 "targets": [{"expr": "s", "meaning": "the son's age now", "unit": "years"}],
 "whole_numbers": true, "positive": true}

Rules:
- One lowercase letter per unknown (not e or i). At most 3 unknowns, 4 equations.
- Each equation has exactly one "=", in plain ASCII math: * for times, ^ for powers.
- Use only numbers the problem states. Spelled numbers are fine ("twice" is 2,
  "half" is 1/2, "15%" is 15/100). Never compute, round, or add a number.
- "source" quotes the words of the problem that equation says.
- targets are what the question asks for, as an unknown or an expression in them.
- whole_numbers: true when the unknowns count people or things.
- positive: true when the unknowns are ages, lengths, prices, or amounts.
- Not a word problem, missing data, or more than 3 unknowns: {"found": false}."""


def word_problem_candidate(text: str) -> bool:
    """A question over at least two stated quantities (one in digits) with a relation word."""
    if not _MIN_CHARS <= len(text) <= _MAX_CHARS or "=" in text:
        return False
    if not _QUESTION.search(text) or not _RELATION.search(text):
        return False
    from app.modules.physics import has_supported_physics_cue

    if has_supported_physics_cue(text):
        return False
    digits = len(_DIGITS.findall(text))
    words = sum(1 for word in _WORD.findall(text.lower()) if word in _NUMBER_WORDS)
    # At least one number in digits: "how many calories are in two eggs and
    # three slices" is a lookup, and a false positive here costs the turn a
    # model call and its web-search classifier.
    return digits >= 1 and digits + words >= 2


def _stated_numbers(text: str) -> set[Fraction]:
    lowered = text.lower()
    stated = {Fraction(1)}
    for number in _DIGITS.findall(lowered):
        stated.add(Fraction(number.replace(",", "")))
    for word in _WORD.findall(lowered):
        for value in _NUMBER_WORDS.get(word, ()):
            stated.add(Fraction(value))
            if word in _FRACTION_WORDS:
                stated.add(Fraction(1, value))
    if "%" in lowered or "percent" in lowered:
        # "15%" may be written 15/100 or 0.15.
        stated |= {Fraction(100)} | {value / 100 for value in stated}
    return stated


def grounded(setup: WordProblemSetup, text: str) -> bool:
    """Every number in the translation is one the problem states."""
    stated = _stated_numbers(text)
    written = [item.equation for item in setup.equations] + [t.expr for t in setup.targets]
    for piece in written:
        for number in _DIGITS.findall(piece):
            if Fraction(number.replace(",", "")) not in stated:
                return False
    return True


async def word_problem_intent(text: str, settings: Settings) -> MathIntent | None:
    """One bounded structured call. Never raises into the chat path."""
    if not settings.math_word_problems_enabled or not word_problem_candidate(text):
        return None
    try:
        setup = await litellm_gateway.complete_structured(
            settings=settings,
            model_alias="title-model",
            messages=[
                {"role": "system", "content": _PROMPT},
                {"role": "user", "content": text.strip()},
            ],
            schema=WordProblemSetup,
            max_tokens=500,
            timeout_seconds=settings.math_word_problem_timeout_seconds,
            allow_fallback=False,
        )
    except Exception:
        logger.warning("word problem extract failed", exc_info=True)
        return None
    if setup is None or not setup.found or not grounded(setup, text):
        return None
    return MathIntent(kind="word_problem", word_problem=setup, operation="solve")
