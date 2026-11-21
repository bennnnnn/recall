"""A picture a maths question asks to see is drawn beside the reply and added under it.

The textbook run (2026-11-13) asked to draw a rhombus, a cube, points in four quadrants
and more, and got none of them: no solver read those requests, and the model was told
not to draw. The turn's read says a maths question asks for a picture; maths reads what
to draw and draws it from the question's own values while the reply streams; finalize
adds it under the reply, unless the reply already holds the server's picture.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models.orm import User
from app.modules.chat import figure_turn
from app.modules.chat.finalize_passes import FINALIZE_PASSES, FinalizeState
from app.modules.chat.turn_decision import TurnDecision
from app.modules.chat.turn_outcome import TurnOutcome
from app.modules.chat.turn_prep import StreamContext
from app.services.solving import VerifiedMathBlock, VerifiedPhysicsBlock
from app.tests.modules.chat.chat_test_support import turn_deps

_FENCE = '```geometry\n{"type":"figure","shape":"cube","points":[{"name":"a","x":0,"y":0},{"name":"b","x":1,"y":0}],"segments":[{"a":"a","b":"b","label":"3 cm"}]}\n```'
_QUESTION = "Find the volume of a cube with sides of 4 m, and draw the cube."


def _settings(**overrides: Any) -> Settings:
    return Settings(_env_file=None, **overrides)  # type: ignore[call-arg]


def _ctx(line: str = _QUESTION, **fields: Any) -> StreamContext:
    user = User(id=uuid4(), name="Bini", plan="pro", emoji_use="some", locale="en")
    ctx = StreamContext(
        user_id=user.id,
        chat_id=uuid4(),
        model="smart-chat",
        prompt_messages=[{"role": "user", "content": line}],
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


def _state(ctx: StreamContext, text: str, settings: Settings | None = None) -> FinalizeState:
    return FinalizeState(
        deps=turn_deps(),
        settings=settings or _settings(),
        ctx=ctx,
        raw=text,
        text=text,
        usage={},
        outcome=TurnOutcome(),
        was_cancelled=False,
        should_cancel=None,
    )


def _read(**fields: Any) -> asyncio.Future[TurnDecision | None]:
    """The turn's read, already answered (a streamed reply waits for it before finalize)."""
    read: asyncio.Future[TurnDecision | None] = asyncio.get_event_loop().create_future()
    read.set_result(TurnDecision(live=False, think=False, **fields))
    return read


class _Figure:
    """Maths' figure, with the read and the build stood in for."""

    def __init__(self, fence: str | None = _FENCE) -> None:
        self.fence = fence
        self.asked: list[tuple[str, list[str]]] = []
        # Each draw's ``asked``: the message asked to see it (True) or it only helps teach.
        self.modes: list[bool] = []

    async def draw(
        self, question: str, earlier: Any, settings: Settings, *, asked: bool = True
    ) -> str | None:
        self.asked.append((question, list(earlier)))
        self.modes.append(asked)
        return self.fence

    def shown(self, verified: Any) -> bool:
        from app.modules.math.figure.substitutes import verified_picture

        return verified_picture(verified)

    def whole(self, text: str) -> bool:
        from app.modules.math.figure.substitutes import holds_whole_picture

        return holds_whole_picture(text)

    def adds_to(self, text: str, fence: str) -> bool:
        from app.modules.math.figure.substitutes import adds_to

        return adds_to(text, fence)

    def without_substitutes(self, text: str) -> str:
        from app.modules.math.figure.substitutes import without_substitutes

        return without_substitutes(text)


@pytest.fixture
def figure(monkeypatch: pytest.MonkeyPatch) -> _Figure:
    stand_in = _Figure()
    monkeypatch.setattr(figure_turn, "_figure", lambda *_: stand_in)
    return stand_in


async def test_a_maths_picture_request_is_drawn_under_the_reply(figure: _Figure) -> None:
    ctx = _ctx(live_read=_read(subject="maths", picture="diagram"))
    ctx.figure = figure_turn.start_figure(_settings(), ctx)
    assert ctx.figure is not None
    text = await figure_turn.attach_figure(_state(ctx, "**Answer**\n\n$V = 64\\ m^3$"))
    assert text.endswith(_FENCE + "\n")
    assert figure.asked == [(_QUESTION, [])]
    assert figure.modes == [True]


