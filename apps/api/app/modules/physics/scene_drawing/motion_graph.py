"""A motion graph a reply describes in stages, checked against the question and drawn by the
server: speed, velocity, acceleration or distance against time.

"Draw (plot) the v against t graph" of a bicycle ride in four stages came back as an error,
then as a sentence claiming a graph (Grade 8 round, t15 and r01), and "Draw i) speed against
time ii) acceleration against time" as words (t16): no solver reads a story in stages, and
the maths plot draws only a formula the question writes. The reply names the stages, never a
coordinate:

{"kind": "motion", "graphs": ["speed", "acceleration"], "stages": [{"speed": "6 km/h",
"time": "5 min"}, {"from": "60 km/h", "to": "-80 m/s", "time": "20 s"}]}

Each value must be one the question states, with its unit; a speed of 0 only when the
question says the body is at rest or stops; a minus sign (the other way) only when it names
two opposite directions. Every stage needs its time. The server works out every point and
every acceleration, in the question's own units for time and speed (m/s² for acceleration,
m for distance). A description that does not check draws nothing.
"""

from __future__ import annotations

import json
import logging
import math
import re
from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.modules.math.schemas import GraphBlockSpec
from app.modules.physics.givens import PHYSICS_UNITS
from app.modules.physics.numbers import normalize_physics_units
from app.modules.physics.scene_drawing.values import Stated
from app.services.law_binding.fit import read_givens
from app.services.law_binding.givens import Given

logger = logging.getLogger(__name__)

Graph = Literal["speed", "velocity", "acceleration", "distance"]
_MAX_TEXTS = 4
_SAMPLES = 24
_LETTERS: dict[str, str] = {"speed": "v", "velocity": "v", "acceleration": "a", "distance": "d"}
# Words that put a body at rest ("from rest", "stopped to talk"), never "the rest of".
_AT_REST = re.compile(
    r"\b(?:from|at)\s+rest\b|\b(?:stops?|stopped|stopping|stationary|parked|halts?|halted)\b",
    re.IGNORECASE,
)
_OPPOSITE = (("north", "south"), ("east", "west"), ("left", "right"), ("up", "down"))
_KM_PER_HOUR = re.compile(r"(?<=\d)(\s*)km\s*/\s*hrs?\b", re.IGNORECASE)
_REVERSES = re.compile(r"\bopposite\s+direction|\brevers|\bturns?\s+(?:back|around)\b", re.I)


class _Stage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    speed: str | None = None
    start: str | None = Field(default=None, alias="from")
    end: str | None = Field(default=None, alias="to")
    time: str


class _Motion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["motion"]
    graphs: list[Graph] = Field(min_length=1, max_length=2)
    stages: list[_Stage] = Field(min_length=1, max_length=8)


def described_motion(body: str, texts: Sequence[str]) -> list[GraphBlockSpec]:
    """The graphs one ```draw block describes, of the first of ``texts`` it checks against."""
    try:
        data = json.loads(body)
    except ValueError:
        return []
    if not isinstance(data, dict) or data.get("kind") != "motion":
        return []
    try:
        motion = _Motion.model_validate(data)
    except ValidationError as exc:
        logger.info("described motion not read: %s", exc.errors()[0].get("loc"))
        return []
    for text in [t for t in texts if t and t.strip()][:_MAX_TEXTS]:
        stages = _checked(motion, text)
        if stages is not None:
            return [_graph(kind, stages) for kind in dict.fromkeys(motion.graphs)]
    logger.info("described motion not drawn: no text it checks against")
    return []


# A stage as the server draws it: start and end velocity (m/s), duration (s).
_Checked = tuple[list[tuple[float, float, float]], tuple[float, str], tuple[float, str]]


def _units(text: str) -> str:
    """ "3minutes": the units as the physics readers write them; "60 km/hr" too, which
    ``normalize_physics_units`` leaves as it is."""
    return _KM_PER_HOUR.sub(r"\1km/h", normalize_physics_units(text))


