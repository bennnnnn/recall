"""Check the arithmetic in working the model wrote itself.

A reply the server could not verify still shows its working, and a slip in one
multiplication carries into the answer. This reads each ``$...$`` line of the
reply, keeps the equalities whose two sides are plain numbers once units are
dropped (``$3\\,\\text{m/s}^2 \\times 5\\,\\text{s} = 15\\,\\text{m/s}$`` checks
``3 * 5 = 15``), and recomputes the left side. A step is wrong only when its
shown value is off by more than its own rounding and more than 1%: models round
as they go, and ``9.81 * 2.02 = 19.8`` is right.

Anything with a variable, a function, a percent or a degree sign is left alone.
Pure text work with a small expression walker: nothing is ``eval``-ed, and
powers are capped, so a reply cannot make the server compute a huge number.
"""

from __future__ import annotations

import ast
import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from decimal import InvalidOperation

from app.services.glyphs import fold_operator_glyphs
from app.services.md_fence_scan import iter_fences, map_fence_blocks
from app.services.school_rounding import round_places

_INLINE_CODE = re.compile(r"`[^`\n]*`")
# A written result: 14.8, -3, or 1.204 * 10^24 once it is plain text.
_SHOWN = re.compile(
    r"\(?(?P<mantissa>-?\d+(?:\.(?P<decimals>\d+))?)"
    r"(?:(?:\*10\*\*\(?|e)(?P<power>[-+]?\d+)\)?)?\)?"
)
_INLINE_MATH = re.compile(r"(?<![\\$])\$(?!\$)([^$\n]+?)(?<!\\)\$(?!\$)")
# 3.98 \times 10^{-19} is one number: "a * 10^-19 / b * 10^-19" divides two of them.
_SCIENTIFIC = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:\\times|\\cdot|\u00d7|\*)\s*10\s*\^\s*\{?\s*([-+]?\d+)\s*\}?"
)
# A word inside \text{} ("and", "for x = 3") joins two statements; it is not a unit.
_TEXT_WORD = re.compile(r"\\text\s*\{\s*[A-Za-z]{2,}(?:\s+[A-Za-z]+)*\s*\}")
_UNIT_WORDS = frozenset(
    {
        "kg",
        "mol",
        "cm",
        "mm",
        "km",
        "ms",
        "min",
        "hr",
        "Hz",
        "kHz",
        "MHz",
        "Pa",
        "kPa",
        "atm",
        "mL",
        "kJ",
        "MJ",
        "kW",
        "MW",
        "kWh",
        "eV",
        "keV",
        "MeV",
        "nm",
        "rad",
        "deg",
        "mph",
        "ft",
        "in",
        "lb",
        "lbs",
        "psi",
        "mmHg",
        "torr",
        "cal",
        "kcal",
        "Wh",
        "mA",
        "kV",
        "mV",
        "kN",
        "GW",
        "GJ",
        "mg",
        "ug",
    }
)
# A result in a prefixed unit the working did not use (7200 m = 7.2 km, 4.52e6 J = 4.5 MJ)
# is a conversion, not arithmetic to check.
_PREFIXED_UNIT = re.compile(r"\\(?:text|mathrm)\s*\{\s*([kMGmµμnpc][A-Za-z]+)")
_OPERATOR = re.compile(r"[-+*/]|sqrt|pi|sind|cosd|tand")
# sin 75°, \sin(60^\circ): a sine of degrees, the one function of an angle working writes.
_TRIG_DEGREES = re.compile(
    r"\\(sin|cos|tan)\s*\(?\s*(-?\d+(?:\.\d+)?)\s*(?:°|\^\s*\{?\s*\\circ\s*\}?)\s*\)?"
)
_FUNCTIONS = r"sqrt|pi|sind|cosd|tand"
_UNIT_GROUP = re.compile(
    r"\\(?:text|mathrm|textrm|rm|operatorname)\s*\{[^{}]*\}(?:\s*\^\s*(?:\{[^{}]*\}|-?\d))?"
)
_FRAC = re.compile(r"\\[dt]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}")
_SQRT = re.compile(r"\\sqrt\s*\{([^{}]*)\}")
_POWER = re.compile(r"\^\s*\{([^{}]*)\}")
_RELATION = re.compile(r"\\approx|≈|=")
_MAX_EXPONENT = 64
# Models round as they go: a step within 1% of its value is not called a slip.
_RELATIVE_SLACK = 0.01


