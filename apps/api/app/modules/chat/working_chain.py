# ruff: noqa: RUF001, RUF003 -- the module reads × and − as replies write them.
"""Each value the working works out, worked again from its own method at full precision.

A working names a value and works it out over one line or several ("$e = \\frac{4.905
\\times 1.5}{(1.0 \\times 10^{11}) \\times (2.25\\pi \\times 10^{-8})}$", then "$e =
\\frac{7.3575}{2250\\pi \\times 10^{-3}}$", then "$e \\approx 1.041\\,\\mathrm{m}$"): a
chain. Its first form of numbers is its method, the formula with the values put in; every
form after it only does arithmetic, so each must keep the method's value. The value is
worked at full precision: a number an earlier chain showed rounded ("ω = 50.56"), or a card
stated, is that chain's whole value; a number put in for a name of the formula ("T =
\\frac{2\\pi}{\\omega}", then "\\frac{2\\pi}{1.087 \\times 10^{-3}}") that rounds the name's
value is that value; a standard value written rounded (0.8660 for cos 30°, ``working_exact``)
is exact. A given, a number of the question, is exact as written.

Each form is held to the method within its own rounding and the reach of the method's own
rounded inputs (``tex_spread``). One that misses is a slip; one right on the rounded numbers
its own line wrote but not at full precision is drift (rounding carried, not arithmetic).
Either way the chain keeps the method's value, and a later chain that uses the wrong number,
or a wrong form of it ("\\frac{3.27}{\\pi}"), gets the right one: the reply's own method with
the arithmetic redone, never another law.

Units are read where Pint can read them (``working_units``): "r = 9.00 cm = 0.09 m" is one
value in two units, and a chain that goes on in another unit is converted, never a slip.

Nothing is eval-ed (``tex_arithmetic.evaluate``). Pure: no IO.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from app.modules.chat.card_walk import answer_cards
from app.modules.chat.formula_inputs import aligned_names
from app.modules.chat.tex_arithmetic import (
    evaluate,
    is_unit_word,
    math_statement_spans,
    plain_arithmetic,
)
from app.modules.chat.tex_spread import half_place, spread
from app.modules.chat.working_cards import card_value
from app.modules.chat.working_check import NAME, OPERATOR, statement_parts
from app.modules.chat.working_claims import Claim, claims_in, names_in, plain_name, solved_for
from app.modules.chat.working_exact import standard_values
from app.modules.chat.working_numbers import shown_number
from app.modules.chat.working_units import (
    converted,
    in_base_units,
    quantity_unit,
    read_for_certain,
    same_unit,
    unit_after,
)
from app.services.answer_fence import VERIFIED_ANSWER_MARKER

# A number in a plain side: 50.56, 1.0874e-3, 290000.
_PLAIN_NUMBER = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?(?:e[-+]?\d+)?)(?![\w.])")
# A power's own digits: "10**(-8)", "x**2".
_EXPONENT_BEFORE = re.compile(r"\*\*\(?[-+]?$")
# A number written rounded is carried only with this many figures: "0.5", "38" are too
# common to be sure of (the ½ of a kinetic energy), as ``working_fix`` carries them.
CARRIED_FIGURES = 3
# A TeX token: a command, a number, or one character (the form a later line writes again).
_TOKEN = re.compile(r"\\[A-Za-z]+|\d+(?:\.\d+)?|\\.|\S")
_SPACING = frozenset({"\\,", "\\;", "\\:", "\\!", "\\ ", "\\left", "\\right"})
_PM = re.compile(r"\\pm|\\mp|±|∓")
# The number a card states, its power of ten with it: 0.241, 2.41 \times 10^{-4}, −3.
_CARD_NUMBER = re.compile(
    r"^[-−]?\d+(?:\.\d+)?(?:\s*(?:\\times|\\cdot|×)\s*10\s*\^\s*(?:\{\s*[-−]?\d+\s*\}|[-−]?\d))?"
)
# What may follow the number on a card: spacing and one unit group.
_ONLY_UNIT = re.compile(
    r"^(?:\\[,; !]|\s|~)*(?:\^\s*\{?\s*\\circ\s*\}?|°)?\s*"
    r"(?:\\(?:mathrm|text|textrm|rm)\s*\{[^{}]*\}(?:\s*\^\s*(?:\{[^{}]*\}|-?\d))?)?\s*$"
)


@dataclass
class Chain:
    """One value the working works out: its name, its value by its own method at full
    precision (in ``unit``, Pint text, "" when none is written), where it is written, and the
    first form or number that does not keep that value."""

    name: str
    value: float
    unit: str
    start: int
    end: int
    method: str
    # How far the method's own rounded inputs reach: no form is held closer than this.
    reach: float
    # A given: a number stated, not worked out ("m = 10 kg").
    given: bool = False
    # The first form that does not hold, as written.
    slip: str = ""
    # A shown number right only on the rounded numbers its line wrote.
    drift: str = ""
    # The last plain number the chain shows (TeX).
    shown: str = ""
    # A chain whose units Pint could not follow: nothing after it is held.
    broken: bool = False
    # The formula in names its method puts the values into ("2\\pi N"), "" when none.
    formula: str = ""
    # The name as the working writes it ("K_{rot}"), for a note.
    label: str = ""
    # The method worked on the digits it writes, and how far their rounding reaches.
    written: tuple[float, float] | None = None


@dataclass(frozen=True)
class CardRead:
    """An unchecked card that states one number: where the number is in the reply, as
    written, the unit after it, the name it gives, and the chain whose value it states."""

    start: int
    end: int
    number: str
    unit_tex: str
    approximate: bool
    since: int
    chain: Chain | None
    # Where the card's fence body ends: the closing lines after it start past it.
    body_end: int = 0
    # The card stands below the formal reader's line: the server's value, not the model's.
    server: bool = False
    # The reply's last card: only the lines after it are its closing summary.
    last: bool = False


@dataclass
class _Env:
    """What the working has worked out so far."""

    question: frozenset[str]
    standard: dict[str, float]
    # A carried number's value and the figures it was written to.
    numbers: dict[str, tuple[float, int]] = field(default_factory=dict)
    clashed: set[str] = field(default_factory=set)
    forms: list[tuple[re.Pattern[str], float]] = field(default_factory=list)
    names: dict[str, list[float]] = field(default_factory=dict)
    # Number keys whose written digits are the value itself: a given, an exact result.
    exact: set[str] = field(default_factory=set)
    # The last chain of each name, and the unit each name was last written in.
    chains: dict[str, Chain] = field(default_factory=dict)

    def carry(self, written: str, value: float) -> None:
        """``written`` stands for ``value`` from now on, unless it is a given or another
        value's digits too."""
        key = key_of(written)
        if key in self.question or key in self.clashed or not _carried(written):
            return
        if key in self.numbers and not math.isclose(self.numbers[key][0], value, rel_tol=1e-9):
            del self.numbers[key]
            self.clashed.add(key)
            return
        self.numbers[key] = (value, figures(written))

    def value_of(self, written: str) -> float | None:
        """The whole value ``written`` stands for: only a number written to as many figures
        as the carried one ("2.00" for 1.998 never makes the 2 of ½ or of 2gh 1.998)."""
        key = key_of(written)
        if key in self.question:
            return None
        if key in self.numbers:
            value, carried = self.numbers[key]
            return value if figures(written) >= carried else None
        return self.standard.get(written)

    def known_name(self, name: str) -> float | None:
        """The one value ``name`` has had, or None when it has had none or several."""
        values = self.names.get(name, [])
        if not values or any(not math.isclose(v, values[0], rel_tol=1e-6) for v in values):
            return None
        return values[0]


