"""One response-intent contract across extraction, direct replies, and fences."""

import pytest

from app.core.config import Settings
from app.modules.math.fence import validate_math_fences
from app.modules.math.response_intent import (
    MathMethod,
    MathResponseMode,
    classify_math_response_intent,
)
from app.modules.math.tools.block import _build_verified_block
from app.modules.math.tools.direct import maybe_direct_math_reply
from app.modules.math.tools.extract import extract_math_intent
from app.modules.math.tools.prompt import _withhold_hint_answer, build_math_augmentation

_SETTINGS = Settings(math_tools_enabled=True)


def _block(query: str):
    intent = extract_math_intent(query)
    assert intent is not None
    block = _build_verified_block(intent, _SETTINGS)
    assert block is not None
    return block


def test_semantic_modes_and_requested_methods_are_centralized() -> None:
    assert classify_math_response_intent("just give me x").mode == MathResponseMode.ANSWER_ONLY
    assert classify_math_response_intent("walk me through it").mode == MathResponseMode.STEPS
    assert classify_math_response_intent("Why?").referential is True
    assert classify_math_response_intent("How do plants grow?").referential is False
    requested = classify_math_response_intent(
        "Use the quadratic formula and do not factor this equation"
    )
    assert requested.requested_method == MathMethod.QUADRATIC_FORMULA


def test_equivalent_equation_prompts_follow_the_requested_presentation() -> None:
    normal = "Solve 2x+3=7"
    answer_only = "Solve 2x+3=7. Just give me x; no work."
    steps = "Show every step for 2x+3=7"
    explain = "Explain why each step is valid for 2x+3=7"
    lowercase = "Solve 2x+3=7 and keep x lowercase in the final answer"

    normal_reply = maybe_direct_math_reply(_block(normal), normal, response_style="short")
    answer_reply = maybe_direct_math_reply(
        _block(answer_only), answer_only, response_style="balanced"
    )
    steps_reply = maybe_direct_math_reply(_block(steps), steps, response_style="balanced")
    explain_reply = maybe_direct_math_reply(_block(explain), explain, response_style="detailed")
    lowercase_reply = maybe_direct_math_reply(
        _block(lowercase), lowercase, response_style="balanced"
    )

    assert normal_reply is not None and "**1." in normal_reply
    assert answer_reply == "```answer\nx = 2\n```\n"
    assert steps_reply is not None and "**1." in steps_reply and "**2." in steps_reply
    assert explain_reply is not None and "this removes the added 3" in explain_reply
    assert (
        lowercase_reply is not None and "x = 2" in lowercase_reply and "X =" not in lowercase_reply
    )


def test_hint_mode_removes_every_answer_bearing_channel() -> None:
    query = "Give me one hint for x^2-5x+6=0 without revealing either root."
    response_intent = classify_math_response_intent(query)
    safe = _withhold_hint_answer(_block(query), response_intent)

    assert response_intent.mode == MathResponseMode.HINT
    assert safe.canonical_answer is None
    assert safe.canonical_fence is None and safe.canonical_fences == []
    assert safe.key_steps == () and safe.check_latex is None
    assert safe.direct_reply is not None and "x = 2" not in safe.direct_reply
    assert "x = 3" not in safe.text

    leaked_draft = "The roots are 2 and 3.\n\n```answer\nx = 2 or x = 3\n```"
    finalized = validate_math_fences(leaked_draft, verified=safe)
    assert finalized == safe.direct_reply
    assert "roots are" not in finalized and "```answer" not in finalized


@pytest.mark.asyncio
async def test_answer_only_suppresses_a_canonical_number_line() -> None:
    query = "Solve x^2<4. Answer only."
    _augmentation, verified = await build_math_augmentation(query, _SETTINGS)
    assert verified is not None
    draft = "```answer\n-2 < x < 2\n```\n\n```graph\n{}\n```"
    finalized = validate_math_fences(draft, verified=verified)
    assert "```answer" in finalized
    assert "```graph" not in finalized
