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

logger = logging.getLogger(__name__)

_MAX_TOKENS = 400
_MAX_CHARS = 1200
_EARLIER_CHARS = 600

_PROMPT = (
    "The user wants to see a picture for a maths question. Say what to draw, as JSON, "
    "from what the question states.\n"
    "\n"
    "Copy every number exactly as the question writes it. Never work a number out, round "
    "it or make one up: leave out any value the question does not state, and the app "
    'works out the rest. When the last message only asks to draw or show "it", the '
    "picture is what the earlier user message states.\n"
    "\n"
    "kind:\n"
    '- "polygon": a triangle, a four-sided shape or a regular polygon\n'
    '- "circle": a circle and its parts, or a shape drawn inside or around a circle\n'
    '- "lines": parallel lines cut by a transversal, two crossing lines, one angle, '
    "angles on a straight line, complementary angles\n"
    '- "solid": a cube, a cuboid or box, a prism, a cylinder, a cone, a pyramid or a '
    "sphere, or its net\n"
    '- "number_line": numbers or an inequality shown on a number line\n'
    '- "function": the graph of a line or a curve y = f(x), a conversion graph, or a '
    "quantity that changes by the same amount each step\n"
    '- "points": points plotted on a coordinate plane\n'
    '- "none": data to chart (a bar graph, pie chart, line graph of recorded values, '
    "pictograph, histogram, tally), a photo, or nothing to draw\n"
    "\n"
    "Fields, only those the picture needs:\n"
    "- shape: for a polygon one of triangle, right_triangle, isosceles_triangle, "
    "equilateral_triangle, square, rectangle, parallelogram, rhombus, trapezium, kite, "
    "regular_polygon; for lines one of parallel_lines, intersecting_lines, angle, "
    "angles_on_line, complementary_angles, perpendicular_lines; for a solid one of cube, "
    "cuboid, triangular_prism, cylinder, cone, square_pyramid, sphere, hemisphere; for a "
    'circle "circle".\n'
    '- vertices: the letters naming the corners in order ("ABCD"), or "".\n'
    "- center: the letter naming a circle's centre or the point where diagonals meet "
    '("O"), or "".\n'
    '- measures: each stated value, as {"what": ..., "name": ..., "value": ...}. what is '
    "one of side, base, height, leg, hypotenuse, equal_side, parallel_side, diagonal, "
    "angle (in degrees), perimeter, radius, diameter, chord, length, width, edge, "
    'slant_height. name is the letters it is named with ("AB" for a side, "A" for the '
    'angle at A), or "". For a prism, length is the prism\'s own length (its height or '
    "altitude), and the sides of its end triangle are side, leg or hypotenuse.\n"
    "- sides: a regular polygon's number of sides.\n"
    '- parts: extra parts to draw: "diagonals", "radius", "diameter", "net" (the solid\'s '
    "net).\n"
    '- inscribed: a shape drawn inside the circle with its corners on it ("square"); '
    "circumscribed: a shape drawn around the circle.\n"
    '- unit: the unit of length ("cm"), or "".\n'
    '- numbers: the numbers to mark on a number line, as written ("-5/2", "1.5"); '
    'inequality: the inequality to show, copied exactly ("-2 < x <= 3").\n'
    '- expr: the right side of y = ... ("2x + 1", "2.54x", "144 - 4x"); variable: its '
    'letter ("x"); x_min and x_max: the range of x the question states; x_label and '
    'y_label: what each axis measures ("inches", "centimetres").\n'
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
    settings: Settings, question: str, earlier: Sequence[str]
) -> FigureRequest | None:
    """The model's reading of what to draw, or None when there is no read."""
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
                {"role": "system", "content": _PROMPT},
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


async def draw_figure(question: str, earlier: Sequence[str], settings: Settings) -> str | None:
    """The fence of the picture the question asks to see, or None."""
    if not settings.figure_read_enabled or not question.strip():
        return None
    request = await read_figure(settings, question, earlier)
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
