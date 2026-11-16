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

_FENCE = '```geometry\n{"type":"figure","shape":"cube","points":[{"name":"a","x":0,"y":0},{"name":"b","x":1,"y":0}],"segments":[{"a":"a","b":"b"}]}\n```'
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


async def test_an_unasked_figure_never_counts_as_a_request_to_draw() -> None:
    """The photo and painted-picture intercepts ask only whether the message asks."""
    unasked = cast("asyncio.Task[TurnDecision | None]", _read(subject="maths", picture="none"))
    asked = cast("asyncio.Task[TurnDecision | None]", _read(subject="maths", picture="diagram"))
    assert not await figure_turn.read_asks_for_a_figure(unasked)
    assert await figure_turn.read_asks_for_a_figure(asked)


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