def key_of(written: str) -> str:
    """A plain number as a key: "50.560", "(50.56)" and "5.056e1" are one number."""
    try:
        return repr(float(written.strip("()")))
    except ValueError:
        return written


def figures(written: str) -> int:
    """Significant figures as written: "2.00" has 3, "2" and "200" have 1, "0.0417" has 3."""
    digits = written.strip("()-+−").lower().partition("e")[0].replace(".", "").lstrip("0")
    return len(digits.rstrip("0") if "." not in written else digits)


def _carried(written: str) -> bool:
    return figures(written) >= CARRIED_FIGURES


def question_numbers(question: str) -> frozenset[str]:
    """The question's numbers as keys: each is a given, exact as written."""
    found: set[str] = set()
    for match in _QUESTION_NUMBER.finditer(question):
        found.add(key_of(match.group(1)))
        if match.group(2):
            power = match.group(2).translate(_SUPERSCRIPT_DIGITS)
            if re.fullmatch(r"-?\d+", power):
                found.add(key_of(f"{match.group(1)}e{int(power)}"))
    return frozenset(found)


_QUESTION_NUMBER = re.compile(
    r"(?<![\d.])(\d+(?:\.\d+)?)(?:\s*[×x*]\s*10\s*\^?\s*([⁻\-−]?\d+|[⁻⁰¹²³⁴⁵⁶⁷⁸⁹]+))?"
)
_SUPERSCRIPT_DIGITS = str.maketrans("⁻⁰¹²³⁴⁵⁶⁷⁸⁹−", "-0123456789-")


