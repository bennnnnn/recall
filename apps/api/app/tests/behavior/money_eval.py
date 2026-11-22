"""Measure how money turns told over several lines get the server's numbers.

A script, not a test: it calls the real read models through the gateway, so it needs an
OpenRouter key in the environment and nothing else (no database).

    python -m app.tests.behavior.money_eval --runs 2

Every turn of ``money_corpus.json`` is a line after a chat, labelled with what the server
must make of it: ``request`` (a loan, card payoff or saving it works, with the values it
must work from; ``null`` for a value the user never gave, which the server assumes),
``ask`` (a request with no amount yet; ``or_ask`` and ``or_none`` take that too) or ``none`` (advice, a look-alike, another
subject: no calculator). It scores the word rules alone (``before``: ``read``,
``follow_up``, ``purchase``) and the turn as it runs now (``after``: the rules, then the
turn's read and, when it says money, the model's reading held to the chat,
``money.read_check``), and prints the turns each misses.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

CORPUS = Path(__file__).with_name("money_corpus.json")
_CONCURRENCY = 6


def load(path: Path = CORPUS) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = json.loads(path.read_text())
    return rows


def _rules(row: dict[str, Any]) -> Any:
    """The request the word rules read, or None."""
    from app.modules.money.follow_up import follow_up_request
    from app.modules.money.purchase import purchase_request
    from app.modules.money.read import read_money_request

    earlier = [(text,) for role, text in row["history"] if role == "user"]
    before = earlier[-1] if earlier else ()
    text = row["prompt"]
    return (
        follow_up_request(text, earlier)
        or read_money_request(text)
        or purchase_request(text, before)
    )


async def _after(row: dict[str, Any], settings: Any, model: str | None) -> tuple[Any, str]:
    """The request the turn makes now, and what the read said the message is about."""
    from app.modules.chat import turn_decision
    from app.modules.money.model_read import read_money_chat
    from app.modules.money.read_check import Chat, checked_request

    found = _rules(row)
    if found is not None:
        return found, "rules"
    recent = [SimpleNamespace(role=role, content=text) for role, text in row["history"]]
    task = turn_decision.start_turn_decision(settings, row["prompt"], recent=recent)
    read = await task if task is not None else None
    subject = getattr(read, "subject", None) or "no read"
    if subject != "money":
        return None, subject
    chat = [(role, text) for role, text in row["history"]]
    reading = await read_money_chat(settings, chat, row["prompt"], model_alias=model)
    if reading is None:
        return None, "money, no reading"
    lines = Chat(
        user_lines=[text for role, text in chat if role == "user"] + [row["prompt"]],
        replies=[text for role, text in chat if role == "assistant"][-1:],
    )
    return checked_request(reading, lines), f"money {reading.model_dump(by_alias=True)}"


def judge(row: dict[str, Any], request: Any) -> bool:
    from app.modules.money.read import sized

    expect = row["expect"]
    if row.get("or_ask") and request is not None and not sized(request):
        return True  # either reading is fair: what the income allows, or ask the amount
    if row.get("or_none") and request is None:
        return True  # nothing stated to work from: the reply's model asks for it
    if expect == "none":
        return request is None
    if request is None:
        return False
    if expect == "ask":
        return not sized(request)
    if row.get("products") and request.product.key not in row["products"]:
        return False
    for name, value in row["values"].items():
        got = request.values.get(name)
        if value is None and got is not None:
            return False
        if value is not None and (got is None or abs(got - value) > 1e-6):
            return False
    return True


async def measure(rows: list[dict[str, Any]], runs: int, model: str | None) -> dict[str, Any]:
    from app.core.config import Settings

    settings = Settings()
    gate = asyncio.Semaphore(_CONCURRENCY)
    found: dict[str, Any] = {row["id"]: {"before": [], "after": [], "why": []} for row in rows}

    async def one(row: dict[str, Any]) -> None:
        async with gate:
            request, why = await _after(row, settings, model)
        found[row["id"]]["after"].append(judge(row, request))
        found[row["id"]]["why"].append(why)
        found[row["id"]]["before"].append(judge(row, _rules(row)))

    async def never_capped(*_args: Any, **_kwargs: Any) -> bool:
        return False

    with patch("app.services.quota.global_spend_exceeded", never_capped):
        for _ in range(runs):
            await asyncio.gather(*(one(row) for row in rows))
    return found


def report(rows: list[dict[str, Any]], found: dict[str, Any]) -> str:
    right: Counter[str] = Counter()
    seen: Counter[str] = Counter()
    misses: list[str] = []
    for row in rows:
        kind = row["expect"]
        for when in ("before", "after"):
            for index, ok in enumerate(found[row["id"]][when]):
                seen[f"{when} {kind}"] += 1
                seen[when] += 1
                right[f"{when} {kind}"] += ok
                right[when] += ok
                if not ok and when == "after":
                    why = found[row["id"]]["why"][index]
                    misses.append(f"  {row['id']:<10} {row['prompt'][:40]!r:<44} {why}")
    lines = [
        f"{key:<16} {right[key]}/{seen[key]} ({right[key] / seen[key]:.0%})" for key in sorted(seen)
    ]
    return "\n".join([*lines, "misses (after):", *misses])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--model", default=None, help="the money read's alias (ROUTING.money_read)")
    args = parser.parse_args()
    rows = load()
    print(report(rows, asyncio.run(measure(rows, args.runs, args.model))))


if __name__ == "__main__":
    main()
