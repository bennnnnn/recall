"""A chain of transformations is drawn whole or not at all: a picture draws two at most, so
a third step is refused, never cut off (an image after the second step left out is the
wrong final image)."""

from __future__ import annotations

import json
from typing import Any

from app.modules.math.figure.build import build_figure_fence, figure_fence
from app.modules.math.figure.request import TRANSFORMS_READ, FigureRequest
from app.modules.math.schemas.figure import PointsGraphSpec

TWO = (
    "The point A(2, 3) is reflected in the x-axis and then rotated 90° anticlockwise about "
    "the origin. Find the final image."
)
THREE = (
    "The point A(2, 3) is reflected in the x-axis, then rotated 90° anticlockwise about the "
    "origin, then translated by (1, 2). Find the final image."
)
_REFLECT = {"kind": "reflection", "mirror": "x-axis"}
_ROTATE = {"kind": "rotation", "angle": 90, "direction": "anticlockwise"}
_TRANSLATE = {"kind": "translation", "vector": {"x": 1, "y": 2}}


def _reading(*steps: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "points", "points": [{"name": "A", "x": 2, "y": 3}], "transforms": list(steps)}


def _images(fence: str) -> set[tuple[float, float]]:
    body = fence.removeprefix("```graph\n").rsplit("\n```", 1)[0]
    graph = PointsGraphSpec.model_validate(json.loads(body))
    return {(p.x, p.y) for p in graph.points if p.role == "image"}


def test_transform_chains_two_steps_draw_both_images() -> None:
    fence = figure_fence(FigureRequest.model_validate(_reading(_REFLECT, _ROTATE)), [TWO])
    assert fence is not None
    assert _images(fence) == {(2.0, -3.0), (3.0, 2.0)}


def test_transform_chains_a_third_step_read_is_kept_not_cut_to_two() -> None:
    request = FigureRequest.model_validate(_reading(_REFLECT, _ROTATE, _TRANSLATE))
    assert len(request.transforms) == 3


def test_transform_chains_three_steps_read_draw_nothing() -> None:
    reading = json.dumps(_reading(_REFLECT, _ROTATE, _TRANSLATE))
    assert build_figure_fence(reading, [THREE]) is None


def test_transform_chains_three_steps_written_with_two_read_draw_nothing() -> None:
    reading = json.dumps(_reading(_REFLECT, _ROTATE))
    assert build_figure_fence(reading, [THREE]) is None


def test_transform_chains_a_longer_list_than_kept_still_refuses() -> None:
    steps = [_TRANSLATE] * (TRANSFORMS_READ + 3)
    request = FigureRequest.model_validate(_reading(*steps))
    assert len(request.transforms) == TRANSFORMS_READ
    assert build_figure_fence(request.model_dump_json(), [THREE]) is None