@dataclass
class Reading:
    """What a working works out: its chains, its cards, and the claims its own values do not
    bear out."""

    chains: list[Chain]
    cards: list[CardRead]
    claims: list[Claim]
    # Each given's number as written (a key) and its unit (Pint text), by name.
    givens: dict[str, tuple[str, str]]


@dataclass
class _Walk:
    """Where the walk is: the chain the last statement went on, and each name's formula."""

    current: Chain | None = None
    formulas: dict[str, str] = field(default_factory=dict)


def read_chains(reply: str, question: str = "") -> Reading:
    """Every chain and card of ``reply``'s working, in reading order, and every claim its
    own values contradict (the module docstring)."""
    env = _Env(question_numbers(question), standard_values(reply, question))
    unknowns = solved_for(reply)
    reading = Reading([], [], [], {})
    cards = _cards(reply)
    walk = _Walk()
    for segment, follows, at in math_statement_spans(reply):
        while cards and cards[0][0] < at:
            reading.cards.append(_card_chain(cards.pop(0), reading.chains, walk, env))
        parts, starts = statement_parts(segment, at)
        name = _name_of(parts[0].strip())
        if len(parts) < 2 and not any(char.isdigit() for char in segment):
            # A name said in a sentence ("the wall's force $N_w$") works nothing out.
            continue
        if len(parts) < 2 or _PM.search(segment):
            walk.current = None
        elif not name:
            # A statement of no single name: an equation of numbers solved for one name
            # ("21250 = 241.67\\theta"), or a claim when its sides are the working's values.
            walk.current = _solved(parts, starts, env)
            if walk.current is not None:
                reading.chains.append(walk.current)
                env.names.setdefault(walk.current.name, []).append(walk.current.value)
            else:
                after = _unit_word(reply[at + len(segment) : at + len(segment) + _AFTER])
                reading.claims += claims_in(parts, lambda n: _known(env, n, unknowns), after)
        else:
            _statement(name, parts, starts, follows, env, reading, walk)
    reading.cards += [_card_chain(card, reading.chains, walk, env) for card in cards]
    return reading


def _known(env: _Env, name: str, unknowns: set[str]) -> tuple[float, str] | None:
    """A name's one value and the unit it was written in, for a claim."""
    value = None if name in unknowns else env.known_name(name)
    source = env.chains.get(name)
    if value is None or source is None:
        return None
    return value, source.unit


# How far past the maths a claim's unit may be written: "= 405.5$ J".
_AFTER = 16
_WORD_AFTER = re.compile(r"\$?\s*([A-Za-zΩµ]{1,4})\b")


