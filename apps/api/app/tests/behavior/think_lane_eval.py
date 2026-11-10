"""Measure whether Auto gives a question that needs thinking a model that can think.

A script, not a test: it calls the real read model (and, with ``--latency``, the reply
models) through the gateway, so it needs an OpenRouter key in the environment and nothing
else (no database).

    python -m app.tests.behavior.think_lane_eval --runs 3 --latency 2

Every turn of ``think_need_corpus.json`` is routed offline as a Pro user on Auto
(``harness.route_case``: its lane, and whether a server solver verified it). Main gives it
the word rules' level on that lane; this branch gives it the read's ``think`` and, on the
maths lane with nothing verified, the lane that can think (``thinking.lane_for_think``).
It prints, for each, how many turns get a model that reasons: on the set that needs
thinking, and on the rest; how many verified maths turns changed lane (none should); and
with ``--latency``, the switched turns answered on both lanes: time to first text, the
whole reply, and its cost.
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import patch

from app.tests.behavior.think_need_eval import ThinkTurn, load, measure_read


@dataclass
class Routed:
    turn: ThinkTurn
    model: str
    solved: bool
    rules_level: str
    messages: list[dict[str, Any]]
    # Per run of the read: (model, level) on this branch.
    branch: list[tuple[str, str]] = field(default_factory=list)


def reasons(model: str, level: str) -> bool:
    """The model sends a reasoning effort at this level (not none, not off)."""
    from app.gateways.reasoning import EFFORTS, thinking_value
    from app.models import model_catalog

    value = thinking_value(model_catalog.get(model), level)
    return value in EFFORTS and value != "none"


async def _inline(fn: Any, *args: Any, **_kwargs: Any) -> Any:
    return fn(*args)


async def route_all(turns: list[ThinkTurn]) -> list[Routed]:
    """Each turn's Auto lane for a Pro user, offline, one at a time (the harness patches)."""
    from app.core.config import Settings
    from app.modules.chat.model_routing.thinking import thinking_level
    from app.tests.behavior.cases import Case, Expect
    from app.tests.behavior.harness import route_case

    routed: list[Routed] = []
    with patch("app.core.sympy_executor.run_sympy", _inline):
        for turn in turns:
            route = await route_case(
                Case(turn.id, "math", turn.prompt, Expect(), "", history=turn.history, pro=True)
            )
            prior_user = next((t for r, t in reversed(turn.history) if r == "user"), None)
            level = thinking_level(turn.prompt, prior_user=prior_user, settings=Settings())
            messages = [*route.context.prompt_messages, {"role": "user", "content": turn.prompt}]
            routed.append(Routed(turn, route.model, route.solved, level, messages))
    return routed


def branch_lanes(routed: list[Routed], reads: dict[str, list[bool | None]]) -> None:
    """The branch's (model, level) per run: the read's think, then the lane rule."""
    from app.modules.chat.model_routing.thinking import lane_for_think, with_read

    pool = ["free-chat", "smart-chat", "glm-5.3-flash", "glm-5.2", "gpt-6-luna", "qwen-3.7-flash"]
    for item in routed:
        for think in reads[item.turn.id]:
            if think is None:
                item.branch.append((item.model, item.rules_level))
                continue
            level = with_read(think)
            lane = lane_for_think(item.model, pool) if level == "hard" and not item.solved else None
            item.branch.append((lane or item.model, level))


def report(routed: list[Routed], runs: int) -> str:
    hard = [r for r in routed if r.turn.think]
    plain = [r for r in routed if not r.turn.think]

    def share(items: list[Routed], branch: bool) -> float:
        if not branch:
            return sum(reasons(r.model, r.rules_level) for r in items) / max(1, len(items))
        hits = sum(reasons(*r.branch[run]) for r in items for run in range(runs))
        return hits / max(1, len(items) * runs)

    moved = [r for r in routed if any(model != r.model for model, _ in r.branch)]
    verified_moved = [r for r in moved if r.solved]
    lines = [
        f"{len(routed)} turns ({len(hard)} need thinking), Pro on Auto, {runs} reads each",
        f"  need thinking, get a model that reasons: main {share(hard, False):.1%}, "
        f"branch {share(hard, True):.1%}",
        f"  don't need it, get one anyway: main {share(plain, False):.1%}, "
        f"branch {share(plain, True):.1%}",
        f"  verified maths turns that changed lane: {len(verified_moved)} of "
        f"{sum(r.solved for r in routed)}",
        f"  turns moved off the maths lane in any run: {len(moved)}",
    ]
    for r in moved:
        lanes = sorted({model for model, _ in r.branch})
        lines.append(f"    [{r.turn.id}] {r.model} -> {lanes} {r.turn.prompt[:60]!r}")
    return "\n".join(lines)


async def timed_reply(
    model: str, level: str, messages: list[dict[str, Any]]
) -> tuple[float, float, float]:
    """(seconds to first text, seconds in all, cost in USD) of one streamed reply."""
    from app.core.config import Settings
    from app.gateways import litellm_gateway as gateway
    from app.models.model_catalog import estimate_cost_usd

    route = gateway.resolve_route(model)
    kwargs = gateway._litellm_kwargs(Settings(), route, latency_sensitive=True, thinking=level)
    started = time.monotonic()
    first: float | None = None
    usage: Any = None
    response = await gateway.acompletion(
        model=route.model,
        messages=messages,
        max_tokens=4000,
        stream=True,
        stream_options={"include_usage": True},
        **kwargs,
    )
    async for chunk in response:
        if getattr(chunk, "usage", None):
            usage = chunk.usage
        delta = chunk.choices[0].delta if chunk.choices else None
        if first is None and delta is not None and getattr(delta, "content", None):
            first = time.monotonic() - started
    total = time.monotonic() - started
    cost = estimate_cost_usd(
        model,
        input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
        output_tokens=getattr(usage, "completion_tokens", 0) or 0,
    )
    return first if first is not None else total, total, cost or 0.0


async def latency(routed: list[Routed], runs: int) -> str:
    moved = [r for r in routed if any(model != r.model for model, _ in r.branch)]
    rows: dict[str, list[tuple[float, float, float]]] = {"main": [], "branch": []}
    for r in moved:
        lane = next(model for model, _ in r.branch if model != r.model)
        for _ in range(runs):
            rows["main"].append(await timed_reply(r.model, r.rules_level, r.messages))
            rows["branch"].append(await timed_reply(lane, "hard", r.messages))
    lines = [f"  {len(moved)} moved turns answered {runs}x on each lane:"]
    for name, values in rows.items():
        if values:
            first, total, cost = (statistics.median(v[i] for v in values) for i in range(3))
            lines.append(
                f"    {name}: first text p50 {first:.1f}s, whole reply p50 {total:.1f}s, "
                f"cost p50 ${cost:.5f}"
            )
    return "\n".join(lines)


async def run(runs: int, latency_runs: int) -> None:
    turns = load()
    routed = await route_all(turns)
    outcomes, _costs = await measure_read(turns, runs)
    reads = {
        o.turn.id: [think if ok else None for think, ok in zip(o.thought, o.answered, strict=True)]
        for o in outcomes
    }
    branch_lanes(routed, reads)
    print(report(routed, runs))
    if latency_runs:
        print(await latency(routed, latency_runs))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--latency", type=int, default=0, help="replies per moved turn and lane")
    args = parser.parse_args()
    asyncio.run(run(args.runs, args.latency))


if __name__ == "__main__":
    main()