@dataclass(frozen=True)
class WrongStep:
    """``left`` as written, the value shown after it, and what it really is."""

    left: str
    shown: str
    value: float


def _plain(tex: str) -> str | None:
    """A LaTeX side as a Python arithmetic expression, or None when it is not numbers."""
    text = tex.replace("\\left", "").replace("\\right", "")
    text = _SCIENTIFIC.sub(r"(\1e\2)", text)
    text = _TRIG_DEGREES.sub(r" \1d(\2)", text)
    text = re.sub(r"\\pi(?![A-Za-z])", " pi ", text)
    text = _TEXT_WORD.sub(lambda m: m.group(0) if _is_unit(m.group(0)) else "#", text)
    text = _UNIT_GROUP.sub(" ", text)
    for _ in range(4):
        text = _FRAC.sub(r"((\1)/(\2))", text)
        text = _SQRT.sub(r"sqrt(\1)", text)
        text = _POWER.sub(r"**(\1)", text)
    text = fold_operator_glyphs(text)
    for latex, plain in (
        ("\\times", "*"),
        ("\\cdot", "*"),
        ("\\div", "/"),
        ("\\,", ""),
        ("\\;", ""),
        ("\\!", ""),
        ("\\ ", ""),
        ("{,}", ""),
    ):
        text = text.replace(latex, plain)
    text = text.replace("^", "**").replace("{", "(").replace("}", ")")
    text = re.sub(r"\s+", "", text)
    # 1,500 is a number; a comma anywhere else is a list.
    text = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", text)
    letters = re.sub(rf"{_FUNCTIONS}|(?<=\d)e(?=[-+]?\d)", "", text)
    if not text or re.search(r"[A-Za-z\\%°',#]", letters):
        return None
    # 2(3), (2)(3), 25sqrt(73), 2pi, pi(3): a product written without a sign.
    text = re.sub(
        rf"(?<=[\d)])(?=\(|{_FUNCTIONS})|(?<=\))(?=\d)|(?<=pi)(?=[\d(]|{_FUNCTIONS})", "*", text
    )
    return text


def _is_unit(text_group: str) -> bool:
    inner = text_group[text_group.index("{") + 1 : -1].strip()
    return inner in _UNIT_WORDS


def _converts_unit(left_tex: str, right_tex: str) -> bool:
    """The result is in a prefixed unit the working never wrote."""
    left_units = set(_PREFIXED_UNIT.findall(left_tex))
    return any(unit not in left_units for unit in _PREFIXED_UNIT.findall(right_tex))


def _evaluate(expression: str) -> float | None:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        return None
    try:
        value = _walk(tree.body)
    except (ArithmeticError, ValueError):
        return None
    return value if value is not None and math.isfinite(value) else None


def _walk(node: ast.AST) -> float | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub | ast.UAdd):
        operand = _walk(node.operand)
        if operand is None:
            return None
        return -operand if isinstance(node.op, ast.USub) else operand
    if isinstance(node, ast.BinOp):
        left, right = _walk(node.left), _walk(node.right)
        if left is None or right is None:
            return None
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Pow):
            if abs(right) > _MAX_EXPONENT or (left < 0 and not float(right).is_integer()):
                return None
            return float(left**right)
        return None
    if isinstance(node, ast.Name) and node.id == "pi":
        return math.pi
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in _CALLS
        and len(node.args) == 1
        and not node.keywords
    ):
        inner = _walk(node.args[0])
        if inner is None or (node.func.id == "sqrt" and inner < 0):
            return None
        return _CALLS[node.func.id](inner)
    return None


def _sind(degrees: float) -> float:
    return math.sin(math.radians(degrees))


def _cosd(degrees: float) -> float:
    return math.cos(math.radians(degrees))


def _tand(degrees: float) -> float:
    return math.tan(math.radians(degrees))


_CALLS: dict[str, Callable[[float], float]] = {
    "sqrt": math.sqrt,
    "sind": _sind,
    "cosd": _cosd,
    "tand": _tand,
}


def _shown_number(plain: str) -> tuple[float, float] | None:
    """A written result and half its last place: ``14.8`` → (14.8, 0.05)."""
    match = _SHOWN.fullmatch(plain)
    if match is None:
        return None
    power = int(match.group("power") or 0)
    if abs(power) > _MAX_EXPONENT:
        return None
    places = len(match.group("decimals") or "")
    value = float(match.group("mantissa")) * 10.0**power
    return value, 0.5 * 10.0 ** (power - places)


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
_DECIMAL = re.compile(r"(?<![\d.])(?<!\*\*)(?<!\*\*\()\d+\.\d+(?:e[-+]?\d+)?")


