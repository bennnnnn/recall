"""Measure the check that takes back a reply saying it can't get live facts.

A script, not a test: it calls Perplexity's Decider through OpenRouter, so it needs an
OpenRouter key in the environment, and nothing else (no database).

    python -m app.tests.behavior.live_denial_eval --runs 2

Every reply of ``live_denial_corpus.json`` is labelled ``denies``: it says it cannot check,
search or see live public facts, or that it is looking them up instead of answering
(``tool_loop.live_denial``). The rest look like it and are not: a hedge that it may be out
of date, an offer to look it up, the user's own things it cannot see (a package, messages,
a booking), a draft or translation of the user's words, a quote of a denial, a long answer
that mentions one. A turn asks the check only where ``may_check`` allows (a draft or a
translation never), so a reply is counted as retried when the turn would ask and the check
says yes. Prints, per run: denials caught and other replies retried, the same for the
held-out replies (written after the question was settled, never tuned on), each area, the
latency, and every reply either way wrong.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import patch

CORPUS = Path(__file__).with_name("live_denial_corpus.json")
_CONCURRENCY = 4


@dataclass(frozen=True)
class Reply:
    """One reply written without search, the message it answers, and its label."""

    id: str
    area: str
    denies: bool
    message: str
    reply: str
    holdout: bool = False


def load(path: Path = CORPUS) -> list[Reply]:
    return [Reply(**item) for item in json.loads(path.read_text(encoding="utf-8"))["replies"]]


def asked(message: str) -> bool:
    """The turn would ask the check: not a draft, translation or edit of the user's words
    (``live_denial.may_check``; the corpus's turns are otherwise plain questions)."""
    from app.modules.turn_reading.writing_kind import writing_request_kind

    return writing_request_kind(message) is None


@dataclass
class Outcome:
    reply: Reply
    retried: list[bool] = field(default_factory=list)
    seconds: list[float] = field(default_factory=list)


async def measure(replies: list[Reply], runs: int) -> list[Outcome]:
    from app.core.config import Settings
    from app.modules.chat.tool_loop.live_denial import denies_live_data

    settings = Settings()
    outcomes = {reply.id: Outcome(reply) for reply in replies}
    gate = asyncio.Semaphore(_CONCURRENCY)

    async def one(reply: Reply) -> None:
        async with gate:
            started = time.monotonic()
            said = asked(reply.message) and await denies_live_data(
                settings, reply.message, reply.reply
            )
            outcomes[reply.id].seconds.append(time.monotonic() - started)
            outcomes[reply.id].retried.append(said)

    # A measurement is not the product's spend.
    with patch("app.gateways.llm_spend.meter_reported_cost", lambda *_args: None):
        for _ in range(runs):
            await asyncio.gather(*(one(reply) for reply in replies))
    return list(outcomes.values())


def rates(outcomes: list[Outcome], run: int) -> tuple[int, int, int, int]:
    """(denials caught, denials, others retried, others) in one run."""
    yes = [o for o in outcomes if o.reply.denies]
    no = [o for o in outcomes if not o.reply.denies]
    return (
        sum(o.retried[run] for o in yes),
        len(yes),
        sum(o.retried[run] for o in no),
        len(no),
    )


def _line(name: str, outcomes: list[Outcome], run: int) -> str:
    caught, denials, retried, others = rates(outcomes, run)
    return f"{name}: caught {caught}/{denials}  retried {retried}/{others}"


def report(outcomes: list[Outcome], runs: int) -> str:
    lines: list[str] = []
    held = [o for o in outcomes if o.reply.holdout]
    for run in range(runs):
        lines.append(_line(f"run {run + 1}", outcomes, run))
        lines.append("  " + _line("held-out", held, run))
    for area in sorted({o.reply.area for o in outcomes}):
        group = [o for o in outcomes if o.reply.area == area]
        lines.append("  " + _line(area, group, 0))
    seconds = sorted(s for o in outcomes for s in o.seconds)
    if seconds:
        p95 = seconds[min(len(seconds) - 1, int(len(seconds) * 0.95))]
        lines.append(f"check: p50 {statistics.median(seconds):.2f}s  p95 {p95:.2f}s")
    for outcome in outcomes:
        wrong = sum(said != outcome.reply.denies for said in outcome.retried)
        if wrong:
            label = "missed" if outcome.reply.denies else "retried"
            lines.append(
                f"  {label} {wrong}/{runs} [{outcome.reply.id}] {outcome.reply.reply[:90]!r}"
            )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--only", help="comma-separated reply ids")
    args = parser.parse_args()
    replies = load()
    if args.only:
        wanted = {item.strip() for item in args.only.split(",")}
        replies = [reply for reply in replies if reply.id in wanted]
    print(report(asyncio.run(measure(replies, args.runs)), args.runs))


if __name__ == "__main__":
    main()
