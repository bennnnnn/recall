"""Measure whether the turn's read gives the ```steps card only to one procedure done in order.

A script, not a test: ``read`` calls the Decider through its gateway, so it needs an
OpenRouter key in the environment, and nothing else (no database).

    python -m app.tests.behavior.steps_need_eval read --runs 3
    python -m app.tests.behavior.steps_need_eval read --runs 3 --at 0.5

Every turn of ``steps_need_corpus.json`` is labelled ``steps`` (a task or a method carried
out in a fixed order: tie a tie, renew a passport, balance a chemical equation) or not (tips
and ways to reach a goal, advice, a choice to weigh, how something works, a plan, a fact,
chat). ``read`` asks the Decider's ``steps`` question in the call the turn sends it
(``decider_read.LAYOUT_QUESTIONS``, with the names question) at
each threshold on the tuning turns, then on the held-out ones (the owner's 2026-11-27
groups, written before any tuning) at ``--at``.

The ship rule, held out: a card on tips at most 5%, the card on procedures at least 90%.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path

CORPUS = Path(__file__).with_name("steps_need_corpus.json")
_CONCURRENCY = 6
MIN_RECALL = 0.90
MAX_FALSE_CARDS = 0.05


@dataclass(frozen=True)
class StepsTurn:
    """One labelled message, the chat before it, and whether its answer is one procedure."""

    id: str
    steps: bool
    prompt: str
    history: tuple[tuple[str, str], ...] = ()
    holdout: bool = False


def load(path: Path = CORPUS) -> list[StepsTurn]:
    return [
        StepsTurn(
            id=item["id"],
            steps=bool(item["steps"]),
            prompt=item["prompt"],
            history=tuple((role, text) for role, text in item.get("history", ())),
            holdout=bool(item.get("holdout")),
        )
        for item in json.loads(path.read_text(encoding="utf-8"))
    ]


@dataclass
class Outcome:
    turn: StepsTurn
    odds: list[float] = field(default_factory=list)
    seconds: list[float] = field(default_factory=list)


def rates(outcomes: list[Outcome], at: float) -> tuple[float, float]:
    """(the card on the procedures, the card on the rest) over every answered run."""
    card = [odds >= at for o in outcomes if o.turn.steps for odds in o.odds]
    plain = [odds >= at for o in outcomes if not o.turn.steps for odds in o.odds]
    return sum(card) / max(1, len(card)), sum(plain) / max(1, len(plain))


async def measure_read(turns: list[StepsTurn], runs: int) -> tuple[list[Outcome], list[float]]:
    """The Decider's ``steps`` odds on each turn, ``runs`` times, and each call's cost."""
    from app.core.config import Settings
    from app.gateways.decider_gateway import decide
    from app.models import model_catalog
    from app.models.routing_lanes import ROUTING
    from app.modules.chat.decider_read import LAYOUT_QUESTIONS
    from app.modules.chat.turn_decision import decision_messages

    settings = Settings()
    model = model_catalog.get(ROUTING.decider).model.removeprefix("openrouter/")
    outcomes = {turn.id: Outcome(turn) for turn in turns}
    costs: list[float] = []
    gate = asyncio.Semaphore(_CONCURRENCY)

    async def one(turn: StepsTurn) -> None:
        async with gate:
            state = decision_messages(turn.prompt, list(turn.history))[-1]["content"]
            started = time.monotonic()
            try:
                reply = await decide(
                    settings,
                    model=model,
                    state=state,
                    questions=dict(LAYOUT_QUESTIONS),
                    seconds=5.0,
                )
            except Exception as exc:  # A failed call is counted, never retried.
                print(f"  unread [{turn.id}] {type(exc).__name__}")
                return
            outcome = outcomes[turn.id]
            outcome.seconds.append(time.monotonic() - started)
            outcome.odds.append(float(reply.answers["steps"].noul or 0.0))
            costs.append(reply.usage.cost)

    for _ in range(runs):
        await asyncio.gather(*(one(turn) for turn in turns))
    return list(outcomes.values()), costs


def report_read(outcomes: list[Outcome], costs: list[float], at: float | None) -> str:
    tuning = [o for o in outcomes if not o.turn.holdout]
    held = [o for o in outcomes if o.turn.holdout]
    lines = [f"{len(tuning)} tuning turns, {len(held)} held out"]
    for threshold in (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8):
        recall, false = rates(tuning, threshold)
        lines.append(
            f"  tuning at {threshold:.1f}: card on procedures {recall:.1%}  on tips {false:.1%}"
        )
    if at is not None and held:
        recall, false = rates(held, at)
        verdict = "ship" if recall >= MIN_RECALL and false <= MAX_FALSE_CARDS else "hold"
        lines.append(
            f"  HELD OUT at {at:.2f}: card on procedures {recall:.1%}  on the rest {false:.1%}  "
            f"({verdict}; rule: >= {MIN_RECALL:.0%}, <= {MAX_FALSE_CARDS:.0%})"
        )
    seconds = sorted(s for o in outcomes for s in o.seconds)
    if seconds:
        p95 = seconds[min(len(seconds) - 1, int(len(seconds) * 0.95))]
        lines.append(f"  read: p50 {statistics.median(seconds):.2f}s  p95 {p95:.2f}s")
    if costs:
        lines.append(f"  read cost: ${statistics.mean(costs):.7f} a turn")
    for o in outcomes:
        if at is None and o.turn.holdout:
            continue
        mean = statistics.mean(o.odds) if o.odds else float("nan")
        mark = "STEPS" if o.turn.steps else "none "
        lines.append(f"  {o.turn.id:9} {mark} odds {mean:.2f} {o.turn.prompt[:70]!r}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mode", choices=("read",))
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--at", type=float, help="the threshold to judge held-out turns at")
    args = parser.parse_args()
    turns = load()
    if args.at is None:
        # Tuning: the held-out turns are not read at all until a threshold is chosen.
        turns = [turn for turn in turns if not turn.holdout]
    outcomes, costs = asyncio.run(measure_read(turns, args.runs))
    print(report_read(outcomes, costs, args.at))


if __name__ == "__main__":
    main()