def _exact_side(plain: str, rounded: dict[str, float]) -> str:
    """``plain`` with each earlier rounded result in it put back to its exact value.

    A line built on a rounded result may carry the exact one: "2 * 0.36 = 0.71" is right
    when 0.36 was 0.357, and was flagged "0.72, not 0.71" (2026-10-30, a long-jump answer).
    A given is exact as written, so "3.2 * 4.5 = 14.8" is still a slip; a whole number or
    an exponent is never taken for a rounded result (the "2" of "3^2" after "9/4 = 2")."""
    return _DECIMAL.sub(
        lambda m: f"({rounded[m.group(0)]!r})" if m.group(0) in rounded else m.group(0), plain
    )


def _is_wrong(value: float, shown: float, rounding: float, approximate: bool) -> bool:
    if _prefix_shift(value, shown):
        return False
    difference = abs(value - shown)
    slack = _RELATIVE_SLACK * (2 if approximate else 1) * max(abs(value), abs(shown))
    return difference > rounding * (1 + 1e-9) and difference > slack


# A name a step solves for or a given names: t, v_1, t_{\text{flight}}, \mu, \theta_1.
_NAME = re.compile(r"(?:\\[A-Za-z]+|[A-Za-z])(?:_\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}|_\w)?")


def _note_rounded(
    left_tex: str,
    left: str | None,
    right: str | None,
    rounded: dict[str, float],
    worked: dict[str, float],
) -> None:
    """Record a result written rounded: within half its last place of a step's exact value
    ("3.5/9.8 = 0.36", "0.357 ≈ 0.36", or "t = 3.5/9.8" and then "t = 0.36"). A given
    ("m = 3.2"), an exact result ("6/30 = 0.2") and a name reused for a new value are not."""
    if right is None:
        return
    shown = _shown_number(right)
    exact: float | None = None
    if left is not None:
        exact = _evaluate(_exact_side(left, rounded))
    elif _NAME.fullmatch(name := left_tex.replace(" ", "")):
        if shown is None:
            if (value := _evaluate(_exact_side(right, rounded))) is not None:
                worked[name] = value
            return
        if name not in worked:
            # A given ("mu = 0.3"): the same digits after it are this value, not a rounding.
            rounded.pop(right, None)
            return
        exact = worked.get(name)
    if exact is None or shown is None:
        return
    off = abs(exact - shown[0])
    if 0 < off <= shown[1] * (1 + 1e-9) and not math.isclose(exact, shown[0], rel_tol=1e-12):
        rounded[right] = exact


def wrong_steps(reply: str) -> list[WrongStep]:
    """The steps in ``reply`` whose arithmetic does not hold, in reading order."""
    found: list[WrongStep] = []
    # A number an earlier step rounded ("3.5/9.8 = 0.36", or "t = 3.5/9.8" and then
    # "t = 0.36"), and each name's exact value from its expression.
    rounded: dict[str, float] = {}
    worked: dict[str, float] = {}
    last = ""
    # The line before: the name it worked out and its last expression ("L", "√(6·14·28·48)/21").
    before: tuple[str, str, str] | None = None
    prose = _INLINE_CODE.sub(" ", map_fence_blocks(reply, lambda _fence, _body: "\n"))
    for match in _INLINE_MATH.finditer(prose):
        segment = match.group(1)
        parts = _RELATION.split(segment)
        relations = _RELATION.findall(segment)
        if len(parts) > 1 and not parts[0].strip():
            # "$= 0.36$" goes on from the line before.
            parts[0] = last
        last = parts[-1]
        for index in range(len(parts) - 1):
            left_tex, right_tex = parts[index].strip(), parts[index + 1].strip()
            left, right = _plain(left_tex), _plain(right_tex)
            _note_rounded(left_tex, left, right, rounded, worked)
            if left is None or right is None or left == right:
                continue
            step = _slip(left_tex, right_tex, left, right, relations[index] != "=", rounded)
            if step is not None:
                found.append(step)
        before = _chain(parts, relations, before, found)
    return found


