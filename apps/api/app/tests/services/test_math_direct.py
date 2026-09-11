"""Direct verified-math replies skip the LLM when language adds nothing."""

from __future__ import annotations

import pytest

from app.core.config import Settings
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


def test_can_direct_skips_graphs_and_camera() -> None:
    graph = VerifiedMathBlock(
        text="plot",
        canonical_fence={"type": "graph", "expr": "x"},
        canonical_answer="y = x",
    )
    assert can_direct_verified_math_reply(graph, "graph y=x") is False
    assert (
        can_direct_verified_math_reply(
            _answer_block("x = 2"),
            "1+1=x",
            has_image_attachment=True,
        )
        is False
    )


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
