"""SymPy MCP adapter."""

from __future__ import annotations

from typing import Any

from app.core.config import Settings
from app.gateways.mcp.base import ToolResult
from app.models.math_schemas import EquationInput, GraphSampleInput, RectangleGeometryInput
from app.services import math_service, math_tools


class SympyAdapter:
    name = "sympy"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def describe(self) -> str:
        return "Symbolic math: solve equations, simplify, differentiate, integrate, geometry, graphs."

    async def invoke(self, args: dict[str, Any]) -> ToolResult:
        action = str(args.get("action") or "solve").strip().lower()
        try:
            if action == "solve":
                data = EquationInput(
                    lhs=str(args.get("lhs") or ""),
                    rhs=str(args.get("rhs") or ""),
                    variables=list(args.get("variables") or ["x"]),
                )
                result = math_service.solve_equation(data)
                return ToolResult(name=self.name, content="\n".join(result.steps))
            if action == "rectangle":
                data = RectangleGeometryInput(
                    width=float(args["width"]),
                    height=float(args["height"]),
                    unit=str(args.get("unit") or "cm"),
                )
                result = math_service.rectangle_geometry(data)
                return ToolResult(
                    name=self.name,
                    content=(
                        f"Rectangle {result.width}×{result.height} {result.unit}: "
                        f"diagonal={result.diagonal}, angle={result.angle_deg}°"
                    ),
                )
            if action == "graph":
                data = GraphSampleInput(
                    expr=str(args.get("expr") or "x**2"),
                    variable=str(args.get("variable") or "x"),
                    x_min=float(args.get("x_min") or -10),
                    x_max=float(args.get("x_max") or 10),
                )
                result = math_service.sample_function(data)
                return ToolResult(
                    name=self.name,
                    content=f"Sampled {len(result.points)} points for {result.expr}",
                )
            intent = math_tools.extract_math_intent(str(args.get("text") or ""))
            if intent:
                block = math_tools._build_verified_block(intent, self.settings)
                if block:
                    return ToolResult(name=self.name, content=block)
            return ToolResult(name=self.name, content="No math result.")
        except Exception as exc:
            return ToolResult(name=self.name, content=f"Math error: {exc}")
