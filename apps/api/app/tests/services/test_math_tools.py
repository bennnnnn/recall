"""Tests for math tools heuristics and prompt injection."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.services import math_tools


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Solve x^2 + 2 = 6", True),
        ("What's the weather?", False),
        ("A rectangle is 8×5 cm. Find the diagonal angle.", True),
        ("Graph y = x^2", True),
        ("Draw a rectangle", True),
    ],
)
def test_needs_symbolic_math(text: str, expected: bool) -> None:
    assert math_tools.needs_symbolic_math(text) is expected


def test_extract_equation_intent() -> None:
    intent = math_tools.extract_math_intent("Solve x^2 + 2 = 6")
    assert intent is not None
    assert intent.kind == "equation"
    assert intent.lhs is not None
    assert intent.rhs is not None


def test_extract_rectangle_intent() -> None:
    intent = math_tools.extract_math_intent("rectangle 8 x 5 cm find diagonal")
    assert intent is not None
    assert intent.kind == "rectangle"
    assert intent.width == 8
    assert intent.height == 5


def test_extract_draw_rectangle_defaults() -> None:
    intent = math_tools.extract_math_intent("Draw a rectangle")
    assert intent is not None
    assert intent.kind == "rectangle"
    assert intent.width == 6
    assert intent.height == 4


def test_extract_square_intent() -> None:
    intent = math_tools.extract_math_intent("Draw a square with side 5 cm")
    assert intent is not None
    assert intent.kind == "square"
    assert intent.side == 5


@pytest.mark.asyncio
async def test_augment_prompt_injects_geometry_block() -> None:
    settings = Settings(math_tools_enabled=True)
    messages = [{"role": "user", "content": "rectangle 8 x 5 cm diagonal angle"}]
    out = await math_tools.augment_prompt_messages(
        messages,
        "rectangle 8 x 5 cm diagonal angle",
        settings,
    )
    assert len(out) == 2
    assert "```geometry" in out[0]["content"]
    assert "diagonal" in out[0]["content"]


@pytest.mark.asyncio
async def test_augment_prompt_injects_graph_block() -> None:
    settings = Settings(math_tools_enabled=True)
    messages = [{"role": "user", "content": "Graph y = x^2"}]
    out = await math_tools.augment_prompt_messages(messages, "Graph y = x^2", settings)
    assert len(out) == 2
    assert "```graph" in out[0]["content"]
    assert "points" in out[0]["content"]


@pytest.mark.asyncio
async def test_augment_prompt_injects_sympy_block() -> None:
    settings = Settings(math_tools_enabled=True)
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "Solve x^2 + 2 = 6"},
    ]
    out = await math_tools.augment_prompt_messages(
        messages,
        "Solve x^2 + 2 = 6",
        settings,
    )
    assert len(out) == 3
    assert out[1]["role"] == "system"
    assert "SymPy" in out[1]["content"]
    assert "Solutions" in out[1]["content"]
