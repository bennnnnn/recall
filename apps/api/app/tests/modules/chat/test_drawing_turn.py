"""The picture a maths reply describes: asked for, kept off the phone, checked, drawn.

Round 3 (2026-11-14) left 32 of 61 pictures undrawn: the server drew only what its figure
read could name, and the reply model was told never to draw. Now, on a maths turn asking
to see a picture, the reply describes it in a ```draw block; the block never streams to
the phone; finalize checks it against the question and draws it under the reply, in place
of the figure read's picture and of any sketch or Mermaid diagram the reply drew for it.
A block on a turn not asked for one, or one that does not check, goes with no note.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models.orm import User
from app.modules.chat import drawing_turn, figure_turn
from app.modules.chat.draw_stream import DrawScan, without_draw_blocks
from app.modules.chat.drawing_turn import ReplyDrawing, ask_for_a_drawing, attach_drawing
from app.modules.chat.finalize_passes import FinalizeState
from app.modules.chat.stream_accum import StreamAccum
from app.modules.chat.turn_decision import TurnDecision
from app.modules.chat.turn_outcome import TurnOutcome
from app.modules.chat.turn_prep import StreamContext
from app.modules.chat.worked_stream import ReplyFilter
from app.modules.math.drawing.contract import DRAW_CONTRACT
from app.services.md_fence_scan import iter_closed_fences
from app.tests.modules.chat.chat_test_support import turn_deps

_VECTORS = (
    "Find the angle between the vectors (-1, 1, 1) and (2, 2, 2), and draw both from the origin."
)
_DESCRIPTION = json.dumps(
    {
        "kind": "space",
        "items": [
            {"item": "axes"},
            {"item": "vector", "name": "u", "to": [-1, 1, 1]},
            {"item": "vector", "name": "v", "to": [2, 2, 2]},
        ],
    }
)
_REPLY = f"Let $u$ and $v$ be the vectors.\n\n**Answer** $\\theta \\approx 70.53^\\circ$\n\n```draw\n{_DESCRIPTION}\n```\n"


def _settings(**overrides: Any) -> Settings:
    return Settings(_env_file=None, **overrides)  # type: ignore[call-arg]


def _ctx(line: str = _VECTORS, **fields: Any) -> StreamContext:
    user = User(id=uuid4(), name="Bini", plan="pro", emoji_use="some", locale="en")
    ctx = StreamContext(
        user_id=user.id,
        chat_id=uuid4(),
        model="smart-chat",
        prompt_messages=[{"role": "system", "content": "rules"}, {"role": "user", "content": line}],
        run_title=False,
        user_message_content=line,
        reserved_tokens=0,
        max_output_tokens=0,
        user_timezone="UTC",
        user=user,
    )
    for name, value in fields.items():
        setattr(ctx, name, value)
    return ctx


def _decision(**fields: Any) -> TurnDecision:
    return TurnDecision(live=False, think=False, **fields)


def _read(**fields: Any) -> asyncio.Future[TurnDecision | None]:
    read: asyncio.Future[TurnDecision | None] = asyncio.get_event_loop().create_future()
    read.set_result(_decision(**fields))
    return read


def _deadline(seconds: float = 1.2) -> float:
    return asyncio.get_running_loop().time() + seconds


def _state(ctx: StreamContext, text: str, *, cancelled: bool = False) -> FinalizeState:
    return FinalizeState(
        deps=turn_deps(),
        settings=_settings(),
        ctx=ctx,
        raw=text,
        text=text,
        usage={},
        outcome=TurnOutcome(),
        was_cancelled=cancelled,
        should_cancel=None,
    )


@pytest.mark.parametrize(
    ("subject", "picture", "asked"),
    [
        ("maths", "diagram", True),
        # The contract draws graphs too (kind "plot").
        ("maths", "graph", True),
        ("maths", "none", False),
        ("physics", "diagram", False),
        ("everyday", "diagram", False),
        ("maths", "image", False),
    ],
)
async def test_ask_for_a_drawing_follows_the_read(subject: str, picture: str, asked: bool) -> None:
    ctx = _ctx()
    await ask_for_a_drawing(
        ctx, _settings(), _decision(subject=subject, picture=picture), _deadline()
    )
    assert (ctx.drawing is not None) == asked
    assert any(m["content"] == DRAW_CONTRACT for m in ctx.prompt_messages) == asked
    if asked:
        assert ctx.drawing is not None and ctx.drawing.asked == "read"
        # Beside the message, before it.
        assert ctx.prompt_messages[-2]["content"] == DRAW_CONTRACT


@pytest.mark.parametrize(
    ("line", "maths", "asked"),
    [
        ("Draw the cone of radius 3 cm and find its volume.", True, True),
        ("Sketch the vectors a = (1, 2, 3) and b = (0, 1, 1).", True, True),
        ("Show that the volume of the frustum is (π/3)h(R² + rR + r²).", True, False),
        ("Find the volume of a cone of radius 3 cm and height 4 cm.", True, False),
        ("Draw me a cat wearing a hat.", False, False),
    ],
)
async def test_ask_for_a_drawing_without_a_read_asks_a_maths_message_in_words(
    monkeypatch: pytest.MonkeyPatch, line: str, maths: bool, asked: bool
) -> None:
    monkeypatch.setattr(drawing_turn, "_a_maths_turn", lambda _ctx: maths)
    ctx = _ctx(line)
    await ask_for_a_drawing(ctx, _settings(), None, _deadline())
    assert (ctx.drawing is not None and ctx.drawing.asked == "words") == asked


async def test_ask_for_a_drawing_is_off_with_its_switch_or_an_instant_reply() -> None:
    read = _decision(subject="maths", picture="diagram")
    off = _ctx()
    await ask_for_a_drawing(off, _settings(draw_descriptions_enabled=False), read, _deadline())
    instant = _ctx(instant_reply="It is 3 pm.")
    await ask_for_a_drawing(instant, _settings(), read, _deadline())
    assert off.drawing is None and instant.drawing is None


_SKETCH = "Find the local maximum of f(x) = x/(1 + x)², and sketch its graph."


@pytest.mark.parametrize(
    ("line", "picture", "verified", "kept"),
    [
        # Round 3's c031: the solver's card alone answered, and no graph could be described.
        (_SKETCH, "graph", True, False),
        # The read says no picture: the instant reply stands.
        (_SKETCH, None, True, True),
        # A server reply with no solve behind it (the time, a setting) is no maths card.
        (_SKETCH, "graph", False, True),
        # Nothing asked to be seen: no wait, the instant reply stands.
        ("Find the local maximum of f(x) = x/(1 + x)².", "graph", True, True),
    ],
)
async def test_a_picture_asked_for_takes_the_place_of_an_instant_card(
    line: str, picture: str | None, verified: bool, kept: bool
) -> None:
    from app.services.solving import VerifiedMathBlock

    solved = VerifiedMathBlock(text="1/4") if verified else None
    read = _read(subject="maths", picture=picture) if picture else _read(subject="maths")
    ctx = _ctx(line, instant_reply="The maximum is 1/4.", verified_subject=solved, live_read=read)
    await drawing_turn.write_for_a_picture(ctx, _settings())
    assert (ctx.instant_reply is not None) == kept


async def _late(decision: TurnDecision, after: float) -> TurnDecision | None:
    await asyncio.sleep(after)
    return decision


@pytest.mark.parametrize(
    ("line", "after", "asked"),
    [
        # Round 3's c082: the reply's call went out before the read; it says draw.
        ("Find the angle between (−1, 1, 1) and (2, 2, 2), and draw both vectors.", 0.05, "read"),
        # No word asking to see anything: no wait.
        ("Find the angle between (−1, 1, 1) and (2, 2, 2).", 0.05, None),
        # A read later than the reply waits for one: no picture.
        ("Draw both vectors (−1, 1, 1) and (2, 2, 2).", 5.0, None),
        # Nothing maths about it (round 2's review: "show me something fun" waited 1.2 s).
        ("hi! show me something fun", 0.05, None),
    ],
)
async def test_a_message_asking_to_see_waits_for_a_late_read(
    line: str, after: float, asked: str | None
) -> None:
    task = asyncio.ensure_future(_late(_decision(subject="maths", picture="diagram"), after))
    ctx = _ctx(line, live_read=task)
    await ask_for_a_drawing(ctx, _settings(live_read_wait_seconds=0.5), None, _deadline(0.5))
    assert (ctx.drawing.asked if ctx.drawing is not None else None) == asked
    # Waited on, never cancelled: the figure read waits for the same read.
    assert not task.cancelled()
    task.cancel()


@pytest.mark.wall_clock
async def test_the_picture_wait_shares_the_reply_s_deadline() -> None:
    """The reply already waited out its time for the read: the contract waits no more."""
    task = asyncio.ensure_future(_late(_decision(subject="maths", picture="diagram"), 0.2))
    ctx = _ctx("Draw both vectors (−1, 1, 1) and (2, 2, 2).", live_read=task)
    loop = asyncio.get_running_loop()
    began = loop.time()
    await ask_for_a_drawing(ctx, _settings(), None, began)
    assert loop.time() - began < 0.1 and ctx.drawing is None
    task.cancel()


def _stream(pieces: list[str]) -> tuple[str, StreamAccum]:
    accum = StreamAccum()
    reply = ReplyFilter(accum, None)
    for piece in pieces:
        sent = reply.feed(piece)
        accum.parts.append(piece)
        accum.shown.append(sent)
    accum.shown.append(reply.flush())
    return "".join(accum.shown), accum


@pytest.mark.parametrize("size", [1, 2, 3, 7, 40, 1000])
def test_a_draw_block_never_streams_to_the_phone(size: int) -> None:
    pieces = [_REPLY[i : i + size] for i in range(0, len(_REPLY), size)]
    sent, accum = _stream(pieces)
    assert "```draw" not in sent and '"kind"' not in sent
    assert sent.startswith("Let $u$ and $v$ be the vectors.") and "70.53" in sent
    assert [body for _at, body in accum.drawings] == [_DESCRIPTION]


def test_a_block_closed_at_the_very_end_is_whole() -> None:
    sent, accum = _stream(["Done.\n\n```draw\n", _DESCRIPTION, "\n```"])
    assert sent == "Done.\n\n" and [body for _at, body in accum.drawings] == [_DESCRIPTION]


def test_other_fences_stream_as_written() -> None:
    reply = "Here:\n\n```python\nprint('draw')\n```\n\n```drawing\nnot ours\n```\nDone."
    sent, accum = _stream([reply[i : i + 3] for i in range(0, len(reply), 3)])
    assert sent == reply and accum.drawings == []


def test_an_unclosed_draw_block_is_never_shown() -> None:
    sent, accum = _stream(["Answer: 3.\n\n```draw\n", '{"kind":"space",', '"items":[]}'])
    assert sent == "Answer: 3.\n\n" and len(accum.drawings) == 1


_BLOCK = f"```draw\n{_DESCRIPTION}\n"


@pytest.mark.parametrize(
    ("reply", "shown", "kept"),
    [
        # A block closed with tildes, or with a longer run, is closed: the text after it shows.
        (f"Done.\n\n{_BLOCK}~~~\nAfter.", "Done.\n\nAfter.", 1),
        (f"Done.\n\n{_BLOCK}````\nAfter.", "Done.\n\nAfter.", 1),
        # An example of a block inside an outer fence is the example's content.
        (f"Like this:\n````markdown\n{_BLOCK}```\n````\nEnd.", None, 0),
        # "```draw" mid-line opens nothing.
        ("Write it as ```draw then JSON.\nEnd.", None, 0),
        # A block cut off at the reply's end runs to it.
        (f"Answer: 3.\n\n{_BLOCK}", "Answer: 3.\n\n", 1),
    ],
)
@pytest.mark.parametrize("size", [1, 5, 1000])
def test_one_rule_for_a_draw_block_live_and_saved(
    reply: str, shown: str | None, kept: int, size: int
) -> None:
    sent, accum = _stream([reply[i : i + size] for i in range(0, len(reply), size)])
    assert sent == (reply if shown is None else shown)
    assert len(accum.drawings) == kept
    saved, bodies = without_draw_blocks(reply)
    assert saved == sent and len(bodies) == kept


@pytest.mark.parametrize(
    ("first", "held"),
    [
        # A short run with text after it can never open a fence: it streams before its line ends.
        ("`useEffect` runs after", False),
        ("~5 min later the", False),
        ("``x`` and", False),
        # A run that may still grow into a fence waits for its line's end.
        ("``", True),
        ("~", True),
        ("```dra", True),
        ("   ~~~", True),
    ],
)
def test_only_a_line_that_may_open_a_fence_waits(first: str, held: bool) -> None:
    scan = DrawScan(lambda _body: None)
    assert (scan.feed(first) == "") is held


def test_text_taken_back_takes_its_drawings() -> None:
    accum = StreamAccum(parts=["a"], shown=["a"])
    accum.drawings = [(1, "kept"), (2, "taken")]
    accum.shown.append("b")
    accum.retract(1, 2)
    assert accum.drawings == [(1, "kept")]


async def test_a_checked_description_is_drawn_under_the_reply() -> None:
    ctx = _ctx(live_read=_read(subject="maths", picture="diagram"))
    ctx.drawing = ReplyDrawing("read", descriptions=[_DESCRIPTION])
    text = "Let $u$ and $v$ be the vectors.\n\n**Answer** $\\theta \\approx 70.53^\\circ$"
    state = _state(ctx, text + "\n\n```mermaid\ngraph LR\n  O --> A\n```")
    out = await attach_drawing(state)
    assert out.startswith(text) and "```mermaid" not in out
    assert out.rstrip().endswith("```") and '"shape":"space"' in out
    assert ctx.drawing.drawn and state.committed == out


async def test_a_drawn_graph_takes_the_place_of_a_graph_of_its_curve_alone() -> None:
    """Round 3's c009 showed a solve's plot of the curve beside the drawn graph; a solver's
    number line and a chart are no graph of that curve, and stay (2026-11-15 review)."""
    line = "Let f(x) = x^2 - 4. Sketch the graph of f and solve x^2 - 4 < 0."
    ctx = _ctx(line, live_read=_read(subject="maths", picture="graph"))
    plot = {"kind": "plot", "items": [{"item": "curve", "name": "f", "y": "x^2 - 4"}]}
    ctx.drawing = ReplyDrawing("read", descriptions=[json.dumps(plot)])
    xs = [i / 4 for i in range(-12, 13)]
    curve = json.dumps([[x, x * x - 4] for x in xs])
    cube = json.dumps([[x, x**3] for x in xs])
    solved = f'```graph\n{{"type":"function","expr":"x^2 - 4","points":{curve}}}\n```'
    other = f'```graph\n{{"type":"function","expr":"x^3","points":{cube}}}\n```'
    line_fence = (
        '```graph\n{"type":"number_line","expr":"x^2 - 4 < 0","intervals":'
        '[{"start":-2,"end":2}]}\n```'
    )
    chart = '```chart\n{"mark":"line"}\n```'
    text = f"The vertex is (0, -4).\n\n{solved}\n\n{other}\n\n{line_fence}\n\n{chart}"
    out = await attach_drawing(_state(ctx, text))
    graphs = [body for _start, _end, body in iter_closed_fences(out, "graph")]
    assert len(graphs) == 3 and '"type":"plot"' in graphs[-1]
    assert '"x^2 - 4","points"' not in out and '"x^3"' in out and "number_line" in out
    assert "```chart" in out


@pytest.mark.wall_clock
async def test_an_instant_reply_never_waits_for_the_read() -> None:
    """ "Show your steps" waited 1.2 s for a read that had not come (2026-11-15 review)."""
    from app.services.solving import VerifiedMathBlock

    pending: asyncio.Future[TurnDecision | None] = asyncio.get_event_loop().create_future()
    line = "Find the local maximum of f(x) = x/(1 + x)² and show your steps."
    ctx = _ctx(
        line,
        instant_reply="The maximum is 1/4.",
        verified_subject=VerifiedMathBlock(text="1/4"),
        live_read=pending,
    )
    loop = asyncio.get_running_loop()
    began = loop.time()
    await drawing_turn.write_for_a_picture(ctx, _settings())
    assert loop.time() - began < 0.1 and ctx.instant_reply is not None
    sketch = _ctx(
        _SKETCH,
        instant_reply="The maximum is 1/4.",
        verified_subject=VerifiedMathBlock(text="1/4"),
        live_read=pending,
    )
    await drawing_turn.write_for_a_picture(sketch, _settings())
    assert sketch.instant_reply is None
    pending.cancel()


async def test_a_description_in_the_text_is_taken_out_and_drawn() -> None:
    ctx = _ctx(live_read=_read(subject="maths", picture="diagram"))
    ctx.drawing = ReplyDrawing("read")
    out = await attach_drawing(_state(ctx, _REPLY))
    assert "```draw" not in out and "```geometry" in out


@pytest.mark.parametrize(
    ("drawing", "read", "description"),
    [
        # Not asked for one: the block goes, nothing is drawn.
        (None, {"subject": "maths", "picture": "diagram"}, _DESCRIPTION),
        # Asked on the message's words, then the read said no picture.
        (ReplyDrawing("words"), {"subject": "maths", "picture": "none"}, _DESCRIPTION),
        (ReplyDrawing("words"), {"subject": "everyday", "picture": "diagram"}, _DESCRIPTION),
        # A vector the question does not write: nothing left but the axes.
        (
            ReplyDrawing("read"),
            {"subject": "maths", "picture": "diagram"},
            json.dumps(
                {"kind": "space", "items": [{"item": "vector", "name": "w", "to": [3, 1, 4]}]}
            ),
        ),
    ],
)
async def test_a_description_not_wanted_or_not_held_draws_nothing(
    drawing: ReplyDrawing | None, read: dict[str, str], description: str
) -> None:
    ctx = _ctx(live_read=_read(**read), drawing=drawing)
    text = f"The angle is about 70.53°.\n\n```draw\n{description}\n```"
    out = await attach_drawing(_state(ctx, text))
    assert out.strip() == "The angle is about 70.53°."


async def test_a_stopped_reply_draws_nothing() -> None:
    ctx = _ctx(live_read=_read(subject="maths", picture="diagram"))
    ctx.drawing = ReplyDrawing("read", descriptions=[_DESCRIPTION])
    out = await attach_drawing(_state(ctx, "The angle is", cancelled=True))
    assert out == "The angle is" and not ctx.drawing.drawn


@pytest.mark.parametrize(
    ("read_fence", "both"),
    [
        # The read's figure of the kind the reply drew stands aside for it.
        ('```geometry\n{"type":"figure","shape":"cube"}\n```', False),
        # One of the other kind joins it: a reply may carry a figure and a graph.
        ('```graph\n{"type":"function","expr":"x"}\n```', True),
    ],
)
async def test_one_picture_of_each_kind(read_fence: str, both: bool) -> None:
    ctx = _ctx(live_read=_read(subject="maths", picture="diagram"))
    ctx.drawing = ReplyDrawing("read", descriptions=[_DESCRIPTION])
    ctx.figure = asyncio.ensure_future(asyncio.sleep(0, result=read_fence))
    state = _state(ctx, "Let $u$ and $v$ be the vectors.")
    state.text = await attach_drawing(state)
    out = await figure_turn.attach_figure(state)
    assert out.count("```geometry") == 1
    assert ("```graph" in out) == both


@pytest.mark.parametrize(
    "line",
    [
        # "The graph of y = …" names a curve; it asks for no picture (2026-11-15 review).
        "Find the x-intercepts of the graph of y = x^2 - 4.",
        "Find the gradient of the graph of y = x^3 at x = 2.",
        "What is the vertex of the parabola? Don't draw anything, just give the coordinates: "
        "y = x^2 - 4x + 1",
    ],
)
async def test_an_instant_card_stays_unless_asked_to_draw(line: str) -> None:
    from app.services.solving import VerifiedMathBlock

    pending: asyncio.Future[TurnDecision | None] = asyncio.get_event_loop().create_future()
    ctx = _ctx(
        line,
        instant_reply="x = ±2",
        verified_subject=VerifiedMathBlock(text="2"),
        live_read=pending,
    )
    await drawing_turn.write_for_a_picture(ctx, _settings())
    pending.cancel()
    assert ctx.instant_reply is not None


@pytest.mark.parametrize(
    "line",
    [
        "Find the area enclosed by f(x) = 4 - x^2 and g(x) = 3x. Show the curves and shade the region.",
        "Find the area enclosed by f(x) = ln x and the x-axis from x = 1 to x = e. Show it on a graph.",
        "Find the local maximum of f(x) = x/(1 + x)^2, and sketch its graph.",
    ],
)
async def test_an_instant_card_gives_way_to_an_ask_to_draw(line: str) -> None:
    from app.services.solving import VerifiedMathBlock

    pending: asyncio.Future[TurnDecision | None] = asyncio.get_event_loop().create_future()
    ctx = _ctx(
        line,
        instant_reply="The area is 125/6.",
        verified_subject=VerifiedMathBlock(text="125/6"),
        live_read=pending,
    )
    await drawing_turn.write_for_a_picture(ctx, _settings())
    pending.cancel()
    assert ctx.instant_reply is None
