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