@pytest.mark.parametrize(
    "read",
    [
        {"subject": "maths", "picture": "photo"},
        {"subject": "maths", "picture": "molecule"},
        {"subject": "physics", "picture": "diagram"},
        {"subject": "everyday", "picture": "graph"},
    ],
)
async def test_no_picture_without_a_maths_picture_read(
    figure: _Figure, read: dict[str, str]
) -> None:
    ctx = _ctx(live_read=_read(**read))
    ctx.figure = figure_turn.start_figure(_settings(), ctx)
    text = await figure_turn.attach_figure(_state(ctx, "Reply."))
    assert text == "Reply."
    assert figure.asked == []


async def test_a_read_that_never_came_draws_nothing(figure: _Figure) -> None:
    async def never() -> TurnDecision | None:
        raise asyncio.CancelledError

    ctx = _ctx(live_read=asyncio.ensure_future(never()))
    ctx.figure = figure_turn.start_figure(_settings(), ctx)
    assert await figure_turn.attach_figure(_state(ctx, "Reply.")) == "Reply."


def test_no_read_starts_no_picture(figure: _Figure) -> None:
    assert figure_turn.start_figure(_settings(), _ctx(live_read=None)) is None


async def test_a_turn_whose_solve_drew_the_graph_reads_none(figure: _Figure) -> None:
    graph = {"type": "function", "expr": "x", "points": [[0, 0], [1, 1]]}
    verified = VerifiedMathBlock(text="", canonical_fence=graph)
    ctx = _ctx(live_read=_read(subject="maths", picture="diagram"), verified_subject=verified)
    assert figure_turn.start_figure(_settings(), ctx) is None


async def test_a_reply_made_without_a_solve_waits_for_no_picture(figure: _Figure) -> None:
    # "What time is it in Tokyo?" waited 1.7 s at finalize for a read that said no picture.
    ctx = _ctx("What time is it in Tokyo?", live_read=_read(), instant_reply="It is 3:04 pm.")
    assert figure_turn.start_figure(_settings(), ctx) is None


async def test_a_flowchart_always_stays(figure: _Figure) -> None:
    # "Show the steps as a flow diagram" lost its Mermaid when every one was stripped.
    line = "Graph y = 2x + 1 and show the steps as a flow diagram."
    ctx = _ctx(line, live_read=_read(subject="maths", picture="graph"))
    ctx.figure = figure_turn.start_figure(_settings(), ctx)
    reply = "The steps:\n\n```mermaid\nflowchart TD\n  A[Start] --> B[Plot]\n```"
    text = await figure_turn.attach_figure(_state(ctx, reply))
    assert "```mermaid" in text and text.endswith(_FENCE + "\n")


async def test_the_switch_turns_it_off(figure: _Figure) -> None:
    ctx = _ctx(live_read=_read(subject="maths", picture="diagram"))
    assert figure_turn.start_figure(_settings(figure_read_enabled=False), ctx) is None


async def test_a_reply_holding_the_server_s_picture_gets_no_second(figure: _Figure) -> None:
    ctx = _ctx(live_read=_read(subject="maths", picture="graph"))
    ctx.figure = figure_turn.start_figure(_settings(), ctx)
    reply = 'Here.\n\n```graph\n{"type":"function","expr":"x","points":[[0,0],[1,1]]}\n```'
    assert await figure_turn.attach_figure(_state(ctx, reply)) == reply
    await asyncio.sleep(0)
    assert ctx.figure is not None and ctx.figure.cancelled()


async def test_the_model_s_own_sketch_goes_when_the_picture_comes(figure: _Figure) -> None:
    ctx = _ctx(live_read=_read(subject="maths", picture="graph"))
    ctx.figure = figure_turn.start_figure(_settings(), ctx)
    reply = "Order: $-1.2 < 0.5$\n\n```text\n←────●────────●────→\n    -1.2     0.5\n```"
    text = await figure_turn.attach_figure(_state(ctx, reply))
    assert "```text" not in text
    assert text.startswith("Order:") and text.endswith(_FENCE + "\n")


