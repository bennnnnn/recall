"""Where a described vector picture's bodies and arrows go: every coordinate is the server's.

``bodies``: each body sits behind the point the bodies head for, its arrow toward it, so two
cars approaching a junction come in along their roads and two balls about to meet face each
other; bodies heading the same way queue one behind the other. Their arrows ride on them and
keep their sizes in proportion. ``tail``: every arrow from one point. ``chain``: each arrow
from the last one's tip. Both draw arrows at their true relative lengths (``vector_sum``),
in stages, one arrow after another, the resultant last. A compass picture stands on N and E
axes; a picture along one line of left and right stands on a ground line.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass

from app.modules.physics.display import plain_number
from app.modules.physics.schemas import (
    SimulationAngle,
    SimulationAxes,
    SimulationBlockSpec,
    SimulationBody,
    SimulationVector,
)
from app.modules.physics.schemas.scene_titles import TitleKey
from app.services.law_binding.givens import Given
from app.services.rounding_rule import number_parts

# The SI unit of each quantity a picture draws: the unit its values are compared in, and the
# one a worked-out size is written in when the question states its values in several.
SI_UNITS = {"velocity": "m/s", "force": "N", "displacement": "m", "momentum": "kg m/s"}
_TITLES: dict[str, tuple[str, TitleKey]] = {
    "velocity": ("Velocities", "velocities"),
    "force": ("Forces", "forces"),
    "displacement": ("Displacements", "displacements"),
    "momentum": ("Momentum", "momentum"),
}
_BEFORE: tuple[str, TitleKey] = ("Before the Collision", "before_collision")
_COLLIDES = re.compile(r"\b(?:collid\w*|collision|crash\w*|impact|hits?|strikes?)\b", re.I)
_BOXES = re.compile(
    r"\b(?:car|truck|lorry|bus|van|vehicle|block|box|crate|trolley|cart|wagon|train|tram)\b",
    re.IGNORECASE,
)
_RADIUS = 0.16
_REACH = 1.0
_QUEUE = 0.9
_MOST_STAGE = 5
_AXIS_INSET = 0.04
# Momenta that cancel to this share of their sizes leave the bodies at rest.
_AT_REST = 1e-9


@dataclass(frozen=True)
class Arrow:
    """One checked arrow: its stated value and label, its angle (degrees counter-clockwise
    from east), its body's name and mass when it has them."""

    given: Given
    label: str
    angle: float
    compass: bool
    name: str | None
    mass: Given | None
    mass_label: str | None
    direction: str
    # The description's own name for it, which a later arrow's angle may name ("90° to F1").
    key: str = ""

    @property
    def unit(self) -> tuple[float, float]:
        rad = math.radians(self.angle)
        return _clean(math.cos(rad)), _clean(math.sin(rad))

    @property
    def si(self) -> float:
        return self.given.si if self.given.si is not None else self.given.value


def _card(value: float) -> str:
    """A worked-out size as an answer card writes it (``rounding_rule``), so the picture
    and the card under the reply say one number."""
    mantissa, exponent = number_parts(value)
    return mantissa if exponent is None else plain_number(value)


def _clean(value: float) -> float:
    return 0.0 if abs(value) < 1e-12 else round(value, 9)


def laid_out(
    arrows: Sequence[Arrow],
    layout: str,
    quantity: str,
    resultant: bool,
    question: str,
    after: bool = False,
) -> list[SimulationBlockSpec]:
    """The picture of ``arrows``: their bodies (and, ``after``, the bodies as one once they
    collide), or the arrows from one point or head to tail."""
    if layout == "bodies":
        scenes = [_bodies(arrows, quantity, question)]
        moving_off = _after(arrows) if after else None
        return [*scenes, moving_off] if moving_off is not None else scenes
    return [_summed(arrows, layout == "chain", quantity, resultant)]


