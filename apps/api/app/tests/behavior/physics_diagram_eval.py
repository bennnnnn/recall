"""Measure the diagrams physics turns draw when the message asks to see one.

A script, not a test: it sends every question of ``physics_diagram_corpus.json`` to a
running API (``./scripts/dev.sh api``, a provider key in its environment) as a Pro dev
account, each in a fresh chat, and reads the reply's pictures. A question that asks for a
diagram counts as drawn when its reply carries a ```simulation fence of the kind its entry
names that validates, and, for arrows the entry lists, every stated arrow drawn with its
size and direction. A look-alike asks to see nothing: it counts as wrong when its reply
says it could not draw a picture. The replies land in ``--out`` for reading.

    python -m app.tests.behavior.physics_diagram_eval --api http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from pathlib import Path
from typing import Any

import httpx

CORPUS = Path(__file__).with_name("physics_diagram_corpus.json")
_FENCE = re.compile(r"```simulation\n(.*?)```", re.DOTALL)
_NOT_DRAWN = "couldn't draw"
# The simulation types a corpus kind may come as.
KIND_TYPES: dict[str, frozenset[str]] = {
    "vectors": frozenset({"vector_sum", "free_body", "collision"}),
    "free_body": frozenset({"free_body", "incline"}),
    "incline": frozenset({"incline", "free_body"}),
    "atwood": frozenset({"free_body"}),
    "pulley": frozenset({"free_body"}),
    "projectile": frozenset({"projectile_motion"}),
    "circuit": frozenset({"circuit"}),
    "rays": frozenset({"rays"}),
    "collision": frozenset({"collision", "free_body", "vector_sum"}),
    "pendulum": frozenset({"pendulum"}),
}
# Compass directions of travel, as (dx, dy) with east +x and north +y.
_HEADINGS = {
    "east": (1.0, 0.0),
    "west": (-1.0, 0.0),
    "north": (0.0, 1.0),
    "south": (0.0, -1.0),
    "N30E": (math.sin(math.radians(30)), math.cos(math.radians(30))),
}


def load(path: Path = CORPUS) -> dict[str, list[dict[str, Any]]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {"draw": raw["draw"], "look_alikes": raw["look_alikes"]}


def pictures(reply: str) -> list[dict[str, Any]]:
    """The reply's scenes that validate."""
    from app.modules.physics.schemas import SimulationBlockSpec

    specs = []
    for body in _FENCE.findall(reply):
        try:
            specs.append(SimulationBlockSpec.model_validate(json.loads(body)).model_dump())
        except ValueError as exc:  # a fence that does not validate is no picture
            print(f"  (a picture that does not validate: {type(exc).__name__})")
    return specs


def _number(text: str) -> float | None:
    found = re.search(r"\d+(?:\.\d+)?", text.replace(",", ""))
    return float(found.group()) if found else None


def arrow_drawn(specs: list[dict[str, Any]], size: str, heading: str | None) -> bool:
    """A drawn arrow labelled with ``size`` pointing along ``heading`` (any, when None)."""
    want = _number(size)
    for spec in specs:
        for vector in spec.get("vectors") or []:
            label = vector.get("label") or ""
            if want is None or _number(label) != want:
                continue
            if heading is None:
                return True
            hx, hy = _HEADINGS[heading]
            length = math.hypot(vector["dx"], vector["dy"])
            if (vector["dx"] * hx + vector["dy"] * hy) / length > 0.99:
                return True
    return False


def judged(entry: dict[str, Any], reply: str) -> tuple[bool, str]:
    specs = pictures(reply)
    types = sorted({spec["type"] for spec in specs})
    if not specs:
        return False, "no picture" + (" (said it could not)" if _NOT_DRAWN in reply else "")
    if not set(types) & KIND_TYPES[entry["kind"]]:
        return False, f"wrong kind {types}"
    missing = [
        f"{size} {heading}"
        for size, heading in entry.get("arrows", [])
        if not arrow_drawn(specs, size, heading)
    ]
    if missing:
        return False, f"{types} missing arrows {missing}"
    return True, ",".join(types)


class Client:
    def __init__(self, api: str) -> None:
        self.http = httpx.Client(base_url=api.rstrip("/"), timeout=30.0)
        made = self.http.post("/auth/dev", json={"email": "diagrams@recall.local", "name": "Bini"})
        made.raise_for_status()
        self.headers = {"Authorization": f"Bearer {made.json()['access_token']}"}
        self.http.post("/auth/me/pro-dev", headers=self.headers).raise_for_status()
        self.http.patch(
            "/auth/me", headers=self.headers, json={"ai_data_consent": True}
        ).raise_for_status()

    def ask(self, prompt: str) -> str:
        self.http.post("/chats/usage/today/reset", headers=self.headers)
        chat = self.http.post("/chats", headers=self.headers, json={"model": "auto"})
        chat.raise_for_status()
        tokens: list[str] = []
        with self.http.stream(
            "POST",
            f"/chats/{chat.json()['id']}/messages/stream",
            headers=self.headers,
            json={"content": prompt, "client_timezone": "Africa/Nairobi"},
            timeout=180.0,
        ) as response:
            for line in response.iter_lines():
                if not line.startswith("data:"):
                    continue
                try:
                    event = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "token":
                    tokens.append(str(event.get("content") or ""))
                elif event.get("type") == "done" and event.get("final_content"):
                    tokens = [str(event["final_content"])]
                elif event.get("type") == "error":
                    return f"ERROR {event.get('message')}"
        return "".join(tokens)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--out", default="tmp/physics_diagrams.json")
    parser.add_argument("--only", default="")
    args = parser.parse_args()
    corpus = load()
    only = {name for name in args.only.split(",") if name}
    client = Client(args.api)
    results: list[dict[str, Any]] = []
    drawn = wrong = 0
    for group in ("draw", "look_alikes"):
        for entry in corpus[group]:
            if only and entry["id"] not in only:
                continue
            reply = client.ask(entry["prompt"])
            time.sleep(2.2)  # under the API's per-minute message limit
            if group == "draw":
                ok, why = judged(entry, reply)
                drawn += ok
            else:
                ok = _NOT_DRAWN not in reply
                why = "no note" if ok else "said it could not draw"
                wrong += not ok
            print(f"{'ok ' if ok else 'MISS'} {group:11} {entry['id']:24} {why}", flush=True)
            results.append(
                {"id": entry["id"], "group": group, "ok": ok, "why": why, "reply": reply}
            )
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    asked = sum(1 for r in results if r["group"] == "draw")
    print(f"drawn {drawn}/{asked}; look-alikes saying 'could not draw': {wrong}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
