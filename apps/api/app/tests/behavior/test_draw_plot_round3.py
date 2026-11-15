"""Round 3's graphs, through the real turn routing and finalize step.

Grade 12 round 3 (2026-11-14) asked for 37 graphs and got 18 none and several wrong: a
curve joined across its asymptote, a cusp lost to x^(1/3) of a negative, a window cutting
an intercept, no tangent, no shading, no rectangles. Each question here runs through the
turn's routing offline, as the battery does; its reply carries the ```draw description of
kind "plot" a reply would write, and the real finalize passes draw it under the reply as
one ```graph ``plot``. Nothing reaches the user as a description, and no other graph of the
question stands beside the drawn one.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from app.modules.chat.drawing_turn import ReplyDrawing
from app.modules.chat.turn_decision import TurnDecision
from app.services.md_fence_scan import iter_closed_fences
from app.tests.behavior.cases import Case, Expect
from app.tests.behavior.harness import Route, route_case, saved_reply

_ROUND3 = json.loads(Path(__file__).with_name("draw_plot_round3.json").read_text())
# A graph the model wrote itself, which the drawn plot stands in for.
_OWN_GRAPH = '```graph\n{"type":"function","expr":"x^2","points":[[0,0],[1,1]]}\n```'


async def _finalized(entry: dict[str, Any]) -> str:
    case = Case(id=entry["id"], category="math", prompt=entry["prompt"], expect=Expect(), good="")
    route: Route = await route_case(case)
    ctx = route.context
    read: asyncio.Future[TurnDecision | None] = asyncio.get_event_loop().create_future()
    read.set_result(TurnDecision(live=False, think=False, subject="maths", picture="graph"))
    ctx.live_read = read
    ctx.drawing = ReplyDrawing("read", descriptions=[entry["description"]])
    ctx.instant_reply = None
    route.instant_text = f"The working is above; the answer stands.\n\n{_OWN_GRAPH}"
    return await saved_reply(route)


@pytest.mark.parametrize("entry", _ROUND3, ids=[entry["id"] for entry in _ROUND3])
async def test_round3_graph_is_drawn(entry: dict[str, Any]) -> None:
    final = await _finalized(entry)
    assert "```draw" not in final and '"items"' not in final
    graphs = [body for _s, _e, body in iter_closed_fences(final, "graph")]
    assert len(graphs) == 1 and json.loads(graphs[0])["type"] == "plot"
