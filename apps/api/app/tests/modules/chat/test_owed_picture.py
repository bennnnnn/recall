"""A picture the turn's read asked for is drawn by the app or said in one line not to be;
no Mermaid flowchart stands in for it (Grade 8 round and owner, 2026-11-18)."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

import pytest

from app.modules.chat import stream_pipeline
from app.modules.chat.drawing_turn import ReplyDrawing
from app.modules.chat.owed_picture import (
    APP_PICTURES,
    held_to_the_ask,
    mermaid_stands_in,
    not_drawn_line,
    shows_a_picture,
)
from app.modules.chat.stream_accum import StreamAccum
from app.modules.chat.turn_decision import TurnDecision
from app.modules.chat.turn_prep import StreamContext

_FLOWCHART = "```mermaid\nflowchart LR\n  A[Small piston] --> B[Large piston]\n```"
_GRAPH = '```graph\n{"type":"trajectory"}\n```'


def _decision(subject: str, picture: str) -> TurnDecision:
    return TurnDecision.model_validate(
        {"live": False, "think": False, "subject": subject, "picture": picture}
    )


def _ctx(line: str, read: TurnDecision | None = None, **fields: Any) -> StreamContext:
    ctx = StreamContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        model="free-chat",
        prompt_messages=[],
        run_title=False,
        user_message_content=line,
        reserved_tokens=0,
        max_output_tokens=0,
        **fields,
    )
    if read is not None:
        future: asyncio.Future[TurnDecision | None] = asyncio.get_event_loop().create_future()
        future.set_result(read)
        ctx.live_read = future  # type: ignore[assignment]
    return ctx


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "line, subject, picture, stands_in",
    [
        (
            "Draw a hydraulic press diagram and describe how it functions.",
            "physics",
            "diagram",
            True,
        ),
        ("draw the circuit diagram for this", "physics", "diagram", True),
        ("show me how a bicycle looks", "everyday", "image", True),
        (
            "Draw a flowchart of the steps to solve a projectile problem",
            "physics",
            "diagram",
            False,
        ),
        ("Show the steps of mitosis as a flow", "everyday", "diagram", False),
        ("Draw a diagram of our web app's services", "code", "diagram", False),
        ("Explain how a hydraulic press works", "physics", "none", False),
    ],
)
async def test_a_flowchart_stands_in_only_for_a_picture_that_is_none(
    line: str, subject: str, picture: str, stands_in: bool
) -> None:
    assert mermaid_stands_in(_decision(subject, picture), line) is stands_in


@pytest.mark.asyncio
async def test_a_physical_diagram_loses_its_flowchart_and_says_it_was_not_drawn() -> None:
    ctx = _ctx("Draw a hydraulic press diagram.", _decision("physics", "diagram"))
    text = held_to_the_ask(f"{_FLOWCHART}\n\nIt multiplies force.", ctx, "en")
    assert "```mermaid" not in text
    assert text == "It multiplies force.\n\nI couldn't draw this diagram.\n"


@pytest.mark.asyncio
async def test_a_drawn_picture_needs_no_line() -> None:
    ctx = _ctx("Draw the v-t graph.", _decision("physics", "graph"))
    reply = f"It speeds up.\n\n{_GRAPH}\n"
    assert held_to_the_ask(reply, ctx, "en") == reply


@pytest.mark.asyncio
async def test_an_empty_reply_is_the_line_alone_in_the_reply_s_language() -> None:
    ctx = _ctx("Zeichne den Graphen.", _decision("maths", "graph"))
    assert held_to_the_ask("", ctx, "de") == f"{not_drawn_line('graph', 'de')}\n"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "subject, picture",
    [("everyday", "diagram"), ("physics", "none"), ("everyday", "photo"), ("maths", "image")],
)
async def test_a_turn_owed_no_app_picture_is_left_as_it_is(subject: str, picture: str) -> None:
    ctx = _ctx("Tell me about it.", _decision(subject, picture))
    assert held_to_the_ask("It is so.", ctx, "en") == "It is so."


def test_no_read_and_no_description_asked_owes_nothing() -> None:
    assert held_to_the_ask("It is so.", _ctx("draw it"), "en") == "It is so."
    asked = _ctx("draw it", drawing=ReplyDrawing("words", subject="physics"))
    assert held_to_the_ask("It is so.", asked, "en").endswith("I couldn't draw this diagram.\n")


def test_a_reply_of_only_its_picture_s_description_is_a_reply() -> None:
    """t15: "Draw the v-t graph" answered with a ```draw block alone raised "That model
    isn't responding"; finalize now draws it or says it could not."""
    accum = StreamAccum()
    accum.drawings.append((0, '{"kind":"plot"}'))
    drawing = _ctx("Draw the graph.", drawing=ReplyDrawing("read"))
    assert stream_pipeline._describes_its_picture(drawing, accum)
    assert not stream_pipeline._describes_its_picture(_ctx("Draw the graph."), accum)
    assert not stream_pipeline._describes_its_picture(drawing, StreamAccum())


def test_the_summary_records_as_shown_every_picture_the_app_draws() -> None:
    """One picture record (#2499): a reply this pass counts as drawn is one the chat's
    summary marks "[shown: …]", and the summary also marks the two pictures this pass never
    counts as the drawing owed, a flowchart (Mermaid) and a photo."""
    from app.modules.chat.compaction import _SHOWN, summary_text

    assert set(_SHOWN) == APP_PICTURES | {"mermaid", "photo"}
    assert summary_text(_FLOWCHART) == "[shown: a flowchart]"
    assert shows_a_picture(_GRAPH) and summary_text(_GRAPH) == "[shown: a graph]"


def test_every_language_has_every_line() -> None:
    from app.modules.chat.owed_picture import _NOT_DRAWN

    assert {len(lines) for lines in _NOT_DRAWN.values()} == {3}
    assert not_drawn_line("diagram", "xx") == not_drawn_line("diagram", "en")
    assert len({not_drawn_line("graph", lang) for lang in _NOT_DRAWN}) == len(_NOT_DRAWN)


@pytest.mark.parametrize(
    "reply, kept",
    [
        # t30's second run: the sentence about the flowchart went with it.
        (
            f"{_FLOWCHART}\n\nThat diagram is the simplest way to see it.\n\nPush the small piston.",
            "Push the small piston.",
        ),
        (f"Here is the setup:\n\n{_FLOWCHART}\n\nIt multiplies force.", "It multiplies force."),
        (
            f"It multiplies force.\n\n{_FLOWCHART}\n\nPush harder to lift more.",
            "It multiplies force.\n\nPush harder to lift more.",
        ),
    ],
)
def test_a_flowchart_s_own_sentence_goes_with_it(reply: str, kept: str) -> None:
    from app.modules.chat.owed_picture import without_flowcharts

    assert without_flowcharts(reply).strip() == kept


def test_two_flowcharts_that_share_a_paragraph_cut_only_themselves() -> None:
    """Review: each card took the paragraph between them, and the second cut ran on into
    the reply's last words."""
    from app.modules.chat.owed_picture import without_flowcharts

    reply = (
        f"{_FLOWCHART}\n\nThat diagram shows part a; below is part b:\n\n{_FLOWCHART}\n\n"
        "Both follow Ohm's law."
    )
    assert without_flowcharts(reply).strip() == "Both follow Ohm's law."


@pytest.mark.asyncio
async def test_the_line_takes_the_place_of_the_sentence_that_presented_the_picture() -> None:
    """Review: "Here is the v-t graph of the car's motion:" stood over "I couldn't draw this
    graph." once a picture pass had taken the graph it led into."""
    ctx = _ctx("Draw the v against t graph.", _decision("physics", "graph"))
    reply = "Here is the v–t graph of the car's motion:\n\nThe slope is the acceleration."
    assert held_to_the_ask(reply, ctx, "en") == (
        "I couldn't draw this graph.\n\nThe slope is the acceleration.\n"
    )
    listed = "The graph has two parts:\n\n- a rise\n- a flat stretch"
    assert held_to_the_ask(listed, ctx, "en") == f"{listed}\n\nI couldn't draw this graph.\n"


@pytest.mark.asyncio
async def test_a_photo_asked_for_keeps_its_words_without_its_flowchart() -> None:
    """Review: a photo turn's stand-in flowchart goes, and no "couldn't draw this diagram"
    is said of a photo; a reply that was only the flowchart still says it."""
    ctx = _ctx(
        "Explain how a bicycle works and show a photo of one.", _decision("everyday", "photo")
    )
    assert held_to_the_ask(f"Pedals turn the chain.\n\n{_FLOWCHART}", ctx, "en") == (
        "Pedals turn the chain."
    )
    assert held_to_the_ask(_FLOWCHART, ctx, "en") == "I couldn't draw this diagram.\n"
