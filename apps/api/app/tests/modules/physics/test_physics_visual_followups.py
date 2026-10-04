"""The reported grade-10 exercise -> native-diagram conversation."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models.orm import Chat, User
from app.modules.physics.block import _build_physics_block
from app.modules.physics.direct import maybe_direct_physics_reply
from app.modules.physics.extract import extract_physics_intent
from app.modules.physics.fence import validate_physics_fences
from app.modules.physics.visual_requests import (
    ANIMATION_UNAVAILABLE,
    VISUAL_UNAVAILABLE,
    exercise_for_request,
    has_native_visual,
    physics_visual_followup,
)
from app.services.chat.prompt_builder import _PromptContextBlocks
from app.services.chat.turn_prep.context import build_stream_prompt_context
from app.services.chat.turn_prep.mode import _TurnMode
from app.services.subject_solving import detect_subject

_QUERY = "Do one 10th grde physics problem"


@pytest.mark.parametrize(
    "prompt",
    ["Physics", "Explain Newton's laws", "What is kinetic energy?", "Explain thermodynamics"],
)
def test_conceptual_physics_uses_the_visual_capability_policy(prompt: str) -> None:
    assert detect_subject(prompt) == "physics"
    assert (
        physics_visual_followup(
            "show an animation",
            [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": "Would you like an animation?"},
            ],
        )
        is not None
    )


@pytest.mark.parametrize(
    "prompt", ["I have no energy today", "There is friction at work", "Describe my work"]
)
def test_everyday_prose_does_not_claim_the_physics_policy(prompt: str) -> None:
    assert detect_subject(prompt) != "physics"


async def _turn(content: str, history: list[dict[str, str]]):
    user = User(
        id=uuid4(),
        name="Physics review",
        email="physics-review@example.com",
        response_style="balanced",
        locale="en",
        timezone="UTC",
        memory_enabled=False,
    )
    chat = Chat(id=uuid4(), user_id=user.id, title="Physics review")
    rows = [SimpleNamespace(id=uuid4(), **row) for row in history]
    current = SimpleNamespace(id=uuid4(), role="user", content=content)
    rows.append(current)
    blocks = _PromptContextBlocks(
        memory_block="",
        todos_section=None,
        gmail_todos_section=None,
        recent_all=rows,
        attachment_rag_block="",
        chat=chat,
    )
    settings = Settings(
        math_tools_enabled=True,
        chemistry_enabled=False,
        web_search_enabled=False,
        web_search_classifier_enabled=False,
        mcp_tools_enabled=False,
        mcp_tool_loop_enabled=False,
        attachments_enabled=False,
        gmail_enabled=False,
        google_calendar_enabled=False,
    )
    with (
        patch("app.services.chat.turn_prep.context._instant_reply_needs_db", return_value=False),
        patch(
            "app.services.chat.prompt_builder._load_context_blocks", AsyncMock(return_value=blocks)
        ),
        patch(
            "app.services.chat.turn_prep.context._load_prior_user_messages",
            AsyncMock(return_value=[]),
        ),
        patch("app.services.model_health.enrich_models_health", AsyncMock(return_value={})),
        patch(
            "app.services.chat.turn_prep.context.plan_service.chat_fallback_models", return_value=[]
        ),
    ):
        return await build_stream_prompt_context(
            user.id,
            chat.id,
            content,
            "free-chat",
            settings,
            AsyncMock(),
            client_timezone=None,
            client_location=None,
            client_latitude=None,
            client_longitude=None,
            user=user,
            chat=chat,
            turn_mode=_TurnMode(
                lightweight=False,
                rich_context=False,
                minimal_personal=False,
                day_planning=False,
                day_reflection=False,
            ),
            recent_messages=rows,
            current_user_message_id=current.id,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query,followup",
    [
        (_QUERY, "show me a diagram"),
        (_QUERY, "show an animation"),
        (_QUERY, "animate it"),
        (_QUERY, "diagram?"),
        (_QUERY, "draw it"),
        (_QUERY, "Okay diagram"),
        (_QUERY, "Can I see an animation?"),
        ("Give me a 10th grade physics exercise", "Okay diagram"),
        ("Do one 10th grde physics exercise", "show an animation"),
    ],
)
async def test_exact_two_turn_request_returns_native_motion(
    query: str,
    followup: str,
    thread_sympy_executor: None,
) -> None:
    assert detect_subject(query) == "physics"
    first = await _turn(query, [])
    assert first.instant_reply is not None
    assert first.instant_reply.startswith("**Problem**")
    assert has_native_visual(first.verified_subject, animation=True)
    assert first.instant_reply.count("```simulation") == 1
    history = [
        {"role": "user", "content": query},
        {"role": "assistant", "content": first.instant_reply},
    ]
    second = await _turn(followup, history)
    assert second.instant_reply is not None
    assert "**Diagram**" in second.instant_reply
    assert "**Substitution**" not in second.instant_reply
    assert second.instant_reply.count("```simulation") == 1
    assert has_native_visual(second.verified_subject, animation=True)
    assert second.verified_subject.physics_intent == first.verified_subject.physics_intent
    assert second.verified_subject.canonical_fences == first.verified_subject.canonical_fences


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "problem",
    [
        "A ball is dropped from 20 m. What is its velocity after 1 s?",
        "A ball is thrown upward at 20 m/s. What is its velocity after 1 s?",
    ],
)
async def test_directional_prelude_preserves_final_native_diagram(
    problem: str, thread_sympy_executor: None
) -> None:
    context = await _turn(
        "show me a diagram",
        [
            {"role": "user", "content": problem},
            {"role": "assistant", "content": "Would you like a diagram?"},
        ],
    )
    assert context.instant_reply is not None
    assert context.instant_reply.startswith("Upward is positive.")
    final = validate_physics_fences(context.instant_reply, verified=context.verified_subject)
    assert final.count("```answer") == 1
    assert final.count("```graph") == 1
    assert final.count("```simulation") == 1


@pytest.mark.asyncio
async def test_accepting_prior_offer_solves_problem_again(thread_sympy_executor: None) -> None:
    problem = exercise_for_request(_QUERY)
    history = [
        {"role": "user", "content": _QUERY},
        {
            "role": "assistant",
            "content": (
                f"**Problem**\n\n{problem}\n\nWrong answer: 999 m.\n\n"
                'Would you like an animation?\n```simulation\n{"type":"made_up"}\n```'
            ),
        },
    ]
    second = await _turn("I want one", history)
    assert second.instant_reply is not None
    assert "Wrong answer: 999 m" not in second.instant_reply
    assert "made_up" not in second.instant_reply
    assert has_native_visual(second.verified_subject, animation=True)
    assert "10.1" in second.instant_reply


@pytest.mark.asyncio
@pytest.mark.parametrize("followup", ["show a diagram", "show an animation", "I want one"])
async def test_unsupported_visual_declines_without_provider_or_drawing(
    followup: str,
    thread_sympy_executor: None,
) -> None:
    history = [
        {"role": "user", "content": "Find the specific heat when Q=100 J, m=2 kg and delta T=5 K"},
        {"role": "assistant", "content": "Would you like an animation?"},
    ]
    result = await _turn(followup, history)
    assert result.instant_reply in {VISUAL_UNAVAILABLE, ANIMATION_UNAVAILABLE}
    assert "```" not in validate_physics_fences(
        result.instant_reply, verified=result.verified_subject
    )


@pytest.mark.parametrize(
    "history",
    [
        [],
        [{"role": "assistant", "content": "Would you like an animation?"}],
        [
            {"role": "user", "content": _QUERY},
            {"role": "assistant", "content": "Done."},
            {"role": "user", "content": "Tell me a joke"},
            {"role": "assistant", "content": "A joke."},
        ],
        [{"role": "user", "content": _QUERY}, {"role": "assistant", "content": "Done."}],
    ],
)
def test_acceptance_needs_adjacent_physics_offer(history: list[dict[str, str]]) -> None:
    assert physics_visual_followup("I want one", history) is None


def test_visual_request_does_not_swallow_a_second_task() -> None:
    history = [{"role": "user", "content": _QUERY}, {"role": "assistant", "content": "Done."}]
    assert physics_visual_followup("show a diagram and solve a different problem", history) is None
    assert exercise_for_request(_QUERY + " about circuits") is None


def test_direct_presentation_is_bound_to_request_and_problem() -> None:
    problem = exercise_for_request(_QUERY)
    assert problem is not None
    intent = extract_physics_intent(problem)
    assert intent is not None
    verified = _build_physics_block(intent, Settings(), [])
    assert verified is not None
    verified = replace(
        verified,
        physics_problem_text=problem,
        physics_request_text=_QUERY,
        physics_presentation="exercise",
    )
    assert maybe_direct_physics_reply(verified, _QUERY) is not None
    assert maybe_direct_physics_reply(verified, "a different request") is None
    assert (
        maybe_direct_physics_reply(replace(verified, physics_problem_text="Force is 999"), _QUERY)
        is None
    )


def test_model_drawings_and_unrenderable_offers_are_removed() -> None:
    text = (
        "The result needs another input.\n\nWould you like an animation?\n\n"
        "```html\n<svg><circle /></svg>\n```\n"
        "```mermaid\ngraph LR; A-->B\n```\n"
        "```text\n    o\n   /|\n```\n"
        '```simulation\n{"type":"made_up"}\n'
    )
    assert validate_physics_fences(text) == "The result needs another input."


@pytest.mark.parametrize(
    "problem, duration, end",
    [
        (
            "A ball is dropped from 20 m. How long until it hits the ground?",
            (40 / 9.81) ** 0.5,
            [0, 0],
        ),
        (
            "A car starts at 10 m/s and accelerates at -2 m/s^2 for 10 s. Find the distance traveled.",
            10,
            [0, 0],
        ),
    ],
)
def test_linear_scene_uses_physical_position_and_time(problem, duration, end) -> None:
    assert problem is not None
    intent = extract_physics_intent(problem)
    assert intent is not None
    verified = _build_physics_block(intent, Settings(), [])
    assert verified is not None
    assert has_native_visual(verified, animation=True)
    scene = next(f for f in verified.canonical_fences if "bodies" in f)
    assert scene["duration_s"] == pytest.approx(duration)
    assert scene["bodies"][0]["path"][-1] == pytest.approx(end)
    if intent.kind == "suvat":
        # The body's displacement reverses; cumulative distance is not position.
        assert scene["bodies"][0]["path"][50][0] == pytest.approx(25, abs=0.01)


def test_visual_history_does_not_cross_an_accepted_unrelated_offer() -> None:
    history = [
        {
            "role": "user",
            "content": "A ball is dropped from 20 m. How long until it hits the ground?",
        },
        {"role": "assistant", "content": "2.02 s. Would you like a dinner recipe?"},
        {"role": "user", "content": "yes"},
        {"role": "assistant", "content": "A pancake recipe."},
    ]
    assert physics_visual_followup("show a diagram", history) is None


@pytest.mark.asyncio
async def test_single_new_offered_problem_is_the_visual_source(thread_sympy_executor: None) -> None:
    new_problem = exercise_for_request(_QUERY)
    history = [
        {
            "role": "user",
            "content": "A ball is dropped from 20 m. How long until it hits the ground?",
        },
        {
            "role": "assistant",
            "content": (
                f"It takes 2.02 s.\n\n**Problem**\n\n{new_problem}\n\n"
                "Would you like a diagram for this new problem?"
            ),
        },
    ]
    second = await _turn("I want one", history)
    assert second.verified_subject.physics_problem_text == new_problem
    assert second.verified_subject.physics_intent.kind == "projectile"


@pytest.mark.asyncio
async def test_multiple_offered_problems_decline_the_visual(thread_sympy_executor: None) -> None:
    history = [
        {"role": "user", "content": _QUERY},
        {
            "role": "assistant",
            "content": (
                f"**Problem**\n\n{exercise_for_request(_QUERY)}\n\n"
                "**Problem**\n\nA ball is dropped from 20 m. How long until it hits the ground?\n\n"
                "Would you like a diagram?"
            ),
        },
    ]
    second = await _turn("I want one", history)
    assert second.instant_reply == VISUAL_UNAVAILABLE


@pytest.mark.asyncio
async def test_question_in_problem_does_not_strip_the_native_scene(
    thread_sympy_executor: None,
) -> None:
    problem = "A ball is dropped from 20 m. How long until it hits the ground?"
    history = [
        {"role": "user", "content": problem},
        {"role": "assistant", "content": "It takes 2.02 s."},
    ]
    second = await _turn("show me a diagram", history)
    finalized = validate_physics_fences(second.instant_reply, verified=second.verified_subject)
    assert finalized.count("```simulation") == 1
    assert finalized.count("```answer") == 1
    assert finalized.count("```graph") == 1


@pytest.mark.parametrize(
    "promise",
    [
        "I will animate this for you.",
        "I'll draw a diagram for you.",
        "Would you like a visualization?",
        "Would you like an animated version?",
        "Would a diagram help?",
        "Here is the diagram:",
    ],
)
def test_variants_of_unsupported_visual_promises_are_removed(promise: str) -> None:
    assert validate_physics_fences("The calculation needs another input. " + promise) == (
        "The calculation needs another input."
    )


def test_indented_ascii_diagram_is_not_a_rendering_fallback() -> None:
    assert (
        validate_physics_fences("Here is the diagram:\n\n    o\n    |\n----+----")
        == VISUAL_UNAVAILABLE
    )
    assert validate_physics_fences(
        "I can't draw a verified native diagram for this problem."
    ).startswith("I can't")


def test_ground_is_inside_partial_vertical_motion_viewport() -> None:
    intent = extract_physics_intent("A ball is dropped from 20 m. Find its speed after 1 s.")
    assert intent is not None
    verified = _build_physics_block(intent, Settings(), [])
    assert verified is not None
    scene = next(f for f in verified.canonical_fences if "bodies" in f)
    assert scene["ground"] is True
    assert scene["y_min"] <= 0 <= scene["y_max"]
    assert scene["duration_s"] == 1
    assert scene["bodies"][0]["path"][-1][1] == pytest.approx(20 - 9.81 / 2)


@pytest.mark.parametrize(
    "language", ["svg", "SVG", "html", "HTML", "mermaid", "text", "ascii", "plaintext"]
)
def test_visual_only_provider_reply_gets_an_unavailable_response(language: str) -> None:
    assert (
        validate_physics_fences(f"```{language}\n<svg><circle /></svg>\n```") == VISUAL_UNAVAILABLE
    )


@pytest.mark.asyncio
async def test_new_image_does_not_reuse_a_previous_physics_visual() -> None:
    from app.models.schemas.math import MathImageExtract
    from app.services.chat.prompt_builder import fetch_web_and_tools
    from app.services.subject_solving import SubjectAugmentation

    augment = AsyncMock(return_value=SubjectAugmentation("math", None, None))
    with patch("app.services.chat.prompt_builder.build_subject_augmentation", augment):
        await fetch_web_and_tools(
            "show me a diagram",
            Settings(web_search_enabled=False),
            prompt_messages=[],
            has_image_attachment=True,
            image_math_extract=MathImageExtract(kind="graph", expr="x^2", source_text="Plot y=x^2"),
            physics_followup_problem="A ball is dropped from 20 m. How long until it hits the ground?",
        )
    assert augment.await_args is not None
    assert augment.await_args.kwargs["detected_subject"] == "math"
    assert augment.await_args.args[0] == "show me a diagram"
    assert augment.await_args.kwargs["response_intent_text"] is None


@pytest.mark.parametrize(
    "prose",
    [
        "Here is how to read the plot: its upward slope means positive acceleration.",
        "I will use the slope of the velocity-time plot to calculate acceleration, which gives 2 m/s^2.",
        "Would you like an explanation of the velocity-time plot?",
        "I will show that the slope of a velocity-time graph equals acceleration.",
        "I can show that energy is conserved by equating the initial and final energies.",
        "I will show this calculation step by step: a = F/m = 2 m/s^2.",
    ],
)
def test_explaining_an_existing_plot_is_not_a_drawing_promise(prose: str) -> None:
    assert validate_physics_fences(prose) == prose
    assert (
        physics_visual_followup(
            "yes",
            [
                {"role": "user", "content": "A 5 kg mass accelerates at 2 m/s^2. Find the force."},
                {"role": "assistant", "content": prose},
            ],
        )
        is None
    )


def test_unlabeled_drawing_fence_gets_an_unavailable_response() -> None:
    assert validate_physics_fences("```\n    o\n    |\n----+----\n```") == VISUAL_UNAVAILABLE


@pytest.mark.asyncio
async def test_animation_disclaimer_does_not_change_a_static_diagram_offer(
    thread_sympy_executor: None,
) -> None:
    history = [
        {
            "role": "user",
            "content": "What is the normal force on a 5 kg block on a 30 degree incline?",
        },
        {
            "role": "assistant",
            "content": "Would you like a diagram? I cannot animate this problem yet.",
        },
    ]
    followup = physics_visual_followup("I want one", history)
    assert followup is not None and followup.animation is False
    result = await _turn("I want one", history)
    assert result.instant_reply is not None and result.instant_reply != ANIMATION_UNAVAILABLE
    assert result.instant_reply.count("```simulation") == 1


@pytest.mark.asyncio
async def test_accepting_a_bulleted_native_visual_offer(thread_sympy_executor: None) -> None:
    problem = exercise_for_request(_QUERY)
    history = [
        {"role": "user", "content": _QUERY},
        {
            "role": "assistant",
            "content": (
                f"**Problem**\n\n{problem}\n\n"
                "Let me know if you'd like:\n\n- A diagram (free-body or velocity-time graph),\n"
                "- A follow-up problem."
            ),
        },
    ]
    result = await _turn("I want one", history)
    assert result.instant_reply.count("```simulation") == 1
    cleaned = validate_physics_fences(history[-1]["content"])
    assert "Let me know if" not in cleaned
    assert "A diagram" not in cleaned
