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
from app.services.math.fence import validate_math_fences
from app.services.math.tools import _build_verified_block, extract_math_intent, needs_symbolic_math
from app.services.math.tools.direct import maybe_direct_math_reply
from app.services.math.tools.prompt import build_math_augmentation
from app.services.physics.block import _format_visible_answer
from app.services.physics.direct import _expected_intent
from app.services.solving import VerifiedMathBlock
from app.services.tool_loop import turn_needs_tool_loop

_SETTINGS = Settings(math_tools_enabled=True, mcp_tool_loop_enabled=True)
_DROP = "A ball is dropped from a height of 20 m. Find its {} after 1 second. Use g=10."
_PROJECTILE = "A projectile is launched at 20 m/s at 45 degrees. Find its {}. Use g=10."
_AVERAGE_SPEED = "Find the average speed for 100 m in 20 s."
_ELECTRIC_FORCE = (
    "Two point charges of 2 microcoulombs and 3 microcoulombs are separated by 0.5 m. "
    "Find the electric force."
)
_CASES = [
    ("A ball is dropped from a height of 20 m. Find the time to ground. Use g=10.", "2 s", True),
    (_DROP.format("velocity"), "-10 m/s", True),
    (_DROP.format("speed"), "10 m/s", True),
    (_DROP.format("height"), "15 m", True),
    ("A ball is in free fall from 20 m. Find its acceleration. Use g=10.", "-10 m/s^2", False),
    (_PROJECTILE.format("range"), "40 m", True),
    (_PROJECTILE.format("maximum height"), "10 m", True),
    ("Find the force on a 5 kg object with acceleration 2 m/s^2.", "10 N", False),
    ("Find the acceleration of a 5 kg object under a force of 20 N.", "4 m/s^2", False),
    ("Find the mass of an object with force 20 N and acceleration 4 m/s^2.", "5 kg", False),
    ("Find the kinetic energy of a 2 kg object moving at 3 m/s.", "9 J", False),
    ("Find the potential energy of a 2 kg object at height 5 m. Use g=10.", "100 J", False),
    ("Find the work done by a force of 10 N over a distance of 3 m.", "30 J", False),
    ("What is the power of a force of 10 N moving at 3 m/s?", "30 W", False),
    ("A machine does 1,200 J of work in 30 seconds. What is its power?", "40 W", False),
    (_AVERAGE_SPEED, r"5\ \mathrm{m}/\mathrm{s}", False),
    (_ELECTRIC_FORCE, "0.2157 N", False),
    (
        "A car travels 180 meters in 12 seconds. What is its average speed?",
        r"15\ \mathrm{m}/\mathrm{s}",
        False,
    ),
]


def _verified(query: str) -> VerifiedMathBlock:
    intent = extract_math_intent(query)
    assert intent is not None
    verified = _build_verified_block(intent, _SETTINGS)
    assert verified is not None
    return verified


def test_electric_force_uses_textbook_scientific_notation() -> None:
    verified = _verified(_ELECTRIC_FORCE)
    reply = maybe_direct_math_reply(verified, _ELECTRIC_FORCE)
    assert reply is not None
    assert r"8.987552 \times 10^{9}" in reply
    assert r"2 \times 10^{-6}" in reply
    assert "e+09" not in reply


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
    if verified.physics_intent is not None:
        headings = ["**Given**", "**Find**", "**Formula**", "**Substitution**", "**Answer**"]
        assert all(reply.count(heading) == 1 for heading in headings)
        assert [reply.index(heading) for heading in headings] == sorted(
            reply.index(heading) for heading in headings
        )
    assert "Explanation" not in reply
    assert "$average speed$" not in reply
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
        ("A ball is dropped from 2000 cm. Find the time to ground. Use g=10.", "2 s"),
        ("A ball is dropped from 20 m. Find its speed after 500 ms. Use g=10.", "5 m/s"),
        ("A ball is dropped from 20 m. Find the time to ground.", "2.02 s"),
        ("A ball is in free fall from 20 m. Find its acceleration. Use g=1.62.", "-1.62 m/s^2"),
        ("A projectile is launched at 72 km/h at 30 degrees. Find its range. Use g=10.", "34.64 m"),
        ("Find the force on a 500 g object with acceleration -2 m/s^2.", "-1 N"),
        ("Find the acceleration of a 2 kg object under a force of -5 N.", "-2.5 m/s^2"),
        ("Find the mass of an object with force -20 N and acceleration -4 m/s^2.", "5 kg"),
        ("Find the kinetic energy of a 500 g object moving at -4 m/s.", "4 J"),
        ("Find the potential energy of a 0.5 kg object at height 200 cm. Use g=10.", "10 J"),
        ("Find the work done by a force of -10 N over a distance of 300 cm.", "-30 J"),
        ("What is the power of a force of 5 N moving at -2 m/s?", "-10 W"),
        ("Find the average speed for 1 km in 2 min.", r"0.5\ \mathrm{km}/\mathrm{min}"),
        ("Find the average speed for 0 m in 20 s.", r"0\ \mathrm{m}/\mathrm{s}"),
    ],
)
def test_other_quantities_units_signs_and_existing_precision(query: str, answer: str) -> None:
    verified = _verified(query)
    assert verified.canonical_answer == answer
    reply = maybe_direct_math_reply(verified, query)
    assert reply is not None and f"```answer\n{answer}\n```" in reply


