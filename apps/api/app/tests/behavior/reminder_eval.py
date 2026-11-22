"""Measure what a reminder turn comes to: the card, its time, one question, no false claim.

A script, not a test: it calls the real read models through the gateway (the Decider's
reminder question and the model that writes the request down), so it needs an OpenRouter key
in the environment and nothing else (no database; reminders are in memory, as the sweep's).

    python -m app.tests.behavior.reminder_eval --runs 2
    python -m app.tests.behavior.reminder_eval --no-read     # the word rules alone

Every turn of ``reminder_corpus.json`` is a user message, the chat before it and the reply a
model wrote (the live QA round of 2026-11-22 for the eight transcripts). It goes through the
real finalize on a frozen clock, Sunday 22 November 2026 at 10:00 in Los Angeles. ``card``
turns must end with a card due at one of ``due`` (the user's local time) whose title holds a
word of ``title``; ``ask`` turns ask one question and offer no card; ``none`` turns (look-alikes,
another language, "did it save?" after an untapped card) offer no card; ``no_repeat_ask`` turns
offer a card or ask no question of when. On every turn a reply with no card claims no
reminder, and above a card it claims none either.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from zoneinfo import ZoneInfo

CORPUS = Path(__file__).with_name("reminder_corpus.json")
ZONE = "America/Los_Angeles"
NOW = datetime(2026, 11, 22, 18, 0, tzinfo=UTC)
_CONCURRENCY = 6
# How long each model read of a request took.
READ_SECONDS: list[float] = []
_CARD_RE = re.compile(r"```reminder_proposal\n(.*?)\n```", re.S)
# A reply that says a reminder exists: judged on its own words, not by the app's reader.
_CLAIM_RE = re.compile(
    r"\b(?:i'?ve set|i have set|i'?ll remind you|i will remind you|i'?ll ping you|it'?s saved"
    r"|it is saved|it saved|reminders?'?s? (?:is |are )?(?:now )?set|is set for|you'?re all set"
    r"|all set|i'?ve added|added for|added —|got you covered|got it noted|is set\b|it'?s set"
    r"|set ✅|i'?ve scheduled|i scheduled|reminder added|you'?ll get (?:a|the) (?:ping|nudge"
    r"|notification))",
    re.I,
)
_NEGATED = re.compile(r"\b(?:not|n't|never|no reminder|tap)\b", re.I)


def load(path: Path = CORPUS) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = json.loads(path.read_text())
    return rows


def cards(text: str) -> list[dict[str, Any]]:
    found = []
    for body in _CARD_RE.findall(text):
        try:
            found.extend(json.loads(body).get("items", []))
        except json.JSONDecodeError:
            continue
    return found


def local(due: str) -> str:
    return datetime.fromisoformat(due).astimezone(ZoneInfo(ZONE)).strftime("%Y-%m-%dT%H:%M")


def claims(text: str) -> list[str]:
    prose = _CARD_RE.sub(" ", text)
    found = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n", prose):
        if _CLAIM_RE.search(sentence) and not _NEGATED.search(sentence):
            found.append(sentence.strip())
    return found


def judge(row: dict[str, Any], final: str) -> list[str]:
    """What went wrong on the turn; [] when it came out as the row expects."""
    items = cards(final)
    problems = [f"claims: {c!r}" for c in claims(final)]
    expect = row["expect"]
    if expect == "card":
        if not items:
            problems.append("no card")
        else:
            item = items[0]
            due = local(item["due_at"]) if item.get("due_at") else None
            if due not in row["due"]:
                problems.append(f"card at {due}, not {row['due'][0]}")
            title = item.get("title", "").lower()
            if not any(word in title for word in row["title"]):
                problems.append(f"card title {item.get('title')!r}")
            if row.get("repeat") and item.get("repeat") != row["repeat"]:
                problems.append(f"repeat {item.get('repeat')!r}")
    elif expect == "ask":
        if items:
            problems.append("card where a question was due")
        if "?" not in final:
            problems.append("asked nothing")
    elif expect == "none":
        if items:
            problems.append(f"look-alike card {items[0].get('title')!r}")
    elif expect == "no_repeat_ask" and not items and re.search(r"\bwhen\b", final, re.I):
        problems.append("asked when again")
    return problems


@contextmanager
def _clock() -> Iterator[None]:
    from app.tests.behavior import sweep

    with patch.object(sweep, "SWEEP_NOW", NOW), sweep.frozen_clock():
        yield


async def run_row(settings: Any, row: dict[str, Any], *, read: bool, lock: asyncio.Lock) -> str:
    """The row's reply through the real finalize, as the turn holds it. The reads run beside
    each other; finalize, which patches the in-memory reminders in, one turn at a time."""
    from app.modules.chat.finalize_passes import enrich_final_content
    from app.modules.chat.turn_deps import default_deps
    from app.modules.chat.turn_outcome import TurnOutcome
    from app.modules.chat.turn_prep import StreamContext
    from app.modules.conversation import messages_repository
    from app.tests.behavior import sweep
    from app.tests.behavior.harness import offline_pubchem

    user = replace_zone(sweep._user(pro=True))
    deps = replace(
        default_deps(),
        session_factory=sweep._session,
        users=SimpleNamespace(get_by_id=AsyncMock(return_value=user)),
    )
    history = [tuple(pair) for pair in row["history"]]
    rows = [SimpleNamespace(role=role, content=text) for role, text in history]
    ctx = StreamContext(
        user_id=user.id,
        chat_id=uuid4(),
        model="free-chat",
        prompt_messages=[
            *({"role": role, "content": text} for role, text in history),
            {"role": "user", "content": row["prompt"]},
        ],
        run_title=False,
        user_message_content=row["prompt"],
        reserved_tokens=0,
        max_output_tokens=0,
        user_timezone=ZONE,
        user=user,
    )
    ctx.recent_messages = [*rows, SimpleNamespace(role="user", content=row["prompt"])]
    outcome = sweep.Outcome(
        entry=sweep.Entry(id=row["id"], area="todo", prompt=row["prompt"], reply="")
    )
    if read:
        from app.modules.chat.reminder_turn import start_reminder_read

        ctx.reminder_read = start_reminder_read(settings, ctx)
        if ctx.reminder_read is not None:
            # The read runs beside the reply's stream, which takes longer than it: the reply
            # here is already written, so the read is waited for first, and timed.
            started = time.monotonic()
            await asyncio.wait([ctx.reminder_read.task])
            READ_SECONDS.append(time.monotonic() - started)
    async with lock:
        with (
            sweep._stores(outcome, user),
            offline_pubchem(),
            patch.object(
                messages_repository,
                "list_recent",
                AsyncMock(return_value=ctx.recent_messages),
            ),
        ):
            final: str = await enrich_final_content(
                deps,
                AsyncMock(),
                settings,
                ctx,
                assistant_text=row["reply"],
                usage={},
                outcome=TurnOutcome(),
                was_cancelled=False,
                should_cancel=None,
            )
    return final


def replace_zone(user: Any) -> Any:
    user.timezone = ZONE
    return user


async def measure(rows: list[dict[str, Any]], runs: int, *, read: bool) -> dict[str, list[Any]]:
    from app.core.config import Settings
    from app.tests.behavior.harness import battery_settings

    key = Settings().openrouter_api_key
    settings = battery_settings().model_copy(
        update={"openrouter_api_key": key, "mock_llm_enabled": False}
    )
    gate = asyncio.Semaphore(_CONCURRENCY)
    lock = asyncio.Lock()
    found: dict[str, list[Any]] = {row["id"]: [] for row in rows}

    async def one(row: dict[str, Any]) -> None:
        async with gate:
            final = await run_row(settings, row, read=read, lock=lock)
            found[row["id"]].append((judge(row, final), final))

    async def never_capped(*_args: Any, **_kwargs: Any) -> bool:
        return False

    # Imported before the clock is frozen, as the turn's modules are: a module the clock never
    # saw would read the real time. One frozen clock for every turn: entered per turn, the
    # turns running beside each other put the real clock back under each other.
    if read:
        from app.modules.chat import reminder_turn  # noqa: F401
        from app.modules.todos import bare_hour, model_read, read_check  # noqa: F401

    with patch("app.services.quota.global_spend_exceeded", never_capped), _clock():
        for _ in range(runs):
            await asyncio.gather(*(one(row) for row in rows))
    return found


def report(rows: list[dict[str, Any]], found: dict[str, list[Any]], *, show: bool) -> str:
    right: Counter[str] = Counter()
    seen: Counter[str] = Counter()
    tally: Counter[str] = Counter()
    misses: list[str] = []
    for row in rows:
        kind = row["expect"] if row["expect"] != "none" else f"none/{row.get('kind', '')}"
        for problems, final in found[row["id"]]:
            seen[kind] += 1
            if not problems:
                right[kind] += 1
            for problem in problems:
                tally[problem.split(":")[0].split(" at ")[0]] += 1
            if problems:
                line = f"  {row['id']:<22} {'; '.join(problems)}"
                misses.append(f"{line}\n      -> {final[:300]!r}" if show else line)
    total = sum(seen.values())
    lines = [f"{kind:<20} {right[kind]}/{seen[kind]}" for kind in sorted(seen)]
    lines.append(f"{'all':<20} {sum(right.values())}/{total}")
    lines.append("problems: " + ", ".join(f"{k} {v}" for k, v in tally.most_common()))
    if READ_SECONDS:
        ordered = sorted(READ_SECONDS)
        p50, p95 = ordered[len(ordered) // 2], ordered[int(len(ordered) * 0.95)]
        lines.append(f"model read: {len(ordered)} reads, p50 {p50:.2f} s, p95 {p95:.2f} s")
    return "\n".join([*lines, "misses:", *misses])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--no-read", action="store_true", help="the word rules alone")
    parser.add_argument("--only", default="", help="comma-separated row ids")
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()
    rows = load()
    if args.only:
        wanted = set(args.only.split(","))
        rows = [row for row in rows if row["id"] in wanted]
    found = asyncio.run(measure(rows, args.runs, read=not args.no_read))
    print(report(rows, found, show=args.show))


if __name__ == "__main__":
    main()
