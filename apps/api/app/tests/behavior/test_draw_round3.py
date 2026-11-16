"""Round 3's 3D and word-problem pictures, through the real turn routing and finalize step.

Grade 12 round 3 (2026-11-14) asked for 20 pictures of solids in space and word-problem
shapes and got 11 none, 4 wrong (a default triangle for stated vertices, a cone for a
frustum, a circle card for a sphere, a cone labelled from a rate) and a Mermaid flowchart
for two vectors. Each question here runs through the turn's routing offline, as the
battery does; its reply carries the ```draw description a reply would write, and the real
finalize passes draw it under the reply or leave it out. Nothing reaches the user as a
description, and no other picture of the question stands beside the drawn one.
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

_ROUND3 = json.loads(Path(__file__).with_name("draw_round3.json").read_text())


async def _finalized(entry: dict[str, Any]) -> str:
    case = Case(id=entry["id"], category="math", prompt=entry["prompt"], expect=Expect(), good="")
    route: Route = await route_case(case)
    ctx = route.context
    read: asyncio.Future[TurnDecision | None] = asyncio.get_event_loop().create_future()
    read.set_result(TurnDecision(live=False, think=False, subject="maths", picture="diagram"))
    ctx.live_read = read
    ctx.drawing = ReplyDrawing("read", descriptions=[entry["description"]])
    ctx.instant_reply = None
    reply = f"{entry['working']}\n\nThe working is above; the answer stands.\n\n```mermaid\ngraph LR\n  A --> B\n```"
    route.instant_text = reply.strip()
    return await saved_reply(route)


@pytest.mark.parametrize("entry", _ROUND3, ids=[entry["id"] for entry in _ROUND3])
async def test_round3_picture_is_drawn_or_left_out(entry: dict[str, Any]) -> None:
    final = await _finalized(entry)
    assert "```draw" not in final and '"kind"' not in final
    figures = [body for _s, _e, body in iter_closed_fences(final, "geometry")]
    if entry["expect"] == "drop":
        assert not figures
        return
    assert len(figures) == 1 and '"type":"figure"' in figures[0]
    # The flowchart that stood in for the picture goes with it (c082).
    assert "```mermaid" not in final
