"""Whole physics asks display the solved quantity, never an invented formula."""

from collections.abc import AsyncGenerator
from dataclasses import replace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services.chat.stream_pipeline import stream_and_finalize
from app.services.chat.turn_prep.context import StreamContext
from app.services.math_fence import validate_math_fences
from app.services.math_tools import _build_verified_block, extract_math_intent, needs_symbolic_math
from app.services.math_tools.block.common import VerifiedMathBlock
from app.services.math_tools.direct import maybe_direct_math_reply
from app.services.math_tools.direct_physics import _expected_intent
from app.services.math_tools.prompt import build_math_augmentation
from app.services.tool_loop import turn_needs_tool_loop

_SETTINGS = Settings(math_tools_enabled=True, mcp_tool_loop_enabled=True)
_DROP = "A ball is dropped from a height of 20 m. Find its {} after 1 second. Use g=10."
_PROJECTILE = "A projectile is launched at 20 m/s at 45 degrees. Find its {}. Use g=10."
_CASES = [
    ("A ball is dropped from a height of 20 m. Find the time to ground. Use g=10.", "2.00 s", True),
    (_DROP.format("velocity"), "-10.00 m/s", True),
    (_DROP.format("speed"), "10.00 m/s", True),
    (_DROP.format("height"), "15.00 m", True),
    ("A ball is in free fall from 20 m. Find its acceleration. Use g=10.", "-10 m/s^2", False),
    (_PROJECTILE.format("range"), "40.00 m", True),
    (_PROJECTILE.format("maximum height"), "10.00 m", True),
    ("Find the force on a 5 kg object with acceleration 2 m/s^2.", "10.00 N", False),
    ("Find the acceleration of a 5 kg object under a force of 20 N.", "4.00 m/s^2", False),
    ("Find the mass of an object with force 20 N and acceleration 4 m/s^2.", "5.00 kg", False),
    ("Find the kinetic energy of a 2 kg object moving at 3 m/s.", "9.00 J", False),
    ("Find the potential energy of a 2 kg object at height 5 m. Use g=10.", "100.00 J", False),
    ("Find the work done by a force of 10 N over a distance of 3 m.", "30.00 J", False),
    ("What is the power of a force of 10 N moving at 3 m/s?", "30.00 W", False),
    ("Find the average speed for 100 m in 20 s.", r"5.0\ \mathrm{m}/\mathrm{s}", False),
]


def _verified(query: str) -> VerifiedMathBlock:
    intent = extract_math_intent(query)
    assert intent is not None
    verified = _build_verified_block(intent, _SETTINGS)
    assert verified is not None
    return verified


@pytest.mark.asyncio
@pytest.mark.parametrize("query,answer,graph", _CASES)
async def test_complete_physics_request_streams_existing_answer_without_provider_or_tools(
    query: str, answer: str, graph: bool
) -> None:
    assert needs_symbolic_math(query)
    _, verified = await build_math_augmentation(query, _SETTINGS)
    assert verified is not None
    assert verified.canonical_answer == answer
    reply = maybe_direct_math_reply(verified, query)
    assert reply is not None
    assert reply.count("```answer") == 1
    assert f"```answer\n{answer}\n```\n" in reply
    assert reply.count("```graph") == int(graph)
    assert reply.endswith("```\n")
    assert "\\frac" not in reply  # P01's incorrect model-derived formula cannot appear.
    assert "Explanation" not in reply
    finalized = validate_math_fences(reply, verified=verified)
    # Finalization may compact the blank line between the two canonical fences.
    assert [line for line in finalized.splitlines() if line] == [
        line for line in reply.splitlines() if line
    ]
    assert not turn_needs_tool_loop(query, settings=_SETTINGS, has_verified_math=True)
    assert not turn_needs_tool_loop(query, settings=_SETTINGS, has_instant_reply=True)
    ctx = StreamContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        model="smart-chat",
        prompt_messages=[],
        run_title=False,
        user_message_content=query,
        reserved_tokens=100,
        max_output_tokens=1000,
        instant_reply=reply,
        verified_math=verified,
    )
    with (
        patch("app.services.chat.stream_pipeline.run_tool_loop_path", AsyncMock()) as tools,
        patch("app.services.chat.stream_pipeline.run_llm_token_stream") as llm,
    ):
        stream = stream_and_finalize(MagicMock(), MagicMock(), _SETTINGS, ctx, should_cancel=None)
        assert isinstance(stream, AsyncGenerator)
        try:
            assert await anext(stream) == reply
            tools.assert_not_awaited()
            llm.assert_not_called()
        finally:
            await stream.aclose()


