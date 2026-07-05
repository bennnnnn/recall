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
    out, verified = await math_tools.augment_prompt_messages(
        messages,
        "rectangle 8 x 5 cm diagonal angle",
        settings,
    )
    assert len(out) == 2
    assert "```geometry" in out[0]["content"]
    assert "diagonal" in out[0]["content"]
    assert verified is not None
    assert verified.canonical_fence is not None
    assert verified.canonical_fence["type"] == "rectangle"


@pytest.mark.asyncio
async def test_augment_prompt_injects_graph_block() -> None:
    settings = Settings(math_tools_enabled=True)
    messages = [{"role": "user", "content": "Graph y = x^2"}]
    out, verified = await math_tools.augment_prompt_messages(messages, "Graph y = x^2", settings)
    assert len(out) == 2
    assert "```graph" in out[0]["content"]
    assert "points" in out[0]["content"]
    assert verified is not None
    assert verified.canonical_fence is not None
    assert verified.canonical_fence["type"] == "function"


@pytest.mark.asyncio
async def test_augment_prompt_injects_sympy_block() -> None:
    settings = Settings(math_tools_enabled=True)
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "Solve x^2 + 2 = 6"},
    ]
    out, verified = await math_tools.augment_prompt_messages(
        messages,
        "Solve x^2 + 2 = 6",
        settings,
    )
    assert len(out) == 3
    assert out[1]["role"] == "system"
    assert "SymPy" in out[1]["content"]
    assert "Solutions" in out[1]["content"]
    # Equation answers are plain-text/LaTeX, not a geometry/graph fence.
    assert verified is not None
    assert verified.canonical_fence is None


@pytest.mark.asyncio
async def test_sympy_solve_runs_off_event_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    """The blocking SymPy call must not run on the event loop thread."""
    import threading

    settings = Settings(math_tools_enabled=True)
    caller_thread = threading.current_thread()
    seen_thread: dict[str, threading.Thread] = {}

    original = math_tools._build_verified_block

    def spy(intent, settings):  # type: ignore[no-untyped-def]
        seen_thread["thread"] = threading.current_thread()
        return original(intent, settings)

    monkeypatch.setattr(math_tools, "_build_verified_block", spy)

    out, _verified = await math_tools.augment_prompt_messages(
        [{"role": "user", "content": "Solve x^2 + 2 = 6"}],
        "Solve x^2 + 2 = 6",
        settings,
    )

    assert seen_thread["thread"] is not caller_thread
    assert len(out) == 2


@pytest.mark.asyncio
async def test_augment_prompt_times_out_gracefully(monkeypatch: pytest.MonkeyPatch) -> None:
    """A hung solve should fall back to no verified block, not hang the caller."""
    settings = Settings(math_tools_enabled=True, math_solve_timeout_seconds=0.05)

    def slow_build(intent, settings):  # type: ignore[no-untyped-def]
        import time

        time.sleep(0.5)
        return "should never be returned"

    monkeypatch.setattr(math_tools, "_build_verified_block", slow_build)

    messages = [{"role": "user", "content": "Solve x^2 + 2 = 6"}]
    out, verified = await math_tools.augment_prompt_messages(
        messages,
        "Solve x^2 + 2 = 6",
        settings,
    )

    assert out == messages
    assert verified is None