class _Reading:
    """The question's stated quantities, read in order: each stage's values are taken after
    the stage before's, so a value stated for one stage is never another's ("5 min" on the
    flat road is not the last stretch's)."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.left = sorted(Stated.of(_units(text)).left, key=lambda given: given.start)
        self.after = -1
        self.reached = -1

    def take(self, written: str, sample: str) -> Given | None:
        read = list(read_givens(_units(written), PHYSICS_UNITS))
        kind = read_givens(f"1 {sample}", PHYSICS_UNITS)
        if len(read) != 1 or not kind or read[0].dimension != kind[0].dimension:
            return None
        # The next value of its kind the question states: one passed over is a stage left
        # out, and a graph that skips one is wrong from there on.
        one = next(
            (g for g in self.left if g.start > self.after and g.dimension == read[0].dimension),
            None,
        )
        if one is None or not _close(one, read[0]):
            return None
        self.left.remove(one)
        self.reached = max(self.reached, one.start)
        return one

    def next_stage(self) -> None:
        self.after = self.reached

    def states_more(self, sample: str) -> bool:
        """The question states another value of ``sample``'s kind after this stage's."""
        kind = read_givens(f"1 {sample}", PHYSICS_UNITS)
        return bool(kind) and any(
            g.start > self.after and g.dimension == kind[0].dimension for g in self.left
        )


def _checked(motion: _Motion, text: str) -> _Checked | None:
    """Each stage's velocities and duration in SI, and the units the axes take; None when a
    stage is not the question's. Only the last stage may be left out, and only when the
    question states no time for it (a last stretch with none, t15): one in the middle would
    shift every stage after it, and a last one the question times is part of the motion."""
    reading = _Reading(text)
    stages: list[tuple[float, float, float]] = []
    speeds: list[Given] = []
    times: list[Given] = []
    for index, stage in enumerate(motion.stages):
        # Read before the stage takes its values: a stage that fails may take its time.
        timed = reading.states_more("s")
        checked = _stage(stage, reading, stages[-1][1] if stages else None)
        if checked is None and index == len(motion.stages) - 1 and stages and not timed:
            break
        if checked is None:
            return None
        velocities, duration = checked
        speeds += [given for _v, given in velocities if given is not None]
        times.append(duration)
        stages.append((velocities[0][0], velocities[1][0], duration.si or duration.value))
        reading.next_stage()
    if not stages or not speeds:
        return None
    return stages, _one_unit(speeds, "m/s"), _one_unit(times, "s")


_Velocity = tuple[float, Given | None]


def _stage(
    stage: _Stage, reading: _Reading, carried: float | None
) -> tuple[list[_Velocity], Given] | None:
    """One stage's two velocities and its time. Its first velocity may be the one the stage
    before ended on, stated once ("to 20 m/s in 5 s, then brakes from it to rest in 4 s")."""
    ends = (stage.speed, stage.speed) if stage.speed is not None else (stage.start, stage.end)
    if None in ends or (stage.speed is not None and stage.start is not None):
        return None
    first = _velocity(str(ends[0]), reading) or _carried_over(str(ends[0]), carried)
    # A steady speed is one value, taken once.
    second = first if stage.speed is not None else _velocity(str(ends[1]), reading)
    duration = reading.take(stage.time, "s")
    if first is None or second is None or duration is None or (duration.si or 0) <= 0:
        return None
    return [first, second], duration


def _close(one: Given, other: Given) -> bool:
    a = one.si if one.si is not None else one.value
    b = other.si if other.si is not None else other.value
    return math.isclose(abs(a), abs(b), rel_tol=1e-9)


def _velocity(written: str, reading: _Reading) -> _Velocity | None:
    """A velocity in m/s, and the stated speed it is (None for a rest the words say)."""
    cleaned = written.strip().replace("\u2212", "-")
    # "0" or "0 km/h", never "0.5m/s".
    if re.fullmatch(r"-?0+(?:\.0+)?(?:\s+\S+)?", cleaned):
        return (0.0, None) if _AT_REST.search(reading.text) else None
    backward = cleaned.startswith("-")
    if backward and not _two_ways(reading.text):
        return None
    given = reading.take(cleaned.lstrip("-").strip(), "m/s")
    if given is None or given.si is None:
        return None
    return (-given.si if backward else given.si), given


def _carried_over(written: str, carried: float | None) -> _Velocity | None:
    """The velocity the stage before ended on, when ``written`` is it (in any unit)."""
    if carried is None:
        return None
    cleaned = written.strip().replace("\u2212", "-")
    read = read_givens(_units(cleaned.lstrip("-").strip()), PHYSICS_UNITS)
    if len(read) != 1 or read[0].si is None:
        return None
    velocity = -read[0].si if cleaned.startswith("-") else read[0].si
    return (carried, None) if math.isclose(velocity, carried, rel_tol=1e-9) else None


def _two_ways(text: str) -> bool:
    words = {w.lower() for w in re.findall(r"[a-z]+", text, re.I)}
    return _REVERSES.search(text) is not None or any(
        a in words and b in words for a, b in _OPPOSITE
    )


def _one_unit(values: list[Given], si: str) -> tuple[float, str]:
    """SI units per unit the axis is drawn in, and its name: the question's own unit when
    every value of the kind is stated in it ("6 km/h", "2 km/h"; "5 min" and "3 minutes"),
    else the SI unit ("60 km/h" beside "80 m/s" draws m/s, the unit the working takes)."""
    scales = [v.si / v.value for v in values if v.si is not None and v.value]
    if len(scales) == len(values) and all(math.isclose(x, scales[0]) for x in scales):
        return scales[0], values[0].unit
    return 1.0, si


def _graph(kind: Graph, checked: _Checked) -> GraphBlockSpec:
    stages, speed, time = checked
    t_scale, t_unit = time
    v_scale, v_unit = speed
    points: list[list[float]] = []
    start = travelled = 0.0
    for v0, v1, dt in stages:
        accel = (v1 - v0) / dt
        stop = -v0 / accel if accel else -1.0
        # The instant it turns back is a sample: a speed graph touches 0 there.
        instants = sorted(
            {dt * i / _SAMPLES for i in range(_SAMPLES + 1)} | ({stop} if 0 < stop < dt else set())
        )
        for at in instants:
            v = v0 + accel * at
            y = {
                "velocity": v / v_scale,
                "speed": abs(v) / v_scale,
                "acceleration": accel,
                "distance": travelled + _path(v0, accel, at),
            }[kind]
            points.append([round((start + at) / t_scale, 6), round(y, 6)])
        travelled += _path(v0, accel, dt)
        start += dt
    names = {
        "velocity": ("Velocity", v_unit),
        "speed": ("Speed", v_unit),
        "acceleration": ("Acceleration", "m/s²"),
        "distance": ("Distance", "m"),
    }
    name, unit = names[kind]
    return GraphBlockSpec(
        type="trajectory",
        # The textbook letters: v for speed and velocity, a, and d for a distance.
        expr=f"{_LETTERS[kind]}(t)",
        variable="t",
        x_min=0.0,
        x_max=round(start / t_scale, 6),
        points=points,
        title=f"{name} vs. Time",
        x_label=f"Time ({t_unit})",
        y_label=f"{name} ({unit})",
        trajectory_type="position_vs_time" if kind == "distance" else "velocity_vs_time",
    )


def _path(v0: float, accel: float, t: float) -> float:
    """The distance covered in ``t`` from ``v0`` at ``accel``, a turn back counted forward."""
    stop = -v0 / accel if accel else -1.0
    if 0 < stop < t:
        return abs(v0 * stop + 0.5 * accel * stop**2) + abs(0.5 * accel * (t - stop) ** 2)
    return abs(v0 * t + 0.5 * accel * t**2)
