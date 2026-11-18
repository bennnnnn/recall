"""A physics reply describes its field picture; physics checks it and draws it.

The owner's GCSE set (2026-11-16): "Draw the pattern of the electric field around a) a
positive charge b) a negative charge" came back as ASCII art in code blocks. On a physics
message the read says asks to see a diagram that no solve drew, the reply gets physics'
contract, its ```draw blocks are traced into field lines under it, and its own sketch goes.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.modules.chat import drawing_turn
from app.modules.chat.drawing_turn import ask_for_a_drawing, attach_drawing
from app.modules.math.drawing.contract import DRAW_CONTRACT
from app.modules.physics.field_lines.contract import FIELD_DRAW_CONTRACT
from app.modules.physics.scene_drawing.contract import SCENE_DRAW_CONTRACT
from app.services.md_fence_scan import iter_closed_fences
from app.services.solving import VerifiedPhysicsBlock
from app.tests.modules.chat.test_drawing_turn import _ctx, _deadline, _decision, _settings, _state

# Physics' contract: its setup's scene, then an electric field's lines.
_PHYSICS_CONTRACT = f"{SCENE_DRAW_CONTRACT}\n{FIELD_DRAW_CONTRACT}"
_FIELD = (
    "Draw the pattern of the electric field around: a) a positive charge b) a negative "
    "charge. Explain what the arrows mean."
)


def _block(description: dict[str, Any]) -> str:
    return f"```draw\n{json.dumps(description)}\n```"


async def test_a_physics_diagram_gets_physics_contract() -> None:
    ctx = _ctx(_FIELD)
    await ask_for_a_drawing(
        ctx, _settings(), _decision(subject="physics", picture="diagram"), _deadline()
    )
    assert ctx.drawing is not None and ctx.drawing.subject == "physics"
    assert ctx.prompt_messages[-2]["content"] == _PHYSICS_CONTRACT
    assert not any(m["content"] == DRAW_CONTRACT for m in ctx.prompt_messages)


def _verified(question: str) -> VerifiedPhysicsBlock:
    from app.core.config import Settings
    from app.modules.physics import build_verified_physics_block, extract_physics_intent

    intent = extract_physics_intent(question)
    assert intent is not None
    block = build_verified_physics_block(intent, Settings(math_tools_enabled=True))
    assert block is not None
    return block


async def test_a_physics_solve_that_drew_the_picture_asks_for_no_description(
    thread_sympy_executor: None,
) -> None:
    """A circuit, rays or a scene the solve drew: no description is asked for."""
    verified = _verified(
        "Two point charges of 3.0 nC and 2.0 nC are 5.0 m apart. Find the force between them."
    )
    ctx = _ctx(_FIELD, verified_subject=verified)
    await ask_for_a_drawing(
        ctx, _settings(), _decision(subject="physics", picture="diagram"), _deadline()
    )
    assert ctx.drawing is None


async def test_a_physics_solve_that_drew_nothing_still_gets_the_contract(
    thread_sympy_executor: None,
) -> None:
    """ "Calculate the field strength ... and draw its lines": the solve verifies the number
    and draws no picture, so the reply describes the field (PR #2482 review)."""
    line = (
        "Calculate the electric field strength 0.20 m from a point charge of 8.0 pC and "
        "draw its field lines."
    )
    ctx = _ctx(line, verified_subject=_verified(line))
    await ask_for_a_drawing(
        ctx, _settings(), _decision(subject="physics", picture="diagram"), _deadline()
    )
    assert ctx.drawing is not None and ctx.drawing.subject == "physics"


async def test_descriptions_are_traced_under_the_reply_and_the_sketch_goes(
    thread_sympy_executor: None,
) -> None:
    ctx = _ctx(_FIELD)
    await ask_for_a_drawing(
        ctx, _settings(), _decision(subject="physics", picture="diagram"), _deadline()
    )
    reply = (
        "**Around a positive charge** the lines point outward.\n\n"
        "```\n   \\  |  /\n  -- (+) --\n   /  |  \\\n```\n\n"
        "**Around a negative charge** they point inward.\n\n"
        f"{_block({'kind': 'field', 'part': 'a', 'charges': [{'sign': '+'}]})}\n\n"
        f"{_block({'kind': 'field', 'part': 'b', 'charges': [{'sign': '-'}]})}\n"
    )
    text = await attach_drawing(_state(ctx, reply))
    bodies = [body for _start, _end, body in iter_closed_fences(text, "simulation")]
    assert len(bodies) == 2
    parts = [json.loads(body)["field"]["part"] for body in bodies]
    assert parts == ["a", "b"]
    assert "```draw" not in text and "(+)" not in text
    assert "point outward" in text and "point inward" in text


async def test_a_description_that_does_not_check_leaves_the_reply_as_written(
    thread_sympy_executor: None,
) -> None:
    ctx = _ctx(_FIELD)
    await ask_for_a_drawing(
        ctx, _settings(), _decision(subject="physics", picture="diagram"), _deadline()
    )
    reply = "Lines point outward.\n\n" + _block(
        {"kind": "field", "charges": [{"sign": "+", "at": [1, 2]}]}
    )
    text = await attach_drawing(_state(ctx, reply))
    assert text == "Lines point outward."


@pytest.mark.parametrize("picture", ["photo", "image"])
async def test_a_physics_message_asking_for_a_photo_or_a_painting_gets_no_contract(
    picture: str,
) -> None:
    ctx = _ctx(_FIELD)
    await ask_for_a_drawing(
        ctx, _settings(), _decision(subject="physics", picture=picture), _deadline()
    )
    assert ctx.drawing is None


async def test_physics_turned_off_asks_for_no_description() -> None:
    ctx = _ctx(_FIELD)
    settings = _settings(physics_enabled=False)
    await ask_for_a_drawing(
        ctx, settings, _decision(subject="physics", picture="diagram"), _deadline()
    )
    assert ctx.drawing is None
    assert not any(m["content"] == _PHYSICS_CONTRACT for m in ctx.prompt_messages)


async def test_a_flowchart_the_user_asked_for_stays_beside_the_picture(
    thread_sympy_executor: None,
) -> None:
    line = f"{_FIELD} Also make a flowchart of how to draw field lines."
    ctx = _ctx(line)
    await ask_for_a_drawing(
        ctx, _settings(), _decision(subject="physics", picture="diagram"), _deadline()
    )
    flowchart = "```mermaid\ngraph TD\nA[Start on +] --> B[End on -]\n```"
    reply = (
        f"Lines point outward.\n\n{flowchart}\n\n"
        f"{_block({'kind': 'field', 'part': 'a', 'charges': [{'sign': '+'}]})}\n"
    )
    text = await attach_drawing(_state(ctx, reply))
    assert flowchart in text and "```simulation" in text


@pytest.mark.parametrize(("subject", "contract"), [("physics", True), (None, False)])
async def test_a_physics_message_asking_in_words_gets_the_contract_when_the_read_is_late(
    monkeypatch: pytest.MonkeyPatch, subject: str | None, contract: bool
) -> None:
    """The read had not answered by the reply's call: a message the physics reader reads
    that asks to see something gets physics' contract, as a maths one gets maths' (PR
    #2482 review); a message no subject reads gets none."""
    monkeypatch.setattr(drawing_turn, "_words_subject", lambda _ctx: subject)
    ctx = _ctx(_FIELD)
    await ask_for_a_drawing(ctx, _settings(), None, _deadline())
    assert (ctx.drawing is not None) == contract
    if contract:
        assert ctx.drawing is not None and ctx.drawing.asked == "words"
        assert ctx.prompt_messages[-2]["content"] == _PHYSICS_CONTRACT


async def test_a_physics_problem_asking_to_see_nothing_gets_the_scene_contract(
    thread_sympy_executor: None,
) -> None:
    """29 of 30 hard problems in parts had no picture (2026-11-16): a physics turn no solve
    drew a picture for gets the contract, its setup's scene, as maths gets its teaching
    figure. Its quantities are the pool's reading of the message (Golden Rule 7); a text the
    pool never read (a photo with no words) gets none, and nothing is read on the loop."""
    from app.core.readings import begin_turn, read_off_loop
    from app.services.subjects.registry import subject_adapter

    line = "Two masses of 3 kg and 5 kg hang over a pulley. Find (a) the acceleration."
    begin_turn()
    unread = _ctx(line)
    await ask_for_a_drawing(
        unread, _settings(), _decision(subject="physics", picture="none"), _deadline()
    )
    assert unread.drawing is None
    await read_off_loop(subject_adapter("physics").reads, line, timeout=5.0)
    ctx = _ctx(line)
    await ask_for_a_drawing(
        ctx, _settings(), _decision(subject="physics", picture="none"), _deadline()
    )
    # The setup's scene only: a field's picture is for a message that asks to see one.
    assert ctx.drawing is not None and ctx.prompt_messages[-2]["content"] == SCENE_DRAW_CONTRACT


@pytest.mark.parametrize("line", ["What is inertia?", "Why does a ball fall?"])
async def test_a_physics_message_stating_no_quantity_gets_no_contract(line: str) -> None:
    """ "what is inertia?" asks to see nothing and states no quantity: no 3 k characters of
    contract on it (review of feat/physics-scenes)."""
    ctx = _ctx(line)
    await ask_for_a_drawing(
        ctx, _settings(), _decision(subject="physics", picture="none"), _deadline()
    )
    assert ctx.drawing is None


async def test_a_physics_message_the_read_says_works_nothing_out_gets_no_contract() -> None:
    """ "Why does a 1 kg mass fall as fast as a 10 kg mass?" states masses and poses no
    problem: the read says it works nothing out, so no setup is asked for."""
    ctx = _ctx("Why does a 1 kg mass fall as fast as a 10 kg mass?")
    decision = _decision(subject="physics", picture="none", work=False)
    await ask_for_a_drawing(ctx, _settings(), decision, _deadline())
    assert ctx.drawing is None


async def test_a_follow_up_scene_is_checked_against_the_problem_it_points_to(
    thread_sympy_executor: None,
) -> None:
    """ "now with 25 m/s": the scene is of the problem the follow-up resolution rewrote,
    not of the line (which states no angle) or the original (20 m/s)."""
    line = "now with 25 m/s"
    ctx = _ctx(line)
    await ask_for_a_drawing(
        ctx, _settings(), _decision(subject="physics", picture="diagram"), _deadline()
    )
    ctx.followup_problem = (
        "A ball is kicked at 25 m/s at 30 degrees above the horizontal. Find its range."
    )
    scene = {"kind": "scene", "scene": "projectile", "values": {"speed": "25 m/s", "angle": "30°"}}
    text = await attach_drawing(_state(ctx, "It goes further.\n\n" + _block(scene)))
    assert [json.loads(body)["type"] for _s, _e, body in iter_closed_fences(text, "simulation")]


async def test_the_contracts_quantity_read_is_made_in_the_pool_with_the_message(
    thread_sympy_executor: None,
) -> None:
    """Golden Rule 7: ``contract_for`` asks on the loop what the pool read with the turn's
    message (``PhysicsSubject.reads``), never Pint on the loop."""
    from app.core.readings import begin_turn, kept_reading, read_off_loop
    from app.modules.physics.scene_drawing.values import states_quantities
    from app.services.subjects.registry import subject_adapter

    line = "A 2 kg cart moving at 3 m/s hits a 1 kg cart at rest."
    begin_turn()
    await read_off_loop(subject_adapter("physics").reads, line, timeout=5.0)
    assert kept_reading(states_quantities, line) is True


async def test_a_physics_instant_reply_gives_way_to_field_lines_its_solve_did_not_draw() -> None:
    """ "Calculate the electric field 0.20 m from a point charge of 8.0 pC and draw its
    field lines": the solve's instant reply carried the field strength alone, and no lines
    could be described (Gemini, PR #2482). The read asking for a physics picture the solve
    did not draw lets the model write around the same card."""
    import asyncio

    from app.modules.chat import drawing_turn
    from app.services.solving import VerifiedPhysicsBlock

    line = (
        "Calculate the electric field 0.20 m from a point charge of 8.0 pC and draw its "
        "field lines."
    )
    read: asyncio.Future[Any] = asyncio.get_event_loop().create_future()
    read.set_result(_decision(subject="physics", picture="diagram"))
    ctx = _ctx(
        line,
        instant_reply="E = 1.8 N/C",
        verified_subject=VerifiedPhysicsBlock(text="E = 1.8 N/C"),
        live_read=read,
    )
    await drawing_turn.write_for_a_picture(ctx, _settings())
    assert ctx.instant_reply is None
    # A read that asks to see nothing keeps the card.
    keeps: asyncio.Future[Any] = asyncio.get_event_loop().create_future()
    keeps.set_result(_decision(subject="physics", picture="none"))
    card = _ctx(
        line,
        instant_reply="E = 1.8 N/C",
        verified_subject=VerifiedPhysicsBlock(text="E = 1.8 N/C"),
        live_read=keeps,
    )
    await drawing_turn.write_for_a_picture(card, _settings())
    assert card.instant_reply == "E = 1.8 N/C"


async def test_a_physics_graph_or_a_drawn_scene_gets_no_scene_contract(
    thread_sympy_executor: None,
) -> None:
    """ "Two masses of 3 kg and 5 kg hang over a frictionless pulley. Find the acceleration
    and sketch a velocity-time graph" got the Atwood scene twice (Gemini, PR #2490): a
    physics graph is the plot path's, and a solve that drew its scene gets no second."""
    line = (
        "Two masses of 3 kg and 5 kg hang over a frictionless pulley. Find the acceleration "
        "and sketch a velocity-time graph."
    )
    graph = _ctx(line)
    await ask_for_a_drawing(
        graph, _settings(), _decision(subject="physics", picture="graph"), _deadline()
    )
    # The plot path's (#2486): maths' contract draws the graph, never physics' scene.
    assert graph.drawing is not None and graph.drawing.subject == "math"
    assert not any(m["content"] == SCENE_DRAW_CONTRACT for m in graph.prompt_messages)
    atwood = _verified("In an Atwood machine, m1 = 2 kg and m2 = 3 kg. Find the acceleration.")
    drawn = _ctx(line, verified_subject=atwood)
    await ask_for_a_drawing(
        drawn, _settings(), _decision(subject="physics", picture="none"), _deadline()
    )
    assert drawn.drawing is None


@pytest.mark.parametrize(
    ("line", "subject", "verified"),
    [
        ("No need to sketch it, just find the roots of x^2 - 5x + 6 = 0.", "maths", "math"),
        (
            "Find the field 0.20 m from an 8.0 pC charge; don't draw the field lines.",
            "physics",
            "physics",
        ),
    ],
)
async def test_a_message_that_asks_to_see_nothing_keeps_its_card_and_gets_no_contract(
    line: str, subject: str, verified: str
) -> None:
    """A read that says the message asks to see nothing ("no need to sketch it", "don't draw
    the field lines") keeps the instant card and asks for no description: every picture
    path goes through the read's one asks check (Gemini, PR #2482)."""
    import asyncio

    from app.modules.chat import drawing_turn
    from app.services.solving import VerifiedMathBlock, VerifiedPhysicsBlock

    block = (
        VerifiedMathBlock(text="x = 2, 3")
        if verified == "math"
        else VerifiedPhysicsBlock(text="E = 1.8 N/C")
    )
    read: asyncio.Future[Any] = asyncio.get_event_loop().create_future()
    read.set_result(_decision(subject=subject, picture="none"))
    ctx = _ctx(line, instant_reply="card", verified_subject=block, live_read=read)
    await drawing_turn.write_for_a_picture(ctx, _settings())
    assert ctx.instant_reply == "card"
    asked = _ctx(line)
    await ask_for_a_drawing(
        asked, _settings(), _decision(subject=subject, picture="none"), _deadline()
    )
    assert asked.drawing is None


async def test_a_follow_ups_problem_is_read_for_its_quantities_in_the_pool(
    thread_sympy_executor: None,
) -> None:
    """ "What if the masses were 4 kg and 6 kg?" after an Atwood question: the rewritten
    problem was never read in the pool, so the setup contract found no kept reading and the
    scene was lost (Gemini, PR #2490). Resolving the follow-up reads it there."""
    from app.core.readings import begin_turn, kept_reading, read_off_loop
    from app.modules.physics.scene_drawing.values import states_quantities
    from app.services.subjects.registry import subject_adapter

    problem = "In an Atwood machine, m1 = 2 kg and m2 = 3 kg. Find the acceleration."
    begin_turn()
    changed = await read_off_loop(
        subject_adapter("physics").followups.changed_problem,
        problem,
        [("2 kg", "4 kg"), ("3 kg", "6 kg")],
        timeout=5.0,
    )
    assert changed is not None
    assert kept_reading(states_quantities, changed) is True


async def test_a_shown_problem_is_read_for_its_quantities_in_the_pool(
    thread_sympy_executor: None,
) -> None:
    """ "Draw it" after a physics problem: the problem it shows was never read in the pool,
    so the setup contract found no kept reading (Gemini, PR #2490). Showing it reads it."""
    from app.core.readings import begin_turn, kept_reading, read_off_loop
    from app.modules.physics.scene_drawing.values import states_quantities
    from app.services.subjects.registry import subject_adapter

    problem = "In an Atwood machine, m1 = 2 kg and m2 = 3 kg. Find the acceleration."
    begin_turn()
    shown = await read_off_loop(
        subject_adapter("physics").followups.shown_problem, "draw it", [], problem, timeout=5.0
    )
    assert shown == problem
    assert kept_reading(states_quantities, shown) is True


async def test_a_field_picture_reads_its_own_line_beside_a_follow_ups_problem(
    thread_sympy_executor: None,
) -> None:
    """A force question, then "Draw the electric field lines around: a) a positive charge
    b) a negative charge" with a follow-up problem set: the field pictures were read from
    the earlier problem (``texts[0]``) and none was drawn (Gemini, PR #2490). The problem
    goes to the scene only; the field reads the line."""
    line = "Draw the electric field lines around: a) a positive charge b) a negative charge"
    ctx = _ctx(line)
    await ask_for_a_drawing(
        ctx, _settings(), _decision(subject="physics", picture="diagram"), _deadline()
    )
    ctx.followup_problem = "A 2 kg box is pushed with a force of 10 N. Find its acceleration."
    reply = (
        f"{_block({'kind': 'field', 'part': 'a', 'charges': [{'sign': '+'}]})}\n\n"
        f"{_block({'kind': 'field', 'part': 'b', 'charges': [{'sign': '-'}]})}\n"
    )
    text = await attach_drawing(_state(ctx, "Here they are.\n\n" + reply))
    bodies = [body for _start, _end, body in iter_closed_fences(text, "simulation")]
    assert [json.loads(body)["field"]["part"] for body in bodies] == ["a", "b"]


async def test_a_late_read_that_asks_to_see_nothing_keeps_a_setup_scene() -> None:
    """A setup scene asked for on the message's words, then a read that says "none": the
    read would have asked for that scene too (``_setup_of``), so it stands (Gemini, PR
    #2491)."""
    from app.tests.modules.chat.test_drawing_turn import _read

    ctx = _ctx("A ball is thrown at 10 m/s at 45°. Find its range.")
    ctx.live_read = _read(subject="physics", picture="none")
    scene = drawing_turn.ReplyDrawing(asked="words", subject="physics")
    assert drawing_turn._still_wanted(ctx, scene)
    ctx.live_read = _read(subject="maths", picture="none")
    assert not drawing_turn._still_wanted(ctx, scene)