@pytest.mark.parametrize(
    "raw,visible",
    [
        ("20.20 N", "20.2 N"),
        ("20.00 N", "20 N"),
        ("-2.50 m/s^2", "-2.5 m/s^2"),
        ("50.05 J", "50.05 J"),
        ("3.204e-14 N", "3.204e-14 N"),
        ("21.00 kg*m/s", "21 kg·m/s"),
    ],
)
def test_visible_physics_values_drop_only_redundant_decimal_zeros(raw: str, visible: str) -> None:
    assert _format_visible_answer(raw) == visible


def test_projectile_working_substitutes_givens_without_redundant_zeros() -> None:
    query = "A projectile is launched at 20 m/s at 30 degrees. Find its maximum height."
    reply = maybe_direct_math_reply(_verified(query), query)
    assert reply is not None
    working = reply.split("```", 1)[0]
    assert "5.10" not in working
    assert (
        "**Substitution**\n\n"
        r"$H_{max} = 0 + \frac{20^2 \sin^2(30^\circ)}{2 \cdot 9.81}$"
    ) in working
    assert "```answer\n5.1 m\n```" in reply


def test_collision_hides_the_internal_elasticity_switch_from_given() -> None:
    query = (
        "A 2 kg cart moving at 6 m/s collides perfectly inelastically with a "
        "4 kg cart at rest. Find the final velocity."
    )
    reply = maybe_direct_math_reply(_verified(query), query)

    assert reply is not None
    given = reply.split("**Find**", 1)[0]
    assert "elastic" not in given
    assert "$m_1 = 2" in given
    assert "$m_2 = 4" in given


def test_elastic_collision_shows_both_universal_formulas_and_substitutions() -> None:
    query = (
        "In an elastic collision a 2 kg ball at 3 m/s hits a 1 kg ball at rest. "
        "Find the final velocities."
    )
    reply = maybe_direct_math_reply(_verified(query), query)

    assert reply is not None
    formula = reply.split("**Formula**", 1)[1].split("**Substitution**", 1)[0]
    substitution = reply.split("**Substitution**", 1)[1].split("**Answer**", 1)[0]
    assert r"v_1' = \frac{(m_1-m_2)v_1 + 2m_2v_2}{m_1+m_2}" in formula
    assert r"v_2' = \frac{(m_2-m_1)v_2 + 2m_1v_1}{m_1+m_2}" in formula
    assert r"v_1' = \frac{(2-1)\cdot 3 + 2\cdot 1\cdot 0}{2+1}" in substitution
    assert r"v_2' = \frac{(1-2)\cdot 0 + 2\cdot 2\cdot 3}{2+1}" in substitution
    assert "1.00" not in reply
    assert "4.00" not in reply


def test_friction_given_uses_the_coefficient_symbol_not_raw_mu() -> None:
    query = (
        "A 5 kg block slides down a 30 degree incline with coefficient of kinetic "
        "friction 0.20. Find its acceleration."
    )
    reply = maybe_direct_math_reply(_verified(query), query)

    assert reply is not None
    given = reply.split("**Find**", 1)[0]
    assert r"$\mu = 0.2$" in given
    assert "$mu" not in given


