"""Measure checked physics answers on casual rewordings, before and after the cross-check.

A script, not a test: it calls the real models, so it needs an OpenRouter key in the
environment and nothing else (no database).

    python -m app.tests.behavior.cross_check_eval build --count 400
    python -m app.tests.behavior.cross_check_eval run

``build`` rewrites physics STEM corpus questions (one numeric answer each) the way students
type them, by a model other than the setup's reader, keeping every number, and saves them to
``formal_corpus/physics_casual.json`` (a rewording that drops or changes a number is asked
again, then left out). The QA round's three checked wrong answers (2026-11-22) are kept in it
too, under ``qa-``. ``run`` solves each offline as the chat turn does
(``physics.prompt.solve_or_say_why`` in the SymPy pool), then holds every checked answer to
the formal reader's reading (``physics.cross_check``) and counts, before and after:

- checked right: a checked card whose value is the corpus answer (1%, any unit of its kind);
- checked wrong: a checked card with another value, the one outcome to remove;
- unchecked: no checked card, the model's own reply (the eval does not grade it).

It also prints the reading's wait (median, p90, max), the checks lost on answers that were
right (the cost), and each checked wrong answer that stayed, with its verdict.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import re
import statistics
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import patch

from pydantic import BaseModel

HERE = Path(__file__).parent
CASUAL = HERE / "formal_corpus" / "physics_casual.json"
_CONCURRENCY = 6
# Not the setup's reader (``ROUTING.physics_setup``): its own wording would read easily.
_WRITER = "free-chat"
_SEED = 20261122

# The live QA round's three checked wrong answers (2026-11-22), with their worked answers.
QA_CASES: tuple[dict[str, Any], ...] = (
    {
        "id": "qa-braking-initial-speed",
        "prompt": "a car is slowing down at 3 m/s^2 for 4 s and at the end it is going 8 m/s. "
        "How fast was it going before it started braking?",
        "answer": [20.0, "m/s"],
    },
    {
        "id": "qa-kicked-sideways-vertical-velocity",
        "prompt": "a ball gets kicked sideways at 15 m/s off a 30 m cliff, whats its vertical "
        "velocity after 2 s?",
        "answer": [19.62, "m/s"],
    },
    {
        "id": "qa-thrown-sideways-speed",
        "prompt": "a ball gets thrown sideways at 10 m/s off a 20 m high cliff. whats its "
        "speed after 1 s?",
        "answer": [14.01, "m/s"],
    },
)

_STYLES = (
    "a tired student texting late at night, all lowercase, no punctuation",
    "a student who uses everyday words instead of physics words",
    "a confused student asking for help, with a short aside",
    "a student in a hurry, very short, abbreviations like u and pls",
    "a student telling it as a little story, values in a different order",
    "a parent helping with homework, plain words",
)

_REWRITE = (
    "You are {style}. Rewrite this homework question the way you would type it into a chat "
    "app on your phone, casually. Keep EVERY number and unit exactly as written, keep what "
    'is asked, and add no new number. Reply as JSON {{"message": "..."}}.\n\nQuestion: '
    "{prompt}"
)


class Rewrite(BaseModel):
    message: str = ""


_NUMBER = re.compile(r"\d+(?:\.\d+)?")
# A unit's power ("m/s^2") is no number of the question's.
_POWER = re.compile(r"\^\s*\{?-?\d+\}?")


def numbers_kept(original: str, rewritten: str) -> bool:
    """Every number of the question is in the rewording, and it adds none."""
    want = Counter(_NUMBER.findall(_POWER.sub("", original)))
    got = Counter(_NUMBER.findall(_POWER.sub("", rewritten)))
    return all(got[number] >= count for number, count in want.items()) and set(got) <= set(want)


def bank() -> list[dict[str, Any]]:
    """Physics corpus questions with one numeric answer, asked alone in English."""
    from app.tests.behavior.stem_sweep import load

    return [
        {"id": entry.id, "prompt": entry.prompt, "answer": list(entry.answers[0])}
        for entry in load("physics")
        if entry.expect == "answer"
        and len(entry.answers) == 1
        and not entry.parts
        and not entry.history
        and entry.locale == "en"
    ]


async def _never_capped(*_args: Any, **_kwargs: Any) -> bool:
    return False


async def build(count: int) -> None:
    from app.core.config import Settings
    from app.gateways.structured_completion import complete_structured

    settings = Settings()
    rows = bank()
    random.Random(_SEED).shuffle(rows)  # noqa: S311 - a fixed sample, not a secret
    picked = rows[:count]
    gate = asyncio.Semaphore(_CONCURRENCY)
    found: dict[str, dict[str, Any]] = {}

    async def one(index: int, row: dict[str, Any]) -> None:
        async with gate:
            for attempt in range(2):
                style = _STYLES[(index + attempt) % len(_STYLES)]
                reply = await complete_structured(
                    settings=settings,
                    model_alias=_WRITER,
                    messages=[
                        {
                            "role": "user",
                            "content": _REWRITE.format(style=style, prompt=row["prompt"]),
                        }
                    ],
                    schema=Rewrite,
                    max_tokens=300,
                    timeout_seconds=40,
                    allow_fallback=False,
                )
                text = reply.message.strip() if reply else ""
                if text and numbers_kept(row["prompt"], text):
                    found[row["id"]] = {
                        "id": f"{row['id']}-casual",
                        "source": row["id"],
                        "style": style,
                        "original": row["prompt"],
                        "prompt": text,
                        "answer": row["answer"],
                    }
                    return

    with patch("app.services.quota.global_spend_exceeded", _never_capped):
        await asyncio.gather(*(one(index, row) for index, row in enumerate(picked)))
    kept = [found[row["id"]] for row in picked if row["id"] in found]
    qa = [{**case, "source": case["id"], "style": "live QA", "original": ""} for case in QA_CASES]
    CASUAL.write_text(json.dumps(qa + kept, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(kept)} of {len(picked)} rewordings kept, plus {len(qa)} QA cases -> {CASUAL}")


# The setup's reader in the app (``ROUTING.physics_setup``), and a second one measured beside it.
_READERS = ("smart-chat", "free-chat")
_REPLY_MODELS = ("free-chat", "smart-chat", "qwen-3.7-flash")


@dataclass
class Row:
    item: dict[str, Any]
    outcome: str = ""
    # The checked card's value is the corpus answer; None when nothing was checked.
    right: bool | None = None
    answers: list[tuple[float, str]] = field(default_factory=list)
    # By reader: the verdict as the turn reaches it, the reading's own wait, what it read.
    verdicts: dict[str, str] = field(default_factory=dict)
    seconds: dict[str, float] = field(default_factory=dict)
    readings: dict[str, str] = field(default_factory=dict)
    # On a disagreement, what the student would get instead: each reply model's own answer,
    # and the server's value for the setup when its own answer agrees (right or not).
    replies: dict[str, bool | None] = field(default_factory=dict)
    server_right: bool | None = None

    @property
    def verdict(self) -> str:
        return self.verdicts.get(_READERS[0], "unread")


def load() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = json.loads(CASUAL.read_text(encoding="utf-8"))
    return items


def graded(answers: list[tuple[float, str]], want: list[Any]) -> bool:
    """A checked card is right when one of its values is the corpus answer."""
    from app.tests.behavior.stem_sweep import same_quantity

    target = (float(want[0]), str(want[1]))
    return any(same_quantity(answer, target)[0] for answer in answers)


def _solve(row: Row, settings: Any) -> Any:
    """The turn's solve, in this process: a script, one question at a time."""
    from app.modules.physics.cross_check import solver_answers
    from app.modules.physics.prompt import solve_or_say_why

    outcome, block, _why = solve_or_say_why(row.item["prompt"], settings, None)
    row.outcome = outcome
    if outcome != "verified" or block is None:
        return None
    row.answers = solver_answers(block)
    row.right = graded(row.answers, row.item["answer"])
    return block


