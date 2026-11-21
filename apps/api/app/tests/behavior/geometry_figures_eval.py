"""Score the figures drawn for geometry questions that ask to see none.

A script, not a test: it calls the real figure read through the gateway, so it needs an
OpenRouter key in the environment, and nothing else (no database).

    python -m app.tests.behavior.geometry_figures_eval --runs 2
    python -m app.tests.behavior.geometry_figures_eval --only circ-sector,trig-ladder

Each question of ``geometry_figures_corpus.json`` is asked the way a tutorial asks it, never
"draw", and labelled with whether a figure helps teach it. The figure read runs told the
user did not ask (``math.figure.read``), the figure is built and checked against the
question, and then held to the case: its named sides in proportion, its named angles true,
every value in ``labels`` shown, and at least ``needs`` of each part (arcs, angles). A case
is right, wrong (drawn but failing a check), missed (not drawn) or unwanted (drawn for a
question labelled none). A coordinate plane (a ```graph ``points`` fence) is held to its
case too: ``image`` the exact corners of a transformation's image, ``at`` a lettered
point's coordinates, ``circle`` a circle's centre and radius. The owner (2026-11-20): every kind of geometry, the complex too,
drawn by itself as part of the tutorial.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

CORPUS = Path(__file__).with_name("geometry_figures_corpus.json")
# A side's scale may differ from the first side's by this much; an angle by a degree.
_SCALE_TOLERANCE = 0.02
_ANGLE_TOLERANCE = 1.0
Point = tuple[float, float]


def _fence_json(fence: str) -> dict[str, Any] | None:
    match = re.match(r"```\w+\n(.*)\n```", fence.strip(), re.S)
    if not match:
        return None
    try:
        body = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    return body if isinstance(body, dict) else None


def _points(fig: dict[str, Any]) -> dict[str, Point]:
    return {
        p["name"]: (p["x"], p["y"])
        for p in fig.get("points", [])
        if isinstance(p, dict) and {"name", "x", "y"} <= p.keys()
    }


def _rays(fig: dict[str, Any], pts: dict[str, Point], at: str) -> list[str] | None:
    for mark in fig.get("angles", []):
        if mark.get("at") == at and mark.get("a") in pts and mark.get("b") in pts:
            return [mark["a"], mark["b"]]
    ends = [
        seg["b"] if seg["a"] == at else seg["a"]
        for seg in fig.get("segments", [])
        if at in (seg["a"], seg["b"])
    ]
    ends = [name for name in ends if name in pts]
    return ends if len(ends) == 2 else None


def _angle_at(fig: dict[str, Any], pts: dict[str, Point], at: str) -> float | None:
    rays = _rays(fig, pts, at)
    if rays is None:
        return None
    (ax, ay), (bx, by), (cx, cy) = pts[rays[0]], pts[rays[1]], pts[at]
    v1, v2 = (ax - cx, ay - cy), (bx - cx, by - cy)
    n1, n2 = math.hypot(*v1), math.hypot(*v2)
    if not n1 or not n2:
        return None
    cosine = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)))
    return math.degrees(math.acos(cosine))


def _shown(fig: dict[str, Any]) -> str:
    return " ".join(
        str(item.get("label") or item.get("name") or "")
        for key in ("segments", "angles", "points", "marks", "arcs")
        for item in (fig.get(key) or [])
        if isinstance(item, dict)
    )


def _side_problems(case: dict[str, Any], pts: dict[str, Point]) -> list[str]:
    problems: list[str] = []
    scales: list[tuple[str, float]] = []
    for name, value in (case.get("sides") or {}).items():
        if name[0] in pts and name[1] in pts:
            scales.append((name, math.dist(pts[name[0]], pts[name[1]]) / value))
        else:
            problems.append(f"side {name} not drawn")
    for name, scale in scales[1:]:
        if abs(scale / scales[0][1] - 1) > _SCALE_TOLERANCE:
            problems.append(f"side {name} out of proportion ({scale / scales[0][1]:.2f})")
    return problems


def _near(one: Any, other: Any) -> bool:
    return all(abs(a - b) <= 1e-6 for a, b in zip(one, other, strict=True))


def _image_coordinates(fig: dict[str, Any]) -> set[Point]:
    """Every corner a coordinate plane draws as a transformation's image: its points, its
    polygons' corners and its segments' ends."""
    found = [(p["x"], p["y"]) for p in fig.get("points", []) if p.get("role") == "image"]
    for polygon in fig.get("polygons", []):
        if polygon.get("role") == "image":
            found += [tuple(corner) for corner in polygon["points"]]
    for seg in fig.get("segments", []):
        if seg.get("role") == "image" and "start" in seg:
            found += [tuple(seg["start"]), tuple(seg["end"])]
    return {(round(x, 6), round(y, 6)) for x, y in found}


def _plane_problems(case: dict[str, Any], fig: dict[str, Any]) -> list[str]:
    """A coordinate plane held to the case: the image's corners exactly where the stated
    transformation puts them (``image``), a lettered point where it is (``at``), and a
    circle's centre and radius (``circle``)."""
    problems: list[str] = []
    if "image" in case:
        want = {(round(x, 6), round(y, 6)) for x, y in case["image"]}
        got = _image_coordinates(fig)
        if got != want:
            problems.append(f"image at {sorted(got)}, not {sorted(want)}")
    for label, where in (case.get("at") or {}).items():
        spots = [
            (p["x"], p["y"])
            for p in fig.get("points", [])
            if p.get("label") == label or str(p.get("label", "")).startswith(label + "(")
        ]
        if not any(_near(spot, where) for spot in spots):
            problems.append(f"point {label} not at {where}")
    if "circle" in case:
        circles = fig.get("circles") or []
        if not any(_near([*c["center"], c["radius"]], case["circle"]) for c in circles):
            problems.append(f"no circle {case['circle']}")
    return problems


