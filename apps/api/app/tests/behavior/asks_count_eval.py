"""Measure how many separate results the turn's read says a message asks for.

A script, not a test: ``read`` calls the Decider through its gateway, so it needs an
OpenRouter key in the environment, and nothing else (no database).

    python -m app.tests.behavior.asks_count_eval rules
    python -m app.tests.behavior.asks_count_eval read --runs 3
    python -m app.tests.behavior.asks_count_eval read --held-out
    python -m app.tests.behavior.asks_count_eval read --stem

Every turn of ``asks_count_corpus.json`` is labelled with the separate results it asks for
(four standing for four or more): the 60 hard physics questions of the 2026-11-21 live
round, then turns written beside them and never tuned on (``holdout``: one ask with "and"
in its givens, one quantity in two cases, other languages, maths and chemistry, a claim to
check, a picture asked beside one result). ``rules`` asks physics' word count
(``physics.parts.asks_count``), the fallback with no read; ``read`` asks the Decider's
``asks`` question (``decider_read.ASKS_QUESTION``). Reported: exact counts, and the two
errors that matter to the gate (``chat.asks_turn``): a turn of several asks read as one
(an instant reply that drops a part, the failure it exists for) and one ask read as several
(a reply the model writes around the card, slower, never wrong). The ship rule: no
several-asks turn read as one, and at most 5% of one-ask turns read as several.

``--stem`` reads the physics STEM sweep's answer questions with no history, labelled with
the parts each checks (one when it checks a single answer), and prints every turn the read
counts otherwise: a disagreement there is often a label's, since an entry checks only the
answers its corpus spells out.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path

CORPUS = Path(__file__).with_name("asks_count_corpus.json")
STEM = Path(__file__).with_name("stem_corpus") / "physics"
_CONCURRENCY = 8
MAX_FALSE_SEVERAL = 0.05


@dataclass(frozen=True)
class AsksTurn:
    id: str
    asks: int
    prompt: str
    holdout: bool = False


def load(path: Path = CORPUS) -> list[AsksTurn]:
    return [
        AsksTurn(item["id"], int(item["asks"]), item["prompt"], bool(item.get("holdout")))
        for item in json.loads(path.read_text(encoding="utf-8"))
    ]


def load_stem() -> list[AsksTurn]:
    turns: list[AsksTurn] = []
    for path in sorted(STEM.glob("*.json")):
        for item in json.loads(path.read_text(encoding="utf-8")):
            if item["expect"] != "answer" or item.get("history"):
                continue
            turns.append(
                AsksTurn(item["id"], min(len(item.get("parts") or ()) or 1, 4), item["prompt"])
            )
    return turns


def rules_count(turn: AsksTurn) -> int:
    from app.modules.physics.parts import asks_count

    return min(asks_count(turn.prompt), 4)


@dataclass
class Outcome:
    turn: AsksTurn
    counts: list[int] = field(default_factory=list)
    seconds: list[float] = field(default_factory=list)


async def measure_read(turns: list[AsksTurn], runs: int) -> tuple[list[Outcome], list[float]]:
    """The Decider's count on each turn, ``runs`` times, and each call's cost."""
    from app.core.config import Settings
    from app.gateways.decider_gateway import decide
    from app.models import model_catalog
    from app.models.routing_lanes import ROUTING
    from app.modules.chat.decider_read import ASKS_COUNTS, ASKS_QUESTION
    from app.modules.chat.turn_decision import decision_messages

    settings = Settings()
    model = model_catalog.get(ROUTING.decider).model.removeprefix("openrouter/")
    outcomes = {turn.id: Outcome(turn) for turn in turns}
    costs: list[float] = []
    gate = asyncio.Semaphore(_CONCURRENCY)

    async def one(turn: AsksTurn) -> None:
        async with gate:
            state = decision_messages(turn.prompt, [])[-1]["content"]
            started = time.monotonic()
            try:
                reply = await decide(
                    settings, model=model, state=state, questions=dict(ASKS_QUESTION), seconds=8.0
                )
            except Exception as exc:  # A failed call is counted, never retried.
                print(f"  unread [{turn.id}] {type(exc).__name__}")
                return
            outcome = outcomes[turn.id]
            outcome.seconds.append(time.monotonic() - started)
            outcome.counts.append(ASKS_COUNTS.get(str(reply.answers["asks"].choice), 0))
            costs.append(reply.usage.cost)

    for _ in range(runs):
        await asyncio.gather(*(one(turn) for turn in turns))
    return list(outcomes.values()), costs


def report(outcomes: list[Outcome], costs: list[float]) -> str:
    reads = [(o.turn, count) for o in outcomes for count in o.counts]
    several = [count for turn, count in reads if turn.asks > 1]
    single = [count for turn, count in reads if turn.asks == 1]
    exact = sum(1 for turn, count in reads if count == turn.asks)
    missed = sum(1 for count in several if count == 1)
    false = sum(1 for count in single if count > 1)
    rate = false / max(1, len(single))
    verdict = "ship" if missed == 0 and rate <= MAX_FALSE_SEVERAL else "hold"
    lines = [
        f"{len(outcomes)} turns, {len(reads)} reads: exact {exact / max(1, len(reads)):.1%}",
        f"  several asks read as one: {missed} of {len(several)}",
        f"  one ask read as several: {false} of {len(single)} ({rate:.1%})  -> {verdict}",
    ]
    seconds = sorted(s for o in outcomes for s in o.seconds)
    if seconds:
        p95 = seconds[min(len(seconds) - 1, int(len(seconds) * 0.95))]
        lines.append(f"  read: p50 {statistics.median(seconds):.2f}s  p95 {p95:.2f}s")
    if costs:
        lines.append(f"  read cost: ${statistics.mean(costs):.7f} a turn")
    for o in outcomes:
        if any(count != o.turn.asks for count in o.counts):
            lines.append(
                f"  {o.turn.id:28} asks {o.turn.asks} read {o.counts} {o.turn.prompt[:70]!r}"
            )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mode", choices=("rules", "read"))
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--held-out", action="store_true", help="read the held-out turns too")
    parser.add_argument("--stem", action="store_true", help="the physics STEM sweep instead")
    args = parser.parse_args()
    turns = load_stem() if args.stem else load()
    if not args.stem and not args.held_out:
        turns = [turn for turn in turns if not turn.holdout]
    if args.mode == "rules":
        outcomes = [Outcome(turn, counts=[rules_count(turn)]) for turn in turns]
        print(report(outcomes, []))
        return
    outcomes, costs = asyncio.run(measure_read(turns, args.runs))
    print(report(outcomes, costs))


if __name__ == "__main__":
    main()