def _bodies(arrows: Sequence[Arrow], quantity: str, question: str) -> SimulationBlockSpec:
    along_line = not any(a.compass for a in arrows) and all(a.unit[1] == 0.0 for a in arrows)
    bodies: list[SimulationBody] = []
    vectors: list[SimulationVector] = []
    for index, arrow in enumerate(arrows):
        ux, uy = arrow.unit
        ahead = sum(1 for other in arrows[:index] if _same_way(other, arrow))
        reach = _REACH * (1 + _QUEUE * ahead)
        x, y = -ux * reach, (_RADIUS if along_line else -uy * reach)
        box = arrow.name is not None and _BOXES.search(arrow.name) is not None
        bodies.append(
            SimulationBody(
                path=[[x, y], [x, y]],
                radius=_RADIUS,
                label=_body_label(arrow),
                role="primary" if index % 2 == 0 else "secondary",
                shape="box" if box else "circle",
            )
        )
        vectors.append(
            SimulationVector(
                anchor=[ux * (_RADIUS + 0.04), uy * (_RADIUS + 0.04)],
                dx=ux * arrow.si,
                dy=uy * arrow.si,
                label=arrow.label[:24],
                role="force" if quantity == "force" else "motion",
                body=index,
            )
        )
    xs = [p for b in bodies for p in (b.path[0][0] - 0.6, b.path[0][0] + 0.6)] + [-0.5, 0.5]
    ys = [p for b in bodies for p in (b.path[0][1] - 0.6, b.path[0][1] + 0.6)] + [-0.5, 0.5]
    title, key = _BEFORE if _COLLIDES.search(question) else _TITLES[quantity]
    compass = any(a.compass for a in arrows)
    return SimulationBlockSpec(
        type="free_body",
        title=title,
        title_key=key,
        bodies=bodies,
        vectors=vectors,
        x_min=min(xs),
        x_max=max(xs),
        y_min=-0.45 if along_line else min(ys),
        y_max=1.0 if along_line else max(ys),
        ground=along_line,
        axes=_axes(min(xs), max(xs), min(ys), max(ys), compass) if not along_line else None,
        alt=_alt(arrows, quantity),
    )


def _same_way(one: Arrow, other: Arrow) -> bool:
    return abs((one.angle - other.angle + 180.0) % 360.0 - 180.0) < 1.0


def _body_label(arrow: Arrow) -> str | None:
    parts = [part for part in (arrow.name, arrow.mass_label) if part]
    return ", ".join(parts)[:32] or None


def _axes(x0: float, x1: float, y0: float, y1: float, compass: bool) -> SimulationAxes:
    """Axes through the meeting point, inside the frame: N and E for a compass picture."""
    # In from the frame's edge by a share of its size: a picture of 0.2 N or of centimetres
    # is as wide as a fixed inset (review, #2593).
    across, up = (x1 - x0) * _AXIS_INSET, (y1 - y0) * _AXIS_INSET
    return SimulationAxes(
        origin=[0.0, 0.0],
        x=[min(x0 + across, 0.0), max(x1 - across, 0.0)],
        y=[min(y0 + up, 0.0), max(y1 - up, 0.0)],
        x_label="E" if compass else "x",
        y_label="N" if compass else "y",
    )


def _after(arrows: Sequence[Arrow]) -> SimulationBlockSpec | None:
    """The bodies as one after they stick: momentum shared, so their velocity is the sum of
    m·v over the sum of the masses, worked out here from the stated values; None when the
    momenta cancel (2 kg at 3 m/s against 3 kg at 2 m/s): at rest, there is no arrow to draw,
    and a float's 1e-16 m/s is no velocity."""
    momenta = [(_kg(a) * a.si * a.unit[0], _kg(a) * a.si * a.unit[1]) for a in arrows]
    px, py = sum(p[0] for p in momenta), sum(p[1] for p in momenta)
    total = sum(_kg(a) for a in arrows)
    scale = sum(math.hypot(*p) for p in momenta)
    if total <= 0.0 or math.hypot(px, py) <= _AT_REST * scale:
        return None
    vx, vy = px / total, py / total
    speed = math.hypot(vx, vy)
    compass = any(a.compass for a in arrows)
    named = [a.name for a in arrows if a.name]
    names = " and ".join(named) or "The bodies"
    label = in_stated_unit(speed, arrows, "velocity")
    together = " + ".join(named) if len(named) == len(arrows) else ""
    body = SimulationBody(
        path=[[0.0, 0.0], [0.0, 0.0]], radius=_RADIUS * 1.3, label=together[:32] or None
    )
    ux, uy = vx / speed, vy / speed
    angles = _off_axis(ux, uy, compass)
    return SimulationBlockSpec(
        type="free_body",
        title="After the Collision",
        title_key="after_collision",
        bodies=[body],
        vectors=[
            SimulationVector(
                anchor=[ux * _RADIUS * 1.4, uy * _RADIUS * 1.4],
                dx=vx,
                dy=vy,
                label=label,
                role="motion",
                body=0,
            )
        ],
        angles=angles,
        x_min=-1.2,
        x_max=1.2,
        y_min=-1.2,
        y_max=1.2,
        axes=_axes(-1.2, 1.2, -1.2, 1.2, compass),
        alt=f"{names} move off together at {label}"[:300],
    )


def _kg(arrow: Arrow) -> float:
    mass = arrow.mass
    if mass is None:
        return 0.0
    return mass.si if mass.si is not None else mass.value


