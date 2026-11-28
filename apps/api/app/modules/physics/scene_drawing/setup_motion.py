"""The graphs of a scene's own motion against time, drawn by the server from its own solve.

"Generate three graphs over the first 5 seconds: displacement, velocity and acceleration
against time" of a block sliding down a 30° slope with μk 0.20, and "s-t, v-t and a-t graphs
for both masses over 3 s" of an Atwood machine, drew nothing (live, 2026-11-27): a motion a
reply describes in stages takes only speeds the question states, and here every speed is an
answer. Such a motion is the scene's: a body released from rest under one constant
acceleration. The read names the scene and the span asked:

    {"kind": "motion", "of": "incline", "graphs": ["displacement", "velocity",
    "acceleration"], "time": "5 s"}

The server reads the setup itself (``setup.setup_readings``, the question or the statement
before its parts), works the acceleration out with that scene's solver, and draws each graph
from rest: s = ½at², v = at and a, sampled over the span. The span must be a time the
question states and the words must start the body from rest. A block that does not slide (its
friction holds it) or slides up, a reading of another situation, or a span the question does
not give draws nothing. An Atwood machine's two masses get a graph each, upward positive, each
titled with its mass.
"""

from __future__ import annotations

import json
import logging
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.modules.math.schemas import GraphBlockSpec
from app.modules.physics.display import GIVEN_FIGURES, plain_number
from app.modules.physics.graph_labels import SPOKEN, SYMBOLS, TIME, axis_label, graph_title
from app.modules.physics.scene_drawing.setup import setup_readings
from app.modules.physics.scene_drawing.values import Stated, starts_from_rest
from app.modules.physics.schemas import PhysicsIntent
from app.modules.physics.solver import solve_physics
from app.modules.physics.solvers.si import to_si
from app.services.question_parts import statement_before_parts

logger = logging.getLogger(__name__)

Graph = Literal["displacement", "distance", "velocity", "speed", "acceleration"]
Scene = Literal["incline", "atwood"]
# The readings of each scene's setup (``kinds.SCENES``'s), whose solve gives the acceleration.
_READS: dict[Scene, str] = {"incline": "incline_acceleration", "atwood": "atwood"}
_ASKS_ACCELERATION = "Find the acceleration."
_SAMPLES = 24
# The graphs of where the body is (the rest are of how fast it goes, or speeds up).
_PATHS = frozenset({"displacement", "distance"})
# A span past an hour is no school motion from rest (and no sane picture of one).
_MAX_SECONDS = 3600.0
_UNITS: dict[Graph, str] = {
    "displacement": "m",
    "distance": "m",
    "velocity": "m/s",
    "speed": "m/s",
    "acceleration": "m/s²",
}


class _SetupMotion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["motion"]
    of: Scene
    graphs: list[Graph] = Field(min_length=1, max_length=3)
    time: str = Field(max_length=30)


@dataclass(frozen=True)
class _Body:
    """One body's motion: its acceleration along the axis drawn (signed), and its title."""

    accel: float
    name: str | None


def described_setup_motion(body: str, texts: Sequence[str]) -> list[GraphBlockSpec]:
    """The graphs one block describes of its scene's motion from rest; none when it does not
    check against ``texts`` (the problem first)."""
    try:
        data = json.loads(body)
    except ValueError:
        return []
    if not isinstance(data, dict) or data.get("kind") != "motion" or "of" not in data:
        return []
    try:
        motion = _SetupMotion.model_validate(data)
    except ValidationError as exc:
        logger.info("described setup motion not read: %s", exc.errors()[0].get("loc"))
        return []
    question = texts[0] if texts else ""
    span = _span(motion.time, question)
    if span is None or not starts_from_rest(question):
        logger.info("described setup motion not drawn: no span, or not from rest")
        return []
    bodies = _bodies(motion.of, question)
    if not bodies:
        logger.info("described setup motion not drawn: no %s reading", motion.of)
        return []
    graphs = list(dict.fromkeys(motion.graphs))
    return [_graph(kind, one, span) for kind in graphs for one in bodies]


def _span(written: str, question: str) -> float | None:
    """The span in seconds, when it is a time the question states."""
    stated = Stated.of(question).equal_to(written, "s")
    if not stated or stated[0].si is None:
        return None
    seconds = stated[0].si
    return seconds if 0 < seconds <= _MAX_SECONDS else None


def _bodies(scene: Scene, question: str) -> list[_Body]:
    """Each moving body's acceleration, from the reader's reading of the setup and the scene's
    own solver; none when no reading of that setup holds."""
    setup = statement_before_parts(question)
    stated = [question, setup] if setup else [question]
    # The setup's acceleration, asked of the readers as its solve would be: a question that
    # asks only for its pictures ("Draw its free-body diagram and plot its v-t graph") asks
    # them nothing they read.
    texts = [*stated, *(f"{text.rstrip()} {_ASKS_ACCELERATION}" for text in stated)]
    reading = next(
        (r for text in texts for r in setup_readings(text) if r.physics_op == _READS[scene]),
        None,
    )
    if reading is None:
        return []
    accel = _acceleration(reading)
    if accel is None or accel <= 0:
        return []  # a block its friction holds, or two equal masses: no motion to draw
    params = reading.physics_params or {}
    if scene == "incline":
        # Down the slope, the way it slides; a block sliding up it slows (another motion).
        return [] if params.get("motion_sign", 1.0) != 1.0 else [_Body(accel, None)]
    units = reading.physics_units or {}
    masses = sorted(
        ((params[p], units.get(p) or "kg") for p in ("m1", "m2") if p in params),
        key=lambda mass: to_si(mass[0], mass[1], expected_key="m1"),
        reverse=True,
    )
    if len(masses) != 2:
        return []
    # Upward positive: the heavier mass falls, the lighter one rises.
    return [
        _Body(sign * accel, f"{plain_number(value, GIVEN_FIGURES)} {unit}")
        for sign, (value, unit) in zip((-1.0, 1.0), masses, strict=True)
    ]


def _acceleration(reading: PhysicsIntent) -> float | None:
    """The acceleration the scene's solver works out, in m/s²."""
    try:
        result = solve_physics(reading)
    except Exception as exc:  # A setup the solver refuses has no motion to draw.
        logger.info("setup motion not solved (%s)", type(exc).__name__)
        return None
    accel = next((q.value for q in result.quantities if q.unit == "m/s^2"), None)
    return accel if accel is not None and math.isfinite(accel) else None


def _graph(kind: Graph, body: _Body, span: float) -> GraphBlockSpec:
    points: list[list[float]] = []
    for step in range(_SAMPLES + 1):
        t = span * step / _SAMPLES
        value = {
            "displacement": 0.5 * body.accel * t**2,
            "distance": 0.5 * abs(body.accel) * t**2,
            "velocity": body.accel * t,
            "speed": abs(body.accel) * t,
            "acceleration": body.accel,
        }[kind]
        points.append([round(t, 6), round(value, 6) + 0.0])
    symbol = SYMBOLS[kind]
    title = graph_title(symbol)
    return GraphBlockSpec(
        type="trajectory",
        expr=f"{symbol}(t)",
        variable="t",
        x_min=0.0,
        x_max=round(span, 6),
        points=points,
        title=f"{title} ({body.name})" if body.name else title,
        x_label=axis_label(TIME, "s"),
        y_label=axis_label(symbol, _UNITS[kind]),
        quantity=SPOKEN[kind],
        trajectory_type="position_vs_time" if kind in _PATHS else "velocity_vs_time",
    )