@pytest.mark.parametrize(
    "query,symbol,substitution",
    [
        ("Find the force on a 5 kg object with acceleration 2 m/s^2.", "F", "F = 5 \\cdot 2"),
        (
            "Find the acceleration of a 5 kg object under a force of 20 N.",
            "a",
            r"a = \frac{20}{5}",
        ),
        (
            "Find the mass of an object with force 20 N and acceleration 4 m/s^2.",
            "m",
            r"m = \frac{20}{4}",
        ),
    ],
)
def test_force_rearrangements_name_the_quantity_actually_being_found(
    query: str, symbol: str, substitution: str
) -> None:
    reply = maybe_direct_math_reply(_verified(query), query)
    assert reply is not None
    assert f"**Find**\n\n${symbol}$" in reply
    assert f"**Substitution**\n\n${substitution}$" in reply


@pytest.mark.parametrize(
    "query,answer,find,rearranged,substitution",
    [
        (
            "A car travels 20 m in 4 s. What is its speed?",
            r"5\ \mathrm{m}/\mathrm{s}",
            "$v$",
            None,
            r"$v = \frac{20\,\mathrm{m}}{4\,\mathrm{s}}$",
        ),
        (
            "A car moves at 5 m/s for 4 s. What distance does it travel?",
            r"20\ \mathrm{m}",
            "$d$",
            "$d = vt$",
            r"$d = 5 \cdot 4$",
        ),
        (
            "A car travels 20 m at 5 m/s. How long does it take?",
            r"4\ \mathrm{s}",
            "$t$",
            r"$t = \frac{d}{v}$",
            r"$t = \frac{20}{5}$",
        ),
    ],
)
def test_speed_law_uses_its_universal_formula_before_any_rearrangement(
    query: str,
    answer: str,
    find: str,
    rearranged: str | None,
    substitution: str,
) -> None:
    assert needs_symbolic_math(query)
    verified = _verified(query)
    assert verified.canonical_answer == answer
    reply = maybe_direct_math_reply(verified, query)
    assert reply is not None
    assert f"**Find**\n\n{find}" in reply
    assert "**Formula**\n\nSpeed formula:\n\n$v = \\frac{d}{t}$" in reply
    if rearranged is not None:
        assert rearranged in reply
    assert f"**Substitution**\n\n{substitution}" in reply
    assert f"```answer\n{answer}\n```" in reply


@pytest.mark.parametrize("index", [1, 4])
def test_signed_free_fall_answer_states_reference_direction(index: int) -> None:
    query, _, _ = _CASES[index]
    reply = maybe_direct_math_reply(_verified(query), query)
    assert reply is not None and reply.startswith("Upward is positive.\n\n**Given**")


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
    speed = _verified(_AVERAGE_SPEED)
    assert maybe_direct_math_reply(speed, _AVERAGE_SPEED.replace("100 m", "50 m")) is None
    assert maybe_direct_math_reply(speed, _AVERAGE_SPEED.replace("20 s", "20 min")) is None


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


@pytest.mark.parametrize(
    "query,expected_type",
    [
        (_CASES[0][0], "position_vs_time"),  # time to ground
        (_DROP.format("velocity"), "velocity_vs_time"),
        (_DROP.format("speed"), "velocity_vs_time"),
        (_DROP.format("height"), "position_vs_time"),
        (_PROJECTILE.format("range"), "parametric"),
    ],
)
def test_direct_guard_expects_the_type_the_solver_emits(query: str, expected_type: str) -> None:
    """The guard and the solver must name the same trajectory_type.

    They are two hard-coded tables that have to agree, and disagreement fails
    *silently*: `can_direct_physics` rejects the fence, the direct reply is
    dropped, and the turn quietly falls back to the model path with no error
    anywhere. When velocity/speed started emitting `velocity_vs_time`, this is
    the test that would have caught a guard left on `position_vs_time`.
    """
    verified = _verified(query)
    assert verified.canonical_fence is not None
    assert verified.canonical_fence.get("trajectory_type") == expected_type

    # Same fence, wrong type — the direct reply must disappear, proving the
    # assertion above is load-bearing rather than decorative.
    assert maybe_direct_math_reply(verified, query) is not None
    wrong = "parametric" if expected_type != "parametric" else "position_vs_time"
    assert (
        maybe_direct_math_reply(
            replace(
                verified, canonical_fence=verified.canonical_fence | {"trajectory_type": wrong}
            ),
            query,
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
        "app.services.physics.solver.solve_physics", side_effect=AssertionError("re-solved")
    ):
        assert maybe_direct_math_reply(verified, query) is not None


def test_post_impact_request_does_not_gain_a_verified_direct_answer() -> None:
    query = _DROP.format("speed").replace("1 second", "3 seconds")
    intent = extract_math_intent(query)
    assert intent is not None
    assert _build_verified_block(intent, _SETTINGS) is None
