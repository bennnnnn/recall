"""Multi-curve graph overlay — "graph y=x^2 and y=2x on the same graph"."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.models.math_schemas import GraphBlockSpec
from app.services import math_fence, math_text_match, math_tools


class TestGraphExprPairSignal:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("graph y=x^2 and y=2x on the same graph", ("x^2", "2x")),
            ("compare y=x^2 and y=2x", ("x^2", "2x")),
            ("plot x^2 and 2x together", ("x^2", "2x")),
        ],
    )
    def test_matches_two_function_asks(self, text, expected):
        assert math_text_match.graph_expr_pair(text) == expected

    def test_does_not_swallow_trailing_prose_as_a_second_function(self):
        """Regression: "plot sin(x) and explain it" used to be read as a
        second function literally named "explain it"."""
        assert math_text_match.graph_expr_pair("plot sin(x) and explain it") is None

    def test_single_function_ask_does_not_match(self):
        assert math_text_match.graph_expr_pair("plot x^2") is None


class TestAugmentPromptMessagesForGraphPair:
    @pytest.mark.asyncio
    async def test_produces_two_curve_canonical_fence(self):
        settings = Settings(
            mcp_tools_enabled=False, web_search_enabled=False, math_tools_enabled=True
        )
        text = "graph y=x^2 and y=2x on the same graph"
        messages = [{"role": "system", "content": "base"}, {"role": "user", "content": text}]
        _, verified = await math_tools.augment_prompt_messages(messages, text, settings)
        assert verified is not None
        fence = verified.canonical_fence
        assert fence is not None
        assert fence["expr2"] is not None
        assert fence["points2"]
        assert len(fence["points2"]) > 1

    @pytest.mark.asyncio
    async def test_single_function_ask_is_unaffected(self):
        settings = Settings(
            mcp_tools_enabled=False, web_search_enabled=False, math_tools_enabled=True
        )
        text = "plot sin(x) and explain it"
        messages = [{"role": "system", "content": "base"}, {"role": "user", "content": text}]
        _, verified = await math_tools.augment_prompt_messages(messages, text, settings)
        assert verified is not None
        assert verified.canonical_fence["expr2"] is None


class TestDensifyPreservesSecondCurve:
    def test_densify_sparse_first_curve_keeps_second_curve_intact(self):
        sparse = GraphBlockSpec(
            expr="x**2",
            variable="x",
            x_min=-10,
            x_max=10,
            points=[[-2, 4], [0, 0], [2, 4]],  # sparse — under _MIN_CURVE_POINTS
            expr2="2*x",
            variable2="x",
            points2=[[-10, -20], [10, 20]],
            label="y = x^2",
            label2="y = 2x",
        )
        densified = math_fence.densify_sparse_graph(sparse)
        assert len(densified.points) > len(sparse.points)  # curve 1 got densified
        assert densified.expr2 == "2*x"
        assert densified.points2 == [[-10, -20], [10, 20]]  # curve 2 untouched
        assert densified.label2 == "y = 2x"