def _off_axis(ux: float, uy: float, compass: bool) -> list[SimulationAngle]:
    """The arc from the nearest axis to a velocity that lies along none."""
    direction = math.degrees(math.atan2(uy, ux)) % 360.0
    axis = round(direction / 90.0) * 90.0
    off = direction - axis
    if abs(off) < 0.5:
        return []
    return [
        SimulationAngle(
            vertex=[0.0, 0.0],
            start_deg=min(axis, direction),
            end_deg=max(axis, direction),
            label=f"{_card(abs(off))}°",
            role="result",
        )
    ]


def _summed(
    arrows: Sequence[Arrow], chained: bool, quantity: str, resultant: bool
) -> SimulationBlockSpec:
    """Arrows from one point, or head to tail, at their true relative lengths; with
    ``resultant``, their sum from the start to the end, labelled with its size."""
    vectors: list[SimulationVector] = []
    x = y = 0.0
    for index, arrow in enumerate(arrows):
        ux, uy = arrow.unit
        dx, dy = ux * arrow.si, uy * arrow.si
        vectors.append(
            SimulationVector(
                anchor=[x, y] if chained else [0.0, 0.0],
                dx=dx,
                dy=dy,
                label=arrow.label[:24],
                role="force",
                stage=min(index, _MOST_STAGE),
            )
        )
        if chained:
            x, y = x + dx, y + dy
    sx = sum(v.dx for v in vectors)
    sy = sum(v.dy for v in vectors)
    angles: list[SimulationAngle] = []
    if resultant and math.hypot(sx, sy) > 1e-9 * max(a.si for a in arrows):
        size = in_stated_unit(math.hypot(sx, sy), arrows, quantity)
        vectors.append(
            SimulationVector(
                anchor=[0.0, 0.0],
                dx=sx,
                dy=sy,
                label=f"R = {size}"[:24],
                role="result",
                stage=min(len(arrows), _MOST_STAGE),
            )
        )
        angles = _resultant_angle(arrows[0], sx, sy, len(arrows))
    tips = [(v.anchor[0] + v.dx, v.anchor[1] + v.dy) for v in vectors]
    xs = [0.0, *(t[0] for t in tips)]
    ys = [0.0, *(t[1] for t in tips)]
    reach = max(max(xs) - min(xs), max(ys) - min(ys)) or 1.0
    margin = reach * 0.22
    compass = any(a.compass for a in arrows)
    x0, x1, y0, y1 = min(xs) - margin, max(xs) + margin, min(ys) - margin, max(ys) + margin
    title, key = _TITLES[quantity]
    return SimulationBlockSpec(
        type="vector_sum",
        title=title,
        title_key=key,
        vectors=vectors,
        angles=angles,
        x_min=x0,
        x_max=x1,
        y_min=y0,
        y_max=y1,
        axes=_axes(x0, x1, y0, y1, compass),
        alt=_alt(arrows, quantity),
    )


def in_stated_unit(si: float, arrows: Sequence[Arrow], quantity: str) -> str:
    """A worked-out size in the unit the question states its values in, when it uses one."""
    units = {arrow.given.unit for arrow in arrows}
    first = arrows[0]
    if len(units) == 1 and first.given.unit and first.si:
        return f"{_card(si * first.given.value / first.si)} {first.given.unit}"
    return f"{_card(si)} {SI_UNITS[quantity]}"


def _resultant_angle(first: Arrow, sx: float, sy: float, stage: int) -> list[SimulationAngle]:
    """The resultant's angle from the first arrow, worked out here."""
    start = first.angle
    end = math.degrees(math.atan2(sy, sx)) % 360.0
    sweep = (end - start + 180.0) % 360.0 - 180.0
    if abs(sweep) < 1.0:
        return []
    low, high = (start, start + sweep) if sweep > 0 else (start + sweep, start)
    return [
        SimulationAngle(
            vertex=[0.0, 0.0],
            start_deg=low,
            end_deg=high,
            label=f"{_card(abs(sweep))}°",
            role="result",
            stage=min(stage, _MOST_STAGE),
        )
    ]


def _alt(arrows: Sequence[Arrow], quantity: str) -> str:
    """One sentence a screen reader says: each arrow's body, size and direction."""
    parts = []
    for arrow in arrows:
        who = _body_label(arrow)
        where = f" {arrow.direction}" if arrow.direction else ""
        parts.append(f"{who + ': ' if who else ''}{arrow.label}{where}")
    return f"{_TITLES[quantity][0]}: " + "; ".join(parts)[:280]
