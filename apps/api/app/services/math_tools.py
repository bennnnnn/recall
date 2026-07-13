"""Pre-stream symbolic math augmentation for chat prompts."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Literal

from app.core.config import Settings
from app.models.math_schemas import (
    EquationInput,
    GeometryBlockSpec,
    GraphBlockSpec,
    GraphSampleInput,
    MathIntent,
    RectangleGeometryInput,
    RightTriangleGeometryBlockSpec,
    RightTriangleGeometryInput,
    SquareGeometryInput,
    TriangleGeometryBlockSpec,
    TriangleGeometryInput,
)
from app.services import math_service

logger = logging.getLogger(__name__)

_DRAW_RECTANGLE = re.compile(
    r"\b(?:draw|show|sketch|visuali[sz]e)\s+(?:a\s+)?rectangle\b",
    re.IGNORECASE,
)

_DRAW_RIGHT_TRIANGLE = re.compile(
    r"\b(?:draw|show|sketch|visuali[sz]e)\s+(?:the\s+)?right\s+triangle\b",
    re.IGNORECASE,
)

_DRAW_SQUARE = re.compile(
    r"\b(?:draw|show|sketch|visuali[sz]e)\s+(?:a\s+)?square\b",
    re.IGNORECASE,
)

_DEFAULT_RECT = re.compile(
    r"\b(?:draw|show)\s+(?:a\s+)?rectangle\b",
    re.IGNORECASE,
)

_MATH_KEYWORDS = re.compile(
    r"\b("
    r"solve|simplify|factor|expand|differentiate|derivative|integrate|integral|"
    r"equation|algebra|quadratic|polynomial|"
    r"find the angle|diagonal|rectangle|triangle|geometry|"
    r"graph|plot|function|y\s*=\s*|"
    r"sqrt|square root|pythagor"
    r")\b",
    re.IGNORECASE,
)

_EQUATION_IN_TEXT = re.compile(
    r"([0-9a-zA-Z+\-*/().\s^]+?)\s*=\s*([0-9a-zA-Z+\-*/().\s^]+)",
)

_RECT_DIMS = re.compile(
    r"(?:rectangle|rect)?\s*(?:is|of|with)?\s*"
    r"(?P<w>\d+(?:\.\d+)?)\s*(?:×|x|\*|\sby\s)\s*(?P<h>\d+(?:\.\d+)?)\s*(?P<unit>cm|m|mm|in|ft|units?)?",
    re.IGNORECASE,
)

_SQUARE_SIDE = re.compile(
    r"\bsquare\b[\s\S]{0,60}?(?:side|edge)\s*(?:=|:)?\s*(?P<s>\d+(?:\.\d+)?)",
    re.IGNORECASE,
)

_TRI_BASE_HEIGHT = re.compile(
    r"base\s*=\s*(?P<base>\d+(?:\.\d+)?)\s*(?:cm|m|mm|in|ft)?"
    r"[\s\S]{0,80}?height\s*=\s*(?P<height>\d+(?:\.\d+)?)",
    re.IGNORECASE,
)

_RIGHT_TRI = re.compile(r"\bright\s+triangle\b", re.IGNORECASE)

_RIGHT_TRI_DIMS = re.compile(
    r"(?P<base>\d+(?:\.\d+)?)\s*(?:×|x|\*|\sby\s)\s*(?P<height>\d+(?:\.\d+)?)\s*(?P<unit>cm|m|mm|in|ft|units?)?",
    re.IGNORECASE,
)

_GRAPH_EXPR = re.compile(
    r"\b(?:graph|plot)\s+(?:y\s*=\s*)?(?P<expr>[0-9a-zA-Z+\-*/().\s^]+)",
    re.IGNORECASE,
)

_CALC_OP = re.compile(
    r"\b(simplify|differentiate|derivative|integrate|integral)\b",
    re.IGNORECASE,
)

_TRAILING_FILLER_RE = re.compile(
    r"\s+(?:please|now|thanks?|thank\s+you|for\s+me|to\s+me|real\s+quick|quickly|briefly)\.?\s*$",
    re.IGNORECASE,
)


def _strip_trailing_filler(expr: str) -> str:
    """`_GRAPH_EXPR`/the calculus expr-match are greedy captures of everything
    after the trigger word, so natural phrasing like "graph x^2 please" or
    "differentiate x^2 for me" sweeps the trailing words into the
    "expression" — which then fails to parse and silently disables the
    verified-math augmentation for phrasing a real user would actually type."""
    s = expr.strip()
    # A conjunction essentially never appears inside a math expression
    # itself — anything from " and "/" then " onward is a new clause of
    # natural language (e.g. "sin(x) and explain it"), not part of the expr.
    s = re.split(r"\s+(?:and|then)\s+", s, maxsplit=1, flags=re.IGNORECASE)[0]
    prev = None
    while prev != s:
        prev = s
        s = _TRAILING_FILLER_RE.sub("", s).strip()
    return s


def needs_symbolic_math(text: str, *, has_image_attachment: bool = False) -> bool:
    cleaned = text.strip()
    if not cleaned and not has_image_attachment:
        return False
    from app.services.math_image_extract import is_math_camera_prompt

    if has_image_attachment and is_math_camera_prompt(cleaned):
        return True
    if (
        _DRAW_RECTANGLE.search(cleaned)
        or _DRAW_RIGHT_TRIANGLE.search(cleaned)
        or _DRAW_SQUARE.search(cleaned)
    ):
        return True
    if has_image_attachment and _MATH_KEYWORDS.search(cleaned):
        return True
    if _EQUATION_IN_TEXT.search(cleaned) and _MATH_KEYWORDS.search(cleaned):
        return True
    if _RECT_DIMS.search(cleaned):
        return True
    if _GRAPH_EXPR.search(cleaned):
        return True
    if _CALC_OP.search(cleaned):
        return True
    if re.search(r"\bsolve\b", cleaned, re.IGNORECASE) and _EQUATION_IN_TEXT.search(cleaned):
        return True
    return bool(_MATH_KEYWORDS.search(cleaned) and _EQUATION_IN_TEXT.search(cleaned))


def extract_math_intent(text: str) -> MathIntent | None:
    cleaned = text.strip()
    if not cleaned:
        return None

    rect = _RECT_DIMS.search(cleaned)
    if rect:
        unit = (rect.group("unit") or "cm").lower()
        if unit.startswith("unit"):
            unit = "units"
        return MathIntent(
            kind="rectangle",
            width=float(rect.group("w")),
            height=float(rect.group("h")),
            unit=unit,
            operation="solve",
        )

    if _DEFAULT_RECT.search(cleaned):
        return MathIntent(kind="rectangle", width=6, height=4, unit="cm", operation="solve")

    if re.search(r"\bsquare\b", cleaned, re.IGNORECASE):
        side_match = _SQUARE_SIDE.search(cleaned)
        if side_match:
            side = float(side_match.group("s"))
            return MathIntent(
                kind="square", side=side, width=side, height=side, unit="cm", operation="solve"
            )
        equal = re.search(
            r"(?P<s>\d+(?:\.\d+)?)\s*(?:×|x|\*|\sby\s)\s*(?P=s)\s*(?:cm|m|mm|in|ft)?",
            cleaned,
            re.IGNORECASE,
        )
        if equal:
            side = float(equal.group("s"))
            return MathIntent(
                kind="square", side=side, width=side, height=side, unit="cm", operation="solve"
            )
        return MathIntent(kind="square", side=5, width=5, height=5, unit="cm", operation="solve")

    if _RIGHT_TRI.search(cleaned):
        rt_dims = _RIGHT_TRI_DIMS.search(cleaned)
        if rt_dims:
            unit = (rt_dims.group("unit") or "cm").lower()
            if unit.startswith("unit"):
                unit = "units"
            return MathIntent(
                kind="right_triangle",
                base=float(rt_dims.group("base")),
                height=float(rt_dims.group("height")),
                unit=unit,
                operation="solve",
            )
        return MathIntent(kind="right_triangle", base=6, height=4, unit="cm", operation="solve")

    tri = _TRI_BASE_HEIGHT.search(cleaned)
    if tri:
        return MathIntent(
            kind="triangle",
            base=float(tri.group("base")),
            height=float(tri.group("height")),
            unit="cm",
            operation="solve",
        )

    if re.search(r"\btriangle\b", cleaned, re.IGNORECASE) and re.search(
        r"\b(?:area|draw|visuali[sz]e|sketch)\b", cleaned, re.IGNORECASE
    ):
        return MathIntent(kind="triangle", base=8, height=5, unit="cm", operation="solve")

    graph = _GRAPH_EXPR.search(cleaned)
    if graph:
        expr = _strip_trailing_filler(graph.group("expr")).replace("^", "**")
        return MathIntent(kind="graph", expr=expr, operation="graph")

    calc = _CALC_OP.search(cleaned)
    if calc:
        op_word = calc.group(1).lower()
        calc_op: Literal["simplify", "differentiate", "integrate"] = (
            "differentiate" if op_word in {"differentiate", "derivative"} else "integrate"
        )
        if op_word == "simplify":
            calc_op = "simplify"
        expr_match = re.search(
            r"(?:simplify|differentiate|derivative|integrate|integral)\s+(.+)$", cleaned, re.I
        )
        expr = _strip_trailing_filler(expr_match.group(1)) if expr_match else cleaned
        return MathIntent(kind="calculus", expr=expr, operation=calc_op)

    eq = math_service.try_extract_equation_from_text(cleaned)
    if eq:
        return MathIntent(
            kind="equation",
            lhs=eq.lhs,
            rhs=eq.rhs,
            operation="solve",
            variable=eq.variables[0] if eq.variables else "x",
        )

    return None


@dataclass(frozen=True)
class VerifiedMathBlock:
    """The system-prompt hint text plus the exact fence (if any) it asked
    the model to reuse verbatim — canonical_fence lets a post-stream check
    correct the model's actual output rather than only trusting compliance."""

    text: str
    canonical_fence: dict[str, Any] | None = None


