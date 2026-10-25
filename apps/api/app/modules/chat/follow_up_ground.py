"""Whether a turn still works a subject problem: how much of the problem's ground it reuses.

Live (2026-10-25, one chat with the free model): two lines after a rectangle problem,
"cool. i'm going to lisbon next month for 4 days, what should i not miss?" got "What if
perimeter was 48 cm?" under its travel tips. Judging the line by its own words cut real
follow-ups off as well ("how high would it bounce back up?", "why do we set each bracket
to zero?"), so a turn is judged by what it said: its line and its reply. A reply that still
works the problem reuses the problem's ground: its words ("perimeter", "ball"), its
numbers with their units (19.8 m/s; a single digit is weak, a recipe has them too), its
units, and its maths ("x^2 - 5x + 6", "x = 2", the variable x). Travel tips, a recipe or
the user's to-do list reuse one thing at most: a word ("water", "bike") or a unit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.modules.chat.follow_up_words import LATIN, NOT_UNITS, STOP_WORDS, TOPIC_WORD
from app.services.text_normalize import straighten_apostrophes

# Enough shared ground to still work the problem: two things it said (a word of the
# problem and its number, a step of its maths and its variable), or a number with its unit.
_ENOUGH = 2.0
# A word only the problem's reply used is half a tie: a worked answer says many words.
_REPLY_WORD = 0.5
# 19.8 m/s again is the problem's own quantity; 19.8 alone is one thing it said.
_NUMBER_WITH_UNIT = 2.0
_NUMBER = 1.0
# A single digit, or a unit, is weak: "2 eggs", "a 30 cm pizza". A few add up to one.
_WEAK = 0.5
_WEAK_MOST = 1.0
# A reply's start says what it works on; this keeps a long one quick to read.
_TURN_CHARS = 6000
# Words that ask about a problem, show it or measure it, and the chat's fillers: every
# reply uses them, whatever it is about.
_ASKS_OR_SHOWS = """again another answer calculate change check correct different easier easy
explain explanation figure find give happen hard harder help instead matter mean method part
problem question quick same simple simpler simply solve step take teach tell took understand
work wrong chart diagram draw equation example formula graph number picture plot result show
table value visual fast high long many often"""
_FILLERS = """actually anyway anything around cool even every first going gonna good great last
maybe next nice okay please real really right someone something still sure thank think until
very want well"""
_NAMES_NOTHING = frozenset(f"{_ASKS_OR_SHOWS} {_FILLERS}".split())
# The turn's words are read from three letters: "the hit" is the problem's "hits", and a
# problem word is never shorter than three letters once its plural "s" is off.
_TURN_WORD = re.compile(rf"[{LATIN}]{{3,}}")
# "doesn't" is "does", not the word "doesn"; "what's" is "what".
_CONTRACTION = re.compile(r"n't\b|'(?:s|re|ll|ve|m|d)\b")
_SYMBOLS = str.maketrans(
    {
        "\u00b2": "^2",  # squared
        "\u00b3": "^3",  # cubed
        "\u2212": "-",  # the minus sign
        "\u2013": "-",  # an en dash
        "\u00d7": "*",  # times
        "\u00b7": "*",  # a middle dot
        "\u00f7": "/",  # divided by
        "\u2009": " ",  # a thin space
    }
)
# A number, and its unit: "20 m", "9.8 m/s^2", "72 cm^2", "18 g/mol", "$80".
_QUANTITY = re.compile(
    r"(?<![\w.^])([$\u20ac\u00a3]?)(-?\d+(?:\.\d+)?)"
    r"(?:(\s*)([a-zA-Z\u00b5\u00b0%][a-zA-Z\u00b0/^0-9]*))?"
)
_SMALL = 10
# Maths written out: "x^2-5x+6=0", "(x-2)(x-3)", "v=gt", in Latin or Greek letters.
_LETTER = re.compile("[a-z\u03b1-\u03c9]")
_PIECE = re.compile("[a-z\u03b1-\u03c90-9.^()+\\-*/=]+")
_OPERATOR = re.compile(r"[=+\-*/^]")
_DIGIT_OR_POWER = re.compile(r"[\d^]")
_GROUP = re.compile(r"\(([^()]*)\)")
_VARIABLE = re.compile("(?<![a-z\u03b1-\u03c9])[a-z\u03b1-\u03c9](?![a-z\u03b1-\u03c9])")
_LATEX_SPACING = re.compile(r"\\(?:left|right|[,!;])")
_LATEX_TIMES = re.compile(r"\\(?:cdot|times)")
_LATEX_FRACTION = re.compile(r"\\frac\{([^{}]*)\}\{([^{}]*)\}")
_SPACED_OPERATOR = re.compile(r"\s*([=+\-*/^])\s*")


@dataclass(frozen=True)
class _Ground:
    words: frozenset[str]
    quantities: tuple[tuple[float, str | None], ...]
    maths: frozenset[str]

    @property
    def units(self) -> frozenset[str]:
        return frozenset(unit for _value, unit in self.quantities if unit)

    @property
    def variables(self) -> frozenset[str]:
        return frozenset(v for piece in self.maths for v in _VARIABLE.findall(piece))


def works_the_problem(problem: str, problem_reply: str | None, turn: str) -> bool:
    """Whether ``turn`` (this line and its reply) reuses enough of what ``problem`` and
    its first reply said to be still working it."""
    asked, replied = _ground(problem), _ground(problem_reply or "")
    said = _ground(turn, _TURN_WORD)
    words = len(said.words & asked.words) + _REPLY_WORD * len(
        (said.words & replied.words) - asked.words
    )
    units = _WEAK * len(said.units & (asked.units | replied.units))
    maths = asked.maths | replied.maths
    shared_maths = len(said.maths & maths) + float(
        bool(said.variables & (asked.variables | replied.variables))
    )
    numbers = _shared_numbers(said.quantities, asked.quantities + replied.quantities)
    return words + min(units, _WEAK_MOST) + shared_maths + numbers >= _ENOUGH


def _ground(text: str, pattern: re.Pattern[str] = TOPIC_WORD) -> _Ground:
    plain = straighten_apostrophes(text[:_TURN_CHARS]).translate(_SYMBOLS)
    return _Ground(_words(plain, pattern), _quantities(plain), _maths(plain))


def _words(text: str, pattern: re.Pattern[str]) -> frozenset[str]:
    folded = _CONTRACTION.sub("", text.casefold())
    words = (_singular(w) for w in pattern.findall(folded) if w not in STOP_WORDS)
    return frozenset(word for word in words if word not in _NAMES_NOTHING)


def _singular(word: str) -> str:
    return word[:-1] if word.endswith("s") and not word.endswith("ss") else word


def _quantities(text: str) -> tuple[tuple[float, str | None], ...]:
    return tuple(
        (float(value), _unit(space, unit) or currency or None)
        for currency, value, space, unit in _QUANTITY.findall(text)
    )


def _unit(space: str, unit: str) -> str | None:
    if not unit or unit.casefold() in NOT_UNITS:
        return None
    if not space and len(unit) == 1 and unit.isalpha():
        return None  # "2w", "5x": a variable, not a unit
    if unit.isalpha() and len(unit) > 3 and unit.endswith("s"):
        return unit[:-1]  # "hours" is "hour"
    return unit


def _shared_numbers(
    said: tuple[tuple[float, str | None], ...], ground: tuple[tuple[float, str | None], ...]
) -> float:
    """The numbers the problem used, each with a unit of the same kind, or with none on
    either side: "20 minutes" is not the ball's 20 m, and "10 minutes" is not the 10 kg
    that "F = 10 * 3" restates bare. A single digit without its unit is weak."""
    units: dict[float, set[str]] = {}
    for value, unit in ground:
        units.setdefault(value, set()).update([unit] if unit else [])
    with_unit: set[float] = set()
    alone: set[float] = set()
    small: set[float] = set()
    for value, unit in said:
        known = units.get(value)
        if known is None:
            continue
        same_kind = _same_kind(unit, known)
        if unit and known and not same_kind:
            continue
        if not (value.is_integer() and abs(value) < _SMALL):
            (with_unit if same_kind else alone).add(value)
        elif same_kind:
            alone.add(value)  # "2 mol" again; a bare 2 is in any recipe
        else:
            small.add(value)
    alone -= with_unit
    small -= alone
    weak = min(_WEAK * len(small), _WEAK_MOST)
    return _NUMBER_WITH_UNIT * len(with_unit) + _NUMBER * len(alone) + weak


def _same_kind(unit: str | None, known: set[str]) -> bool:
    return unit is not None and any(_base(unit) == _base(other) for other in known)


def _base(unit: str) -> str:
    """The unit's first part: "m/s^2" and "m/s" are both "m", "km/h" is "km"."""
    return re.split(r"[/^]", unit, maxsplit=1)[0]


