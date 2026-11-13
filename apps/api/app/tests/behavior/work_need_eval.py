"""Measure whether a turn is laid out as working only when it asks for a result worked out.

A script, not a test: ``read`` calls the Decider through its gateway, so it needs an
OpenRouter key in the environment, and nothing else (no database).

    python -m app.tests.behavior.work_need_eval rules
    python -m app.tests.behavior.work_need_eval read --runs 3

Every turn of ``work_need_corpus.json`` is labelled ``work`` (a value to calculate, an
equation to solve, an expression to simplify, a unit to convert, an equation to balance) or
not (an expression said in words, what a symbol means, a definition, a concept explained,
naming, a fact, practice questions to set), most of the second kind with a number in them.
``rules`` asks what a turn falls back on with no read (``worked_turn.worked_layout``, a
number and a subject); ``read`` asks the Decider's ``work`` question and prints, at each
threshold, recall on the work set and false layouts on the rest, on the tuning turns and
then on the held-out ones (written beside them, never tuned on). The ship rule, held out:
recall at least 90%, false layouts at most 10%.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path

CORPUS = Path(__file__).with_name("work_need_corpus.json")
_CONCURRENCY = 6
MIN_RECALL = 0.90
MAX_FALSE_LAYOUT = 0.10
_SUBJECTS = {"maths": "math", "physics": "physics", "chemistry": "chemistry"}


@dataclass(frozen=True)
class WorkTurn:
    """One labelled message, the chat before it, and whether the reply works a result out."""

    id: str
    area: str
    work: bool
    prompt: str
    history: tuple[tuple[str, str], ...] = ()
    holdout: bool = False


def load(path: Path = CORPUS) -> list[WorkTurn]:
    return [
        WorkTurn(
            id=item["id"],
            area=item["area"],
            work=bool(item["work"]),
            prompt=item["prompt"],
            history=tuple((role, text) for role, text in item.get("history", ())),
            holdout=bool(item.get("holdout")),
        )
        for item in json.loads(path.read_text(encoding="utf-8"))
    ]


def rules_work(turn: WorkTurn) -> bool:
    """The rule a turn falls back on with no read: a number, and a subject's calculation."""
    from app.core.config import Settings
    from app.modules.chat.worked_turn import worked_layout

    subject = _SUBJECTS.get(turn.area, "math")
    layout = worked_layout(
        turn.prompt, subject, Settings(), answered=False, lightweight=False, several_requests=False
    )
    return layout is not None


@dataclass
class Outcome:
    turn: WorkTurn
    odds: list[float] = field(default_factory=list)
    seconds: list[float] = field(default_factory=list)


async def measure_read(turns: list[WorkTurn], runs: int) -> tuple[list[Outcome], list[float]]:
    """The Decider's ``work`` odds on each turn, ``runs`` times, and each call's cost."""
    from app.core.config import Settings
    from app.gateways.decider_gateway import decide
    from app.models import model_catalog
    from app.models.routing_lanes import ROUTING
    from app.modules.chat.decider_read import WORK_QUESTION
    from app.modules.chat.turn_decision import decision_messages

    settings = Settings()
    model = model_catalog.get(ROUTING.decider).model.removeprefix("openrouter/")
    outcomes = {turn.id: Outcome(turn) for turn in turns}
    costs: list[float] = []
    gate = asyncio.Semaphore(_CONCURRENCY)

    async def one(turn: WorkTurn) -> None:
        async with gate:
            state = decision_messages(turn.prompt, list(turn.history))[-1]["content"]
            started = time.monotonic()
            try:
                reply = await decide(
                    settings, model=model, state=state, questions=WORK_QUESTION, seconds=5.0
                )
            except Exception as exc:  # A failed call is counted, never retried.
                print(f"  unread [{turn.id}] {type(exc).__name__}")
                return
            outcome = outcomes[turn.id]
            outcome.seconds.append(time.monotonic() - started)
            outcome.odds.append(float(reply.answers["work"].noul or 0.0))
            costs.append(reply.usage.cost)

    for _ in range(runs):
        await asyncio.gather(*(one(turn) for turn in turns))
    return list(outcomes.values()), costs


def rates(outcomes: list[Outcome], at: float) -> tuple[float, float]:
    """(recall on the work set, false layouts on the rest) over every answered run."""
    work = [odds >= at for o in outcomes if o.turn.work for odds in o.odds]
    plain = [odds >= at for o in outcomes if not o.turn.work for odds in o.odds]
    return sum(work) / max(1, len(work)), sum(plain) / max(1, len(plain))


def report(outcomes: list[Outcome], costs: list[float], at: float | None) -> str:
    tuning = [o for o in outcomes if not o.turn.holdout]
    held = [o for o in outcomes if o.turn.holdout]
    lines = [f"{len(tuning)} tuning turns, {len(held)} held out"]
    for threshold in (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8):
        recall, false = rates(tuning, threshold)
        lines.append(f"  tuning at {threshold:.1f}: recall {recall:.1%}  false layout {false:.1%}")
    if at is not None:
        recall, false = rates(held, at)
        verdict = "ship" if recall >= MIN_RECALL and false <= MAX_FALSE_LAYOUT else "hold"
        lines.append(
            f"  HELD OUT at {at:.2f}: recall {recall:.1%}  false layout {false:.1%}  ({verdict}; "
            f"rule: recall >= {MIN_RECALL:.0%}, false <= {MAX_FALSE_LAYOUT:.0%})"
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
        mark = "WORK" if o.turn.work else "none"
        lines.append(f"  {o.turn.id:10} {mark} odds {mean:.2f} {o.turn.prompt[:70]!r}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mode", choices=("rules", "read"))
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--at", type=float, help="the threshold to judge the held-out turns at")
    args = parser.parse_args()
    turns = load()
    if args.mode == "rules":
        outcomes = [Outcome(turn, odds=[1.0 if rules_work(turn) else 0.0]) for turn in turns]
        recall, false = rates(outcomes, 0.5)
        print(f"rules on {len(turns)} turns: recall {recall:.1%}  false layout {false:.1%}")
        for o in outcomes:
            if (o.odds[0] >= 0.5) != o.turn.work:
                print(
                    f"  {'missed' if o.turn.work else 'laid out'} [{o.turn.id}] {o.turn.prompt[:80]!r}"
                )
        return
    if args.at is None:
        # Tuning: the held-out turns are not read at all until a threshold is chosen.
        turns = [turn for turn in turns if not turn.holdout]
    outcomes, costs = asyncio.run(measure_read(turns, args.runs))
    print(report(outcomes, costs, args.at))


if __name__ == "__main__":
    main()
