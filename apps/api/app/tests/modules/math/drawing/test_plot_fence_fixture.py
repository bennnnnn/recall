"""The plot fences the phone is tested on are the ones the server draws.

`docs/fixtures/plot_fences.json` holds a few questions, a ```draw description for each and
the ```graph ``plot`` body the server draws from it: a function in pieces with its open and
filled circles (round 3's c008), a curve with its asymptotes (c029), and a washer's region,
axis and slice. The phone renders these bodies (`lib/__tests__/plotGraph.test.ts`,
`components/__tests__/PlotGraphCard.test.tsx`); this test holds each to what the server
draws now. After a change meant to alter a plot, `UPDATE_PLOT_FIXTURE=1` rewrites it.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from app.modules.math.drawing.build import drawn_fence

FIXTURE = Path(__file__).resolve().parents[7] / "docs" / "fixtures" / "plot_fences.json"
_CASES: list[dict[str, Any]] = json.loads(FIXTURE.read_text())["cases"]


def _drawn(case: dict[str, Any]) -> dict[str, Any]:
    fence = drawn_fence(json.dumps(case["description"]), [case["question"]], case["reply"])
    assert fence is not None
    body: dict[str, Any] = json.loads(fence.split("\n", 1)[1].rsplit("\n```", 1)[0])
    return body


def test_the_fixture_is_what_the_server_draws() -> None:
    drawn = [_drawn(case) for case in _CASES]
    if os.environ.get("UPDATE_PLOT_FIXTURE"):
        data = json.loads(FIXTURE.read_text())
        for case, body in zip(data["cases"], drawn, strict=True):
            case["body"] = body
        FIXTURE.write_text(json.dumps(data, ensure_ascii=False) + "\n")
        pytest.skip("fixture rewritten")
    for case, body in zip(_CASES, drawn, strict=True):
        assert body == case["body"], case["id"]
