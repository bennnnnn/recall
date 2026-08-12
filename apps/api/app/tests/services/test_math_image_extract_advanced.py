"""Camera OCR beyond a single equation — systems and inequalities.

Before this, ANY photographed math problem that wasn't exactly one "lhs=rhs"
equation (a system of equations, a bare inequality) silently lost the
SymPy-verified path and fell back to the model's unverified free-text guess,
regardless of how well OCR itself extracted the text.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.models.math_schemas import MathImageExtract
from app.services import math_tools


class TestMathImageExtractSchema:
    def test_defaults_to_equation_kind(self):
        parsed = MathImageExtract(lhs="2*x+3", rhs="7", variables=["x"])
        assert parsed.kind == "equation"

    def test_system_kind_with_full_equations(self):
        parsed = MathImageExtract(
            kind="system",
            lhs="x+y",
            rhs="5",
            equations=[("x+y", "5"), ("x-y", "1")],
            variables=["x", "y"],
        )
        assert parsed.kind == "system"
        assert len(parsed.equations) == 2

    def test_system_kind_degrades_to_equation_when_equations_incomplete(self):
        """Graceful degrade: a vision model that says kind="system" but
        only extracted one equation must not lose the whole extraction —
        fall back to treating lhs/rhs as a single equation instead of
        failing schema validation entirely."""
        parsed = MathImageExtract(
            kind="system", lhs="x+y", rhs="5", equations=[("x+y", "5")], variables=["x", "y"]
        )
        assert parsed.kind == "equation"

    def test_inequality_kind_with_valid_comparator(self):
        parsed = MathImageExtract(
            kind="inequality", lhs="x**2-1", rhs="0", comparator=">", variables=["x"]
        )
        assert parsed.kind == "inequality"

    def test_inequality_kind_degrades_to_equation_without_comparator(self):
        parsed = MathImageExtract(kind="inequality", lhs="x", rhs="0", variables=["x"])
        assert parsed.kind == "equation"

    def test_inequality_kind_degrades_to_equation_with_invalid_comparator(self):
        parsed = MathImageExtract(
            kind="inequality", lhs="x", rhs="0", comparator="!=", variables=["x"]
        )
        assert parsed.kind == "equation"

    def test_calculus_kind_requires_expr_and_operation(self):
        parsed = MathImageExtract(
            kind="calculus",
            operation="differentiate",
            expr="x**2",
            variables=["x"],
        )
        assert parsed.kind == "calculus"
        assert parsed.found is True

    def test_incomplete_calculus_marks_not_found(self):
        parsed = MathImageExtract(kind="calculus", expr="x**2", variables=["x"])
        assert parsed.found is False

    def test_incomplete_calculus_degrades_to_equation_when_sides_present(self):
        parsed = MathImageExtract(kind="calculus", lhs="2*x", rhs="4", variables=["x"])
        assert parsed.kind == "equation"
        assert parsed.found is True

    def test_limit_and_graph_and_geometry_kinds(self):
        limit = MathImageExtract(kind="limit", expr="sin(x)/x", limit_point="0", variables=["x"])
        assert limit.kind == "limit"
        graph = MathImageExtract(kind="graph", expr="x**2", variables=["x"])
        assert graph.kind == "graph"
        rect = MathImageExtract(kind="rectangle", width=8, height=5, unit="cm")
        assert rect.kind == "rectangle"
        circle = MathImageExtract(kind="circle", radius=3, unit="cm")
        assert circle.kind == "circle"


class TestAugmentPromptMessagesFromImageExtract:
    @pytest.mark.asyncio
    async def test_system_extract_solves_full_system(self):
        settings = Settings(
            mcp_tools_enabled=False, web_search_enabled=False, math_tools_enabled=True
        )
        extract = MathImageExtract(
            kind="system",
            lhs="x+y",
            rhs="5",
            equations=[("x+y", "5"), ("x-y", "1")],
            variables=["x", "y"],
        )
        text = "Solve the math problem in this image step by step."
        messages = [{"role": "system", "content": "base"}, {"role": "user", "content": text}]
        _, verified = await math_tools.augment_prompt_messages(
            messages, text, settings, has_image_attachment=True, image_math_extract=extract
        )
        assert verified is not None
        assert "x = 3" in verified.text
        assert "y = 2" in verified.text

    @pytest.mark.asyncio
    async def test_inequality_extract_solves_inequality(self):
        settings = Settings(
            mcp_tools_enabled=False, web_search_enabled=False, math_tools_enabled=True
        )
        extract = MathImageExtract(
            kind="inequality", lhs="x**2-1", rhs="0", comparator=">", variables=["x"]
        )
        text = "Solve the math problem in this image step by step."
        messages = [{"role": "system", "content": "base"}, {"role": "user", "content": text}]
        _, verified = await math_tools.augment_prompt_messages(
            messages, text, settings, has_image_attachment=True, image_math_extract=extract
        )
        assert verified is not None
        assert "Inequality" in verified.text

    @pytest.mark.asyncio
    async def test_plain_equation_extract_is_unaffected(self):
        """Backward compat: the original single-equation shape (no kind
        field set explicitly) still produces the same equation-solve path."""
        settings = Settings(
            mcp_tools_enabled=False, web_search_enabled=False, math_tools_enabled=True
        )
        extract = MathImageExtract(lhs="2*x+3", rhs="7", variables=["x"])
        text = "Solve the math problem in this image step by step."
        messages = [{"role": "system", "content": "base"}, {"role": "user", "content": text}]
        _, verified = await math_tools.augment_prompt_messages(
            messages, text, settings, has_image_attachment=True, image_math_extract=extract
        )
        assert verified is not None
        assert "Solutions" in verified.text

    @pytest.mark.asyncio
    async def test_calculus_extract_differentiates(self):
        settings = Settings(
            mcp_tools_enabled=False, web_search_enabled=False, math_tools_enabled=True
        )
        extract = MathImageExtract(
            kind="calculus",
            operation="differentiate",
            expr="x**2",
            variables=["x"],
        )
        text = "Solve the math problem in this image step by step."
        messages = [{"role": "system", "content": "base"}, {"role": "user", "content": text}]
        _, verified = await math_tools.augment_prompt_messages(
            messages, text, settings, has_image_attachment=True, image_math_extract=extract
        )
        assert verified is not None
        assert verified.canonical_fence is not None
        assert verified.canonical_fence["type"] == "answer"
        assert "2" in verified.canonical_fence["content"]

    @pytest.mark.asyncio
    async def test_limit_extract_evaluates(self):
        settings = Settings(
            mcp_tools_enabled=False, web_search_enabled=False, math_tools_enabled=True
        )
        extract = MathImageExtract(
            kind="limit",
            expr="x**2",
            limit_point="3",
            variables=["x"],
        )
        text = "Solve the math problem in this image step by step."
        _, verified = await math_tools.augment_prompt_messages(
            [{"role": "user", "content": text}],
            text,
            settings,
            has_image_attachment=True,
            image_math_extract=extract,
        )
        assert verified is not None
        assert verified.canonical_fence == {"type": "answer", "content": "9"}

    @pytest.mark.asyncio
    async def test_unicode_equation_extract_solves(self):
        """OCR multiply-sign must ascii-ize through normalize so SymPy can verify."""
        settings = Settings(
            mcp_tools_enabled=False, web_search_enabled=False, math_tools_enabled=True
        )
        extract = MathImageExtract(lhs="2\u00d7x+3", rhs="7", variables=["x"])
        text = "Solve the math problem in this image step by step."
        _, verified = await math_tools.augment_prompt_messages(
            [{"role": "user", "content": text}],
            text,
            settings,
            has_image_attachment=True,
            image_math_extract=extract,
        )
        assert verified is not None
        assert "2" in verified.text
        assert verified.canonical_fence is not None

    @pytest.mark.asyncio
    async def test_rectangle_extract_builds_geometry_fence(self):
        settings = Settings(
            mcp_tools_enabled=False, web_search_enabled=False, math_tools_enabled=True
        )
        extract = MathImageExtract(kind="rectangle", width=8, height=5, unit="cm")
        text = "Solve the math problem in this image step by step."
        _, verified = await math_tools.augment_prompt_messages(
            [{"role": "user", "content": text}],
            text,
            settings,
            has_image_attachment=True,
            image_math_extract=extract,
        )
        assert verified is not None
        assert verified.canonical_fence is not None
        assert verified.canonical_fence["type"] == "rectangle"
