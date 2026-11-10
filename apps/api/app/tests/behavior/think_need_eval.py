"""Measure whether a turn thinks before it answers only when the question needs it.

A script, not a test: ``read`` calls the real read model through the gateway, so it needs
an OpenRouter key in the environment, and nothing else (no database).

    python -m app.tests.behavior.think_need_eval rules
    python -m app.tests.behavior.think_need_eval read --runs 3

Every turn of ``think_need_corpus.json`` is labelled ``think`` (several dependent steps or
parts, a word problem to set up, a proof, a trade-off, code to write or debug, a logic
puzzle) or not (chat, simple facts, how-to, writing, a one-step calculation, a line the
server's solver checks). ``rules`` asks the word rules the turn falls back on
(``thinking_level`` with no read); ``read`` asks the turn's read (``web_search.live_read``,
its ``think``). Each prints recall on the think set, false thinking on the rest (and the
same on the held-out turns, written after the read's wording), the read's latency and its
cost per turn. The ship rule: recall at least 90%, false thinking
at most 10%.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

CORPUS = Path(__file__).with_name("think_need_corpus.json")
_CONCURRENCY = 6
MIN_RECALL = 0.90
MAX_FALSE_THINKING = 0.10


@dataclass(frozen=True)
class ThinkTurn:
    """One labelled question, the chat before it, and whether to think first."""

    id: str
    area: str
    think: bool
    prompt: str
    history: tuple[tuple[str, str], ...] = ()
    # Written after the read's wording was settled, and never tuned on.
    holdout: bool = False


def load(path: Path = CORPUS) -> list[ThinkTurn]:
    return [
        ThinkTurn(
            id=item["id"],
            area=item["area"],
            think=bool(item["think"]),
            prompt=item["prompt"],
            history=tuple((role, text) for role, text in item.get("history", ())),
            holdout=bool(item.get("holdout")),
        )
        for item in json.loads(path.read_text(encoding="utf-8"))
    ]


def rules_think(turn: ThinkTurn) -> bool:
    """The word rules' answer: what a turn gets when the read gives none."""
    from app.core.config import Settings
    from app.modules.chat.model_routing.thinking import thinking_level

    prior_user = next((text for role, text in reversed(turn.history) if role == "user"), None)
    return thinking_level(turn.prompt, prior_user=prior_user, settings=Settings()) == "hard"


@dataclass
class Outcome:
    turn: ThinkTurn
    thought: list[bool] = field(default_factory=list)
    seconds: list[float] = field(default_factory=list)
    unread: int = 0


async def measure_read(turns: list[ThinkTurn], runs: int) -> tuple[list[Outcome], list[float]]:
    """The read's ``think`` on each turn, ``runs`` times, and each call's cost in USD."""
    from app.core.config import Settings
    from app.gateways.llm_spend import response_cost_usd
    from app.modules.web_search import live_read

    settings = Settings()
    outcomes = {turn.id: Outcome(turn) for turn in turns}
    costs: list[float] = []
    gate = asyncio.Semaphore(_CONCURRENCY)

    async def one(turn: ThinkTurn) -> None:
        async with gate:
            recent = [SimpleNamespace(role=role, content=text) for role, text in turn.history]
            started = time.monotonic()
            task = live_read.start_live_read(settings, turn.prompt, recent=recent)
            read = await task if task is not None else None
            outcome = outcomes[turn.id]
            outcome.seconds.append(time.monotonic() - started)
            outcome.unread += read is None
            outcome.thought.append(bool(read is not None and read.think))

    def meter(alias: str, response: object) -> None:
        # A measurement is not the product's spend: priced here, never counted.
        costs.append(response_cost_usd(alias, response))

    async def never_capped(*_args: Any, **_kwargs: Any) -> bool:
        return False

    with (
        patch("app.services.quota.global_spend_exceeded", never_capped),
        patch("app.gateways.llm_spend.meter_model_call", meter),
    ):
        for _ in range(runs):
            await asyncio.gather(*(one(turn) for turn in turns))
    return list(outcomes.values()), costs


def rates(outcomes: list[Outcome], run: int) -> tuple[float, float, float]:
    """(recall on the think set, false thinking on the rest, precision) in one run."""
    hard = [o for o in outcomes if o.turn.think]
    plain = [o for o in outcomes if not o.turn.think]
    caught = sum(o.thought[run] for o in hard)
    false = sum(o.thought[run] for o in plain)
    return (
        caught / max(1, len(hard)),
        false / max(1, len(plain)),
        caught / max(1, caught + false),
    )


def _means(outcomes: list[Outcome], runs: int) -> str:
    all_rates = [rates(outcomes, run) for run in range(runs)]
    recall, false, precision = (statistics.mean(r[i] for r in all_rates) for i in range(3))
    return f"recall {recall:.1%}  false thinking {false:.1%}  precision {precision:.1%}"


def report(outcomes: list[Outcome], runs: int, costs: list[float] | None = None) -> str:
    hard = sum(o.turn.think for o in outcomes)
    lines = [f"{len(outcomes)} turns: {hard} need thinking, {len(outcomes) - hard} don't"]
    all_rates = [rates(outcomes, run) for run in range(runs)]
    for run, (recall, false, precision) in enumerate(all_rates):
        lines.append(
            f"  run {run + 1}: recall {recall:.1%}  false thinking {false:.1%}  "
            f"precision {precision:.1%}"
        )
    lines.append(
        f"  mean:  {_means(outcomes, runs)}  "
        f"(ship rule: recall >= {MIN_RECALL:.0%}, false thinking <= {MAX_FALSE_THINKING:.0%})"
    )
    held = [o for o in outcomes if o.turn.holdout]
    if held and len(held) < len(outcomes):
        lines.append(f"  held-out ({len(held)} turns), mean: {_means(held, runs)}")
    seconds = sorted(s for o in outcomes for s in o.seconds)
    if seconds:
        p95 = seconds[min(len(seconds) - 1, int(len(seconds) * 0.95))]
        unread = sum(o.unread for o in outcomes)
        lines.append(
            f"  read: p50 {statistics.median(seconds):.2f}s  p95 {p95:.2f}s  unread {unread}"
        )
    if costs:
        lines.append(f"  read cost: ${statistics.mean(costs):.6f} a turn")
    for outcome in outcomes:
        wrong = sum(t != outcome.turn.think for t in outcome.thought)
        if wrong:
            label = "missed" if outcome.turn.think else "thought"
            lines.append(
                f"  {label} {wrong}/{runs} [{outcome.turn.id}] {outcome.turn.prompt[:80]!r}"
            )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mode", choices=("rules", "read"))
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--only", help="comma-separated turn ids")
    args = parser.parse_args()
    turns = load()
    if args.only:
        wanted = {item.strip() for item in args.only.split(",")}
        turns = [turn for turn in turns if turn.id in wanted]
    if args.mode == "rules":
        outcomes = [Outcome(turn, thought=[rules_think(turn)]) for turn in turns]
        print(report(outcomes, 1))
        return
    outcomes, costs = asyncio.run(measure_read(turns, args.runs))
    print(report(outcomes, args.runs, costs))


if __name__ == "__main__":
    main()