async def _reading(
    row: Row, settings: Any, cache: dict[str, Any], alias: str
) -> dict[str, Any] | None:
    """One reader's formal reading of the question as JSON-ready data, from ``cache`` when
    kept."""
    from app.modules.physics.formal_read import formal_reading

    key = f"{row.item['id']}|{alias}"
    if key not in cache:
        started = time.monotonic()
        reading = await formal_reading(row.item["prompt"], settings, model_alias=alias)
        seconds = time.monotonic() - started
        cache[key] = (
            None
            if reading is None
            else {"setup": reading.setup.model_dump(), "result": reading.result, "seconds": seconds}
        )
    kept: dict[str, Any] | None = cache[key]
    return kept


async def _read(row: Row, settings: Any, cache: dict[str, Any], alias: str) -> None:
    """One reader's verdict as the turn reaches it, and the reading's own wait, uncapped."""
    from app.modules.physics.cross_check import reading_asks, verdict
    from app.services.formal.problem import FormalProblem

    kept = await _reading(row, settings, cache, alias)
    if kept is None:
        row.verdicts[alias], row.readings[alias] = "unread", "no read"
        return
    row.seconds[alias] = float(kept["seconds"])
    setup = FormalProblem.model_validate(kept["setup"])
    asks = reading_asks(setup, kept["result"])
    found = verdict(row.answers, asks)
    if row.seconds[alias] > settings.formal_wait_seconds:
        found = "unread"  # the turn stopped waiting: the check stands
    row.verdicts[alias] = found
    row.readings[alias] = "; ".join(
        ", ".join(f"{low:.4g}-{high:.4g}" for low, high in ask.values) + f" {ask.unit}"
        for ask in asks
    ) or str(kept["result"].get("reason") or "no value")
    agreed = [
        answer
        for answer in (kept["result"].get("answers") or [])
        if kept["result"].get("solved") and answer.get("agrees") is True
    ]
    if alias == _READERS[0] and agreed:
        row.server_right = graded(
            [(float(answer["value"]), str(answer["unit"])) for answer in agreed],
            row.item["answer"],
        )


