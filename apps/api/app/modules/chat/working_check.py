"""Check the arithmetic in working the model wrote itself.

A reply the server could not verify still shows its working, and a slip in one
multiplication carries into the answer. This reads each ``$...$`` line of the
reply, keeps the equalities whose two sides are plain numbers once units are
dropped (``$3\\,\\text{m/s}^2 \\times 5\\,\\text{s} = 15\\,\\text{m/s}$`` checks
``3 * 5 = 15``), and recomputes the left side. A step is wrong only when its
shown value is off by more than its own rounding and more than the slack a rounding
chain has: 1%, or less where the inputs' own rounding cannot reach that far
(``tex_spread``). Models round as they go, and ``9.81 * 2.02 = 19.8`` is right;
``\\sqrt{1088.5} = 33.11`` is not, though only 0.4% off.

Roots, sines, cosines and tangents (of degrees or radians), logs, e, pi, powers of ten
and the ± of a quadratic are read; a variable, a percent or a word is left alone. Pure
text work with a small expression walker: nothing is ``eval``-ed, and powers are capped,
so a reply cannot make the server compute a huge number. ``working_fix`` puts a wrong
number right and carries it on.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field, replace

from app.modules.chat.tex_arithmetic import (
    UNIT_GROUP,
    evaluate,
    log_readings,
    math_statement_spans,
    plain_arithmetic,
    plain_branches,
)
from app.modules.chat.tex_spread import half_place, spread
from app.modules.chat.working_align import Piece, pieces
from app.modules.chat.working_numbers import shown_like, shown_number
from app.modules.chat.working_systems import unheld_equations

# A result in a prefixed unit the working did not use (7200 m = 7.2 km, 4.52e6 J = 4.5 MJ)
# is a conversion, not arithmetic to check.
_PREFIXED_UNIT = re.compile(r"\\(?:text|mathrm)\s*\{\s*([kMGmµμnpc][A-Za-z]+)")
# Units that only start with a prefix's letter: "4 g / 2.016 g/mol = 1.984 mol" is a division,
# never a step to millis.
_NOT_PREFIXED = frozenset({"mol", "min", "mph", "mmHg", "cal", "cd", "mi", "mile", "miles"})
OPERATOR = re.compile(r"[-+*/]|sqrt|abs|pi|sind|cosd|tand|rsin|rcos|rtan|ln|lg|lbin|exp|euler")
RELATION = re.compile(r"\\approx|≈|=")
# Models round as they go: a step within 1% of its value is not called a slip.
_RELATIVE_SLACK = 0.01


@dataclass(frozen=True)
class Fix:
    """The wrong number at ``start:end`` of the reply, and the value it stands for."""

    start: int
    end: int
    number: str
    value: float


@dataclass(frozen=True)
class WrongStep:
    """``left`` as written, the value shown after it, and what it really is. ``fixes``: the
    numbers to write again, where the step can be put right in place (none when its right
    side is another exact form); ``name``: what the step works out ("t"), or ""."""

    left: str
    shown: str
    value: float
    fixes: tuple[Fix, ...] = ()
    name: str = ""


def _converts_unit(left_tex: str, right_tex: str) -> bool:
    """The result is in a prefixed unit the working never wrote, or in another unit of a
    measure the working wrote in: "π rad = 180°", "4.8e-19 J = 3 eV" (review, #2520)."""
    left_units = set(_PREFIXED_UNIT.findall(left_tex))
    prefixed = (unit for unit in _PREFIXED_UNIT.findall(right_tex) if unit not in _NOT_PREFIXED)
    if any(unit not in left_units for unit in prefixed):
        return True
    left_kinds, right_kinds = _unit_kinds(left_tex), _unit_kinds(right_tex)
    return any(
        kind in left_kinds and left_kinds[kind] != units for kind, units in right_kinds.items()
    )


# Units of one measure a working converts between, by the measure.
_KINDS: dict[str, frozenset[str]] = {
    "angle": frozenset({"rad", "deg", "°", "\\circ", "degrees", "radians"}),
    "energy": frozenset({"J", "kJ", "MJ", "GJ", "eV", "keV", "MeV", "cal", "kcal", "Wh", "kWh"}),
    "time": frozenset({"s", "ms", "min", "hr", "h", "minutes", "hours", "seconds"}),
    "length": frozenset({"m", "cm", "mm", "km", "nm", "ft", "in", "mi"}),
}
_UNIT_TOKEN = re.compile(r"\\(?:text|mathrm)\s*\{([^{}]*)\}|(°|\\circ)")


def _unit_kinds(tex: str) -> dict[str, frozenset[str]]:
    """The units a side writes, by the measure each is of."""
    found: dict[str, set[str]] = {}
    for match in _UNIT_TOKEN.finditer(tex):
        unit = (match.group(1) or match.group(2) or "").strip()
        for kind, units in _KINDS.items():
            if unit in units:
                found.setdefault(kind, set()).add(unit)
    return {kind: frozenset(units) for kind, units in found.items()}


# "≈ 4.5 MJ" after 4.52e6 J with the unit outside the maths: a prefix step, not a slip.
_PREFIX_POWERS = (2, 3, 6, 9, 12)


def _prefix_shift(value: float, shown: float) -> bool:
    if value == 0 or shown == 0 or (value > 0) != (shown > 0):
        return False
    ratio = abs(value / shown)
    return any(
        math.isclose(ratio, 10.0**power, rel_tol=0.02)
        or math.isclose(ratio, 10.0**-power, rel_tol=0.02)
        for power in _PREFIX_POWERS
    )


# A decimal in a plain side (0.36, 3.98e-19), not a power's exponent.
DECIMAL = re.compile(r"(?<![\d.])(?<!\*\*)(?<!\*\*\()\d+\.\d+(?:e[-+]?\d+)?")


def _exact_side(plain: str, rounded: dict[str, float]) -> str:
    """``plain`` with each earlier rounded result in it put back to its exact value.

    A line built on a rounded result may carry the exact one: "2 * 0.36 = 0.71" is right
    when 0.36 was 0.357, and was flagged "0.72, not 0.71" (2026-10-30, a long-jump answer).
    A given is exact as written, so "3.2 * 4.5 = 14.8" is still a slip; a whole number or
    an exponent is never taken for a rounded result (the "2" of "3^2" after "9/4 = 2")."""
    return DECIMAL.sub(
        lambda m: f"({rounded[m.group(0)]!r})" if m.group(0) in rounded else m.group(0), plain
    )


def _is_wrong(
    value: float, shown: float, rounding: float, approximate: bool, spread: float | None = None
) -> bool:
    """``shown`` is off ``value`` by more than its own rounding and more than the slack a
    rounding chain has: 1%, or only as far as the inputs' own rounding reaches (``spread``,
    ``tex_spread``) when that is less. "\\sqrt{1088.5} = 33.11" is 0.4% off but no rounding
    of 1088.5 moves its root past 32.99 (live, 2026-11-23)."""
    if _prefix_shift(value, shown):
        return False
    difference = abs(value - shown)
    factor = 2 if approximate else 1
    slack = _RELATIVE_SLACK * factor * max(abs(value), abs(shown))
    if spread is not None:
        slack = min(slack, factor * spread)
    return difference > rounding * (1 + 1e-9) and difference > slack * (1 + 1e-9)


# A name a step solves for or a given names: t, v_1, t_{\text{flight}}, \mu, \theta_1.
NAME = re.compile(r"(?:\\[A-Za-z]+|[A-Za-z])(?:_\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}|_\w)?")


@dataclass
class _Memory:
    """What the working has shown so far: each rounded result with its exact value, each
    name's exact value from its expression, and every number written as a step's result."""

    rounded: dict[str, float] = field(default_factory=dict)
    worked: dict[str, float] = field(default_factory=dict)
    results: set[str] = field(default_factory=set)
    # Where a given is written: the question, and the givens the working stated so far.
    question: str = ""
    givens: set[str] = field(default_factory=set)

    def stands_for_a_range(self, number: str) -> bool:
        """A number that may be rounded: anything but a given. Only the question's numbers, a
        given the working states ("g = 9.8") and a coefficient of its equation ("4.9t^2")
        are exact as written; a number the reply worked out, in prose ("cos 30° ≈ 0.87"),
        display maths or a step, stands for its rounding (review, #2576)."""
        key = _key(number)
        given = key in self.givens_and_question()
        return key in self.results or key in self.rounded or not given

    def givens_and_question(self) -> set[str]:
        return self.givens | set(_DECIMAL_NUMBER.findall(self.question))

    def note_givens(self, parts: list[str]) -> None:
        """A statement's givens: "m = 3.2 kg", and each coefficient of an equation ("4.9" of
        "4.9t^2 - 14.34t - 45 = 0")."""
        name, *values = (part.strip() for part in parts)
        if len(values) == 1 and NAME.fullmatch(name.replace(" ", "")):
            number = _LEADING_NUMBER.fullmatch(_UNIT_TAIL.sub("", values[0]).strip())
            if number is not None and name.replace(" ", "") not in self.worked:
                self.givens.add(_key(plain_arithmetic(number.group(0)) or ""))
        for part in parts:
            self.givens.update(_COEFFICIENT.findall(part))


# A decimal as the question writes it, and one written before a letter in maths ("4.9t").
_DECIMAL_NUMBER = re.compile(r"(?<![\d.])\d+\.\d+(?![\d])")
_COEFFICIENT = re.compile(r"(?<![\d.])(\d+\.\d+)\s*(?=[A-Za-z])")
# A unit after a given's number: "\\ \\text{m/s}^2", "\\,\\mathrm{kg}".
_UNIT_TAIL = re.compile(r"(?:\\[,; ]|\s)*\\(?:text|mathrm)\s*\{[^{}]*\}(?:\^\{?-?\d\}?)?\s*$")


def _key(plain: str) -> str:
    """A plain number as the rounded results are kept: "(1.5e24)" is 1.5e24 (review, #2576)."""
    return plain.strip("()")


def _note_rounded(left_tex: str, left: str | None, right: str | None, memory: _Memory) -> None:
    """Record a result written rounded: within half its last place of a step's exact value
    ("3.5/9.8 = 0.36", "0.357 ≈ 0.36", or "t = 3.5/9.8" and then "t = 0.36"). A given
    ("m = 3.2"), an exact result ("6/30 = 0.2") and a name reused for a new value are not."""
    rounded, worked = memory.rounded, memory.worked
    if right is None:
        return
    shown, key = shown_number(right), _key(right)
    exact: float | None = None
    if left is not None:
        exact = evaluate(_exact_side(left, rounded))
    elif NAME.fullmatch(name := left_tex.replace(" ", "")):
        if shown is None:
            if (value := evaluate(_exact_side(right, rounded))) is not None:
                worked[name] = value
            return
        if name not in worked:
            # A given ("mu = 0.3"): the same digits after it are this value, not a rounding.
            rounded.pop(key, None)
            return
        exact = worked.get(name)
    if exact is None or shown is None:
        return
    memory.results.add(key)
    off = abs(exact - shown[0])
    if 0 < off <= shown[1] * (1 + 1e-9) and not math.isclose(exact, shown[0], rel_tol=1e-12):
        rounded[key] = exact


def statement_parts(segment: str, at: int) -> tuple[list[str], list[int]]:
    """A statement's sides around its relations, and where each starts (spaces off) in the
    reply."""
    bounds = [0, *(edge for match in RELATION.finditer(segment) for edge in match.span())]
    bounds.append(len(segment))
    parts = [segment[bounds[i] : bounds[i + 1]] for i in range(0, len(bounds), 2)]
    starts = [at + bounds[2 * i] + len(part) - len(part.lstrip()) for i, part in enumerate(parts)]
    return parts, starts


def wrong_steps(reply: str, question: str = "") -> list[WrongStep]:
    """The steps in ``reply`` whose arithmetic does not hold, in reading order; a number of
    the ``question`` is a given, exact as written."""
    found: list[WrongStep] = []
    memory = _Memory(question=question)
    last = ""
    # The line before: the name it worked out, its last expression and its first value.
    before: _Line | None = None
    for segment, follows, at in math_statement_spans(reply):
        if not follows:
            # Words between two lines ("**(b)**", "For the second resistor,") start another
            # case: a name reused there is another value (review, #2520).
            before = None
        parts, starts = statement_parts(segment, at)
        relations = RELATION.findall(segment)
        if len(parts) > 1 and not parts[0].strip():
            # "$= 0.36$" goes on from the line before.
            parts[0] = last
        last = parts[-1]
        before = _chain(parts, relations, starts, before, found, memory)
        name = parts[0].strip() if NAME.fullmatch(parts[0].replace(" ", "")) else ""
        for index in range(len(parts) - 1):
            left_tex, right_tex = parts[index].strip(), parts[index + 1].strip()
            left, right = plain_arithmetic(left_tex), plain_arithmetic(right_tex)
            _note_rounded(left_tex, left, right, memory)
            if right is None or left == right:
                continue
            step = _slip_branches(left_tex, right_tex, relations[index] != "=", memory)
            if step is not None:
                found.append(_placed(step, starts[index + 1], name))
        memory.note_givens(parts)
    return found


def _placed(step: WrongStep, start: int, name: str) -> WrongStep:
    """``step`` with its fixes at their place in the reply, and the name its result is of."""
    fixes = tuple(replace(fix, start=fix.start + start, end=fix.end + start) for fix in step.fixes)
    whole = len(fixes) == 1 and step.fixes[0].start == 0 and step.name == _RESULT
    return replace(step, fixes=fixes, name=name if whole else "")


# A step whose fix writes its whole result (``WrongStep.name`` until it is placed).
_RESULT = "\0result"


def _slip_branches(
    left_tex: str,
    right_tex: str,
    approximate: bool,
    memory: _Memory,
    first: list[tuple[float, float | None]] | None = None,
) -> WrongStep | None:
    """``slip`` for a side that may hold a ± (the two roots of a quadratic): it holds when
    either root does, and a wrong one is put right to the root it was nearest."""
    branches = plain_branches(left_tex)
    right = plain_arithmetic(right_tex)
    if branches is None or right is None:
        return None
    _note_pieces(left_tex, right_tex, memory)
    sign = _PLUS_MINUS.search(left_tex)
    if sign is not None and not _ROOTS.search(left_tex):
        # "2.50 \\pm 0.05" is a value and its uncertainty, not two roots (review, #2576).
        return None
    if sign is None or len(branches) == 1:
        return slip(
            left_tex,
            right_tex,
            branches[0],
            right,
            approximate,
            memory.rounded,
            memory=memory,
            first=first,
        )
    signs = ("+", "-") if sign.group(0) in ("\\pm", "\u00b1") else ("-", "+")
    steps: list[WrongStep] = []
    for mark, plain in zip(signs, branches, strict=True):
        branch_tex = f"{left_tex[: sign.start()]}{mark}{left_tex[sign.end() :]}"
        step = slip(
            branch_tex,
            right_tex,
            plain,
            right,
            approximate,
            memory.rounded,
            memory=memory,
            first=first,
        )
        if step is None:
            return None
        steps.append(step)
    fixable = [step for step in steps if step.fixes] or steps
    shown = shown_number(right)
    target = shown[0] if shown is not None else 0.0
    best = min(fixable, key=lambda step: abs(step.value - target) if shown else 0.0)
    return replace(best, left=left_tex)


_PLUS_MINUS = re.compile(r"\\pm|\\mp|\u00b1|\u2213")
# What makes a ± side two roots: a root or a fraction (the quadratic formula).
_ROOTS = re.compile(r"\\sqrt|\\[dt]?frac|/")


def _note_pieces(left_tex: str, right_tex: str, memory: _Memory) -> None:
    """Each number the later side writes for a piece of the earlier is a result: "33.11"
    for the root, rounded when it is within half its last place of it."""
    sides = plain_branches(left_tex)
    if sides is None or len(sides) != 1:
        return
    for piece in pieces(left_tex, right_tex) or []:
        number = plain_arithmetic(piece.number)
        shown = shown_number(number or "")
        if number is None or shown is None:
            continue
        memory.results.add(_key(number))
        if 0 < abs(piece.value - shown[0]) <= shown[1] * (1 + 1e-9):
            memory.rounded[_key(number)] = piece.value


def slip(
    left_tex: str,
    right_tex: str,
    left: str,
    right: str,
    approximate: bool,
    rounded: dict[str, float],
    *,
    memory: _Memory | None = None,
    first: list[tuple[float, float | None]] | None = None,
) -> WrongStep | None:
    """``left = right`` when it does not hold: a worked side (an operation or a function) and
    what it is said to equal, a written result or another exact form (√11375 = 25√73).
    ``first``: the values the same name had on the first line of its working; a result that
    keeps one of them is no slip, though the line before it rounded too coarsely."""
    # A number in powers of ten is one number: "7.36 * 10^-20 J = 0.459 eV" converts a unit.
    if OPERATOR.search(_SCIENTIFIC_PLAIN.sub("1", left).lstrip("-+")) is None:
        return None
    readings = log_readings(left)
    if not readings:
        return None
    memory = memory or _Memory(rounded=rounded)
    shown = shown_number(right, coarse=approximate)
    # Arithmetic only: "7200 m = 7.2 km" restates a value in another unit.
    if shown is not None and _converts_unit(left_tex, right_tex):
        return None
    if shown is None:
        return _between_forms(left_tex, right_tex, left, right, approximate, memory)
    # A side of exact numbers (√65/8, 10 sin 45°/sin 75°) is held to the shown value's own
    # rounding: "≈ 0.999" for 1.0078 is a slip, though under 1%.
    if DECIMAL.search(left) is None:
        if all(is_off(value, shown[0], shown[1]) for value in readings):
            return _result_step(left_tex, right_tex, _nearest(readings, shown[0]))
        return None
    if not all(
        _is_wrong(
            value,
            shown[0],
            shown[1],
            approximate,
            spread(left, memory.stands_for_a_range, natural_log=index > 0),
        )
        for index, value in enumerate(readings)
    ):
        return None
    carried_side = _exact_side(left, {k: v for k, v in memory.rounded.items() if k != _key(right)})
    carried = evaluate(carried_side)
    if carried is not None and not _is_wrong(
        carried, shown[0], shown[1], approximate, spread(carried_side, memory.stands_for_a_range)
    ):
        return None
    if any(
        not _is_wrong(value, shown[0], shown[1], approximate, reach) for value, reach in first or []
    ):
        return None
    return _result_step(left_tex, right_tex, _nearest(readings, shown[0]))


def _nearest(values: list[float], shown: float) -> float:
    return min(values, key=lambda value: abs(value - shown))


# The number a result is written as, at the start of its side: 4.85, -1.9, 1,500,
# 1.5 \times 10^{24}.
_LEADING_NUMBER = re.compile(
    r"[-\u2212]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
    r"(?:\s*(?:\\times|\\cdot|\u00d7)\s*10\s*\^\s*(?:\{\s*[-+\u2212]?\d+\s*\}|[-+]?\d))?"
)


def _result_step(left_tex: str, right_tex: str, value: float) -> WrongStep:
    """A wrong result, with the fix that writes it again when it is a plain number."""
    number = _LEADING_NUMBER.match(right_tex)
    # The number must be the whole result read: "1{,}850" is not 1 (review, #2576).
    if number is None or plain_arithmetic(number.group(0)) != plain_arithmetic(right_tex):
        return WrongStep(left_tex, right_tex, value)
    fix = Fix(0, number.end(), number.group(0), value)
    return WrongStep(left_tex, right_tex, value, (fix,), _RESULT)


def _between_forms(
    left_tex: str, right_tex: str, left: str, right: str, approximate: bool, memory: _Memory
) -> WrongStep | None:
    """Two worked forms held equal. When the later writes pieces of the earlier as numbers
    (``working_align``), each piece is held to its number; otherwise the whole sides. A log
    with no base has two readings (``log_readings``), so such forms are not held (review,
    #2576: "log 2 / 0.05" is 13.86 read as ln)."""
    if _UNBASED_LOG in left or _UNBASED_LOG in right:
        return None
    value = evaluate(left)
    if value is None:
        return None
    # Two sides in different units substitute or convert ("0.98c * 11 μs = 0.98 *
    # 299,792,458 m/s * 11 * 10^-6 s"): no arithmetic to hold them to.
    units = (_units(left_tex), _units(right_tex))
    if all(units) and units[0] != units[1]:
        return None
    other = evaluate(right)
    if other is not None and math.isclose(value, other, rel_tol=1e-9, abs_tol=1e-12):
        # The same value in another form: "\\frac{17 \\times 25 \\times 28}{4 \\times 210}"
        # is 85/6, a fraction cancelled, not two slips.
        return None
    found = pieces(left_tex, right_tex)
    if found is not None:
        fixes = tuple(
            Fix(piece.start, piece.end, piece.number, piece.value)
            for piece in found
            if _piece_wrong(piece, approximate, memory)
        )
        return WrongStep(left_tex, right_tex, value, fixes) if fixes else None
    # Another exact form ("25√73"), or a product of rounded values ("32.61 * 0.9659").
    if other is None or (DECIMAL.search(right) is not None and DECIMAL.search(left) is None):
        return None
    # Two exact forms held equal must be equal; one only said to be near ("pi ≈ 22/7",
    # "sqrt(2) ≈ 7/5") is held to the slack an approximation has (review, #2520).
    exact = DECIMAL.search(left) is None and DECIMAL.search(right) is None and not approximate
    if exact and not math.isclose(value, other, rel_tol=1e-6, abs_tol=1e-9):
        return WrongStep(left_tex, right_tex, value)
    if not exact and _is_wrong(value, other, 0.0, approximate):
        return WrongStep(left_tex, right_tex, value)
    return None


def _piece_wrong(piece: Piece, approximate: bool, memory: _Memory) -> bool:
    """The number written for a piece is not its value: a worked piece (a root, a product) is
    held as a step is; a number written again ("14.339" as "14.34") to its rounding."""
    tex, number = piece.tex, piece.number
    plain, written = plain_arithmetic(tex), plain_arithmetic(number)
    if plain is None or written is None:
        return False
    if OPERATOR.search(_SCIENTIFIC_PLAIN.sub("1", plain).lstrip("-+")) is not None:
        return (
            slip(tex, number, plain, written, approximate, memory.rounded, memory=memory)
            is not None
        )
    shown = shown_number(written, coarse=approximate)
    reach = half_place(plain) if "." in plain and memory.stands_for_a_range(plain) else 0.0
    return shown is not None and _is_wrong(piece.value, shown[0], shown[1], approximate, reach)


# A log with no base written, as a plain side calls it.
_UNBASED_LOG = "lgx("
_SCIENTIFIC_PLAIN = re.compile(r"\(?-?\d+(?:\.\d+)?e[-+]?\d+\)?")


def _units(tex: str) -> tuple[str, ...]:
    """The unit groups a side writes, in order ("\\mathrm{m/s}", "\\text{cm}^2")."""
    return tuple(sorted("".join(group.split()) for group in UNIT_GROUP.findall(tex)))


def is_off(value: float, shown: float, rounding: float) -> bool:
    """``shown`` is not ``value`` written to its own places."""
    return not _prefix_shift(value, shown) and abs(value - shown) > rounding * (1 + 1e-6) + 1e-12


def _branches(earlier: str, later: str) -> bool:
    """Two values of one name, not one value written twice: the ± roots ("(4 + 2)/2" then
    "(4 - 2)/2"), the same expression with one sign turned. A line after a ± is held to
    the root it is nearest (``_slip_branches``)."""
    signs = str.maketrans({"+": "±", "-": "±", "\u2212": "±"})
    return earlier.translate(signs).replace(" ", "") == later.translate(signs).replace(" ", "")


@dataclass(frozen=True)
class _Line:
    """A line that worked a name out: its last expression, its last worked side, and the
    values the name had on the first line of its working."""

    name: str
    expression: str
    worked: str
    first: list[tuple[float, float | None]]


def _chain(
    parts: list[str],
    relations: list[str],
    starts: list[int],
    before: _Line | None,
    found: list[WrongStep],
    memory: _Memory,
) -> _Line | None:
    """The same name worked out on two lines in a row must keep its value: "L = √(6·14·28·48)/21"
    then "L = √279552/21" (live, 2026-11-21: the chord came out 25.19 cm, not 16). Only a line
    worked from an expression is held: "x = 1" then "x = 3" are two roots."""
    name = parts[0].strip()
    if len(parts) < 2 or not name or plain_branches(name) is not None:
        return None
    # A line that reached its value ("P = 2^2 * 5 = 20") is done: the same name next is
    # another case ("P = 3^2 * 5 = 45"), never the same value carried on (review, #2520).
    first_tex = parts[1].strip()
    if (
        before is not None
        and before.name == name
        and before.expression == before.worked
        and not _branches(before.expression, first_tex)
        and _restates_side(before.expression, first_tex)
    ):
        step = _slip_branches(
            before.expression, first_tex, relations[0] != "=", memory, first=before.first
        )
        if step is not None:
            found.append(_placed(step, starts[1], name if NAME.fullmatch(name) else ""))
    worked = [part.strip() for part in parts[1:] if plain_branches(part.strip()) is not None]
    exprs = [part for part in worked if _worked_out(part)]
    if not exprs:
        return None
    if before is not None and before.name == name and before.first:
        first = before.first
    else:
        first = _values(exprs[0], memory)
    return _Line(name, exprs[-1], worked[-1], first)


def _worked_out(tex: str) -> bool:
    """The side has an operation or a function to work out."""
    return any(
        OPERATOR.search(_SCIENTIFIC_PLAIN.sub("1", side).lstrip("-+"))
        for side in plain_branches(tex) or []
    )


def _values(tex: str, memory: _Memory) -> list[tuple[float, float | None]]:
    """Each value a worked side has (two for a ±), with how far rounding may move it."""
    values: list[tuple[float, float | None]] = []
    for side in plain_branches(tex) or []:
        exact = _exact_side(side, memory.rounded)
        value = evaluate(exact)
        if value is not None:
            values.append((value, spread(exact, memory.stands_for_a_range)))
    return values


def _restates_side(earlier: str, later: str) -> bool:
    """``_restates`` for two sides as written, each read as its first branch."""
    first, second = plain_branches(earlier), plain_branches(later)
    return first is not None and second is not None and _restates(first[0], second[0])


_NUMBER_TOKEN = re.compile(r"\d+(?:\.\d+)?")


def _restates(earlier: str, later: str) -> bool:
    """``later`` is ``earlier`` in another form, not another value in the same form: two roots
    or two circles written alike ("(4+2)/2" then "(4-2)/2", "pi(3)^2" then "pi(5)^2") differ
    only in their numbers (review, #2520)."""
    return _NUMBER_TOKEN.sub("#", earlier) != _NUMBER_TOKEN.sub("#", later)


# A worked solution: its equalities are claims, not a quiz ("is 3 * 4 = 13?"). The
# indent is ``[^\S\n]*``, not ``\s*``: from each line start ``\s*`` ran over every blank
# line below it, quadratic in a run of them, and found no heading the next start misses.
# "**Answer:**" with its colon inside the bold is the same heading (textbook round,
# 2026-11-26: a capillary rise worked to 2.03 mm under it had no card).
_WORKOUT_HEADING = re.compile(
    r"^[^\S\n]*\*\*(?:Substitution|Steps|Answer|Working|\d+\.[^*\n]+):?\*\*", re.MULTILINE
)


def is_worked_solution(reply: str) -> bool:
    return _WORKOUT_HEADING.search(reply) is not None


def working_note(reply: str, question: str = "") -> str | None:
    """One line naming the first slip, or None when the working adds up."""
    steps = wrong_steps(reply, question)
    if not steps:
        unheld = unheld_equations(reply)
        if not unheld:
            return None
        values = ", ".join(
            f"{name} = {shown_like(value, '0.00')}" for name, value in unheld[0].values.items()
        )
        return (
            f"Check these values: ${values}$ do not satisfy ${unheld[0].equation}$. "
            "The answer depends on them."
        )
    return step_note(steps[0])


def step_note(step: WrongStep) -> str:
    """The line that names ``step``: its value, and the number it was written as."""
    right = shown_like(step.value, step.shown)
    return (
        f"Check this step: ${step.left} = {right}$, not ${step.shown}$. "
        "The lines after it depend on it."
    )
