"""The figures the phone's label test lays out are the ones the server builds.

``docs/fixtures/server_figures.json`` holds the geometry corpus's figures, each built from
a saved figure read (the model's reading, kept so no model is called here). The phone lays
every one out at three card widths and holds each label clear of every line, mark, arc and
other label (``apps/mobile/lib/__tests__/geometryFigureLabels.test.ts``): text is never
written over the drawing. Here each figure is built again from its reading and must match,
so a builder change reaches the phone's test (``UPDATE_SERVER_FIGURES=1`` rewrites them).

    UPDATE_SERVER_FIGURES=1 uv run pytest app/tests/modules/math/test_server_figures_fixture.py
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import pytest

from app.modules.math.figure.build import build_figure_fence

FIXTURE = Path(__file__).resolve().parents[6] / "docs" / "fixtures" / "server_figures.json"
_FENCE = re.compile(r"^```\w*\n|\n```$")


def _cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
    return cases


def _built(case: dict[str, Any]) -> dict[str, Any] | None:
    fence = build_figure_fence(json.dumps(case["reading"]), [case["prompt"]])
    if fence is None:
        return None
    figure: dict[str, Any] = json.loads(_FENCE.sub("", fence.strip()))
    return figure


def test_server_figures_fixture_is_current() -> None:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if os.environ.get("UPDATE_SERVER_FIGURES"):
        data["cases"] = [{**case, "figure": _built(case)} for case in data["cases"]]
        FIXTURE.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    assert len(data["cases"]) >= 100


@pytest.mark.parametrize("case", _cases(), ids=lambda case: case["id"])
def test_server_figures_fixture_matches_the_builder(case: dict[str, Any]) -> None:
    assert _built(case) == case["figure"]
