"""A sphere in a scene in space: the question's own, its centre and radius worked out.

Where the question writes a sphere's equation, the sphere is that one (SymPy completes the
square): the one the description copies, or the one centred where it puts its centre, its
radius always the equation's (round 2's review drew x² + y² + z² = 25 with radius 25).
Where it writes none, the centre is a point it states and the radius one it names ("radius
5 cm", half of "diameter 10") or the distance to a point it states on the sphere.
"""

from __future__ import annotations

import math
import re
from fractions import Fraction
from typing import Any

from app.modules.math.drawing.lengths import (
    ROUNDED,
    dot,
    exact,
    minus,
    states_size,
    worked_length,
)
from app.modules.math.drawing.question import Question, Triple
from app.modules.math.drawing.roles import named_sizes
from app.modules.math.drawing.vocabulary import SpaceSphere
from app.modules.math.figure.drawing import length_label

_PART_LABEL = re.compile(r"\(\s*[a-z]\s*\)|(?<![\w)])[a-z]\)")


def _written_spheres(question: Question) -> list[tuple[Any, Triple, Fraction]]:
    """Each sphere the question writes an equation of: the equation (its sides' difference),
    its centre and its squared radius (SymPy completes the square). An equation of no real
    sphere (a radius squared of 0 or less) is none."""
    import sympy

    from app.modules.math.tool_check import written_relations

    # "(a) x² + y² + z² - 2y = 4 (b) ...": each part's equation on its own, its letter left out.
    texts = [_PART_LABEL.sub(";\n", text) for text in question.texts]
    x, y, z = sympy.symbols("x y z")
    found: list[tuple[Any, Triple, Fraction]] = []
    for text in texts:
        for lhs, op, rhs in written_relations(text):
            expr = sympy.expand(lhs - rhs)
            if op != "=" or not expr.free_symbols <= {x, y, z}:
                continue
            poly = sympy.Poly(expr, x, y, z)
            if poly.total_degree() != 2 or not all(c.is_Rational for c in poly.coeffs()):
                continue
            square = poly.coeff_monomial(x**2)
            cross = [poly.coeff_monomial(m) for m in (x * y, x * z, y * z)]
            if (
                square == 0
                or any(cross)
                or {poly.coeff_monomial(y**2), poly.coeff_monomial(z**2)} != {square}
            ):
                continue
            a = Fraction(str(square))
            linear = [Fraction(str(poly.coeff_monomial(v))) / a for v in (x, y, z)]
            centre = (-linear[0] / 2, -linear[1] / 2, -linear[2] / 2)
            radius_squared = sum(c * c for c in centre) - Fraction(str(poly.coeff_monomial(1))) / a
            if radius_squared > 0:
                found.append((expr, centre, radius_squared))
    return found


def _sphere_of(item: SpaceSphere, question: Question) -> tuple[Triple, Fraction] | None:
    """The question's own sphere the item is, its centre and squared radius from the
    equation the question writes: the one the item copies, or the one centred where it puts
    its centre. Its radius is the equation's, never the item's own number (round 2's review
    drew x² + y² + z² = 25 with radius 25)."""
    import sympy

    from app.modules.math.tool_check import parse_formula, same_value

    spheres = _written_spheres(question)
    if item.equation.strip():
        sides = item.equation.split("=")
        parsed = [parse_formula(side) for side in sides] if len(sides) == 2 else []
        if len(parsed) != 2 or parsed[0] is None or parsed[1] is None:
            return None
        mine = sympy.expand(parsed[0] - parsed[1])
        matches = [s for s in spheres if same_value(mine, s[0]) or same_value(mine, -s[0])]
    elif item.center is not None:
        matches = [s for s in spheres if s[1] == exact(item.center)]
    else:
        return None
    return (matches[0][1], matches[0][2]) if len(matches) == 1 else None


def _stated_sphere(item: SpaceSphere, question: Question) -> tuple[Triple, Fraction, str] | None:
    """A sphere the question writes no equation of: centred at a point it states, its
    radius one it names ("radius 5 cm", half of "diameter 10") or the distance to a point it
    states on it ("passes through P(4, 6, 3)"), with that radius's label."""
    if item.center is None or not isinstance(item.radius, int | float) or item.radius <= 0:
        return None
    centre = exact(item.center)
    if not question.states_triple(centre):
        return None
    radius = float(item.radius)
    named = [*named_sizes("radius", question), *(d / 2 for d in named_sizes("diameter", question))]
    for size in named:
        if abs(size - radius) <= 1e-9 * max(1.0, size):
            value = Fraction(size).limit_denominator(10_000)
            unit = states_size(question, value) or states_size(question, value * 2) or ""
            return centre, value * value, length_label(size, unit)
    for point in question.triples:
        gap = minus(point, centre)
        squared = dot(gap, gap)
        if squared and abs(math.sqrt(float(squared)) - radius) <= ROUNDED * max(1.0, radius):
            return centre, squared, worked_length(squared)[0]
    return None


def the_sphere(item: SpaceSphere, question: Question) -> tuple[Triple, Fraction, str] | None:
    """The question's sphere the item is: its centre, squared radius and radius label."""
    if not _written_spheres(question):
        return _stated_sphere(item, question)
    found = _sphere_of(item, question)
    if found is None:
        return None
    centre, radius_squared = found
    # Its radius as the server works it out from the equation (√5).
    return centre, radius_squared, worked_length(radius_squared)[0]