def _build_verified_block(intent: MathIntent, settings: Settings) -> VerifiedMathBlock | None:
    lines: list[str] = [
        "Symbolic math results (verified by SymPy — use these exact values in your answer):"
    ]

    try:
        if intent.kind == "equation" and intent.lhs and intent.rhs:
            eq = EquationInput(
                lhs=intent.lhs[: settings.math_max_expr_length],
                rhs=intent.rhs[: settings.math_max_expr_length],
                variables=[intent.variable],
            )
            result = math_service.solve_equation(eq)
            lines.extend(result.steps)
            lines.append(
                "Emit each formula as INLINE $...$ math — do NOT wrap math in "
                "backticks (`` `$...$` `` renders as raw code) and do NOT use "
                "```math block fences for step equations (they render late, "
                "leaving blank gaps during streaming). Inline $...$ renders in "
                "sync with the step text. Do NOT recompute the solutions. Show "
                "worked steps by COPYING the verified steps above verbatim — do "
                "NOT derive intermediate algebra yourself. Keep any spacing "
                "(e.g. \\quad) INSIDE the $...$ math delimiters so it renders."
            )
            return VerifiedMathBlock(text="\n".join(lines))

        if intent.kind == "rectangle" and intent.width and intent.height:
            rect_geo = math_service.rectangle_geometry(
                RectangleGeometryInput(width=intent.width, height=intent.height, unit=intent.unit)
            )
            lines.append(
                f"Rectangle: width={rect_geo.width:g} {rect_geo.unit} "
                f"height={rect_geo.height:g} {rect_geo.unit} "
                f"diagonal={rect_geo.diagonal:g} angle={rect_geo.angle_deg:g}°"
            )
            spec = GeometryBlockSpec(
                type="rectangle",
                width=rect_geo.width,
                height=rect_geo.height,
                unit=rect_geo.unit,
                show_diagonal=True,
                show_angle=True,
                diagonal=rect_geo.diagonal,
                angle_deg=rect_geo.angle_deg,
                area=rect_geo.area,
                perimeter=rect_geo.perimeter,
                labels=rect_geo.labels,
            )
            lines.append(
                "When a diagram helps, emit ONLY this fence (adjust labels if needed):\n"
                f"```geometry\n{json.dumps(spec.model_dump(), separators=(',', ':'))}\n```"
            )
            lines.append("Do NOT recompute diagonal, angle, area, or perimeter.")
            return VerifiedMathBlock(text="\n".join(lines), canonical_fence=spec.model_dump())

        if intent.kind == "square" and (intent.side or intent.width):
            side = intent.side or intent.width or 5
            square_geo = math_service.square_geometry(
                SquareGeometryInput(side=side, unit=intent.unit)
            )
            lines.append(
                f"Square: side={square_geo.side:g} {square_geo.unit} "
                f"diagonal={square_geo.diagonal:g} {square_geo.unit} "
                f"area={square_geo.area:g} {square_geo.unit}² "
                f"perimeter={square_geo.perimeter:g} {square_geo.unit}"
            )
            spec = GeometryBlockSpec(
                type="square",
                side=square_geo.side,
                width=square_geo.side,
                height=square_geo.side,
                unit=square_geo.unit,
                show_diagonal=True,
                show_area=True,
                show_perimeter=True,
                diagonal=square_geo.diagonal,
                area=square_geo.area,
                perimeter=square_geo.perimeter,
                labels=square_geo.labels,
            )
            lines.append(
                "When a diagram helps, emit ONLY this fence (NEVER ```json):\n"
                f"```geometry\n{json.dumps(spec.model_dump(), separators=(',', ':'))}\n```"
            )
            lines.append("Do NOT recompute diagonal, area, or perimeter.")
            return VerifiedMathBlock(text="\n".join(lines), canonical_fence=spec.model_dump())

        if intent.kind == "triangle" and intent.base and intent.height:
            tri_geo = math_service.triangle_geometry(
                TriangleGeometryInput(base=intent.base, height=intent.height, unit=intent.unit)
            )
            lines.append(
                f"Triangle: base={tri_geo.base:g} {tri_geo.unit} "
                f"height={tri_geo.height:g} {tri_geo.unit} area={tri_geo.area:g} {tri_geo.unit}²"
            )
            tri_spec = TriangleGeometryBlockSpec(
                type="triangle",
                base=tri_geo.base,
                height=tri_geo.height,
                unit=tri_geo.unit,
                show_labels=True,
                area=tri_geo.area,
                labels=tri_geo.labels,
            )
            lines.append(
                "When a diagram helps, emit ONLY this fence (NEVER ```json):\n"
                f"```geometry\n{json.dumps(tri_spec.model_dump(), separators=(',', ':'))}\n```"
            )
            lines.append("Do NOT recompute area.")
            return VerifiedMathBlock(text="\n".join(lines), canonical_fence=tri_spec.model_dump())

        if intent.kind == "right_triangle" and intent.base and intent.height:
            rt_geo = math_service.right_triangle_geometry(
                RightTriangleGeometryInput(base=intent.base, height=intent.height, unit=intent.unit)
            )
            lines.append(
                f"Right triangle: base={rt_geo.base:g} {rt_geo.unit} "
                f"height={rt_geo.height:g} {rt_geo.unit} "
                f"hypotenuse={rt_geo.hypotenuse:g} {rt_geo.unit} "
                f"area={rt_geo.area:g} {rt_geo.unit}²"
            )
            rt_spec = RightTriangleGeometryBlockSpec(
                type="right_triangle",
                base=rt_geo.base,
                height=rt_geo.height,
                unit=rt_geo.unit,
                show_labels=True,
                show_hypotenuse=True,
                show_angle=True,
                hypotenuse=rt_geo.hypotenuse,
                area=rt_geo.area,
                labels=rt_geo.labels,
            )
            lines.append(
                "When a diagram helps, emit ONLY this fence (NEVER ```json):\n"
                f"```geometry\n{json.dumps(rt_spec.model_dump(), separators=(',', ':'))}\n```"
            )
            lines.append("Do NOT recompute hypotenuse or area.")
            return VerifiedMathBlock(text="\n".join(lines), canonical_fence=rt_spec.model_dump())

        if intent.kind == "graph" and intent.expr:
            sample = math_service.sample_function(
                GraphSampleInput(
                    expr=intent.expr[: settings.math_max_expr_length],
                    variable=intent.variable,
                    x_min=-10,
                    x_max=10,
                    n=settings.math_graph_max_points,
                )
            )
            graph_spec = GraphBlockSpec(
                expr=sample.expr,
                variable=sample.variable,
                x_min=sample.x_min,
                x_max=sample.x_max,
                points=sample.points,
            )
            lines.append(f"Function samples for {sample.expr}: {len(sample.points)} points.")
            lines.append(
                "When a plot helps, emit ONLY this fence:\n"
                f"```graph\n{json.dumps(graph_spec.model_dump(), separators=(',', ':'))}\n```"
            )
            return VerifiedMathBlock(text="\n".join(lines), canonical_fence=graph_spec.model_dump())

        if intent.kind == "calculus" and intent.expr and intent.operation:
            if intent.operation == "simplify":
                out = math_service.simplify_expression(intent.expr, intent.variable)
            elif intent.operation == "differentiate":
                out = math_service.differentiate_expression(intent.expr, intent.variable)
            elif intent.operation == "integrate":
                out = math_service.integrate_expression(intent.expr, intent.variable)
            else:
                return None
            lines.append(f"Result: {out.latex}")
            lines.append("Do NOT recompute. Explain in plain language with $...$ for formulas.")
            return VerifiedMathBlock(text="\n".join(lines))
    except math_service.MathServiceError as exc:
        logger.info("math_tools skipped: %s", exc)
        return None
    except Exception:
        logger.exception("math_tools failed")
        return None

    return None


