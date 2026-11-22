"""Measure how the turn's read takes a short reply to the assistant's last message.

A script, not a test: it calls the real read models through the gateway, so it needs an
OpenRouter key in the environment and nothing else (no database).

    python -m app.tests.behavior.follow_eval --runs 2

Every turn of ``follow_corpus.json`` is one texted reply ("yap", "nah", "the 2nd", "wdym",
"lol ok") after a reply of the assistant's, labelled with what it does to that reply:
accept an offer, decline it, pick one of its options, answer its question, ask for more,
ask what it meant, react to it, or stand alone (owner, 2026-11-21: "users usually answer
with a word, yes or no, yap, yep, or a phrase"). It prints how often the read names each
kind, and the turns it misses.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter, defaultdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

CORPUS = Path(__file__).with_name("follow_corpus.json")
_CONCURRENCY = 6


def load(path: Path = CORPUS) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = json.loads(path.read_text())
    return rows


async def measure(rows: list[dict[str, Any]], runs: int) -> dict[str, list[str | None]]:
    """Each turn's ``follow`` as the read gives it, ``runs`` times."""
    from app.core.config import Settings
    from app.modules.chat import turn_decision

    settings = Settings()
    found: dict[str, list[str | None]] = defaultdict(list)
    gate = asyncio.Semaphore(_CONCURRENCY)

    async def one(row: dict[str, Any]) -> None:
        async with gate:
            recent = [SimpleNamespace(role=role, content=text) for role, text in row["history"]]
            task = turn_decision.start_turn_decision(settings, row["prompt"], recent=recent)
            read = await task if task is not None else None
            found[row["id"]].append(None if read is None else read.follow)

    async def never_capped(*_args: Any, **_kwargs: Any) -> bool:
        return False

    with patch("app.services.quota.global_spend_exceeded", never_capped):
        for _ in range(runs):
            await asyncio.gather(*(one(row) for row in rows))
    return found


# The read's kinds before the short-reply kinds (2026-11-21), for a baseline: one "answer"
# for every reply to a question or an offer, "explain" for more of it, a reaction alone.
OLD_KINDS = {
    "accept": "answer",
    "decline": "answer",
    "pick": "answer",
    "more": "explain",
    "react": "none",
}


def report(
    rows: list[dict[str, Any]], found: dict[str, list[str | None]], *, old: bool = False
) -> str:
    if old:
        rows = [{**row, "follow": OLD_KINDS.get(row["follow"], row["follow"])} for row in rows]
    right: Counter[str] = Counter()
    seen: Counter[str] = Counter()
    misses: list[str] = []
    for row in rows:
        # A reply that is fairly either kind ("vegetarian" to "meat or vegetarian?" answers and
        # picks) names both; either is right.
        allowed = {row["follow"], *(OLD_KINDS.get(k, k) if old else k for k in row.get("also", ()))}
        part = "holdout" if row.get("holdout") else "tuned"
        for got in found[row["id"]]:
            seen[part] += 1
            seen[row["follow"]] += 1
            if got in allowed:
                right[part] += 1
                right[row["follow"]] += 1
            else:
                misses.append(f"  {row['id']:<16} {row['prompt']!r:<26} read {got}")
    lines = [
        f"{kind:<8} {right[kind]}/{seen[kind]} ({right[kind] / seen[kind]:.0%})"
        for kind in sorted(seen)
    ]
    return "\n".join([*lines, "misses:", *sorted(set(misses))])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--old", action="store_true", help="score the kinds before 2026-11-21")
    args = parser.parse_args()
    rows = load()
    print(report(rows, asyncio.run(measure(rows, args.runs)), old=args.old))


if __name__ == "__main__":
    main()