async def _replies(row: Row, settings: Any, cache: dict[str, Any]) -> None:
    """Each reply model's own answer to a question whose check was dropped."""
    from app.tests.behavior.formal_eval import Question, model_alone

    want = (float(row.item["answer"][0]), str(row.item["answer"][1]))
    question = Question(row.item["id"], "casual", row.item["prompt"], want)
    for alias in _REPLY_MODELS:
        key = f"{row.item['id']}|reply|{alias}"
        if key not in cache:
            cache[key] = await model_alone(settings, alias, question)
        row.replies[alias] = cache[key]


async def run(limit: int, cache: dict[str, Any]) -> None:
    """Every question solved, its checked answers read, and the report printed. ``cache``
    holds the readings by question and reader, kept between runs by ``main``."""
    from app.core.config import Settings

    settings = Settings()
    items = load()[: limit or None]
    rows = [Row(item) for item in items]
    gate = asyncio.Semaphore(_CONCURRENCY)
    blocks = [(row, _solve(row, settings)) for row in rows]

    async def one(row: Row) -> None:
        async with gate:
            for alias in _READERS:
                await _read(row, settings, cache, alias)
            if "disagree" in row.verdicts.values():
                await _replies(row, settings, cache)

    with patch("app.services.quota.global_spend_exceeded", _never_capped):
        await asyncio.gather(*(one(row) for row, block in blocks if block is not None))
    print(report(rows))


# How a turn could decide from the readings: whether the check is dropped.
POLICIES: dict[str, Any] = {
    "before (no cross-check)": lambda row: False,
    "first reader": lambda row: row.verdicts.get(_READERS[0]) == "disagree",
    "first reader, unread drops": lambda row: row.verdicts.get(_READERS[0]) != "agree",
    "second reader alone": lambda row: row.verdicts.get(_READERS[1]) == "disagree",
    "either disagrees": lambda row: "disagree" in row.verdicts.values(),
    "first disagrees, second does not agree": lambda row: (
        row.verdicts.get(_READERS[0]) == "disagree" and row.verdicts.get(_READERS[1]) != "agree"
    ),
}


def _tally(rows: list[Row], dropped: Any) -> str:
    counts: Counter[str] = Counter()
    for row in rows:
        if row.outcome != "verified" or dropped(row):
            counts["unchecked"] += 1
        else:
            counts["right" if row.right else "wrong"] += 1
    return (
        f"checked right {counts['right']}, checked wrong {counts['wrong']}, "
        f"unchecked {counts['unchecked']} (of {len(rows)})"
    )


def report(rows: list[Row]) -> str:
    checked = [row for row in rows if row.outcome == "verified"]
    lines = [f"{name + ':':<42} {_tally(rows, dropped)}" for name, dropped in POLICIES.items()]
    for alias in _READERS:
        verdicts = Counter((row.verdicts.get(alias), row.right) for row in checked)
        lines.append(
            f"{alias} verdicts (verdict, solver right): "
            + ", ".join(f"{key}: {n}" for key, n in sorted(verdicts.items(), key=str))
        )
        waits = sorted(row.seconds[alias] for row in checked if alias in row.seconds)
        if waits:
            p90 = waits[min(len(waits) - 1, int(len(waits) * 0.9))]
            lines.append(
                f"{alias} reading wait: median {statistics.median(waits):.2f} s, p90 "
                f"{p90:.2f} s, max {waits[-1]:.2f} s ({len(waits)} reads)"
            )
    dropped = [row for row in checked if row.verdict == "disagree"]
    for alias in _REPLY_MODELS:
        counts = Counter(row.replies.get(alias) for row in dropped)
        lines.append(
            f"first reader's dropped checks, {alias} alone: right {counts[True]}, wrong "
            f"{counts[False]}, no number {counts[None]} (of {len(dropped)})"
        )
    server = Counter(row.server_right for row in dropped)
    lines.append(
        f"first reader's dropped checks, its server value: right {server[True]}, "
        f"wrong {server[False]}, none {server[None]}"
    )
    lines.append("checked wrong before (verdicts):")
    lines += [
        f"  {row.item['id']:<40} {row.verdicts} solver {row.answers} want "
        f"{row.item['answer']} | read {row.readings} | {row.item['prompt']!r}"
        for row in checked
        if not row.right
    ]
    lines.append("checks the first reader drops on right answers:")
    lines += [
        f"  {row.item['id']:<40} {row.verdicts} solver {row.answers} | read {row.readings} | "
        f"{row.item['prompt']!r}"
        for row in dropped
        if row.right
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("build").add_argument("--count", type=int, default=400)
    running = commands.add_parser("run")
    running.add_argument("--limit", type=int, default=0)
    running.add_argument("--readings", type=Path, help="keep the readings here, to rerun on them")
    args = parser.parse_args()
    if args.command == "build":
        asyncio.run(build(args.count))
    else:
        readings: Path | None = args.readings
        cache = json.loads(readings.read_text()) if readings and readings.exists() else {}
        asyncio.run(run(args.limit, cache))
        if readings is not None:
            readings.write_text(json.dumps(cache, default=str))


if __name__ == "__main__":
    main()
