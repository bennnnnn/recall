"""Measure the second opinion (``chat.second_opinion``) on real model replies.

A script, not a test: it calls the real models through the gateway (``apps/api/.env``).

    uv run python -m app.tests.behavior.second_opinion_eval --solved 40 --dump rows.jsonl

Each question runs the real turn path offline (``harness.route_case``) for its prompt, then:

- the turn's model answers that prompt (the reply a student would read);
- the model reader reads the question and the subject's solver solves the read;
- the two are compared; on a conflict the stronger model answers once more, and the
  reply it would keep is chosen as the turn would choose it.

Questions come from the STEM corpus: every ``answer`` entry the server does not answer
today (the turns the second opinion runs on), and with ``--solved N`` a sample of N per
subject that it does answer, routed with the solvers off so the model answers alone, as
it would on a question no solver reads. Both replies, the first and the chosen, are judged
with the sweep's own check (``stem_sweep.check_answer``) on the card the turn would show.
It prints how often it flags, how often a flag was a real error, and how many answers got
better or worse, with the time it adds.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import statistics
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.core.sympy_executor import run_sympy, set_sympy_executor
from app.gateways import litellm_gateway
from app.models.routing_lanes import ROUTING
from app.modules.chat.second_opinion import shown_reply
from app.modules.model_reader.service import read_with_model
from app.modules.model_reader.solve import read_card
from app.services.answer_check import stated_verdict
from app.tests.behavior.harness import Case, Expect, battery_settings, route_case
from app.tests.behavior.stem_sweep import SUBJECT_NAMES, Entry, load
from app.tests.sympy_support import ThreadSympyExecutor

_SNAPSHOT = Path(__file__).with_name("stem_snapshot.json")
_CONCURRENCY = 4


@dataclass
class Row:
    subject: str
    entry: Entry
    solved_today: bool
    first: str = ""
    card: str | None = None
    verdict: str = ""
    redo: str = ""
    chosen: str = "original"
    first_right: bool | None = None
    final_right: bool | None = None
    added_ms: float = 0.0
    error: str = ""
    notes: dict[str, Any] = field(default_factory=dict)


def _right(row: Row, text: str) -> bool | None:
    """Whether the reply's final value is a worked answer (None: it states none plainly).

    Judged as the turn judges, with ``stated_verdict``: within the precision the reply
    gives, in any prefix of the answer's unit."""
    verdicts = {
        stated_verdict(text, f"{value} {unit}".strip()) for value, unit in row.entry.answers
    }
    if verdicts & {"same", "rounded"}:
        return True
    return False if "conflict" in verdicts else None


async def _reply(
    settings: Settings, alias: str, messages: list[dict[str, Any]], max_tokens: int, layout: Any
) -> str:
    """A model's reply as the phone is sent it (a ```worked block laid out)."""
    tokens = [
        token
        async for token in litellm_gateway.stream_chat_completion(
            settings=settings, model_alias=alias, messages=messages, max_tokens=max_tokens
        )
    ]
    return shown_reply(tokens, layout).strip()


async def _one(row: Row, live: Settings, gate: asyncio.Semaphore) -> None:
    async with gate:
        try:
            routing = battery_settings()
            if row.solved_today:
                routing = routing.model_copy(
                    update={"math_tools_enabled": False, "chemistry_enabled": False}
                )
            entry = row.entry
            route = await route_case(
                Case(entry.id, entry.area, entry.prompt, Expect(), "", locale=entry.locale),
                routing,
            )
            ctx = route.context
            messages = [dict(message) for message in ctx.prompt_messages]
            # Offline the history is stubbed: production's recent messages hold the question.
            if not messages or messages[-1].get("role") != "user":
                messages.append({"role": "user", "content": entry.prompt})
            limit = max(int(ctx.max_output_tokens or 0), 1200)
            read_task = asyncio.create_task(read_with_model(entry.prompt, live))
            row.first = await _reply(live, route.model or ctx.model, messages, limit, ctx.worked)
            started = time.perf_counter()
            read = await read_task
            row.notes["read"] = read.reason
            row.card = await run_sympy(read_card, read, live, timeout=10.0) if read.intent else None
            if row.card is None:
                row.verdict = "no_read"
            else:
                verdict = stated_verdict(row.first, row.card)
                row.verdict = {"same": "agree", "rounded": "agree"}.get(verdict, verdict)
                if verdict == "conflict":
                    row.redo = await _reply(live, ROUTING.hard, messages, limit, ctx.worked)
                    if stated_verdict(row.redo, row.card) in {"same", "rounded"}:
                        row.chosen = "redo"
            row.added_ms = round((time.perf_counter() - started) * 1000, 1)
            row.first_right = _right(row, row.first)
            row.final_right = _right(row, row.redo if row.chosen == "redo" else row.first)
        except Exception as exc:  # A crash is a finding.
            row.error = f"{type(exc).__name__}: {exc}"[:200]


