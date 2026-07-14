"""SymPy MCP adapter."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any, TypeVar

from app.core.config import Settings
from app.gateways.mcp.base import ToolResult
from app.models.math_schemas import (
    EquationInput,
    GeometryBlockSpec,
    GraphBlockSpec,
    GraphSampleInput,
    RectangleGeometryInput,
)
from app.models.tool_schemas import SympyToolInput
from app.services import math_service, math_tools

logger = logging.getLogger(__name__)

_T = TypeVar("_T")


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
            "Symbolic math: solve equations, simplify, differentiate, integrate, geometry, graphs."
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

    async def _run_off_loop(self, fn: Callable[[], _T]) -> _T | None:
        """Run synchronous, CPU-bound SymPy work off the event loop with a
        hard timeout.

        BUG FIX (was silent): math_tools.py's chat-path callers already wrap
        every SymPy call this way — its own docstring explains why (solve/
        integrate/etc. are synchronous and can stall every concurrent chat
        stream on this worker's single event loop on a pathological
        expression). This adapter called math_service functions directly,
        synchronously, with none of that protection — a hung/expensive
        expression reaching it via the model-callable "sympy" tool blocked
        the whole worker with no timeout at all.
        """
        try:
            async with asyncio.timeout(self.settings.math_solve_timeout_seconds):
                return await asyncio.to_thread(fn)
        except TimeoutError:
            logger.warning("sympy MCP tool call timed out")
            return None

    async def invoke(self, args: dict[str, Any]) -> ToolResult:
        action = str(args.get("action") or "solve").strip().lower()
        try:
            if action == "solve":
                data = EquationInput(
                    lhs=str(args.get("lhs") or ""),
                    rhs=str(args.get("rhs") or ""),
                    variables=list(args.get("variables") or ["x"]),
                )
                result = await self._run_off_loop(lambda: math_service.solve_equation(data))
                if result is None:
                    return ToolResult(name=self.name, content="Math error: timed out.")
                return ToolResult(name=self.name, content="\n".join(result.steps))
            if action in ("simplify", "diff", "integrate"):
                expr = str(args.get("expr") or "")
                variable = str(args.get("variable") or "x")
                fn = {
                    "simplify": math_service.simplify_expression,
                    "diff": math_service.differentiate_expression,
                    "integrate": math_service.integrate_expression,
                }[action]
                expr_result = await self._run_off_loop(lambda: fn(expr, variable))
                if expr_result is None:
                    return ToolResult(name=self.name, content="Math error: timed out.")
                return ToolResult(name=self.name, content=expr_result.result)
            if action == "rectangle":
                rect_input = RectangleGeometryInput(
                    width=float(args["width"]),
                    height=float(args["height"]),
                    unit=str(args.get("unit") or "cm"),
                )
                rect_result = await self._run_off_loop(
                    lambda: math_service.rectangle_geometry(rect_input)
                )
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
            if action == "graph":
                graph_input = GraphSampleInput(
                    expr=str(args.get("expr") or "x**2"),
                    variable=str(args.get("variable") or "x"),
                    x_min=float(args.get("x_min") or -10),
                    x_max=float(args.get("x_max") or 10),
                    n=self.settings.math_graph_max_points,
                )
                graph_result = await self._run_off_loop(
                    lambda: math_service.sample_function(graph_input)
                )
                if graph_result is None:
                    return ToolResult(name=self.name, content="Math error: timed out.")
                has_discontinuity = len(graph_result.segments) > 1
                graph_spec = GraphBlockSpec(
                    expr=graph_result.expr,
                    variable=graph_result.variable,
                    x_min=graph_result.x_min,
                    x_max=graph_result.x_max,
                    points=graph_result.points,
                    segments=graph_result.segments if has_discontinuity else [],
                )
                fence = graph_spec.model_dump()
                fence_json = json.dumps(fence, separators=(",", ":"))
                return ToolResult(
                    name=self.name,
                    content=(
                        f"Sampled {len(graph_result.points)} points for {graph_result.expr}\n"
                        "When a plot helps, emit ONLY this fence (NEVER ```json):\n"
                        f"```graph\n{fence_json}\n```"
                    ),
                    data=_fence_data(fence),
                )
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