@pytest.mark.parametrize(
    "query,answer",
    [
        ("A ball is dropped from 2000 cm. Find the time to ground. Use g=10.", "2.00 s"),
        ("A ball is dropped from 20 m. Find its speed after 500 ms. Use g=10.", "5.00 m/s"),
        ("A ball is dropped from 20 m. Find the time to ground.", "2.02 s"),
        ("A ball is in free fall from 20 m. Find its acceleration. Use g=1.62.", "-1.62 m/s^2"),
        ("A projectile is launched at 72 km/h at 30 degrees. Find its range. Use g=10.", "34.64 m"),
        ("Find the force on a 500 g object with acceleration -2 m/s^2.", "-1.00 N"),
        ("Find the acceleration of a 2 kg object under a force of -5 N.", "-2.50 m/s^2"),
        ("Find the mass of an object with force -20 N and acceleration -4 m/s^2.", "5.00 kg"),
        ("Find the kinetic energy of a 500 g object moving at -4 m/s.", "4.00 J"),
        ("Find the potential energy of a 0.5 kg object at height 200 cm. Use g=10.", "10.00 J"),
        ("Find the work done by a force of -10 N over a distance of 300 cm.", "-30.00 J"),
        ("What is the power of a force of 5 N moving at -2 m/s?", "-10.00 W"),
        ("Find the average speed for 1 km in 2 min.", r"0.5\ \mathrm{km}/\mathrm{min}"),
        ("Find the average speed for 0 m in 20 s.", r"0\ \mathrm{m}/\mathrm{s}"),
    ],
)
def test_other_quantities_units_signs_and_existing_precision(query: str, answer: str) -> None:
    verified = _verified(query)
    assert verified.canonical_answer == answer
    reply = maybe_direct_math_reply(verified, query)
    assert reply is not None and f"```answer\n{answer}\n```" in reply


@pytest.mark.parametrize("index", [1, 4])
def test_signed_free_fall_answer_states_reference_direction(index: int) -> None:
    query, _, _ = _CASES[index]
    reply = maybe_direct_math_reply(_verified(query), query)
    assert reply is not None and reply.startswith("Upward is positive.\n\n```answer")


@pytest.mark.parametrize("query,answer,graph", _CASES)
@pytest.mark.parametrize(
    "suffix",
    [
        " Explain the formula.",
        " Give a hint only.",
        " Show steps.",
        " And solve x+1=2.",
        " Convert the answer to feet.",
        " How would air resistance change this?",
    ],
)
def test_teaching_mixed_and_requested_units_do_not_disappear(
    query: str, answer: str, graph: bool, suffix: str
) -> None:
    verified = _verified(query)
    assert maybe_direct_math_reply(verified, query + suffix) is None
    assert maybe_direct_math_reply(verified, query, has_image_attachment=True) is None


@pytest.mark.parametrize(
    "query",
    [
        "A ball is dropped from 20 m with initial velocity 5 m/s. Find the time to ground. Use g=10.",
        "A ball is dropped from 20 m on the moon. Find the time to ground.",
        "A ball is dropped from 20 m. Find its speed and height after 1 second. Use g=10.",
        "A ball is dropped from 20 m. Find its acceleration after 1 second. Use g=10.",
        "A ball is dropped from -20 m. Find the time to ground. Use g=10.",
        "A ball is dropped from 20 m. Find its height after -1 second. Use g=10.",
        "A ball is dropped from 20 m. Find its height after 1 second. Use g=-10.",
        "A ball is dropped from 20 m. Find its height after 1 second. Use g=10 cm/s^2.",
        "A ball is dropped from 20 m. Find its height after 1 second. Use g=10. Use g=20.",
        "A projectile is launched at 20 m/s at 45 degrees from a 5 m cliff. Find its range. Use g=10.",
        "A projectile is launched at 20 m/s at 1 radian. Find its range. Use g=10.",
        "A projectile is launched at 20 m/s at 0 degrees. Find its range. Use g=10.",
        "A projectile is launched at 20 m/s at 120 degrees. Find its range. Use g=10.",
        "Find twice the force on a 5 kg object with acceleration 2 m/s^2.",
        "Find the force on a 5 kg object with acceleration 2 m/s^2 and friction 3 N.",
        "Find the force on a 5 kg object with acceleration 2 m/s^2. Use g=10.",
        "Find the force on a 5 kg object with acceleration 2 m/s.",
        "Find the force on a 5 kg object with acceleration 2 m/s^3.",
        "Find the force on a 5 kg object with acceleration 2 m/s^2/3.",
        "Find the force on a 5 kg object with acceleration nan m/s^2.",
        "Find the force on a 5 kg object with acceleration 1000001 m/s^2.",
        "Find the force on a 0 kg object with acceleration 2 m/s^2.",
        "Find the mass of an object with force 20 N and acceleration -4 m/s^2.",
        "Find the work done by a force of 10 N at 60 degrees over a distance of 3 m.",
        "Find the kinetic energy of a 2 kg object moving at 3/2 m/s.",
        "Find the kinetic energy of a 2 kg object moving at 3 m/s and at 4 m/s.",
        "Find the potential energy of a 2 kg object at height 5 m relative to a 2 m platform.",
    ],
)
def test_extra_conditions_or_unsupported_literal_physics_decline(query: str) -> None:
    assert _expected_intent(query) is None