def _unit_word(after: str) -> str:
    """The unit written in words right after the maths ("$ J,"), as Pint text, or ""; a word
    that is no unit's symbol ("so", "the", "in") is no unit."""
    word = _WORD_AFTER.match(after)
    if word is None or not is_unit_word(word[1]) or word[1] == "in":
        return ""
    return word[1] if quantity_unit(word[1]) is not None else ""


def _statement(
    name: str,
    parts: list[str],
    starts: list[int],
    follows: bool,
    env: _Env,
    reading: Reading,
    walk: _Walk,
) -> None:
    """One statement that works ``name`` out: a new chain, or the last one going on."""
    current = walk.current
    going_on = current is not None and follows and current.name == name and not current.shown
    chain = current if going_on and current is not None and not current.broken else None
    units = _units_ahead(parts)
    for index in range(1, len(parts)):
        part = parts[index].strip()
        if chain is not None:
            _hold(chain, part, units[index], env)
            chain.end = starts[index] + len(part)
            continue
        formula = walk.formulas.get(name, "")
        chain = _start(name, part, units[index], starts[index], env, formula)
        if chain is None and plain_arithmetic(part) is None:
            walk.formulas[name] = part
        elif chain is not None:
            chain.formula, chain.label = formula, parts[0].strip()
            _void_stated(chain, reading.chains, env)
            reading.chains.append(chain)
    if chain is not None:
        env.names.setdefault(name, []).append(chain.value)
        env.chains[name] = chain
        if chain.given and chain is not current:
            unit = unit_after(chain.method)
            reading.givens[name] = (key_of(plain_arithmetic(chain.method) or ""), unit)
    walk.current = chain


def _solved(parts: list[str], starts: list[int], env: _Env) -> Chain | None:
    """An equation of numbers with one name, a number times it on one side ("21250 =
    241.67\\theta", "N_w \\times 6.928 = 686"): a chain of that name, its value the
    equation solved (a card under it states that value). None for anything else: two names,
    a name plus a number ("2.8 = 1.1 + 0.05F" is no product), a name in a power."""
    if len(parts) != 2:
        return None
    for side, other in ((parts[0].strip(), parts[1].strip()), (parts[1].strip(), parts[0].strip())):
        names = names_in(side)
        number = _resolved(other, env)
        if len(names) != 1 or number is None:
            continue
        found = names[0]
        once = f"{side[: found.start()]}(1){side[found.end() :]}"
        twice = _resolved(f"{side[: found.start()]}(2){side[found.end() :]}", env)
        coefficient = _resolved(once, env)
        if coefficient is None or twice is None:
            continue
        values = (evaluate(number[1]), evaluate(coefficient[1]), evaluate(twice[1]))
        if None in values or not values[1] or not math.isclose(values[2] or 0, 2 * values[1]):
            continue
        method = f"\\frac{{{other}}}{{{once}}}"
        whole = f"({number[1]})/({coefficient[1]})"
        reach = _reach(whole, env, number[2] | coefficient[2])
        value = (values[0] or 0.0) / values[1]
        name = plain_name(found.group(0))
        end = starts[-1] + len(parts[-1].rstrip())
        chain = Chain(name, value, "", starts[0], end, method, reach, label=found.group(0))
        chain.written = _written_value(chain, env)
        return chain
    return None


