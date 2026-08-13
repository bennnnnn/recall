"""SymPy MCP adapter."""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from app.core.config import Settings
from app.gateways.mcp.base import ToolResult
from app.models.math_schemas import (
    CircleGeometryBlockSpec,
    CircleGeometryInput,
    EquationInput,
    GeometryBlockSpec,
    GraphBlockSpec,
    GraphSampleInput,
    NewtonMethodInput,
    RectangleGeometryInput,
    SquareGeometryInput,
    SystemOfEquationsInput,
)
from app.models.tool_schemas import SympyToolInput
from app.services import math_service, math_tools

logger = logging.getLogger(__name__)

_T = TypeVar("_T")

_ActionHandler = Callable[["SympyAdapter", dict[str, Any]], Awaitable[ToolResult]]


def _fence_data(canonical_fence: dict[str, Any] | None) -> dict[str, Any] | None:
    """Attach canonical fence JSON for post-stream validate_math_fences."""
    if canonical_fence is None:
        return None
    return {"canonical_fence": canonical_fence}


class SympyAdapter:
    name = "sympy"
    input_schema = SympyToolInput

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def describe(self) -> str:
        return (
            "Symbolic math: solve equations / systems / inequalities, simplify, "
            "differentiate, integrate (optional lower/upper for definite), factor, "
            "expand, limits, series, Newton's method, rectangle/square/circle "
            "geometry, and graphs (optional second curve via expr2)."
        )

    def to_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.describe(),
                "parameters": SympyToolInput.model_json_schema(),
            },
        }

    async def _run_off_loop(self, fn: Callable[..., _T], *args: Any) -> _T | None:
        """Run synchronous, CPU-bound SymPy work in the bounded subprocess
        pool with a hard timeout + SIGTERM on timeout.

        BUG FIX (was silent): math_tools.py's chat-path callers already wrap
        every SymPy call this way — its own docstring explains why (solve/
        integrate/etc. are synchronous and can stall every concurrent chat
        stream on this worker's single event loop on a pathological
        expression). This adapter called math_service functions directly,
        synchronously, with none of that protection — a hung/expensive
        expression reaching it via the model-callable "sympy" tool blocked
        the whole worker with no timeout at all.

        The function and args must be picklable (top-level functions + plain
        data) so they can cross the subprocess boundary.
        """
        from app.services.sympy_executor import run_sympy

        try:
            return await run_sympy(fn, *args, timeout=self.settings.math_solve_timeout_seconds)
        except TimeoutError:
            logger.warning("sympy MCP tool call timed out")
            return None

    async def _action_solve(self, args: dict[str, Any]) -> ToolResult:
        data = EquationInput(
            lhs=str(args.get("lhs") or ""),
            rhs=str(args.get("rhs") or ""),
            variables=list(args.get("variables") or ["x"]),
        )
        result = await self._run_off_loop(math_service.solve_equation, data)
        if result is None:
            return ToolResult(name=self.name, content="Math error: timed out.")
        # Parity with heuristic solve: attach ```answer for post-stream rewrite.
        answer = math_tools._format_equation_answer(result.solutions_latex, result.solution_kind)
        return ToolResult(
            name=self.name,
            content=(
                "\n".join(result.steps) + "\nEnd with this final-answer fence (copy verbatim):\n"
                f"```answer\n{answer}\n```"
            ),
            data=_fence_data(math_tools._answer_canonical(answer)),
        )

    async def _action_expr_op(self, args: dict[str, Any]) -> ToolResult:
        action = str(args.get("action") or "").strip().lower()
        expr = str(args.get("expr") or "")
        variable = str(args.get("variable") or "x")
        if action == "integrate":
            lower = str(args.get("lower") or args.get("start") or "").strip()
            upper = str(args.get("upper") or args.get("end") or "").strip()
            if lower and upper:
                expr_result = await self._run_off_loop(
                    math_service.integrate_definite, expr, variable, lower, upper
                )
                if expr_result is None:
                    return ToolResult(name=self.name, content="Math error: timed out.")
                return ToolResult(name=self.name, content=expr_result.result)
        fn = {
            "simplify": math_service.simplify_expression,
            "diff": math_service.differentiate_expression,
            "integrate": math_service.integrate_expression,
            "factor": math_service.factor_expression,
            "expand": math_service.expand_expression,
        }[action]
        expr_result = await self._run_off_loop(fn, expr, variable)
        if expr_result is None:
            return ToolResult(name=self.name, content="Math error: timed out.")
        return ToolResult(name=self.name, content=expr_result.result)

    async def _action_inequality(self, args: dict[str, Any]) -> ToolResult:
        comparator = str(args.get("comparator") or "").strip()
        if comparator not in ("<", ">", "<=", ">="):
            return ToolResult(
                name=self.name,
                content='Math error: inequality requires comparator one of "<", ">", "<=", ">=".',
            )
        variables = list(args.get("variables") or ["x"])
        variable = str(args.get("variable") or (variables[0] if variables else "x"))
        result = await self._run_off_loop(
            math_service.solve_inequality,
            str(args.get("lhs") or ""),
            str(args.get("rhs") or ""),
            variable,
            comparator,
        )
        if result is None:
            return ToolResult(name=self.name, content="Math error: timed out.")
        answer = math_tools._format_equation_answer(result.solutions_latex, result.solution_kind)
        return ToolResult(
            name=self.name,
            content=(
                "\n".join(result.steps) + "\nEnd with this final-answer fence (copy verbatim):\n"
                f"```answer\n{answer}\n```"
            ),
            data=_fence_data(math_tools._answer_canonical(answer)),
        )

    async def _action_system(self, args: dict[str, Any]) -> ToolResult:
        equations = [(str(lhs), str(rhs)) for lhs, rhs in (args.get("equations") or [])]
        system_input = SystemOfEquationsInput(
            equations=equations,
            variables=list(args.get("variables") or ["x", "y"]),
        )
        system_result = await self._run_off_loop(math_service.solve_system, system_input)
        if system_result is None:
            return ToolResult(name=self.name, content="Math error: timed out.")
        answer = math_tools._format_system_answer(
            system_result.solutions, system_result.solution_kind
        )
        return ToolResult(
            name=self.name,
            content=(
                "\n".join(system_result.steps)
                + "\nEnd with this final-answer fence (copy verbatim):\n"
                f"```answer\n{answer}\n```"
            ),
            data=_fence_data(math_tools._answer_canonical(answer)),
        )

    async def _action_limit(self, args: dict[str, Any]) -> ToolResult:
        expr = str(args.get("expr") or "")
        variable = str(args.get("variable") or "x")
        point = str(args.get("point") or "0")
        direction = str(args.get("direction") or "+-")
        limit_result = await self._run_off_loop(
            math_service.compute_limit, expr, variable, point, direction
        )
        if limit_result is None:
            return ToolResult(name=self.name, content="Math error: timed out.")
        return ToolResult(name=self.name, content=limit_result.result)

    async def _action_series(self, args: dict[str, Any]) -> ToolResult:
        expr = str(args.get("expr") or "")
        variable = str(args.get("variable") or "x")
        start = str(args.get("start") or "1")
        end = str(args.get("end") or "oo")
        series_result = await self._run_off_loop(
            math_service.evaluate_series_sum, expr, variable, start, end
        )
        if series_result is None:
            return ToolResult(name=self.name, content="Math error: timed out.")
        return ToolResult(name=self.name, content=series_result.result)

    async def _action_newton(self, args: dict[str, Any]) -> ToolResult:
        newton_input = NewtonMethodInput(
            expr=str(args.get("expr") or ""),
            variable=str(args.get("variable") or "x"),
            initial_guess=float(args.get("guess") or 1.0),
        )
        newton_result = await self._run_off_loop(math_service.newton_method, newton_input)
        if newton_result is None:
            return ToolResult(name=self.name, content="Math error: timed out.")
        if not newton_result.converged or newton_result.root is None:
            return ToolResult(
                name=self.name,
                content=(
                    f"Newton's method did not converge "
                    f"(iterations={newton_result.iterations_used}). "
                    "Do NOT present a root as found."
                ),
            )
        answer = f"{newton_result.root:g}"
        return ToolResult(
            name=self.name,
            content=(
                f"Newton's method: root={newton_result.root}, "
                f"converged={newton_result.converged}, "
                f"iterations={newton_result.iterations_used}"
            ),
            data=_fence_data(math_tools._answer_canonical(answer)),
        )

    async def _action_rectangle(self, args: dict[str, Any]) -> ToolResult:
        rect_input = RectangleGeometryInput(
            width=float(args["width"]),
            height=float(args["height"]),
            unit=str(args.get("unit") or "cm"),
        )
        rect_result = await self._run_off_loop(math_service.rectangle_geometry, rect_input)
        if rect_result is None:
            return ToolResult(name=self.name, content="Math error: timed out.")
        spec = GeometryBlockSpec(
            type="rectangle",
            width=rect_result.width,
            height=rect_result.height,
            unit=rect_result.unit,
            show_diagonal=True,
            show_angle=True,
            diagonal=rect_result.diagonal,
            angle_deg=rect_result.angle_deg,
            area=rect_result.area,
            perimeter=rect_result.perimeter,
            labels=rect_result.labels,
        )
        fence = spec.model_dump()
        fence_json = json.dumps(fence, separators=(",", ":"))
        return ToolResult(
            name=self.name,
            content=(
                f"Rectangle {rect_result.width}x{rect_result.height} {rect_result.unit}: "
                f"diagonal={rect_result.diagonal}, angle={rect_result.angle_deg}°\n"
                "When a diagram helps, emit ONLY this fence (NEVER ```json):\n"
                f"```geometry\n{fence_json}\n```"
            ),
            data=_fence_data(fence),
        )

    async def _action_square(self, args: dict[str, Any]) -> ToolResult:
        side = args.get("side")
        if side is None:
            side = args.get("width")
        if side is None:
            return ToolResult(
                name=self.name,
                content="Math error: square requires side (or width).",
            )
        square_input = SquareGeometryInput(
            side=float(side),
            unit=str(args.get("unit") or "cm"),
        )
        square_result = await self._run_off_loop(math_service.square_geometry, square_input)
        if square_result is None:
            return ToolResult(name=self.name, content="Math error: timed out.")
        spec = GeometryBlockSpec(
            type="square",
            side=square_result.side,
            width=square_result.side,
            height=square_result.side,
            unit=square_result.unit,
            show_diagonal=True,
            show_area=True,
            show_perimeter=True,
            diagonal=square_result.diagonal,
            area=square_result.area,
            perimeter=square_result.perimeter,
            labels=square_result.labels,
        )
        fence = spec.model_dump()
        fence_json = json.dumps(fence, separators=(",", ":"))
        return ToolResult(
            name=self.name,
            content=(
                f"Square side={square_result.side:g} {square_result.unit}: "
                f"diagonal={square_result.diagonal:g}, area={square_result.area:g}\n"
                "When a diagram helps, emit ONLY this fence (NEVER ```json):\n"
                f"```geometry\n{fence_json}\n```"
            ),
            data=_fence_data(fence),
        )

    async def _action_circle(self, args: dict[str, Any]) -> ToolResult:
        if args.get("radius") is None:
            return ToolResult(
                name=self.name,
                content="Math error: circle requires radius.",
            )
        circle_input = CircleGeometryInput(
            radius=float(args["radius"]),
            unit=str(args.get("unit") or "cm"),
        )
        circle_result = await self._run_off_loop(math_service.circle_geometry, circle_input)
        if circle_result is None:
            return ToolResult(name=self.name, content="Math error: timed out.")
        spec = CircleGeometryBlockSpec(
            type="circle",
            radius=circle_result.radius,
            unit=circle_result.unit,
            show_diameter=True,
            show_area=True,
            show_circumference=True,
            diameter=circle_result.diameter,
            area=circle_result.area,
            circumference=circle_result.circumference,
            labels=circle_result.labels,
        )
        fence = spec.model_dump()
        fence_json = json.dumps(fence, separators=(",", ":"))
        return ToolResult(
            name=self.name,
            content=(
                f"Circle radius={circle_result.radius:g} {circle_result.unit}: "
                f"diameter={circle_result.diameter:g}, "
                f"area={circle_result.area:.2f}, "
                f"circumference={circle_result.circumference:.2f}\n"
                "When a diagram helps, emit ONLY this fence (NEVER ```json):\n"
                f"```geometry\n{fence_json}\n```"
            ),
            data=_fence_data(fence),
        )

    async def _action_graph(self, args: dict[str, Any]) -> ToolResult:
        variable = str(args.get("variable") or "x")
        x_min = float(args.get("x_min") or -10)
        x_max = float(args.get("x_max") or 10)
        n = self.settings.math_graph_max_points
        expr = str(args.get("expr") or "x**2")

        # Axis-aligned circle/ellipse relations — parametric sample (not y=f(x)).
        ellipse = math_service.parse_ellipse_relation(expr)
        if ellipse is not None and not str(args.get("expr2") or "").strip():
            a, b = ellipse
            graph_result = await self._run_off_loop(math_service.sample_ellipse, a, b, n)
            if graph_result is None:
                return ToolResult(name=self.name, content="Math error: timed out.")
            graph_spec = GraphBlockSpec(
                expr=graph_result.expr,
                variable=graph_result.variable,
                x_min=graph_result.x_min,
                x_max=graph_result.x_max,
                y_min=-(b + max(1.0, b * 0.15)),
                y_max=b + max(1.0, b * 0.15),
                points=graph_result.points,
                segments=[],
                title=graph_result.expr,
            )
            fence = graph_spec.model_dump()
            fence_json = json.dumps(fence, separators=(",", ":"))
            return ToolResult(
                name=self.name,
                content=(
                    f"Sampled {len(graph_result.points)} parametric points for {graph_result.expr}\n"
                    "When a plot helps, emit ONLY this fence (NEVER ```json):\n"
                    f"```graph\n{fence_json}\n```"
                ),
                data=_fence_data(fence),
            )

        line_spec = math_service.number_line_spec_from_expr(expr, variable)
        if line_spec is not None and not str(args.get("expr2") or "").strip():
            fence = line_spec.model_dump()
            fence_json = json.dumps(fence, separators=(",", ":"))
            return ToolResult(
                name=self.name,
                content=(
                    f"Number line for {line_spec.expr} "
                    "(open circle = not included; filled = included).\n"
                    "When a plot helps, emit ONLY this fence (NEVER ```json):\n"
                    f"```graph\n{fence_json}\n```"
                ),
                data=_fence_data(fence),
            )

        graph_input = GraphSampleInput(
            expr=expr,
            variable=variable,
            x_min=x_min,
            x_max=x_max,
            n=n,
        )
        graph_result = await self._run_off_loop(math_service.sample_function, graph_input)
        if graph_result is None:
            return ToolResult(name=self.name, content="Math error: timed out.")
        has_discontinuity = len(graph_result.segments) > 1

        expr2_raw = str(args.get("expr2") or "").strip()
        expr2 = expr2_raw or None
        variable2 = None
        points2 = None
        segments2 = None
        label = str(args.get("label") or "").strip() or None
        label2 = str(args.get("label2") or "").strip() or None
        if expr2:
            var2 = str(args.get("variable2") or variable)
            sample2 = await self._run_off_loop(
                math_service.sample_function,
                GraphSampleInput(
                    expr=expr2,
                    variable=var2,
                    x_min=x_min,
                    x_max=x_max,
                    n=n,
                ),
            )
            if sample2 is None:
                return ToolResult(name=self.name, content="Math error: timed out.")
            expr2 = sample2.expr
            variable2 = sample2.variable
            points2 = sample2.points
            segments2 = sample2.segments if len(sample2.segments) > 1 else []
            if label is None:
                label = f"y = {graph_result.expr}"
            if label2 is None:
                label2 = f"y = {sample2.expr}"

        graph_spec = GraphBlockSpec(
            expr=graph_result.expr,
            variable=graph_result.variable,
            x_min=graph_result.x_min,
            x_max=graph_result.x_max,
            points=graph_result.points,
            segments=graph_result.segments if has_discontinuity else [],
            expr2=expr2,
            variable2=variable2,
            points2=points2,
            segments2=segments2,
            label=label,
            label2=label2,
        )
        fence = graph_spec.model_dump()
        fence_json = json.dumps(fence, separators=(",", ":"))
        if expr2:
            summary = (
                f"Sampled {len(graph_result.points)} + {len(points2 or [])} points "
                f"for {graph_result.expr} and {expr2}\n"
            )
        else:
            summary = f"Sampled {len(graph_result.points)} points for {graph_result.expr}\n"
        return ToolResult(
            name=self.name,
            content=(
                summary + "When a plot helps, emit ONLY this fence (NEVER ```json):\n"
                f"```graph\n{fence_json}\n```"
            ),
            data=_fence_data(fence),
        )

    async def invoke(self, args: dict[str, Any]) -> ToolResult:
        action = str(args.get("action") or "solve").strip().lower()
        try:
            handler = _ACTION_HANDLERS.get(action)
            if handler is not None:
                return await handler(self, args)
            intent = math_tools.extract_math_intent(str(args.get("text") or ""))
            if intent:
                block = await math_tools._build_verified_block_async(intent, self.settings)
                if block:
                    return ToolResult(
                        name=self.name,
                        content=block.text,
                        data=_fence_data(block.canonical_fence),
                    )
            return ToolResult(name=self.name, content="No math result.")
        except Exception as exc:
            return ToolResult(name=self.name, content=f"Math error: {exc}")


_ACTION_HANDLERS: dict[str, _ActionHandler] = {
    "solve": SympyAdapter._action_solve,
    "simplify": SympyAdapter._action_expr_op,
    "diff": SympyAdapter._action_expr_op,
    "integrate": SympyAdapter._action_expr_op,
    "factor": SympyAdapter._action_expr_op,
    "expand": SympyAdapter._action_expr_op,
    "inequality": SympyAdapter._action_inequality,
    "system": SympyAdapter._action_system,
    "limit": SympyAdapter._action_limit,
    "series": SympyAdapter._action_series,
    "newton": SympyAdapter._action_newton,
    "rectangle": SympyAdapter._action_rectangle,
    "square": SympyAdapter._action_square,
    "circle": SympyAdapter._action_circle,
    "graph": SympyAdapter._action_graph,
}
