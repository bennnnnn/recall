"""A part's picture after that part's answer card, through the real finalize passes.

The drawing pass places each part's picture before working_check lands the parts' cards, so
the picture sat at the end of its part, after any sentence or closing summary there (Gemini
review, #2521). Once the cards land, each picture follows its own part's card.
"""

from __future__ import annotations

import json

import pytest

from app.modules.chat.drawing_turn import ReplyDrawing
from app.modules.chat.finalize_passes import run_finalize_passes
from app.services.md_fence_scan import iter_fences
from app.tests.modules.chat.test_drawing_turn import _ctx, _read, _state

_QUESTION = (
    "a) Sketch y = x^2 - 4x + 3 and find its roots.\n"
    "b) Find its y-intercept and sketch the line y = 2x + 1."
)


def _draw(part: str, curve: str) -> str:
    body = {"kind": "plot", "part": part, "items": [{"item": "curve", "name": "f", "y": curve}]}
    return f"```draw\n{json.dumps(body)}\n```"


_DRAWS = f"\n\n{_draw('a', 'x^2 - 4x + 3')}\n\n{_draw('b', '2x + 1')}\n"
_ROOTS = "**(a) Roots**\n\nFactor: $(x - 1)(x - 3) = 0$\n\n**Answer (a)**\n\n$x = 1, 3$\n\n"
_INTERCEPT = "**(b) Intercept**\n\nAt $x = 0$, $y = 1$.\n\n**Answer (b)**\n\n$(0, 1)$"


@pytest.mark.parametrize(
    "reply",
    [
        f"{_ROOTS}{_INTERCEPT}",
        # A sentence under (a)'s answer, and a closing summary after (b)'s.
        f"{_ROOTS}These are where the curve meets the x-axis.\n\n{_INTERCEPT}\n\n"
        "Both graphs are shown with their parts.",
        f"{_ROOTS}---\n\n{_INTERCEPT}\n\nThe roots are 1 and 3; the line meets the y-axis at 1.",
    ],
)
async def test_each_part_s_picture_follows_its_answer_card_after_every_pass(reply: str) -> None:
    ctx = _ctx(_QUESTION, live_read=_read(subject="maths", picture="graph"))
    ctx.drawing = ReplyDrawing("read")
    ctx.solver_unverified = True
    state = _state(ctx, reply + _DRAWS)
    assert await run_finalize_passes(state) is True
    out = state.text
    fences = list(iter_fences(out))
    cards = [fence for fence in fences if fence.lang == "answer"]
    graphs = [fence for fence in fences if fence.lang == "graph"]
    assert len(cards) == 2 and len(graphs) == 2
    assert len({out[g.start : g.end] for g in graphs}) == 2
    assert "x = 1, 3" in out[cards[0].start : cards[0].end]
    assert "(0, 1)" in out[cards[1].start : cards[1].end]
    for card, graph in zip(cards, graphs, strict=True):
        # Card first, then its picture, with nothing between them.
        assert not out[card.end : graph.start].strip()
    assert "4x" in out[graphs[0].start : graphs[0].end].replace("*", "")
    assert "2x" in out[graphs[1].start : graphs[1].end].replace("*", "")