def _void_stated(chain: Chain, chains: list[Chain], env: _Env) -> None:
    """A value the reply stated with no number of the question behind it ("A = 3.142 \\times
    10^{-7}" among its givens) that its own working then works out otherwise (3.142e-6):
    the stated number was a slip, and stands for the worked value from now on. Only a power
    of ten lost or gained, in a value of three figures in the same unit: "t = 205 s" then
    another t, and "m = 100 g" then 0.1 kg, are no slips."""
    for earlier in chains:
        written = plain_arithmetic(earlier.method)
        if earlier.name != chain.name or not earlier.given or written is None:
            continue
        key = key_of(written)
        certain = read_for_certain(earlier.unit) and earlier.unit != ""
        if key in env.question or not _carried(written) or not certain:
            continue
        if chain.unit not in ("", earlier.unit):
            # A given of the question, a small count, or the value in another unit.
            continue
        if not _ten_fold(earlier.value, chain.value):
            # Another value of a name used twice ("t = 205 s", then t of another event).
            continue
        env.numbers[key] = (chain.value, figures(written))
        env.clashed.discard(key)
        earlier.slip = earlier.method
        # Its value is void: the name has the worked one only.
        values = env.names.get(chain.name, [])
        env.names[chain.name] = [v for v in values if not math.isclose(v, earlier.value)]
        earlier.value = chain.value


def _ten_fold(first: float, second: float) -> bool:
    """The two are ten, a hundred, … times apart, within a rounding's slack."""
    if first == 0 or second == 0:
        return False
    power = math.log10(abs(first / second))
    return round(power) != 0 and abs(power - round(power)) < _TEN_FOLD_SLACK


# How near a whole power of ten two values must be (log10): 0.5% either way.
_TEN_FOLD_SLACK = 0.002


def _name_of(head: str) -> str:
    """The name a statement works out ("e", "v_{y}", "K_{rot}"), or "" for no single name."""
    compact = head.replace(" ", "")
    if not compact or NAME.fullmatch(compact) is None:
        return ""
    return plain_name(compact)


def _units_ahead(parts: list[str]) -> list[str]:
    """Each part's unit: its own, else the next part's that writes one, else ""."""
    units = [unit_after(part.strip()) for part in parts]
    ahead = ""
    for index in range(len(parts) - 1, -1, -1):
        ahead = units[index] or ahead
        units[index] = ahead
    return units


def _resolved(
    tex: str, env: _Env, named: dict[str, float] | None = None
) -> tuple[str, str, set[str]] | None:
    """A side as plain arithmetic twice, as written and with each number put back to its
    whole value (a rounded result, a wrong one, a standard value, a name's value put in),
    and the values put in."""
    placed: set[str] = set()
    for pattern, value in env.forms:
        if pattern.search(tex):
            tex = pattern.sub(f"({value!r})", tex)
            placed.add(repr(value))
    plain = plain_arithmetic(tex)
    if plain is None:
        return None
    extra = named or {}

    def whole(match: re.Match[str]) -> str:
        number = match.group(1)
        if _EXPONENT_BEFORE.search(plain[: match.start()]) or number in placed:
            return number
        value = extra.get(key_of(number))
        value = env.value_of(number) if value is None else value
        if value is None or math.isclose(value, float(number), rel_tol=1e-15):
            return number
        placed.add(repr(value))
        return f"({value!r})"

    return plain, _PLAIN_NUMBER.sub(whole, plain), placed


def _reach(plain: str, env: _Env, placed: set[str]) -> float:
    """How far the rounding of the numbers ``plain`` writes reaches: a given, an exact
    result and a whole value put in are exact; any other decimal stands for its rounding."""

    def rounded(text: str) -> bool:
        key = key_of(text)
        return text not in placed and key not in env.question and key not in env.exact

    found = spread(plain, rounded)
    return found if found is not None else math.inf


def _start(name: str, part: str, unit: str, at: int, env: _Env, formula: str) -> Chain | None:
    """A new chain from its first form of numbers; None while the part holds a name."""
    named, misput = _named_inputs(formula, part, env)
    sides = _resolved(part, env, named)
    if sides is None:
        alias = env.known_name(_name_of(part))
        source = env.chains.get(_name_of(part))
        if alias is None or source is None:
            return None
        chain = Chain(name, alias, unit or source.unit, at, at + len(part), part, source.reach)
        chain.written = source.written
        return chain
    written, whole, placed = sides
    value = evaluate(whole)
    if value is None:
        return None
    chain = Chain(name, value, unit, at, at + len(part), part, _reach(whole, env, placed))
    chain.written = _written_value(chain, env)
    chain.slip = part if misput else ""
    if not _worked(written):
        chain.given, chain.reach, chain.shown = True, 0.0, part
        if key_of(written) in env.question:
            # Only the question's own numbers are exact as written; a value the reply states
            # (1.309 rad for 75°) stands for its rounding.
            env.exact.add(key_of(written))
    return chain


