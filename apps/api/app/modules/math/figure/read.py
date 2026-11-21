"""What a maths question asks to see, read by a fast model, drawn by the server.

The Grade 7 textbook run (2026-11-13) asked for a parallelogram with angle A = 70°, a
right triangle with legs 9 and 12, a rhombus by its diagonals, a cube, a conversion graph,
points in four quadrants and an interval on a number line. The word rules drew a
parallelogram 8 by 5 and a triangle that was not right-angled, both with sizes the
questions never gave, and drew nothing for the rest while the model said the app could
not draw them. So one short structured call reads the kind of picture and the values the
question states (``FigureRequest``), the numbers are checked against the question, and the
server works out the picture (``build``). Nothing here raises into a turn: no read, or a
reading that does not hold, draws nothing.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from app.core import sympy_executor
from app.core.config import Settings
from app.models.routing_lanes import ROUTING
from app.modules.math.figure.build import build_figure_fence
from app.modules.math.figure.request import FigureRequest
from app.modules.math.tools.lesson import wants_answer_only

logger = logging.getLogger(__name__)

_MAX_TOKENS = 400
_MAX_CHARS = 1200
_EARLIER_CHARS = 600

_ASKED = (
    "The user wants to see a picture for a maths question. Say what to draw, as JSON, "
    "from what the question states.\n"
)
# Not asked: a figure only where a student follows the question better with one in front of
# them (the owner, 2026-11-15: "we don't have to ask it to draw, it must draw to teach").
_TEACH = (
    "The user did not ask for a picture. Draw one only when a figure helps a student "
    "follow this maths question: a shape it gives sizes or angles of (any triangle, "
    "rectangle, square, parallelogram, rhombus, trapezium, kite or polygon), a solid or a "
    "circle it measures, angles or lines, points on a coordinate plane, an inequality or "
    "numbers to place on a number line, or the graph of a formula y = ... it asks about "
    "(its slope, intercepts, vertex or where it crosses: kind function). Otherwise kind is "
    "none: arithmetic, fractions or percentages worked "
    "as numbers, money, an equation solved without a graph, a word problem with no shape, "
    "statistics, probability, a definition or a proof in words, and a request for only the "
    "answer. A question that names a shape, a solid, a circle, an angle or points is drawn: "
    "when in doubt, draw it. Say what to draw, as JSON, from what the question states.\n"
    'Not asked, drawn: "A triangle has sides 3, 4 and 5. Is it right-angled?" -> polygon; '
    '"A circle has diameter 10 cm. Find its area." -> circle; "Two angles at a point are '
    '150° and 90°. Find the third." -> lines; "Find the volume of a box 2 m by 3 m by 4 m." '
    '-> solid. Not asked, none: "Solve 3x - 4 = 8.", "What is 3/5 of 40?".\n'
)

# Circles and their theorems (kind circle): each shape names the theorem's figure, and the
# measures and letters say what the question states of it.
_CIRCLES = (
    "\n\n"
    "Circles (kind circle). A question about a circle's parts or one of its theorems is "
    "drawn: a sector or an arc, a chord, a tangent, angles in a circle, a cyclic "
    "quadrilateral, chords that cross, a ring between two circles, a circle with a shape "
    "inside or around it. A cyclic quadrilateral is kind circle, never polygon. A sphere or "
    "a hemisphere is kind solid, never circle.\n"
    "- shape: circle (a circle with its radius, diameter or a chord and its distance from "
    "the centre); sector (a sector or an arc: two radii and the angle between them at the "
    "centre); segment (the part cut off by a chord, with its angle at the centre); annulus "
    "(a ring: two circles with one centre); tangent (a tangent from a point outside); "
    "two_tangents (two tangents from one point); angle_at_centre (an arc's angle at the "
    "centre and at the circumference, or two angles at the circumference on the same arc, "
    "angles in the same segment: never cyclic_quadrilateral); angle_in_semicircle "
    "(a diameter AB and a point C on the circle); cyclic_quadrilateral (four corners on the "
    "circle); intersecting_chords (two chords crossing inside). A polygon with a circle "
    "inside or around it is shape circle with circle_through or circle_within.\n"
    "- measures, besides radius, diameter and chord: central_angle (an angle at the centre: "
    "a sector's or an arc's angle, angle AOB); inscribed_angle (an angle with its corner on "
    "the circle, angle ACB); distance (from the centre to a chord, or to the outside "
    "point: OP); tangent (a tangent's length, from the outside point to where it touches); "
    "angle (the angle between two tangents, named by their point; a cyclic "
    "quadrilateral's corner); length (a part of a chord, named by its ends: AE). A right "
    "angle a theorem gives (in a semicircle, where a tangent touches) is not stated: leave "
    "it out.\n"
    "- point: the letter of the outside point the tangents are drawn from (T in "
    '"tangents TA and TB"), or of where two chords cross ("E"), or "".\n'
    "- vertices: every letter the question names on the circle, the asked ones too, in "
    'this order: where a tangent touches ("T"; "AB" for two), the diameter\'s ends then the '
    'point on the circle ("ABC"), an arc\'s ends then each point its angles stand at '
    '("ABCD" for angles ACB and ADB), a cyclic quadrilateral\'s corners ("ABCD"), the first '
    "chord's ends then the second's (\"ABCD\").\n"
    "- circle_through: the shape whose corners the circle passes through, the circle "
    "around it (a square inscribed in a circle, a triangle's circumcircle, the circle "
    "through a rectangle's corners). circle_within: the shape whose sides the circle "
    "touches, the circle inside it (the circle inscribed in a triangle, its incircle, a "
    "circle that sits inside a square). Name the shape as for a polygon "
    "(equilateral_triangle, right_triangle, rectangle, regular_hexagon); its own sizes are "
    "measures too (side, length, width, leg, hypotenuse), and parts "
    '"radius" marks a radius the question asks for.\n'
    'Examples: "A chord 10 cm long is 12 cm from the centre of a circle. How long is the '
    'radius?" -> {"kind": "circle", "shape": "circle", "unit": "cm", "measures": [{"what": '
    '"chord", "value": 10}, {"what": "distance", "value": 12}]}; "Angle ACB at the '
    'circumference is 35°. Find angle AOB." -> {"kind": "circle", "shape": '
    '"angle_at_centre", "center": "O", "vertices": "ABC", "measures": [{"what": '
    '"inscribed_angle", "name": "ACB", "value": 35}]}; "Find the radius of the circle '
    'inscribed in a square of side 6 m." -> {"kind": "circle", "shape": "circle", '
    '"circle_within": "square", "unit": "m", "measures": [{"what": "side", "value": 6}], '
    '"parts": ["radius"]}; "Tangents from P touch a circle with centre O at A and B. '
    'Angle APB = 50°. Find angle AOB." -> {"kind": "circle", "shape": "two_tangents", '
    '"center": "O", "point": "P", "vertices": "AB", "measures": [{"what": "angle", "name": '
    '"APB", "value": 50}]}'
)

_BODY = (
    "\n"
    "Copy every number exactly as the question writes it. Never work a number out, round "
    "it or make one up: leave out any value the question does not state, and the app "
    'works out the rest. When the last message only asks to draw or show "it", the '
    "picture is what the earlier user messages state. The earlier messages are one problem "
    "and its follow-ups, oldest first: draw the problem's figure with what the follow-ups "
    'and the last message ask about marked ("find the diagonal": parts diagonals; "the '
    'radius": parts radius). A rate (2 cm/min) or a size at one '
    'moment of a changing shape ("when r = 3 cm") is not the figure\'s size: leave it out.\n'
    "\n"
    "kind:\n"
    '- "polygon": a triangle, a four-sided shape or a regular polygon\n'
    '- "circle": a circle and its parts, or a shape drawn inside or around a circle\n'
    '- "lines": parallel lines cut by a transversal, two crossing lines, one angle, '
    "angles on a straight line or about a point, complementary angles\n"
    '- "solid": a cube, a cuboid or box, a prism, a cylinder, a cone, a pyramid or a '
    "sphere, or its net\n"
    '- "number_line": numbers or an inequality shown on a number line\n'
    '- "function": the graph of a formula the question writes, y = f(x)\n'
    '- "points": points plotted on a coordinate plane\n'
    '- "none": data to chart (a bar graph, pie chart, line graph of recorded values, '
    "pictograph, histogram, tally), a photo, nothing to draw, or a shape the shape lists "
    "below do not name (a frustum, points or vectors in space, a polygon at given "
    "coordinates, a window or a ladder): never a listed shape in its place\n"
    "\n"
    "Fields, only those the picture needs:\n"
    "- shape: for a polygon one of triangle, right_triangle, isosceles_triangle, "
    "equilateral_triangle, square, rectangle, parallelogram, rhombus, trapezium, kite, "
    "regular_polygon (regular_hexagon and the like only when the question says regular); "
    "for lines one of parallel_lines, intersecting_lines, angle, angles_on_line, "
    "angles_at_point, complementary_angles, perpendicular_lines; for a solid one of cube, "
    "cuboid, triangular_prism, cylinder, cone, square_pyramid, sphere, hemisphere; for a "
    "circle one of the circle shapes below.\n"
    '- vertices: the letters naming the corners in order ("ABCD"), or "".\n'
    "- center: the letter naming a circle's centre or the point where diagonals meet "
    '("O"), or "".\n'
    "- apex: for an isosceles triangle, the letter where its equal sides meet (AB = AC: "
    '"A"), or "".\n'
    '- measures: each stated value, as {"what": ..., "name": ..., "value": ...}. what is '
    "one of side, base, height, leg, hypotenuse, equal_side, parallel_side, diagonal, "
    "angle (in degrees), apex_angle and base_angle (an isosceles triangle's), perimeter, "
    "radius, diameter, chord, length, width, edge, slant_height. name is the letters it "
    'is named with ("AB" for a side, "A" or "BAC" for an angle), or "". A right angle '
    'the question places ("right-angled at Q") is {"what": "angle", "name": "Q", '
    '"value": 90}. For a prism, length is the prism\'s own length (its height or '
    "altitude), and the sides of its end triangle are side, leg or hypotenuse. For a "
    "pyramid, edge is a slanting edge beside the base.\n"
    "- sides: a regular polygon's number of sides.\n"
    '- parts: extra parts to draw: "diagonals", "radius", "diameter", "net" (the solid\'s '
    "net).\n"
    '- circle_through: a shape drawn inside the circle with its corners on it ("square"); '
    "circle_within: a shape drawn around the circle, its sides touching it.\n"
    '- unit: the unit of length ("cm"), or "".\n'
    '- numbers: the numbers to mark on a number line, as written ("-5/2", "1.5"); '
    'inequality: the inequality to show, copied exactly ("-2 < x <= 3"); integers: true '
    "when only the whole numbers that meet it are asked for.\n"
    '- expr: the right side of y = ... ("2x + 1", "2.54x", "144 - 4t") in the '
    'question\'s own letter; variable: that letter ("x", "t"); x_min and x_max: the ends of '
    "the range the question states, each one value as a JSON string written with ASCII "
    'characters ("-3", "-1/2", "2*pi", "1/e", "e^2"), or null when none is stated; x_label '
    'and y_label: what each axis measures ("inches", "centimetres").\n'
    '- points: [{"name": "A", "x": 2, "y": 3}]; quadrants: true when the question asks '
    "which quadrant.\n"
    "\n"
    'Example: "In parallelogram ABCD, angle A = 70°. Find angle B and draw the '
    'parallelogram." -> {"kind": "polygon", "shape": "parallelogram", "vertices": '
    '"ABCD", "measures": [{"what": "angle", "name": "A", "value": 70}]}'
) + _CIRCLES


def _message(question: str, earlier: Sequence[str]) -> str:
    before = [text[:_EARLIER_CHARS] for text in earlier if text.strip()]
    if not before:
        return question[:_MAX_CHARS]
    joined = "\n".join(f"- {text}" for text in before)
    return f"Earlier user messages:\n{joined}\n\nLast message: {question[:_MAX_CHARS]}"


async def read_figure(
    settings: Settings, question: str, earlier: Sequence[str], *, asked: bool = True
) -> FigureRequest | None:
    """The model's reading of what to draw, or None when there is no read. ``asked``: the
    message asks to see a picture; otherwise the read draws only one that helps teach."""
    from app.core.redis import get_redis_client
    from app.gateways.structured_completion import complete_structured
    from app.services import quota as quota_service

    try:
        if await quota_service.global_spend_exceeded(get_redis_client(), settings):
            return None
        return await complete_structured(
            settings=settings,
            model_alias=ROUTING.math_extract,
            messages=[
                {"role": "system", "content": (_ASKED if asked else _TEACH) + _BODY},
                {"role": "user", "content": _message(question, earlier)},
            ],
            schema=FigureRequest,
            max_tokens=_MAX_TOKENS,
            timeout_seconds=settings.figure_read_timeout_seconds,
            allow_fallback=False,
            quiet_timeout=True,
        )
    except Exception as exc:  # A read is a hint: any failure draws nothing.
        logger.info("figure read failed (%s)", type(exc).__name__)
        return None


async def draw_figure(
    question: str, earlier: Sequence[str], settings: Settings, *, asked: bool = True
) -> str | None:
    """The fence of the picture the question asks to see, or, not asked, of the one that
    helps teach it (``teaching_figures_enabled``); None when nothing is drawn."""
    if not settings.figure_read_enabled or not question.strip():
        return None
    if not asked and (not settings.teaching_figures_enabled or wants_answer_only(question)):
        return None
    request = await read_figure(settings, question, earlier, asked=asked)
    if request is None or request.kind == "none":
        return None
    texts = [question, *earlier]
    try:
        return await sympy_executor.run_sympy(
            build_figure_fence,
            request.model_dump_json(),
            texts,
            timeout=settings.stem_solve_timeout_seconds,
        )
    except Exception as exc:  # A failed build draws nothing; the reply stands.
        logger.info("figure build failed (%s)", type(exc).__name__)
        return None
