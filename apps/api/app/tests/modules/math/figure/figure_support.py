"""Drawing a reading through the whole figure path (grounding, builder, honesty check) and
reading the picture back: its points, its labels, its lengths and angles."""

from __future__ import annotations

import json
from typing import Any

from app.modules.math.figure.build import figure_fence
from app.modules.math.figure.drawing import angle_at, distance
from app.modules.math.figure.request import FigureRequest
from app.modules.math.schemas.figure import FigureSpec


def draw(question: str, reading: dict[str, Any]) -> FigureSpec | None:
    """The figure drawn for ``question`` from ``reading``, or None when nothing is drawn."""
    fence = figure_fence(FigureRequest.model_validate(reading), [question])
    if fence is None:
        return None
    lang, _, rest = fence.removeprefix("```").partition("\n")
    assert lang == "geometry"
    return FigureSpec.model_validate(json.loads(rest.rsplit("\n```", 1)[0]))


def figure(question: str, reading: dict[str, Any]) -> FigureSpec:
    spec = draw(question, reading)
    assert spec is not None
    return spec


def labels(spec: FigureSpec) -> list[str]:
    return sorted(
        [s.label for s in spec.segments if s.label] + [a.label for a in spec.angles if a.label]
    )


def at(spec: FigureSpec, name: str) -> tuple[float, float]:
    point = next(p for p in spec.points if p.name == name)
    return (point.x, point.y)


def labelled_length(spec: FigureSpec, label: str) -> float:
    segment = next(s for s in spec.segments if s.label == label)
    return distance(at(spec, segment.a), at(spec, segment.b))


def labelled_angle(spec: FigureSpec, label: str) -> float:
    mark = next(a for a in spec.angles if a.label == label)
    return angle_at(at(spec, mark.at), at(spec, mark.a), at(spec, mark.b))


def length(spec: FigureSpec, a: str, b: str) -> float:
    return distance(at(spec, a), at(spec, b))


def angle(spec: FigureSpec, vertex: str, a: str, b: str) -> float:
    return angle_at(at(spec, vertex), at(spec, a), at(spec, b))
