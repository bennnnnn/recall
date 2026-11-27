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

from app.modules.chat.owed_picture import held_to_the_ask
from app.modules.chat.picture_talk import without_picture_talk
from app.modules.chat.turn_decision import TurnDecision
from app.modules.chat.turn_prep import StreamContext

_SCENE = '```simulation\n{"type":"incline"}\n```'
_GRAPH = '```graph\n{"type":"trajectory"}\n```'


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
    out = without_picture_talk(text)
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
    assert without_picture_talk(text) == text


def test_a_reply_that_shows_no_picture_keeps_its_words() -> None:
    text = "The app has no scene for this setup, so here it is in words.\n"
    assert without_picture_talk(text) == text


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
