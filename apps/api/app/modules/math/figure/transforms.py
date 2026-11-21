"""A transformation the question states, checked against it and applied by the server.

The read names the transformation (``request.Transform``); it never gives the image. Each
value it holds must be one the question writes: a mirror line it names ("the x-axis") or
writes ("y = -x", the same line by SymPy), an angle in degrees or as a turn ("a half
turn"), the direction the question says (none said is anticlockwise, the convention,
and saying both is no one direction), a centre it writes as a pair or as "the origin", a
vector it writes as a pair or in words ("4 units right and 1 unit up"), a scale factor it
writes with its sign. The image is then worked out exactly, in fractions: a picture of the
image a model computed would be its arithmetic, not the question's.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from app.modules.math.figure.grounding import (
    number_value,
    states_angle,
    states_signed,
    written_numbers,
    written_pairs,
)
from app.modules.math.figure.plane_text import coordinate_text
from app.modules.math.figure.request import Transform

Exact = tuple[Fraction, Fraction]
# A line a x + b y = c, its coefficients exact.
Line = tuple[Fraction, Fraction, Fraction]
_X_AXIS: Line = (Fraction(0), Fraction(1), Fraction(0))
_Y_AXIS: Line = (Fraction(1), Fraction(0), Fraction(0))
_AXIS_WORDS = {
    _X_AXIS: re.compile(r"\bx[\s-]?axis\b"),
    _Y_AXIS: re.compile(r"\by[\s-]?axis\b"),
}
_ORIGIN = re.compile(r"\borigin\b")
_ANTI = re.compile(r"\b(?:anti|counter)[\s-]?clockwise\b")
_CLOCKWISE = re.compile(r"\bclockwise\b")
_TURNS = {
    90: re.compile(r"\bquarter[\s-]turn\b"),
    180: re.compile(r"\bhalf[\s-]turn\b"),
    270: re.compile(r"\bthree[\s-]quarters?[\s-]turn\b"),
}
# The words a question names each transformation with; a read of one it does not name is
# none of the question's.
_NAMED = {
    "reflection": re.compile(r"\breflect|\bmirror|\bimage in\b"),
    "rotation": re.compile(r"\brotat|\bturn"),
    "translation": re.compile(r"\btranslat|\bshift|\bslid|\bmoved?\b"),
    "enlargement": re.compile(r"\benlarg|\bdilat|\bscale factor\b"),
}
# The most transformations one picture draws: the shape, its image and the image's image.
MOST_DRAWN = 2
# One transformation after another ("reflected in the x-axis and then in the y-axis"): a read
# of only one draws the wrong image. "Its image after a reflection" is one.
_COMPOSITE = re.compile(
    r"\b(?:then|followed by)\b[^.?!]{0,40}?"
    r"(?:reflect|rotat|translat|enlarg|dilat|turn|\bin the (?:line|[xy][\s-]?axis))"
)
_RIGHT = re.compile(r"\bright\b")
_LEFT = re.compile(r"\bleft\b")
_UP = re.compile(r"\bup(?:wards?)?\b")
_DOWN = re.compile(r"\bdown(?:wards?)?\b")


@dataclass(frozen=True)
class Mapping:
    """A stated transformation as the server applies it, and what a picture draws of it."""

    kind: str
    apply: Callable[[Exact], Exact]
    mirror: Line | None = None
    # How the question writes its mirror line ("y = -x"), when it is no axis.
    mirror_text: str = ""
    centre: Exact | None = None
    centre_stated: bool = False
    vector: Exact | None = None
    # Anticlockwise degrees, one of 90, 180, 270.
    turn: int = 0
    factor: Fraction | None = None


def _lowered(texts: Sequence[str]) -> str:
    return " ".join(texts).lower().replace("\u2212", "-").replace("\u2013", "-")


def _pairs(texts: Sequence[str]) -> list[Exact]:
    return [pair for text in texts for pair in written_pairs(text)]


def exact_pair(x: float, y: float, texts: Sequence[str]) -> Exact | None:
    """The pair the question writes for (x, y), exactly ("1/3" stays a third), or None."""
    near = 1e-9
    for px, py in _pairs(texts):
        if abs(float(px) - x) <= near * max(1, abs(x)) and abs(float(py) - y) <= near * max(
            1, abs(y)
        ):
            return (px, py)
    return None


def line_of(lhs: Any, rhs: Any) -> Line | None:
    """The line ``lhs = rhs`` is, as a x + b y = c with exact coefficients, or None for a
    relation that is no straight line in x and y."""
    import sympy

    x, y = sympy.symbols("x y")
    difference = sympy.expand(lhs - rhs)
    if not difference.free_symbols or not difference.free_symbols <= {x, y}:
        return None
    try:
        poly = sympy.Poly(difference, x, y)
    except sympy.PolynomialError:
        return None
    if poly.total_degree() != 1:
        return None
    a, b = poly.coeff_monomial(x), poly.coeff_monomial(y)
    c = -poly.coeff_monomial(1)
    if not all(isinstance(value, sympy.Rational) for value in (a, b, c)):
        return None
    return (Fraction(str(a)), Fraction(str(b)), Fraction(str(c)))


def same_line(one: Line, other: Line) -> bool:
    (a1, b1, c1), (a2, b2, c2) = one, other
    return a1 * b2 == a2 * b1 and a1 * c2 == a2 * c1 and b1 * c2 == b2 * c1


def written_lines(texts: Sequence[str]) -> list[Line]:
    """The straight lines the texts write as equations ("y = -x", "x = 2")."""
    from app.modules.math.tool_check import written_relations

    found: list[Line] = []
    for text in texts:
        for lhs, op, rhs in written_relations(text):
            line = line_of(lhs, rhs) if op == "=" else None
            if line is not None:
                found.append(line)
    return found


def _mirror(written: str, texts: Sequence[str]) -> tuple[Line, str] | None:
    """The mirror line the read names, when the question names or writes that line."""
    from app.modules.math.tool_check import written_relations

    text = written.lower().replace("\u2212", "-").strip()
    text = re.sub(r"^(?:the\s+)?(?:line\s+)?", "", text)
    line: Line | None = None
    for axis, words in _AXIS_WORDS.items():
        if words.fullmatch(text.removesuffix(".").strip()):
            line = axis
    if line is None:
        relations = written_relations(text)
        if len(relations) != 1 or relations[0][1] != "=":
            return None
        line = line_of(relations[0][0], relations[0][2])
    if line is None:
        return None
    lowered = _lowered(texts)
    named = any(
        same_line(line, axis) and words.search(lowered) for axis, words in _AXIS_WORDS.items()
    )
    if not named and not any(same_line(line, other) for other in written_lines(texts)):
        return None
    is_axis = any(same_line(line, axis) for axis in _AXIS_WORDS)
    return line, "" if is_axis else _line_text(line)


def _line_text(line: Line) -> str:
    """A mirror line as a textbook writes it: "y = -x", "x = 2", "y = 2x + 1"."""
    a, b, c = line
    if b == 0:
        return f"x = {coordinate_text(c / a)}"
    slope, intercept = -a / b, c / b
    if slope == 0:
        return f"y = {coordinate_text(intercept)}"
    term = {Fraction(1): "x", Fraction(-1): "\u2212x"}.get(slope, f"{coordinate_text(slope)}x")
    if intercept == 0:
        return f"y = {term}"
    sign = "+" if intercept > 0 else "\u2212"
    return f"y = {term} {sign} {coordinate_text(abs(intercept))}"


def _reflect(line: Line) -> Callable[[Exact], Exact]:
    a, b, c = line
    norm = a * a + b * b

    def apply(point: Exact) -> Exact:
        x, y = point
        k = 2 * (a * x + b * y - c) / norm
        return (x - k * a, y - k * b)

    return apply


def _centre(transform: Transform, texts: Sequence[str]) -> tuple[Exact, bool] | None:
    """A rotation's or an enlargement's centre: a pair the question writes, or the origin
    it names ("about the origin", "(0, 0)"); a question naming neither states none. The
    flag says the centre is no origin, so the picture marks it."""
    lowered = _lowered(texts)
    origin = (Fraction(0), Fraction(0))
    at = transform.centre
    if at is None or (at.x == 0 and at.y == 0):
        stated = _ORIGIN.search(lowered) or origin in _pairs(texts)
        return (origin, False) if stated else None
    pair = exact_pair(at.x, at.y, texts)
    return None if pair is None else (pair, True)


def _direction(transform: Transform, texts: Sequence[str]) -> str | None:
    """The rotation's direction: the read's, held to what the question says."""
    lowered = _lowered(texts)
    said = {"anticlockwise"} if _ANTI.search(lowered) else set()
    if _CLOCKWISE.search(_ANTI.sub(" ", lowered)):
        said.add("clockwise")
    read = transform.direction
    if not said:
        return None if read == "clockwise" else "anticlockwise"
    if read:
        return read if read in said else None
    return next(iter(said)) if len(said) == 1 else None


def _turn(transform: Transform, texts: Sequence[str]) -> int | None:
    """The rotation as anticlockwise degrees (90, 180 or 270), from an angle or a turn the
    question writes."""
    lowered = _lowered(texts)
    turns = [degrees for degrees, words in _TURNS.items() if words.search(lowered)]
    angle = transform.angle
    if angle is None:
        if len(turns) != 1:
            return None
        angle = float(turns[0])
    elif angle not in turns and not states_angle(
        [w for text in texts for w in written_numbers(text)], angle
    ):
        return None
    if angle % 90:
        return None
    if angle < 0:
        if transform.direction:
            return None  # "-90° clockwise" is no one rotation
        turn = int(angle)
    else:
        direction = _direction(transform, texts)
        if direction is None and abs(angle) % 360 != 180:
            return None
        turn = int(angle) if direction != "clockwise" else -int(angle)
    turn %= 360
    return turn or None


def _rotate(centre: Exact, turn: int) -> Callable[[Exact], Exact]:
    cx, cy = centre

    def apply(point: Exact) -> Exact:
        dx, dy = point[0] - cx, point[1] - cy
        if turn == 90:
            return (cx - dy, cy + dx)
        if turn == 180:
            return (cx - dx, cy - dy)
        return (cx + dy, cy - dx)

    return apply


def _vector(transform: Transform, texts: Sequence[str]) -> Exact | None:
    """A translation's vector: a pair the question writes, or its parts in words with
    their directions ("3 units left and 2 down")."""
    if transform.vector is None:
        return None
    dx, dy = transform.vector.x, transform.vector.y
    pair = exact_pair(dx, dy, texts)
    if pair is not None:
        return pair
    lowered = _lowered(texts)
    found = [w for text in texts for w in written_numbers(text)]
    for value, plus, minus in ((dx, _RIGHT, _LEFT), (dy, _UP, _DOWN)):
        if value == 0:
            continue
        word = plus if value > 0 else minus
        if not (states_signed(found, abs(value)) and word.search(lowered)):
            return None
    exact = (Fraction(dx).limit_denominator(1000), Fraction(dy).limit_denominator(1000))
    return exact if any(exact) else None


def _factor(transform: Transform, texts: Sequence[str]) -> Fraction | None:
    value = number_value(transform.factor) if transform.factor else None
    if value is None or value == 0 or value == 1:
        return None
    found = [w for text in texts for w in written_numbers(text)]
    return value if states_signed(found, float(value)) else None


def _enlarge(centre: Exact, factor: Fraction) -> Callable[[Exact], Exact]:
    cx, cy = centre
    return lambda point: (cx + factor * (point[0] - cx), cy + factor * (point[1] - cy))


def mapping(transform: Transform, texts: Sequence[str]) -> Mapping | None:
    """The transformation as the question states it, or None when it does not."""
    if not _NAMED[transform.kind].search(_lowered(texts)):
        return None
    if transform.kind == "reflection":
        mirror = _mirror(transform.mirror, texts) if transform.mirror else None
        if mirror is None:
            return None
        return Mapping("reflection", _reflect(mirror[0]), mirror=mirror[0], mirror_text=mirror[1])
    if transform.kind == "translation":
        vector = _vector(transform, texts)
        if vector is None:
            return None
        return Mapping("translation", lambda p: (p[0] + vector[0], p[1] + vector[1]), vector=vector)
    centre = _centre(transform, texts)
    if centre is None:
        return None
    if transform.kind == "rotation":
        turn = _turn(transform, texts)
        if turn is None:
            return None
        return Mapping(
            "rotation", _rotate(centre[0], turn), centre=centre[0], centre_stated=centre[1],
            turn=turn,
        )  # fmt: skip
    factor = _factor(transform, texts)
    if factor is None:
        return None
    return Mapping(
        "enlargement", _enlarge(centre[0], factor), centre=centre[0], centre_stated=centre[1],
        factor=factor,
    )  # fmt: skip


def mappings(transforms: Sequence[Transform], texts: Sequence[str]) -> list[Mapping] | None:
    """Every transformation the read gives, each the question's; None when one is not, when
    the question chains one after another and the read gives only one, or when it chains
    more than a picture draws (an image after the second would be left out)."""
    lowered = _lowered(texts)
    named = [kind for kind, words in _NAMED.items() if words.search(lowered)]
    # Each "then" chains one more step after the first: a read of fewer leaves one out.
    chained = len(_COMPOSITE.findall(lowered))
    if len(transforms) > MOST_DRAWN or chained + 1 > MOST_DRAWN:
        return None
    if len(transforms) < 2 and (chained or len(named) > 1):
        return None
    found = [mapping(transform, texts) for transform in transforms]
    return None if any(item is None for item in found) else [m for m in found if m is not None]


def stated_pair_only_once(pair: Exact, texts: Sequence[str]) -> bool:
    """The question writes this pair once: as a vector or a centre, not also a vertex."""
    return _pairs(texts).count(pair) == 1