def _maths(text: str) -> frozenset[str]:
    """The maths written in ``text``: each expression or equation, its sides and its
    bracketed parts, units taken off first so "9.8 m/s^2" is the number 9.8."""
    pieces: set[str] = set()
    for piece in _PIECE.findall(_written_maths(_without_units(text)).casefold()):
        piece = _balanced(piece.strip("."))
        if not (_LETTER.search(piece) and _OPERATOR.search(piece)):
            continue
        if not (_DIGIT_OR_POWER.search(piece) or "=" in piece):
            continue
        pieces.add(piece)
        parts = [*piece.split("="), *_GROUP.findall(piece)]
        pieces.update(
            _balanced(part)
            for part in parts
            if _LETTER.search(part) and _DIGIT_OR_POWER.search(part)
        )
    return frozenset(pieces)


def _balanced(piece: str) -> str:
    """Without the bracket a sentence opened or closed: "(x-2)(x-3)=0" stays whole."""
    opened, closed = piece.count("("), piece.count(")")
    start, end = 0, len(piece)
    while start < end and piece[start] == "(" and opened > closed:
        start, opened = start + 1, opened - 1
    while end > start and piece[end - 1] == ")" and closed > opened:
        end, closed = end - 1, closed - 1
    return piece[start:end]


def _without_units(text: str) -> str:
    def number_only(match: re.Match[str]) -> str:
        currency, value, space, unit = match.groups()
        if currency or _unit(space or "", unit or ""):
            return value
        return match.group(0)

    return _QUANTITY.sub(number_only, text)


def _written_maths(text: str) -> str:
    """LaTeX and spaced maths in one plain form: "$x - 2 = 0$" is "x-2=0"."""
    text = _LATEX_SPACING.sub("", text)
    text = _LATEX_TIMES.sub("*", text)
    text = _LATEX_FRACTION.sub(r"(\1)/(\2)", text)
    text = text.replace("$", " ").replace("{", "(").replace("}", ")")
    return _SPACED_OPERATOR.sub(r"\1", text)