def _inject_before_last_user(messages: list[dict[str, str]], block: str) -> list[dict[str, str]]:
    augmented = list(messages)
    insert_at = len(augmented)
    for index in range(len(augmented) - 1, -1, -1):
        if augmented[index].get("role") == "user":
            insert_at = index
            break
    augmented.insert(insert_at, {"role": "system", "content": block})
    return augmented


async def augment_prompt_messages(
    messages: list[dict[str, str]],
    user_content: str,
    settings: Settings,
    *,
    has_image_attachment: bool = False,
) -> tuple[list[dict[str, str]], VerifiedMathBlock | None]:
    if not settings.math_tools_enabled:
        return messages, None
    if not needs_symbolic_math(user_content, has_image_attachment=has_image_attachment):
        return messages, None

    intent = extract_math_intent(user_content)
    if intent is None and has_image_attachment:
        lines = [
            "The user attached an image that may contain a math problem. "
            "Extract the equation as lhs/rhs if possible, then explain using verified reasoning. "
            "Use $...$ for formulas and ```geometry / ```graph JSON fences for diagrams."
        ]
        return _inject_before_last_user(messages, "\n".join(lines)), None

    if intent is None:
        return messages, None

    verified = await _build_verified_block_async(intent, settings)
    if not verified:
        return messages, None
    return _inject_before_last_user(messages, verified.text), verified


async def _build_verified_block_async(
    intent: MathIntent, settings: Settings
) -> VerifiedMathBlock | None:
    """Run the sync, CPU-bound SymPy work off the event loop with a hard timeout.

    ``_build_verified_block`` calls into SymPy's ``solve``/``integrate``/etc.,
    which are synchronous and can take arbitrarily long on a pathological
    expression. Without offloading, that would stall every concurrent chat
    stream on this worker's single event loop.
    """
    try:
        async with asyncio.timeout(settings.math_solve_timeout_seconds):
            return await asyncio.to_thread(_build_verified_block, intent, settings)
    except TimeoutError:
        logger.warning(
            "math_tools solve timed out after %ss for kind=%s",
            settings.math_solve_timeout_seconds,
            intent.kind,
        )
        return None
