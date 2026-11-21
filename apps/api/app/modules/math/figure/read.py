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
    # Heights and distances, similar triangles, shapes made of two, angles with a letter.
    "Drawn too: heights and distances (an angle of elevation or depression, a ladder "
    "against a wall, a kite string, a ramp), shadows and similar triangles, a shape made of "
    "two (a rectangle with a semicircle or a triangle on it, an L-shape), a triangle's "
    "exterior angle, a quadrilateral by its angles, a regular polygon by its perimeter or "
    "its angle, complementary or supplementary angles and angles at a point or on a line, "
    "even written with x, a frustum, a tetrahedron, a solid made of two (a cone on a "
    "hemisphere) and a sphere (a solid, never a circle). A word problem about one of "
    'these is drawn: "Two angles are supplementary and one is 65°. Find the other." -> '
    'lines; "A 1.5 m post casts a 2 m shadow when a building casts a 24 m shadow. How tall '
    'is the building?" -> polygon, shadows; "A garden is an L-shape made of a 10 m by 5 m '
    'rectangle and a 4 m by 3 m rectangle. Find its area." -> polygon, rectangle with '
    'attached rectangle; "Triangle KLM is similar to triangle RST, KL = 3 cm and RS = 4.5 '
    'cm." -> polygon, similar_triangles, vertices "KLMRST", both sides; "From two points '
    '25 m apart, the angles of elevation of a mast are 20° and 40°." -> polygon, '
    "elevation, two angle measures and the gap.\n"
    'Not asked, drawn: "A triangle has sides 3, 4 and 5. Is it right-angled?" -> polygon; '
    '"A circle has diameter 10 cm. Find its area." -> circle; "Two angles at a point are '
    '150° and 90°. Find the third." -> lines; "Find the volume of a box 2 m by 3 m by 4 m." '
    '-> solid. Not asked, none: "Solve 3x - 4 = 8.", "What is 3/5 of 40?".\n'
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
    "below do not name (points or vectors in space, a polygon at given coordinates): "
    "never a listed shape in its place\n"
    "\n"
    "Fields, only those the picture needs:\n"
    "- shape: for a polygon one of triangle, right_triangle, isosceles_triangle, "
    "equilateral_triangle, square, rectangle, parallelogram, rhombus, trapezium, kite, "
    "regular_polygon (regular_hexagon and the like only when the question says regular); "
    "for lines one of parallel_lines, intersecting_lines, angle, angles_on_line, "
    "angles_at_point, complementary_angles, perpendicular_lines; for a solid one of cube, "
    "cuboid, triangular_prism, cylinder, cone, square_pyramid, sphere, hemisphere; for a "
    'circle "circle".\n'
    # Heights and distances, similar triangles, composite shapes, other polygons and solids.
    "- shape, more polygons: elevation (something standing up seen from the ground), "
    "depression (looking down from the top of a cliff, tower or lighthouse), leaning (a "
    "ladder, plank or wire from the ground to a wall or pole), slope (a kite string, a "
    "ramp, a slide: nothing stands up); shadows (objects and their shadows at one time); "
    "similar_triangles (vertices: both triangles' six letters, corresponding in order, "
    '"ABCDEF" for ABC ~ DEF, and every side named in either: two triangles the question '
    "calls similar are this one figure, never one triangle); quadrilateral (any four-sided "
    "shape that is none of the named ones). More lines: supplementary_angles. More "
    "solids: frustum (of a cone), "
    "square_frustum (of a square pyramid), tetrahedron.\n"
    "- attached: a second shape joined to the first: for a rectangle or square, "
    "semicircle, triangle, equilateral_triangle, rectangle (an L-shape) or square; for a "
    "round solid, the solid on it: cone, hemisphere, cylinder, or hemispheres (one at each "
    'end). shape is the first part ("a cone on a hemisphere": shape hemisphere, attached '
    'cone), else "". A semicircle cut out of the shape adds "cut" to parts.\n'
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
    # Measures of the scenes, the shapes made of two and the polygons by their angles.
    "  More measures: in a heights scene, height is what stands up (tower, cliff, the "
    "height up the wall), distance the ground (or the water) from its foot, length the "
    "slanting line (ladder, string, ramp, line of sight), angle the angle with the ground "
    "or the horizontal (an angle of elevation or depression), angle_from_vertical one "
    "with the wall or the vertical, gap the distance between two points the angles are "
    "seen from (two angles of elevation from two points: both angles and the gap); "
    "shadow is a shadow's length. Every measure may say what it is of (a field "
    'beside name): an object\'s ("pole", "tree"); in a shape made of two, the attached '
    "part's name "
    '("semicircle", "cone", "triangle"), "second" for a second rectangle, "" for the first '
    "shape; the side a semicircle stands on is its diameter too. In a solid made of two, "
    'a height is of its own part ("cone", "cylinder"). A regular polygon\'s perimeter is '
    "perimeter, never its side; "
    "interior_angle and exterior_angle are each angle of a regular polygon, and "
    'exterior_angle a triangle\'s exterior angle (its name "ACD" or "C"); sides only '
    "when the question states the number.\n"
    '- angle_terms: angles written with a letter, [{"term": "2x", "name": ""}], term '
    'copied exactly ("x + 20"), name its letters or ""; the angles stated in degrees stay '
    "measures.\n"
    "- sides: a regular polygon's number of sides.\n"
    '- parts: extra parts to draw: "diagonals", "radius", "diameter", "net" (the solid\'s '
    "net).\n"
    '- inscribed: a shape drawn inside the circle with its corners on it ("square"); '
    "circumscribed: a shape drawn around the circle.\n"
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
)


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