def _slip(
    left_tex: str,
    right_tex: str,
    left: str,
    right: str,
    approximate: bool,
    rounded: dict[str, float],
) -> WrongStep | None:
    """``left = right`` when it does not hold: a worked side (an operation or a function) and
    what it is said to equal, a written result or another exact form (√11375 = 25√73)."""
    # A number in powers of ten is one number: "7.36 * 10^-20 J = 0.459 eV" converts a unit.
    if _OPERATOR.search(_SCIENTIFIC_PLAIN.sub("1", left).lstrip("-+")) is None:
        return None
    value = _evaluate(left)
    if value is None:
        return None
    shown = _shown_number(right)
    # Arithmetic only: "7200 m = 7.2 km" restates a value in another unit.
    if shown is not None and _converts_unit(left_tex, right_tex):
        return None
    if shown is None:
        # Two sides in different units substitute or convert ("0.98c * 11 μs = 0.98 *
        # 299,792,458 m/s * 11 * 10^-6 s"): no arithmetic to hold them to.
        units = (_units(left_tex), _units(right_tex))
        if all(units) and units[0] != units[1]:
            return None
        # Another exact form ("25√73"), or a product of rounded values ("32.61 * 0.9659").
        other = _evaluate(right)
        if other is None or (_DECIMAL.search(right) is not None and _DECIMAL.search(left) is None):
            return None
        exact = _DECIMAL.search(left) is None and _DECIMAL.search(right) is None
        if exact and not math.isclose(value, other, rel_tol=1e-6, abs_tol=1e-9):
            return WrongStep(left_tex, right_tex, value)
        if not exact and _is_wrong(value, other, 0.0, approximate):
            return WrongStep(left_tex, right_tex, value)
        return None
    # A side of exact numbers (√65/8, 10 sin 45°/sin 75°) is held to the shown value's own
    # rounding: "≈ 0.999" for 1.0078 is a slip, though under 1%.
    if _DECIMAL.search(left) is None:
        if _is_off(value, shown[0], shown[1]):
            return WrongStep(left_tex, right_tex, value)
        return None
    carried = _evaluate(_exact_side(left, {k: v for k, v in rounded.items() if k != right}))
    if _is_wrong(value, shown[0], shown[1], approximate) and (
        carried is None or _is_wrong(carried, shown[0], shown[1], approximate)
    ):
        return WrongStep(left_tex, right_tex, value)
    return None


_SCIENTIFIC_PLAIN = re.compile(r"\(?-?\d+(?:\.\d+)?e[-+]?\d+\)?")


def _units(tex: str) -> tuple[str, ...]:
    """The unit groups a side writes, in order ("\\mathrm{m/s}", "\\text{cm}^2")."""
    return tuple(sorted("".join(group.split()) for group in _UNIT_GROUP.findall(tex)))


def _is_off(value: float, shown: float, rounding: float) -> bool:
    """``shown`` is not ``value`` written to its own places."""
    return not _prefix_shift(value, shown) and abs(value - shown) > rounding * (1 + 1e-6) + 1e-12


def _branches(earlier: str, later: str) -> bool:
    """Two values of one name, not one value written twice: the ± roots ("(4 + 2)/2" then
    "(4 - 2)/2"), the same expression with one sign turned, or a line after a ±."""
    if "\\pm" in earlier or "±" in earlier or "\\mp" in earlier:
        return True
    signs = str.maketrans({"+": "±", "-": "±", "\u2212": "±"})
    return earlier.translate(signs).replace(" ", "") == later.translate(signs).replace(" ", "")


def _chain(
    parts: list[str],
    relations: list[str],
    before: tuple[str, str, str] | None,
    found: list[WrongStep],
) -> tuple[str, str, str] | None:
    """The same name worked out on two lines in a row must keep its value: "L = √(6·14·28·48)/21"
    then "L = √279552/21" (live, 2026-11-21: the chord came out 25.19 cm, not 16). Only a line
    worked from an expression is held: "x = 1" then "x = 3" are two roots."""
    name = parts[0].strip()
    if len(parts) < 2 or not name or _plain(name) is not None:
        return None
    if before is not None and before[0] == name and not _branches(before[1], parts[1].strip()):
        first_tex = parts[1].strip()
        first = _plain(first_tex)
        earlier = _plain(before[1])
        if first is not None and earlier is not None:
            step = _slip(before[1], first_tex, earlier, first, relations[0] != "=", {})
            if step is not None:
                found.append(step)
    worked = [part.strip() for part in parts[1:] if _plain(part.strip()) is not None]
    exprs = [part for part in worked if _OPERATOR.search((_plain(part) or "").lstrip("-+"))]
    return (name, exprs[-1], worked[-1]) if exprs else None