def check(case: dict[str, Any], fence: str) -> list[str]:
    """What the drawn figure gets wrong against the case: proportions, angles, labels, parts."""
    fig = _fence_json(fence)
    if fig is None:
        return ["fence is not JSON"]
    pts = _points(fig)
    problems = _side_problems(case, pts) if pts else []
    problems += _plane_problems(case, fig)
    shown = _shown(fig)
    problems += [
        f"label {label!r} not shown" for label in case.get("labels") or [] if label not in shown
    ]
    for key, least in (case.get("needs") or {}).items():
        if len(fig.get(key) or []) < least:
            problems.append(f"needs {least} {key}, has {len(fig.get(key) or [])}")
    for at, want in (case.get("angles") or {}).items():
        got = _angle_at(fig, pts, at) if at in pts else None
        if got is None:
            problems.append(f"angle {at} not drawn")
        elif abs(got - want) > _ANGLE_TOLERANCE:
            problems.append(f"angle {at} is {got:.1f}°, not {want}°")
    return problems


async def score(settings: Any, case: dict[str, Any]) -> dict[str, Any]:
    from app.modules.math.figure.build import build_figure_fence
    from app.modules.math.figure.read import read_figure

    reading = await read_figure(settings, case["prompt"], [], asked=False)
    fence = None
    if reading is not None and reading.kind != "none":
        fence = build_figure_fence(reading.model_dump_json(), [case["prompt"]])
    return {
        "id": case["id"],
        "kind": reading.kind if reading else "no read",
        "shape": reading.shape if reading else "",
        "drawn": fence is not None,
        "problems": check(case, fence) if fence else [],
        "reading": reading.model_dump(exclude_defaults=True) if reading else None,
        "fence": fence,
    }


def _verdict(case: dict[str, Any], result: dict[str, Any]) -> str:
    if not case["draw"]:
        return "unwanted" if result["drawn"] else "ok"
    if not result["drawn"]:
        return "missed"
    return "wrong" if result["problems"] else "right"


async def run(corpus: Path, runs: int, only: str, out: str) -> int:
    from app.core.config import get_settings

    settings = get_settings()
    cases = json.loads(await asyncio.to_thread(corpus.read_text, encoding="utf-8"))["cases"]
    if only:
        wanted = set(only.split(","))
        cases = [case for case in cases if case["id"] in wanted]
    gate = asyncio.Semaphore(8)

    async def guarded(case: dict[str, Any]) -> dict[str, Any]:
        async with gate:
            return await score(settings, case)

    tally: dict[str, Counter[str]] = defaultdict(Counter)
    every: list[list[dict[str, Any]]] = []
    for _ in range(runs):
        results = await asyncio.gather(*(guarded(case) for case in cases))
        every.append(results)
        for case, result in zip(cases, results, strict=True):
            tally[case["cat"]][_verdict(case, result)] += 1
    total: Counter[str] = Counter()
    for cat, counts in sorted(tally.items()):
        total.update(counts)
        print(f"{cat:15} {dict(counts)}")
    print("TOTAL", dict(total))
    for case, result in zip(cases, every[-1], strict=True):
        verdict = _verdict(case, result)
        if verdict not in {"right", "ok"}:
            print(f"- {result['id']}: {verdict} kind={result['kind']} {result['problems']}")
    if out:
        await asyncio.to_thread(Path(out).write_text, json.dumps(every, indent=1, default=str))
    return 1 if total["wrong"] or total["unwanted"] else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--corpus", type=Path, default=CORPUS)
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--only", default="")
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.corpus, args.runs, args.only, args.out)))


if __name__ == "__main__":
    main()