async def test_a_slow_picture_is_left_out(figure: _Figure, monkeypatch: pytest.MonkeyPatch) -> None:
    async def slow(*_args: Any, **_kwargs: Any) -> str:
        await asyncio.sleep(5)
        return _FENCE

    monkeypatch.setattr(figure, "draw", slow)
    ctx = _ctx(live_read=_read(subject="maths", picture="diagram"))
    ctx.figure = figure_turn.start_figure(_settings(), ctx)
    state = _state(ctx, "Reply.", _settings(figure_wait_seconds=0.05))
    assert await figure_turn.attach_figure(state) == "Reply."
    await asyncio.sleep(0)
    assert ctx.figure is not None and ctx.figure.cancelled()


async def test_a_picture_that_fails_leaves_the_reply(
    figure: _Figure, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def broken(*_args: Any, **_kwargs: Any) -> str:
        raise RuntimeError("no picture")

    monkeypatch.setattr(figure, "draw", broken)
    ctx = _ctx(live_read=_read(subject="maths", picture="diagram"))
    ctx.figure = figure_turn.start_figure(_settings(), ctx)
    assert await figure_turn.attach_figure(_state(ctx, "Reply.")) == "Reply."


async def test_draw_it_reads_the_earlier_question(figure: _Figure) -> None:
    earlier = SimpleNamespace(role="user", content="A rhombus has diagonals 10 cm and 24 cm.")
    reply = SimpleNamespace(role="assistant", content="Its side is 13 cm.")
    line = SimpleNamespace(role="user", content="draw it")
    ctx = _ctx(
        "draw it",
        live_read=_read(subject="maths", picture="diagram", follow="draw"),
        recent_messages=[earlier, reply, line],
    )
    ctx.figure = figure_turn.start_figure(_settings(), ctx)
    await figure_turn.attach_figure(_state(ctx, "Here it is."))
    assert figure.asked == [("draw it", ["A rhombus has diagonals 10 cm and 24 cm."])]


async def test_a_question_that_stands_alone_is_read_without_the_earlier_ones(
    figure: _Figure,
) -> None:
    """The owner's chat (2026-11-20): a rectangle's area and perimeter after a question about
    vectors drew nothing; read beside the vectors, the figure read said "no picture". A
    message the read calls standalone (follow none) is read by itself."""
    earlier = SimpleNamespace(role="user", content="Resolve 60 N at 30° into two components.")
    reply = SimpleNamespace(role="assistant", content="52 N and 30 N.")
    question = "If the length of a rectangle is 4 and the width 5, what is the area?"
    line = SimpleNamespace(role="user", content=question)
    ctx = _ctx(
        question,
        live_read=_read(subject="maths", picture="none", follow="none"),
        recent_messages=[earlier, reply, line],
    )
    ctx.figure = figure_turn.start_figure(_settings(), ctx)
    await figure_turn.attach_figure(_state(ctx, "**Answer**\n\n$A = 20$"))
    assert figure.asked == [(question, [])]


_VECTORS = "Resolve 60 N at 30° from the horizontal into two components."
_RECTANGLE = "If the length of a rectangle is 4 and the width 5, what is the area?"


def _chat(*lines: str) -> list[SimpleNamespace]:
    out = []
    for text in lines:
        out += [
            SimpleNamespace(role="user", content=text),
            SimpleNamespace(role="assistant", content="…"),
        ]
    return out[:-1]


async def test_draw_it_reads_the_problem_and_its_follow_ups_not_the_older_chat(
    figure: _Figure, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The owner's chat (2026-11-20): vectors, then a rectangle, "Find the diagonal", "Draw
    it". Read beside the vectors, "Draw it" drew nothing and the reply said it could not.
    The referent read names the rectangle; the figure reads it and the follow-up since."""
    from app.modules.chat import referent_read

    async def named(*_: Any) -> referent_read.Referent:
        return referent_read.Referent(_RECTANGLE)

    monkeypatch.setattr(referent_read, "referent_for_turn", named)
    ctx = _ctx(
        "Draw it",
        live_read=_read(subject="maths", picture="diagram", follow="draw"),
        recent_messages=_chat(_VECTORS, _RECTANGLE, "Find the diagonal", "Draw it"),
    )
    ctx.figure = figure_turn.start_figure(_settings(), ctx)
    await figure_turn.attach_figure(_state(ctx, "Here it is."))
    assert figure.asked == [("Draw it", [_RECTANGLE, "Find the diagonal"])]


async def test_a_follow_up_reads_the_problem_it_continues(
    figure: _Figure, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.modules.chat import referent_read

    async def continued(*_: Any) -> str:
        return f"{_RECTANGLE} Find the diagonal"

    monkeypatch.setattr(referent_read, "continuation_for_turn", continued)
    ctx = _ctx(
        "Find the diagonal",
        live_read=_read(subject="maths", picture="none", follow="change"),
        recent_messages=_chat(_VECTORS, _RECTANGLE, "Find the diagonal"),
    )
    ctx.figure = figure_turn.start_figure(_settings(), ctx)
    await figure_turn.attach_figure(_state(ctx, "$d = 6.4$"))
    assert figure.asked == [("Find the diagonal", [_RECTANGLE])]


def test_a_short_earlier_line_is_not_taken_for_the_problem_s_start() -> None:
    users = ["5", _RECTANGLE, "Find the diagonal"]
    assert figure_turn.topic_lines(users, _RECTANGLE) == [_RECTANGLE, "Find the diagonal"]
    assert figure_turn.topic_lines(["hello"], "A square of side 3") == ["A square of side 3"]


async def test_a_solid_joins_the_plane_part_a_solve_drew(figure: _Figure) -> None:
    """The textbook's prism (b27): the solve drew the base triangle; the prism joins it."""
    figure.fence = _FENCE  # a cube
    base = {"type": "triangle_sides", "a": 6, "b": 8, "c": 10}
    verified = VerifiedMathBlock(text="", canonical_fence=base)
    ctx = _ctx(live_read=_read(subject="maths", picture="diagram"), verified_subject=verified)
    ctx.figure = figure_turn.start_figure(_settings(), ctx)
    assert ctx.figure is not None
    reply = '**Answer**\n\n```geometry\n{"type":"triangle_sides","a":6,"b":8,"c":10}\n```'
    text = await figure_turn.attach_figure(_state(ctx, reply))
    assert text.count("```geometry") == 2 and text.endswith(_FENCE + "\n")


async def test_a_plane_figure_does_not_repeat_the_solve_s_shape(figure: _Figure) -> None:
    figure.fence = _FENCE.replace('"cube"', '"parallelogram"')
    ctx = _ctx(live_read=_read(subject="maths", picture="diagram"))
    ctx.figure = figure_turn.start_figure(_settings(), ctx)
    reply = 'Here.\n\n```geometry\n{"type":"parallelogram","base":6,"height":4,"side":5}\n```'
    assert await figure_turn.attach_figure(_state(ctx, reply)) == reply


def test_the_picture_joins_after_the_passes_that_strip_unverified_pictures() -> None:
    names = [finalize_pass.name for finalize_pass in FINALIZE_PASSES]
    assert names.index("figure") > names.index("math_fences")
    assert names.index("figure") > names.index("formula_charts")


@pytest.mark.wall_clock
async def test_a_read_still_running_at_finalize_waits_for_no_picture(figure: _Figure) -> None:
    async def slow() -> TurnDecision | None:
        await asyncio.sleep(5)
        return TurnDecision(live=False, think=False, subject="maths", picture="graph")

    read = asyncio.ensure_future(slow())
    ctx = _ctx(live_read=read)
    ctx.figure = figure_turn.start_figure(_settings(), ctx)
    started = asyncio.get_running_loop().time()
    assert await figure_turn.attach_figure(_state(ctx, "Done.")) == "Done."
    assert asyncio.get_running_loop().time() - started < 0.5
    read.cancel()


async def test_a_described_plot_keeps_the_figure_read_s_lettered_points(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ "Plot A(1, 2) and B(4, 8) and the line through them": the reply's checked plot draws
    the line, and the figure read's points graph keeps its letters beside it (2026-11-15
    review). A function graph of the figure read's still gives way to the plot."""
    import json

    from app.modules.chat.drawing_turn import ReplyDrawing
    from app.modules.math.drawing.build import drawn_fence
    from app.modules.math.figure.build import build_figure_fence

    line = "Plot A(1, 2) and B(4, 8) and the line through them."
    request = {
        "kind": "points",
        "points": [{"name": "A", "x": 1, "y": 2}, {"name": "B", "x": 4, "y": 8}],
    }
    points = build_figure_fence(json.dumps(request), [line])
    through = {"item": "line", "name": "L", "through": [["1", "2"], ["4", "8"]]}
    plot = drawn_fence(json.dumps({"kind": "plot", "items": [through]}), [line], "")
    assert points is not None and plot is not None and "A(1, 2)" in points
    stand_in = _Figure(points)
    monkeypatch.setattr(figure_turn, "_figure", lambda subject="math": stand_in)
    ctx = _ctx(line, live_read=_read(subject="maths", picture="graph"))
    ctx.drawing = ReplyDrawing("read", fences=[plot])
    ctx.figure = figure_turn.start_figure(_settings(), ctx)
    text = await figure_turn.attach_figure(_state(ctx, f"The slope is 2.\n\n{plot}\n"))
    assert plot in text and points in text


@pytest.mark.parametrize("picture", ["none", None])
async def test_a_maths_question_asking_for_no_picture_is_drawn_when_one_teaches(
    figure: _Figure, picture: str | None
) -> None:
    """The owner (2026-11-15): a student need not ask; a figure that helps teach is drawn."""
    line = "Find the area of a right triangle with legs 9 cm and 12 cm."
    ctx = _ctx(line, live_read=_read(subject="maths", picture=picture))
    ctx.figure = figure_turn.start_figure(_settings(), ctx)
    text = await figure_turn.attach_figure(_state(ctx, "**Answer**\n\n$54\\ cm^2$"))
    assert text.endswith(_FENCE + "\n")
    assert figure.modes == [False]


async def test_a_question_no_figure_helps_keeps_its_reply(figure: _Figure) -> None:
    figure.fence = None  # the teaching read said none: 15% of 80 has nothing to draw
    ctx = _ctx("What is 15% of 80?", live_read=_read(subject="maths", picture="none"))
    ctx.figure = figure_turn.start_figure(_settings(), ctx)
    assert await figure_turn.attach_figure(_state(ctx, "It is 12.")) == "It is 12."
    assert figure.modes == [False]


async def test_a_subject_turn_is_painted_or_photographed_only_when_its_read_asks() -> None:
    """The photo and painted-picture intercepts ask the read (``drawn_picture.read_lets_it``):
    a maths or physics turn gets a painting or a photo only when the read asks for exactly
    that; "Draw the velocity-time graph" read as physics' graph is the app's to draw (PR #2486
    review), and "show me an animation of this motion" is no photo search (Grade 8 round)."""
    from app.modules.chat.drawn_picture import read_lets_it

    def read(**fields: str) -> asyncio.Task[TurnDecision | None]:
        return cast("asyncio.Task[TurnDecision | None]", _read(**fields))

    assert not await read_lets_it(read(subject="maths", picture="diagram"), "image")
    assert not await read_lets_it(read(subject="physics", picture="graph"), "image")
    assert not await read_lets_it(read(subject="physics", picture="diagram"), "photo")
    assert await read_lets_it(read(subject="physics", picture="image"), "image")
    assert await read_lets_it(read(subject="chemistry", picture="photo"), "photo")
    assert await read_lets_it(read(subject="everyday", picture="photo"), "photo")
    assert await read_lets_it(read(subject="everyday", picture="none"), "photo")
    assert await read_lets_it(None, "photo")


async def test_a_chemistry_question_asking_for_nothing_gets_its_compound_s_structure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stand_in = _Figure("```smiles\nibuprofen\nCC(C)CC1=CC=C(C=C1)C(C)C(=O)O\n```")
    subjects: list[str] = []

    def chosen(subject: str = "math") -> _Figure:
        subjects.append(subject)
        return stand_in

    monkeypatch.setattr(figure_turn, "_figure", chosen)
    ctx = _ctx("What is ibuprofen?", live_read=_read(subject="chemistry", picture="none"))
    ctx.figure = figure_turn.start_figure(_settings(), ctx)
    text = await figure_turn.attach_figure(_state(ctx, "Ibuprofen is a painkiller."))
    assert text.startswith("Ibuprofen is a painkiller.") and "```smiles\nibuprofen" in text
    assert stand_in.modes == [False] and "chemistry" in subjects


async def test_a_chemistry_request_to_see_a_molecule_is_left_to_its_solve(
    figure: _Figure,
) -> None:
    ctx = _ctx("Draw caffeine.", live_read=_read(subject="chemistry", picture="molecule"))
    ctx.figure = figure_turn.start_figure(_settings(), ctx)
    assert await figure_turn.attach_figure(_state(ctx, "Here.")) == "Here."
    assert figure.modes == []


def _chemistry_solve(smiles: str = "") -> Any:
    """A chemistry solve; ``smiles`` set when it drew the compound."""
    return SimpleNamespace(subject="chemistry", result=SimpleNamespace(structure_smiles=smiles))


async def test_a_chemistry_solve_with_no_structure_still_gets_its_compound_s(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A molar-mass question is solved with no picture: its compound's structure is
    drawn, asked of chemistry's figure alone (maths' took any peer's block as a picture)."""
    stand_in = _Figure("```smiles\nglucose\nOCC1OC(O)C(O)C(O)C1O\n```")
    chemistry = figure_turn._figure("chemistry")
    assert chemistry is not None
    monkeypatch.setattr(chemistry, "draw", stand_in.draw)
    line = "What is the molar mass of glucose?"
    ctx = _ctx(line, live_read=_read(subject="chemistry", picture="none"))
    ctx.verified_subject = _chemistry_solve()
    ctx.figure = figure_turn.start_figure(_settings(), ctx)
    assert ctx.figure is not None
    text = await figure_turn.attach_figure(_state(ctx, "It is 180.16 g/mol."))
    assert "```smiles\nglucose" in text and stand_in.modes == [False]


@pytest.mark.parametrize(
    "verified",
    [_chemistry_solve("CN1C=NC2=C1C(=O)N(C(=O)N2C)C"), VerifiedPhysicsBlock(text="")],
    ids=["chemistry-drew-the-structure", "physics-scene"],
)
async def test_a_solve_that_draws_its_own_picture_reads_none(verified: Any) -> None:
    ctx = _ctx(live_read=_read(subject="chemistry", picture="none"), verified_subject=verified)
    assert figure_turn.start_figure(_settings(), ctx) is None


async def test_a_chemistry_solve_gets_no_maths_figure(figure: _Figure) -> None:
    ctx = _ctx(live_read=_read(subject="maths", picture="diagram"))
    ctx.verified_subject = _chemistry_solve()
    ctx.figure = figure_turn.start_figure(_settings(), ctx)
    assert await figure_turn.attach_figure(_state(ctx, "Here.")) == "Here."
    assert figure.modes == []


_BARE_RECTANGLE = (
    "```geometry\n"
    '{"type":"figure","shape":"rectangle","points":[{"name":"_0","x":0,"y":0},'
    '{"name":"_1","x":3,"y":0}],"segments":[{"a":"_0","b":"_1"}]}\n```'
)
_LABELLED_RECTANGLE = (
    "```geometry\n"
    '{"type":"figure","shape":"rectangle","points":[{"name":"A","x":0,"y":0},'
    '{"name":"B","x":8,"y":0}],"segments":[{"a":"A","b":"B","label":"8 cm"}]}\n```'
)
_BARE_CIRCLE = (
    "```geometry\n"
    '{"type":"figure","shape":"circle_parts","points":[{"name":"_0","x":0,"y":0}],'
    '"arcs":[{"center":"_0","rx":3,"ry":3}]}\n```'
)


def test_a_picture_shows_a_value_only_when_a_label_holds_a_number() -> None:
    """A reply's described picture with no value gives way to the figure with them (live,
    2026-11-21: a bare 3-by-2 rectangle stood over the 8 by 6 with its diagonals)."""
    assert not figure_turn._shows_a_value(_BARE_RECTANGLE)
    assert figure_turn._shows_a_value(_LABELLED_RECTANGLE)
    old = '```geometry\n{"type":"rectangle","labels":{"width":"6 cm"}}\n```'
    assert figure_turn._shows_a_value(old)


def test_a_picture_names_something_by_a_label_or_a_lettered_point() -> None:
    """An unasked picture that names nothing is left out (live, 2026-11-21: "What is the
    formula for the area of a circle?" got a bare circle)."""
    assert not figure_turn._names_anything(_BARE_CIRCLE)
    assert figure_turn._names_anything(_LABELLED_RECTANGLE)
    lettered = _BARE_CIRCLE.replace('"name":"_0"', '"name":"O","show":true')
    assert figure_turn._names_anything(lettered)
    # A triangle's vertices kept unlettered name nothing (a review, 2026-11-21).
    hidden = _BARE_CIRCLE.replace('"name":"_0"', '"name":"A"')
    assert not figure_turn._names_anything(hidden)