def _shown_like(value: float, shown: str) -> str:
    """``value`` written the way ``shown`` was: same places, or the same power of ten."""
    plain = _plain(shown) or ""
    match = _SHOWN.fullmatch(plain)
    places = len(match.group("decimals") or "") if match else 0
    if match and match.group("power") is not None:
        power = math.floor(math.log10(abs(value))) if value else 0
        mantissa = value / 10.0**power
        return f"{mantissa:.{places}f} \\times 10^{{{power}}}"
    unit = (
        shown[len(match.group("mantissa")) :]
        if match and shown.startswith(match.group("mantissa"))
        else ""
    )
    try:
        number = str(round_places(value, places))
    except InvalidOperation:
        number = f"{value:.{places}f}"
    if "," in shown:
        whole, _dot, decimals = number.partition(".")
        number = f"{int(whole):,}" + (f".{decimals}" if decimals else "")
    return number + unit


# A worked solution: its equalities are claims, not a quiz ("is 3 * 4 = 13?"). The
# indent is ``[^\S\n]*``, not ``\s*``: from each line start ``\s*`` ran over every blank
# line below it, quadratic in a run of them, and found no heading the next start misses.
_WORKOUT_HEADING = re.compile(
    r"^[^\S\n]*\*\*(?:Substitution|Steps|Answer|Working|\d+\.[^*\n]+)\*\*", re.MULTILINE
)


def is_worked_solution(reply: str) -> bool:
    return _WORKOUT_HEADING.search(reply) is not None


def working_note(reply: str) -> str | None:
    """One line naming the first slip, or None when the working adds up."""
    steps = wrong_steps(reply)
    if not steps:
        from app.modules.chat.working_systems import unheld_equations

        unheld = unheld_equations(reply)
        if not unheld:
            return None
        values = ", ".join(
            f"{name} = {_shown_like(value, '0.00')}" for name, value in unheld[0].values.items()
        )
        return (
            f"Check these values: ${values}$ do not satisfy ${unheld[0].equation}$. "
            "The answer depends on them."
        )
    step = steps[0]
    right = _shown_like(step.value, step.shown)
    return (
        f"Check this step: ${step.left} = {right}$, not ${step.shown}$. "
        "The lines after it depend on it."
    )


# "$\frac{\sqrt{65}}{8}$ cm (approximately 0.999 cm)", "**$2\sqrt{30}$ cm** (approx. $10.95$ cm)":
# an exact value and the decimal a reply gives for it, a few words apart.
_APPROXIMATED = re.compile(
    r"\$(?P<exact>[^$\n]{1,200})\$(?P<gap>[^$\n()~≈]{0,30}?)\(?"
    r"(?:approx(?:imately|\.)?|≈|~)[\s*$]*(?P<number>-?\d+(?:\.\d+)?)"
)


def corrected_approximations(reply: str) -> str:
    """``reply`` with each decimal given for an exact value it misstates written correctly, to
    the same places: "√65/8 cm (approximately 0.999 cm)" is 1.008 (live, 2026-11-21), and
    "2(√10 + √13 + √17) (approximately 19.13)" is 21.78. Only an exact value of plain numbers
    is held, never a side that carries a rounded decimal itself."""

    def fix(match: re.Match[str]) -> str:
        exact_tex = _RELATION.split(match.group("exact"))[-1].strip()
        plain = _plain(exact_tex)
        if plain is None or _DECIMAL.search(plain) is not None:
            return match.group(0)
        value = _evaluate(plain)
        shown = _shown_number(match.group("number"))
        if value is None or shown is None or not _is_off(value, shown[0], shown[1]):
            return match.group(0)
        start = match.start("number") - match.start()
        end = match.end("number") - match.start()
        whole = match.group(0)
        return whole[:start] + _shown_like(value, match.group("number")) + whole[end:]

    return _outside_fences(reply, lambda text: _APPROXIMATED.sub(fix, text))


def _outside_fences(text: str, change: Callable[[str], str]) -> str:
    """``change`` applied to the text between fences, every fence as written."""
    pieces: list[str] = []
    cursor = 0
    for fence in iter_fences(text):
        pieces.extend([change(text[cursor : fence.start]), text[fence.start : fence.end]])
        cursor = fence.end
    pieces.append(change(text[cursor:]))
    return "".join(pieces)