@pytest.mark.parametrize(
    "query",
    [
        "Find the average speed for 100 m in 0 s.",
        "Find the average speed for -100 m in 20 s.",
        "Find the average speed for 100 m in 20 s and 50 m in 5 s.",
        "Find the average speed for 100 m in 20 s on the first leg, then return.",
        "Find the average speed for 100 m in 20 s in km/h.",
        "Find the average speed for 100 m in 20 s. Explain.",
        "Find the average speed for 100 m/s in 20 s.",
    ],
)
def test_average_speed_requires_one_complete_distance_and_duration(query: str) -> None:
    assert _expected_intent(query) is None
    assert maybe_direct_math_reply(_verified(_CASES[-1][0]), query) is None


def test_request_cannot_reuse_another_solved_quantity_unit_or_operation() -> None:
    query = _CASES[1][0]
    verified = _verified(query)
    assert verified.physics_intent == extract_math_intent(query)
    for changed in [
        query.replace("20 m", "30 m"),
        query.replace("20 m", "20 cm"),
        query.replace("velocity", "speed"),
        query.replace("g=10", "g=5"),
    ]:
        assert maybe_direct_math_reply(verified, changed) is None
    assert maybe_direct_math_reply(replace(verified, physics_intent=None), query) is None
    speed = _verified(_CASES[-1][0])
    assert maybe_direct_math_reply(speed, _CASES[-1][0].replace("100 m", "50 m")) is None
    assert maybe_direct_math_reply(speed, _CASES[-1][0].replace("20 s", "20 min")) is None


def test_graph_must_be_single_complete_trajectory() -> None:
    query = _CASES[0][0]
    verified = _verified(query)
    assert verified.canonical_fence is not None
    graph = verified.canonical_fence
    changes: list[dict[str, Any]] = [
        {"points": []},
        {"points": [[0, 20]]},
        {"points": [[0, 20], [1, float("nan")]]},
        {"x_max": 0},
        {"trajectory_type": "parametric"},
        {"type": "function"},
        {"expr2": "x"},
        {"x_max": float("inf")},
        {"x_min": False},
    ]
    for change in changes:
        assert (
            maybe_direct_math_reply(replace(verified, canonical_fence=graph | change), query)
            is None
        )
    assert (
        maybe_direct_math_reply(
            replace(verified, canonical_fences=[{"type": "answer", "content": "other"}]), query
        )
        is None
    )


def test_scalar_requires_its_one_canonical_answer() -> None:
    query = _CASES[7][0]
    verified = _verified(query)
    assert (
        verified.allow_direct is False
    )  # No general permission for unlabeled physical quantities.
    assert maybe_direct_math_reply(verified, query) is not None
    assert maybe_direct_math_reply(replace(verified, canonical_answer="999 N"), query) is None
    assert maybe_direct_math_reply(replace(verified, canonical_fence=None), query) is None


def test_direct_guard_does_not_solve_again() -> None:
    query = _CASES[0][0]
    verified = _verified(query)
    with patch(
        "app.services.physics_solver.solve_physics", side_effect=AssertionError("re-solved")
    ):
        assert maybe_direct_math_reply(verified, query) is not None


def test_post_impact_request_does_not_gain_a_verified_direct_answer() -> None:
    query = _DROP.format("speed").replace("1 second", "3 seconds")
    intent = extract_math_intent(query)
    assert intent is not None
    assert _build_verified_block(intent, _SETTINGS) is None