def _worked(plain: str) -> bool:
    """A plain side with an operation: a worked form, not a number."""
    return OPERATOR.search(plain.lstrip("-+").replace("e-", "e")) is not None


def _named_inputs(formula: str, method: str, env: _Env) -> tuple[dict[str, float], bool]:
    """Each number the method puts in for a name of its formula that rounds the name's
    value: that value ("\\frac{2\\pi}{1.087 \\times 10^{-3}}" for "\\frac{2\\pi}{\\omega}"); and
    whether one was put in a power of ten off it ("6.245 \\times 10^7" for sigma = 6.245e6),
    a slip the method's value is worked without."""
    found: dict[str, float] = {}
    misput = False
    for name, number in (aligned_names(formula, method) or {}).items():
        value = env.known_name(name)
        if value is None or not _carried(number) or key_of(number) in env.question:
            continue
        source = env.chains.get(name)
        unit = source.unit if source is not None else ""
        si = in_base_units(abs(value), unit)
        for whole in (abs(value), si):
            if whole is not None and abs(whole - float(number)) <= half_place(number) * (1 + 1e-9):
                found[key_of(number)] = whole
                break
        else:
            # 632.8 nm put in as 632.8 × 10⁻⁹ is the value in metres; a power of ten off is a
            # slip only where the value's own unit is its SI one (6.245e7 for 6.245e6 Pa).
            if si is not None and math.isclose(si, abs(value)) and _ten_fold(si, float(number)):
                found[key_of(number)] = si
                misput = True
    return found, misput


def _hold(chain: Chain, part: str, unit: str, env: _Env) -> None:
    """Hold one more form or number of ``chain`` to its value (the module docstring)."""
    if unit != chain.unit and unit and chain.unit:
        # A unit not read for certain (rad, rev/min, °C, %) is never held to another.
        if not _convert(chain, unit):
            chain.broken = True
            return
    elif unit and not chain.unit:
        chain.unit = unit
    sides = _resolved(part, env)
    if sides is None:
        return
    written, whole, placed = sides
    value = evaluate(whole)
    if value is None:
        return
    if not _worked(written):
        _hold_number(chain, part, written, env)
        return
    reach = _reach(whole, env, placed)
    if abs(value - chain.value) <= (reach + chain.reach) * (1 + 1e-9) + 1e-12 * abs(chain.value):
        return
    pattern = _form_pattern(part)
    if pattern is not None:
        env.forms.append((pattern, chain.value))
    as_written, raw = evaluate(written), chain.written
    if as_written is not None and raw is not None:
        if abs(as_written - raw[0]) <= raw[1] + _reach(written, env, set()):
            # Right on the rounded numbers the method wrote ("\\tan 10° ≈ 0.1763"): drift.
            chain.drift = chain.drift or part
            return
    chain.slip = chain.slip or part


def _hold_number(chain: Chain, part: str, written: str, env: _Env) -> None:
    """A plain number the chain shows: within its own rounding of the chain's value, or
    drift (right on the rounded inputs the line wrote), or a slip."""
    shown = shown_number(written)
    value = evaluate(written)
    if shown is None or value is None:
        return
    chain.shown = part
    env.carry(written, chain.value)
    off = abs(value - chain.value)
    if off <= (shown[1] + chain.reach) * (1 + 1e-9) + 1e-12 * abs(chain.value):
        if math.isclose(value, chain.value, rel_tol=1e-12):
            env.exact.add(key_of(written))
        return
    raw = chain.written
    if raw is not None and abs(value - raw[0]) <= (shown[1] + raw[1]) * (1 + 1e-9):
        chain.drift = chain.drift or part
        return
    chain.slip = chain.slip or part


