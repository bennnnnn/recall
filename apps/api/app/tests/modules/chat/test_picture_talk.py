"""A reply's words about drawing the pictures the server drew beside it come off.

Two Pro replies (2026-11-27) said "The app has no scene for a block sliding down an incline
in this setup", "The app's picture of the Atwood setup appears with this reply" and "I can
draw the three graphs for the first 3 seconds if you want them as pictures" beside (once the
pictures were drawn) the very pictures they denied or offered.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

import pytest

from app.modules.chat.owed_picture import drawn_kinds, held_to_the_ask
from app.modules.chat.picture_talk import Kind, without_picture_talk
from app.modules.chat.prompt_leaks import drop_draw_block_mentions, drop_prompt_leaks
from app.modules.chat.turn_decision import TurnDecision
from app.modules.chat.turn_prep import StreamContext

_SCENE = '```simulation\n{"type":"incline"}\n```'
_GRAPH = '```graph\n{"type":"trajectory"}\n```'
_BOTH: frozenset[Kind] = frozenset({"graph", "diagram"})


@pytest.mark.parametrize(
    ("said", "kept"),
    [
        (
            "The app has no scene for a block sliding down an incline in this setup, so here "
            "is the picture in words. Draw the slope at 30°.",
            "Draw the slope at 30°.",
        ),
        (
            "The app's picture of the Atwood setup appears with this reply; the two force "
            "lists above label what each diagram shows.",
            "",
        ),
        ("I can draw the three graphs for the first 3 seconds if you want them as pictures.", ""),
        ("Want me to sketch the free-body diagram as well?", ""),
        ("I can't draw diagrams here, but the forces are listed above.", ""),
    ],
)
def test_words_about_drawing_the_pictures_drawn_come_off(said: str, kept: str) -> None:
    text = f"The block slides at 3.21 m/s².\n\n{said}\n\n{_SCENE}\n\n{_GRAPH}\n"
    out = without_picture_talk(text, _BOTH)
    assert said not in out and _SCENE in out and _GRAPH in out
    assert out.startswith("The block slides at 3.21 m/s².")
    if kept:
        assert kept in out


@pytest.mark.parametrize(
    "said",
    [
        # A plan the reply carries out, an offer of something no picture is, and an offer of
        # a kind of picture the reply does not show.
        "I'll show the working for each part below.",
        "If you want, I can also explain why friction acts up the slope.",
        "I can plot the energy graph too if you want.",
        "The graph shows a straight line from the origin.",
    ],
)
def test_other_words_stay(said: str) -> None:
    text = f"The block slides.\n\n{said}\n\n{_SCENE}\n"
    assert without_picture_talk(text, drawn_kinds(text)) == text


def test_a_reply_that_shows_no_picture_keeps_its_words() -> None:
    text = "The app has no scene for this setup, so here it is in words.\n"
    assert without_picture_talk(text, drawn_kinds(text)) == text


def _ctx(line: str, read: TurnDecision) -> StreamContext:
    ctx = StreamContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        model="smart-chat",
        prompt_messages=[],
        run_title=False,
        user_message_content=line,
        reserved_tokens=0,
        max_output_tokens=0,
    )
    future: asyncio.Future[TurnDecision | None] = asyncio.get_event_loop().create_future()
    future.set_result(read)
    ctx.live_read = future  # type: ignore[assignment]
    return ctx


def _read(**fields: Any) -> TurnDecision:
    return TurnDecision.model_validate({"live": False, "think": False, **fields})


async def test_the_owed_picture_pass_takes_them_off_only_beside_a_picture_asked() -> None:
    offer = "I can draw the graphs if you want them as pictures."
    asked = _ctx(
        "Draw its free-body diagram and its graphs.", _read(subject="physics", picture="diagram")
    )
    drawn = f"It slides.\n\n{offer}\n\n{_SCENE}\n"
    assert offer not in held_to_the_ask(drawn, asked, "en")
    # Nothing drawn: the words stay, and the line says the picture was not drawn.
    undrawn = held_to_the_ask(f"It slides.\n\n{offer}\n", asked, "en")
    assert offer in undrawn and "I couldn't draw this diagram." in undrawn
    # A picture nobody asked for: the reply is left as it is.
    unasked = _ctx("How fast does it slide?", _read(subject="physics", picture="none"))
    assert held_to_the_ask(drawn, unasked, "en") == drawn


def test_the_leak_net_and_the_picture_talk_net_each_cut_only_their_own() -> None:
    """A reply that narrates the turn, names the ```draw block and talks about the app's
    pictures: the leak net (``prompt_leaks``, an earlier finalize pass) takes its sentences,
    this net takes the picture talk, and the answer itself stays whole, in either order."""
    line = "Draw its free-body diagram and plot its v-t graph for 4 s."
    narration = (
        "The user asks for a free-body diagram and a graph, so I give the forces first, "
        "and the user prefers short replies, so I keep it short."
    )
    block = "Here is the `draw` block describing this scenario."
    talk = "The app has no scene for this setup, so here is the picture in words."
    offer = "I can draw the graph as a picture if you want."
    answer = "The block slides at 2.81 m/s², so at 4 s it moves at 11.2 m/s."
    reply = f"{narration}\n\n{answer} {block}\n\n{talk} Friction acts up the slope.\n\n{offer}"
    drawn = f"{reply}\n\n{_SCENE}\n\n{_GRAPH}\n"

    def leaks(text: str) -> str:
        return drop_draw_block_mentions(drop_prompt_leaks(text, line, rules=frozenset()), line)

    for out in (
        without_picture_talk(leaks(drawn), _BOTH),
        leaks(without_picture_talk(drawn, _BOTH)),
    ):
        for gone in (narration, block, talk, offer):
            assert gone not in out
        assert answer in out and "Friction acts up the slope." in out
        assert out.count(_SCENE) == 1 and out.count(_GRAPH) == 1


_GRAPHS_ONLY: frozenset[Kind] = frozenset({"graph"})
_DIAGRAM_ONLY: frozenset[Kind] = frozenset({"diagram"})
_NOT_DRAWN = "I can't draw the v–t graph here, but v rises from 0 to 16 m/s over 5 s."


@pytest.mark.parametrize(
    ("said", "drawn", "after"),
    [
        # Only the free-body diagram was drawn: the graph sentence is true and its values stay.
        (_NOT_DRAWN, _DIAGRAM_ONLY, _NOT_DRAWN),
        # The graph was drawn: the refusal goes, what it goes on to say stays.
        (_NOT_DRAWN, _GRAPHS_ONLY, "V rises from 0 to 16 m/s over 5 s."),
        # Curly apostrophes, as models write them.
        ("I can’t draw diagrams here.", _DIAGRAM_ONLY, ""),
        ("I’ll plot the graphs if you want.", _GRAPHS_ONLY, ""),
        # The app a graph is about is no app speaking of its pictures.
        (
            "The graph shows the app reaches 6,000 users.",
            _GRAPHS_ONLY,
            "The graph shows the app reaches 6,000 users.",
        ),
    ],
)
def test_only_words_about_a_kind_drawn_go(said: str, drawn: frozenset[Kind], after: str) -> None:
    text = f"Para A.\n\n{said}\n\n{_SCENE}\n"
    out = without_picture_talk(text, drawn)
    expected = f"Para A.\n\n{after}\n\n{_SCENE}\n" if after else f"Para A.\n\n{_SCENE}\n"
    assert out == expected


def test_a_worked_block_is_no_diagram() -> None:
    worked = "```worked\nGiven: m = 2 kg\n```"
    assert drawn_kinds(f"{worked}\n\n{_GRAPH}\n") == {"graph"}
    text = f"{worked}\n\nWould you like me to draw a free-body diagram too?\n\n{_GRAPH}\n"
    assert without_picture_talk(text, drawn_kinds(text)) == text


def test_a_paragraph_s_first_line_cut_keeps_the_paragraph_apart() -> None:
    text = f"Para A.\n\nI cannot draw diagrams here.\nThe forces are W and N.\n\n{_SCENE}\n"
    out = without_picture_talk(text, _DIAGRAM_ONLY)
    assert out == f"Para A.\n\nThe forces are W and N.\n\n{_SCENE}\n"