def _rows(solved: int, seed: int) -> list[Row]:
    snapshot = json.loads(_SNAPSHOT.read_text())
    rows: list[Row] = []
    rng = random.Random(seed)  # noqa: S311 - a sample, not a secret
    for subject in SUBJECT_NAMES:
        answered = set(snapshot.get(subject, {}).get("answered", []))
        # One worked value to judge against: parts and prose answers are another measure.
        entries = [
            e
            for e in load(subject)
            if e.expect == "answer" and not e.history and e.answers and not e.parts
        ]
        rows += [Row(subject, e, False) for e in entries if e.id not in answered]
        pool = [e for e in entries if e.id in answered]
        rows += [Row(subject, e, True) for e in rng.sample(pool, min(solved, len(pool)))]
    return rows


def _report(rows: list[Row]) -> None:
    for label, group in (
        ("unsolved today", [r for r in rows if not r.solved_today]),
        ("solvers off", [r for r in rows if r.solved_today]),
        ("all", rows),
    ):
        done = [r for r in group if not r.error]
        flagged = [r for r in done if r.verdict == "conflict"]
        replaced = [r for r in flagged if r.chosen == "redo"]
        better = [r for r in replaced if r.first_right is False and r.final_right]
        worse = [r for r in replaced if r.first_right and r.final_right is False]
        true_flags = [r for r in flagged if r.first_right is False]
        wrong_first = [r for r in done if r.first_right is False]
        wrong_final = [r for r in done if r.final_right is False]
        added = [r.added_ms for r in done if r.verdict != "no_read"]
        print(f"\n== {label}: {len(done)} questions ({len(group) - len(done)} errors)")
        print(
            "   verdicts: "
            + ", ".join(
                f"{v}={sum(r.verdict == v for r in done)}"
                for v in ("agree", "conflict", "absent", "unknown", "no_read")
            )
        )
        print(
            f"   flagged {len(flagged)}; of those the first answer was really wrong: {len(true_flags)}"
        )
        print(f"   replaced {len(replaced)}: better {len(better)}, worse {len(worse)}")
        print(f"   wrong answers: first {len(wrong_first)} -> final {len(wrong_final)}")
        if added:
            p95 = sorted(added)[int(0.95 * (len(added) - 1))]
            print(
                f"   time after the reply: p50 {statistics.median(added):.0f} ms, p95 {p95:.0f} ms"
            )


async def main(solved: int, seed: int, dump: Path | None) -> None:
    set_sympy_executor(ThreadSympyExecutor(max_workers=_CONCURRENCY + 1))
    live = Settings(model_reader_timeout_seconds=5.0)
    rows = _rows(solved, seed)
    print(f"{len(rows)} questions")
    gate = asyncio.Semaphore(_CONCURRENCY)
    await asyncio.gather(*(_one(row, live, gate) for row in rows))
    _report(rows)
    if dump is not None:
        with dump.open("w") as handle:
            for row in rows:
                data = asdict(row)
                data["entry"] = {
                    "id": row.entry.id,
                    "prompt": row.entry.prompt,
                    "answers": row.entry.answers,
                }
                handle.write(json.dumps(data, default=str) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--solved", type=int, default=0, help="answered entries per subject, solvers off"
    )
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--dump", type=Path)
    args = parser.parse_args()
    asyncio.run(main(args.solved, args.seed, args.dump))