def _written_value(chain: Chain, env: _Env) -> tuple[float, float] | None:
    """The method worked on the digits it writes, with how far their rounding reaches: a
    given and an exact result are exact, any other decimal stands for its rounding."""
    plain = plain_arithmetic(chain.method)
    if plain is None:
        return None
    value = evaluate(plain)

    def rounded(text: str) -> bool:
        return "." in text and key_of(text) not in env.question and key_of(text) not in env.exact

    reach = spread(plain, rounded)
    if value is None or reach is None:
        return None
    return value, reach


def _convert(chain: Chain, unit: str) -> bool:
    """``chain`` goes on in ``unit``: its value converted, when Pint reads both units."""
    before, after = quantity_unit(chain.unit), quantity_unit(unit)
    if before is None or after is None:
        return False
    value = converted(chain.value, before, after)
    if value is None:
        return False
    if not same_unit(before, after):
        chain.reach = abs(converted(chain.reach, before, after) or 0.0)
        chain.value = value
    chain.unit = unit
    return True


def _form_pattern(part: str) -> re.Pattern[str] | None:
    """A wrong form, as a later line may write it again (its tokens, any spacing): only one
    with an operation and a number of three figures, never a bare number or a name."""
    plain = plain_arithmetic(part)
    if plain is None or not _worked(plain):
        return None
    if not any(_carried(number) for number in _PLAIN_NUMBER.findall(plain)):
        return None
    tokens = [token for token in _TOKEN.findall(part) if token not in _SPACING]
    if len(tokens) < CARRIED_FIGURES:
        return None
    return re.compile(r"(?:\s|\\[,;: !])*".join(re.escape(token) for token in tokens))


def _cards(reply: str) -> list[tuple[int, CardRead, str]]:
    """Each unchecked card stating one number, with where its fence starts and the name it
    gives ("" for none), in order; its chain is found as the walk reaches it."""
    from app.modules.chat.formal_lines import server_valued

    found: list[tuple[int, CardRead, str]] = []
    every = list(answer_cards(reply))
    last_start = every[-1].fence.start if every else -1
    for answer in every:
        body = answer.body(reply)
        read = card_value(body)
        if read is None or VERIFIED_ANSWER_MARKER in body:
            continue
        symbol, number_tex, approximate = read
        number = _CARD_NUMBER.match(number_tex)
        if number is None or not _ONLY_UNIT.match(number_tex[number.end() :]):
            continue
        at = answer.fence.body_start + body.rfind(number_tex)
        if reply[at : at + number.end()] != number.group(0):
            continue
        server = server_valued(reply[answer.since_card : answer.fence.start])
        card = CardRead(
            at,
            at + number.end(),
            number.group(0),
            number_tex[number.end() :],
            approximate,
            answer.since_card,
            None,
            answer.fence.body_end,
            server,
            answer.fence.start == last_start,
        )
        found.append((answer.fence.start, card, plain_name(symbol)))
    return found


def _card_chain(
    card: tuple[int, CardRead, str], chains: list[Chain], walk: _Walk, env: _Env
) -> CardRead:
    """The card with the chain it states: the last of its part it names, or else the
    working's last maths before it; its number then stands for that chain's value."""
    fence_start, read, symbol = card
    part = [chain for chain in chains if read.since <= chain.start and chain.end <= fence_start]
    chain: Chain | None = None
    if symbol:
        named = [each for each in part if each.name == symbol]
        chain = named[-1] if named else None
    elif part and part[-1] is walk.current:
        chain = part[-1]
    if chain is None or chain.broken or chain.given:
        return read
    plain = plain_arithmetic(read.number.replace("−", "-"))
    if plain is not None:
        env.carry(plain.strip("()"), chain.value)
    return CardRead(
        read.start,
        read.end,
        read.number,
        read.unit_tex,
        read.approximate,
        read.since,
        chain,
        read.body_end,
        read.server,
        read.last,
    )
