"""Direct verified-math replies skip the LLM when language adds nothing."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from app.core.config import Settings
from app.models.schemas.math import GraphBlockSpec
from app.services.math_tools.block.common import VerifiedMathBlock
from app.services.math_tools.direct import (
    can_direct_verified_math_reply,
    format_direct_math_reply,
    maybe_direct_math_reply,
    wants_math_explanation,
)
from app.services.math_tools.prompt import build_math_augmentation


def _answer_block(answer: str) -> VerifiedMathBlock:
    return VerifiedMathBlock(
        text="verified",
        canonical_fence={"type": "answer", "content": answer},
        canonical_answer=answer,
    )


def _graph_block(*, x_min: float = -10, x_max: float = 10) -> VerifiedMathBlock:
    return VerifiedMathBlock(
        text="Function samples for x**3: 3 points.",
        canonical_fence=GraphBlockSpec(
            expr="x**3", points=[[-1, -1], [0, 0], [1, 1]], x_min=x_min, x_max=x_max
        ).model_dump(),
    )


@pytest.mark.parametrize(
    "text, expected",
    [
        ("1+1=x", False),
        ("Factor x^2 - 5x + 6", False),
        ("solve 2x^2-7x+3=0", False),
        ("1+1=x and explain every step", True),
        ("Factor x^2 - 5x + 6 and teach me how factoring works", True),
        ("show your work for 1+1", True),
        ("Solve 1+1=x and show me your work", True),
        ("prove 1+1=2", True),
        ("approve this 1+1=x", False),
    ],
)
def test_wants_math_explanation(text: str, expected: bool) -> None:
    assert wants_math_explanation(text) is expected


def test_compound_prompt_keeps_llm() -> None:
    block = _answer_block("x = 1")
    assert can_direct_verified_math_reply(block, "Solve x+1=2") is True
    assert can_direct_verified_math_reply(block, "Solve x+1=2 and tell me a joke") is False
    assert maybe_direct_math_reply(block, "Solve 1+1=x and show me your work") is None


def test_can_direct_skips_force_energy_unlabeled_quantity() -> None:
    block = VerifiedMathBlock(
        text="verified",
        canonical_fence={"type": "answer", "content": "5.00 m/s^2"},
        canonical_answer="5.00 m/s^2",
        allow_direct=False,
    )
    assert can_direct_verified_math_reply(block, "A force of 10 N on 2 kg") is False
    assert maybe_direct_math_reply(block, "A force of 10 N on 2 kg") is None


def test_can_direct_skips_geometry_and_camera() -> None:
    geometry = VerifiedMathBlock(
        text="rectangle",
        canonical_fence={"type": "rectangle", "width": 3, "height": 4},
        canonical_answer="12",
    )
    assert can_direct_verified_math_reply(geometry, "draw a rectangle") is False
    assert (
        can_direct_verified_math_reply(
            _answer_block("x = 2"),
            "1+1=x",
            has_image_attachment=True,
        )
        is False
    )
    assert maybe_direct_math_reply(_graph_block(), "graph y=x^3", has_image_attachment=True) is None


@pytest.mark.parametrize(
    "query",
    [
        "graph y = x^3",
        "Graph y = x³",
        "plot x^3",
        "please graph $y = x^{3}$",
        "draw y=x^3",
        "sketch x^3.",
        "visualize x^3",
    ],
)
def test_plain_explicit_graph_returns_complete_canonical_fence(query: str) -> None:
    verified = _graph_block()
    assert can_direct_verified_math_reply(verified, query) is True
    reply = maybe_direct_math_reply(verified, query)
    assert reply is not None
    assert reply.startswith("```graph\n")
    assert reply.endswith("\n```\n")  # Required to render before mobile receives done.
    assert json.loads(reply.removeprefix("```graph\n").removesuffix("\n```\n")) == (
        verified.canonical_fence
    )
    assert "```answer" not in reply


@pytest.mark.parametrize(
    "query",
    [
        "graph y=x^3 and explain it",
        "explain the graph y=x^3",
        "graph y=x^3 and solve x+1=2",
        "graph y=x^3 and 1+1",
        "graph y=x^3 then factor x^2-1",
        "graph y=x^3 and tell me a joke",
        "graph y=x^3, describe its shape",
        "graph y=x^3; 2+2",
        "graph y=x^3\nshow your work",
        "solve 2+2 then graph y=x^3",
        "graph y=x^3 and y=x^2",
        "graph y=x^3 from -1 to 1 and solve 2+2",
        "graph y=x^3 from 0 to 1",
        "graph y=x^3 from 1 to 0",
        "graph y=x^2",
        "graph y=x^3!",
        "y=x^3",
        "what does y=x^3 look like?",
    ],
)
def test_graph_request_must_be_complete_and_match_verified_plot(query: str) -> None:
    assert maybe_direct_math_reply(_graph_block(), query) is None


@pytest.mark.parametrize("domain", ["from -1 to 1", "on [-1, 1]"])
def test_graph_domain_must_match_verified_bounds(domain: str) -> None:
    query = f"graph y=x^3 {domain}"
    assert maybe_direct_math_reply(_graph_block(x_min=-1, x_max=1), query) is not None
    assert maybe_direct_math_reply(_graph_block(), query) is None


def test_graph_requires_one_complete_function_and_allows_no_other_answer() -> None:
    block = _graph_block()
    assert maybe_direct_math_reply(replace(block, allow_direct=False), "graph y=x^3") is None
    assert maybe_direct_math_reply(replace(block, canonical_answer="x = 3"), "graph y=x^3") is None
    assert (
        maybe_direct_math_reply(
            replace(block, canonical_fences=[{"type": "answer", "content": "3"}]),
            "graph y=x^3",
        )
        is None
    )
    invalid_changes: tuple[dict[str, object], ...] = (
        {"type": "trajectory"},
        {"type": "number_line"},
        {"type": "vertical"},
        {"points": []},
        {"points": [[0, 0]]},
        {"expr2": "x**2", "points2": [[0, 0], [1, 1]]},
    )
    for changes in invalid_changes:
        graph = {**(block.canonical_fence or {}), **changes}
        assert maybe_direct_math_reply(replace(block, canonical_fence=graph), "graph y=x^3") is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "x_min", "x_max"),
    [
        ("graph y = x^3", -10, 10),
        ("graph y = x^3 from -1 to 1", -1, 1),
        ("graph y = x^3 on [-1, 1]", -1, 1),
    ],
)
async def test_exact_cubic_returns_verified_graph_without_model(
    thread_sympy_executor: None, query: str, x_min: int, x_max: int
) -> None:
    from app.services.math_fence import validate_math_fences_worker

    _note, verified = await build_math_augmentation(query, Settings(math_tools_enabled=True))
    assert verified is not None
    reply = maybe_direct_math_reply(verified, query)
    assert reply is not None
    graph = json.loads(reply.removeprefix("```graph\n").removesuffix("\n```\n"))
    assert graph == verified.canonical_fence
    assert graph["expr"] == "x**3"
    assert len(graph["points"]) == 96
    assert (graph["x_min"], graph["x_max"]) == (x_min, x_max)
    final = validate_math_fences_worker(reply, verified)
    assert final.count("```graph") == 1
    assert json.loads(final.split("```graph\n")[1].split("\n```")[0]) == graph


@pytest.mark.asyncio
async def test_factorial_suffix_cannot_be_silently_dropped_by_direct_graph(
    thread_sympy_executor: None,
) -> None:
    query = "graph y=x^3!"
    _note, verified = await build_math_augmentation(query, Settings(math_tools_enabled=True))
    assert maybe_direct_math_reply(verified, query) is None


def test_format_direct_math_reply_includes_answer_fence() -> None:
    text = format_direct_math_reply(_answer_block("x = 2"))
    assert "$x = 2$" in text
    assert "```answer" in text
    assert "x = 2" in text


@pytest.mark.asyncio
async def test_one_plus_one_returns_direct_reply(thread_sympy_executor: None) -> None:
    settings = Settings(math_tools_enabled=True)
    _block, verified = await build_math_augmentation("1+1=x", settings)
    assert verified is not None
    reply = maybe_direct_math_reply(verified, "1+1=x")
    assert reply is not None
    assert "2" in reply
    assert "```answer" in reply


@pytest.mark.asyncio
async def test_explain_keeps_llm_path(thread_sympy_executor: None) -> None:
    settings = Settings(math_tools_enabled=True)
    content = "Solve 1+1=x and explain every step"
    _block, verified = await build_math_augmentation(content, settings)
    assert verified is not None
    assert maybe_direct_math_reply(verified, content) is None


@pytest.mark.asyncio
async def test_bare_arithmetic_returns_direct_reply(thread_sympy_executor: None) -> None:
    """``8-8*2`` must verify (not stamp Couldn't verify) and skip the LLM."""
    settings = Settings(math_tools_enabled=True)
    note, verified = await build_math_augmentation("8-8*2", settings)
    assert verified is not None
    assert note is not None
    assert "could not produce a verified result" not in note.lower()
    reply = maybe_direct_math_reply(verified, "8-8*2")
    assert reply is not None
    assert "-8" in reply.replace(" ", "")


@pytest.mark.asyncio
async def test_date_does_not_skip_the_llm(thread_sympy_executor: None) -> None:
    settings = Settings(math_tools_enabled=True)
    _note, verified = await build_math_augmentation("9/7/2026", settings)
    assert verified is None
    assert maybe_direct_math_reply(verified, "9/7/2026") is None
