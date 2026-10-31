"""Measure the model reader against today's pattern readers (docs/MODEL_READER.md).

A script, not a test: it calls the real model through the gateway (``apps/api/.env``).

    uv run python -m app.tests.behavior.reader_eval translate --per-subject 40
    uv run python -m app.tests.behavior.reader_eval run --langs en,am,es,fr,ar,hi
    uv run python -m app.tests.behavior.reader_eval books <sets dir>

``run`` reads every STEM corpus entry (and each translated copy) three ways and judges
each card with the sweep's own checks (``stem_sweep.check_answer``):

- ``regex``: the turn as it runs today (``stem_sweep.run_entry``, model mocked);
- ``model``: ``turn_reading.read_with_model`` and the same solvers;
- ``both``: a card only when the two agree on its value.

It prints, per subject and language: reach (cards on questions that have an answer),
wrong cards (a value the worked answer is not, or a number for a question with none),
the read's latency p50/p95, and tokens and cost per 1,000 turns. ``books`` runs the
Ethiopian textbook sets from a path (their answers are prose, so it counts reach and
agreement only). ``translate`` writes ``reader_corpus/<lang>.json``, keeping a translation
only when every number survives it.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.core.config import Settings
from app.models.model_catalog import CATALOG
from app.models.routing_lanes import ROUTING
from app.modules.turn_reading.checks import normalized, values_in
from app.modules.turn_reading.schemas import ModelRead
from app.modules.turn_reading.service import read_with_model
from app.tests.behavior.stem_sweep import (
    SUBJECT_NAMES,
    Entry,
    card_values,
    check_answer,
    load,
    run_entry,
)

CORPUS = Path(__file__).with_name("reader_corpus")
LANGUAGES = {
    "am": "Amharic",
    "es": "Spanish",
    "fr": "French",
    "ar": "Arabic",
    "hi": "Hindi",
}
_CONCURRENCY = 6


@dataclass
class Row:
    """One question read three ways."""

    subject: str
    lang: str
    entry: Entry
    regex_card: str | None = None
    regex_wrong: bool = False
    model: ModelRead | None = None
    model_card: str | None = None
    model_wrong: bool = False
    both_card: str | None = None
    both_wrong: bool = False


@dataclass
class Tally:
    rows: list[Row] = field(default_factory=list)

    def line(self, label: str) -> str:
        rows = self.rows
        answerable = [row for row in rows if row.entry.expect == "answer"]

        def reach(attr: str) -> str:
            return f"{sum(1 for row in answerable if getattr(row, attr))}/{len(answerable)}"

        def wrong(attr: str) -> int:
            return sum(1 for row in rows if getattr(row, attr))

        times = sorted(row.model.ms for row in rows if row.model is not None)
        p50 = statistics.median(times) if times else 0.0
        p95 = times[min(len(times) - 1, int(0.95 * len(times)))] if times else 0.0
        reads = [row.model for row in rows if row.model is not None]
        price = _prices()
        cost = (
            1000
            * sum(read.input_tokens * price[0] + read.output_tokens * price[1] for read in reads)
            / max(len(reads), 1)
            / 1e6
        )
        return (
            f"{label:<16} n={len(rows):<4} reach regex {reach('regex_card'):>8} "
            f"model {reach('model_card'):>8} both {reach('both_card'):>8} | wrong "
            f"{wrong('regex_wrong')}/{wrong('model_wrong')}/{wrong('both_wrong')} | "
            f"read p50 {p50 / 1000:.2f}s p95 {p95 / 1000:.2f}s | ${cost:.2f}/1k turns"
        )


def _prices() -> tuple[float, float]:
    entry = next(item for item in CATALOG if item.id == ROUTING.math_extract)
    return entry.input_price_per_m or 0.0, entry.output_price_per_m or 0.0


# --- the three reads ---------------------------------------------------------------


async def _regex(row: Row) -> None:
    """The turn as it runs today, judged as the sweep judges it."""
    entry = row.entry
    try:
        outcome = await run_entry(entry, SUBJECT_NAMES[row.subject])
    except Exception as exc:  # A crash is a finding, as in the sweep.
        print(f"regex crashed on {entry.id}: {type(exc).__name__}", file=sys.stderr)
        return
    route = outcome.route
    if route is not None and route.solved:
        row.regex_card = route.verified_answer or outcome.got or "card"
    row.regex_wrong = any(problem.kind == "wrong" for problem in outcome.problems)


def _solved(subject: str, intent: Any, settings: Settings) -> str | None:
    """The card the subject's solver gives the model's intent."""
    try:
        if subject == "physics":
            from app.modules.physics import build_verified_physics_block

            block: Any = build_verified_physics_block(intent, settings)
        elif subject == "chemistry":
            from app.modules.chemistry.block import build_verified_chemistry

            block = build_verified_chemistry(intent)
        else:
            from app.modules.math.tools.block import _build_verified_block

            block = _build_verified_block(intent, settings)
    except Exception as exc:
        print(f"solve crashed: {type(exc).__name__}", file=sys.stderr)
        return None
    if block is None:
        return None
    return getattr(block, "display_answer", None) or getattr(block, "canonical_answer", None)


def _judge(row: Row, card: str | None) -> bool:
    """A wrong card: a value the worked answer is not, or any card where none belongs."""
    if card is None:
        return False
    entry = row.entry
    if entry.expect != "answer":
        return True
    _got, problems = check_answer(entry, row.subject, f"```answer\n{card}\n```", whole=False)
    return any(problem.kind == "wrong" for problem in problems)


def _same_value(first: str, second: str) -> bool:
    one = card_values(f"```answer\n{first}\n```")
    two = card_values(f"```answer\n{second}\n```")
    if not one or not two:
        return first.strip() == second.strip()
    return abs(one[0][0] - two[0][0]) <= 1e-6 * max(abs(one[0][0]), abs(two[0][0]), 1e-12)


async def _model(row: Row, settings: Settings, gate: asyncio.Semaphore) -> None:
    async with gate:
        row.model = await read_with_model(row.entry.prompt, settings)


def _finish(row: Row, settings: Settings) -> None:
    read = row.model
    if read is not None and read.reason == "ok" and read.intent is not None and read.subject:
        row.model_card = _solved(read.subject, read.intent, settings)
        # A card read as another subject is the model's misread of this one.
        if read.subject != row.subject and row.entry.shared != read.subject:
            row.model_wrong = row.model_card is not None
        else:
            row.model_wrong = _judge(row, row.model_card)
    if row.regex_card and row.model_card and _same_value(row.regex_card, row.model_card):
        row.both_card = row.model_card
        row.both_wrong = row.model_wrong


# --- corpora -----------------------------------------------------------------------


def _sample(entries: list[Entry], count: int, seed: int) -> list[Entry]:
    """The same entries for the same seed: a measurement others can rerun."""
    chooser = random.Random(seed)  # noqa: S311 - a reproducible sample, not a secret
    return chooser.sample(entries, count)


def _translated(lang: str) -> list[tuple[str, Entry]]:
    path = CORPUS / f"{lang}.json"
    if not path.exists():
        return []
    originals = {(subject, entry.id): entry for subject in SUBJECT_NAMES for entry in load(subject)}
    found: list[tuple[str, Entry]] = []
    for item in json.loads(path.read_text()):
        entry = originals.get((item["subject"], item["id"]))
        if entry is not None:
            found.append((item["subject"], _with_prompt(entry, item["prompt"])))
    return found


def _with_prompt(entry: Entry, prompt: str) -> Entry:
    from dataclasses import replace

    return replace(entry, prompt=prompt, history=())


async def run(
    langs: list[str], subjects: list[str], limit: int | None, seed: int, call_seconds: float
) -> None:
    from app.core.sympy_executor import set_sympy_executor
    from app.tests.sympy_support import ThreadSympyExecutor

    set_sympy_executor(ThreadSympyExecutor(max_workers=1))
    settings = Settings(model_reader_timeout_seconds=call_seconds)
    rows: list[Row] = []
    for lang in langs:
        if lang == "en":
            for subject in subjects:
                entries = [entry for entry in load(subject) if not entry.history]
                if limit:
                    entries = _sample(entries, min(limit, len(entries)), seed)
                rows += [Row(subject, "en", entry) for entry in entries]
        else:
            rows += [
                Row(subject, lang, entry)
                for subject, entry in _translated(lang)
                if subject in subjects
            ]
    for row in rows:
        await _regex(row)
    gate = asyncio.Semaphore(_CONCURRENCY)
    await asyncio.gather(*(_model(row, settings, gate) for row in rows))
    for row in rows:
        _finish(row, settings)
    _report(rows, langs, subjects)


def _report(rows: list[Row], langs: list[str], subjects: list[str]) -> None:
    print("reach = cards on questions with an answer; wrong = regex/model/both")
    for lang in langs:
        for subject in subjects:
            picked = [row for row in rows if row.lang == lang and row.subject == subject]
            if picked:
                print(Tally(picked).line(f"{subject} {lang}"))
    reasons: dict[str, int] = {}
    for row in rows:
        if row.model is not None:
            reasons[row.model.reason] = reasons.get(row.model.reason, 0) + 1
    print("model read reasons:", json.dumps(dict(sorted(reasons.items()))))
    wrong = [row for row in rows if row.model_wrong]
    for row in wrong[:40]:
        read = row.model
        print(
            f"  model wrong {row.lang} {row.subject}:{row.entry.id} "
            f"op={read.op if read else None} card={row.model_card!r}"
        )


# --- books -------------------------------------------------------------------------


async def books(items: list[dict[str, Any]], call_seconds: float) -> None:
    """Reach and agreement on the Ethiopian textbook sets (answers are prose)."""
    settings = Settings(model_reader_timeout_seconds=call_seconds)
    gate = asyncio.Semaphore(_CONCURRENCY)
    subject_of = {"physics": "physics", "chemistry": "chemistry", "maths": "math", "math": "math"}
    reads: list[tuple[dict[str, Any], ModelRead]] = []

    async def one(item: dict[str, Any]) -> None:
        async with gate:
            reads.append((item, await read_with_model(item["question"], settings)))

    await asyncio.gather(*(one(item) for item in items))
    cards = 0
    by_subject: dict[str, list[int]] = {}
    for item, read in reads:
        subject = subject_of.get(str(item.get("subject", "")).lower(), "")
        card = (
            _solved(read.subject, read.intent, settings)
            if read.reason == "ok" and read.intent is not None and read.subject
            else None
        )
        counts = by_subject.setdefault(subject, [0, 0, 0])
        counts[0] += 1
        counts[1] += card is not None
        counts[2] += card is not None and read.subject == subject
        cards += card is not None
    print(f"books: {len(reads)} questions, {cards} model cards")
    for subject, (n, carded, same) in sorted(by_subject.items()):
        print(f"  {subject or '?':<10} n={n:<4} cards {carded} (in its own subject {same})")


# --- translate ---------------------------------------------------------------------


class _Translation(BaseModel):
    text: str = Field(max_length=2000)


def _numbers(text: str) -> list[float]:
    return sorted(values_in(normalized(text)))


async def translate(per_subject: int, seed: int) -> None:
    """Write ``reader_corpus/<lang>.json``: a sample of answerable entries per subject,
    translated, kept only when every number survives."""
    from app.gateways.structured_completion import complete_structured

    settings = Settings()
    CORPUS.mkdir(exist_ok=True)
    sample = [
        (subject, entry)
        for subject in SUBJECT_NAMES
        for entry in _sample(
            [entry for entry in load(subject) if entry.expect == "answer" and not entry.history],
            per_subject,
            seed,
        )
    ]
    gate = asyncio.Semaphore(_CONCURRENCY)

    async def one(subject: str, entry: Entry, language: str) -> dict[str, str] | None:
        async with gate:
            done = await complete_structured(
                settings=settings,
                model_alias="smart-chat",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            f"Translate the student's question into {language}, as a "
                            "textbook in that language would write it. Keep every number "
                            "and unit value exactly; write units the way that language's "
                            'textbooks do. Return JSON {"text": "<translation>"}.'
                        ),
                    },
                    {"role": "user", "content": entry.prompt},
                ],
                schema=_Translation,
                max_tokens=600,
                timeout_seconds=30,
            )
        if done is None or _numbers(done.text) != _numbers(entry.prompt):
            return None
        return {"subject": subject, "id": entry.id, "prompt": done.text}

    for lang, language in LANGUAGES.items():
        found = await asyncio.gather(*(one(subject, entry, language) for subject, entry in sample))
        kept = sorted(
            (item for item in found if item is not None),
            key=lambda item: (item["subject"], item["id"]),
        )
        (CORPUS / f"{lang}.json").write_text(json.dumps(kept, ensure_ascii=False, indent=1) + "\n")
        print(
            f"{lang}: kept {len(kept)}, dropped {len(found) - len(kept)} (a number did not survive)"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    run_parser = commands.add_parser("run")
    run_parser.add_argument("--langs", default="en," + ",".join(LANGUAGES))
    run_parser.add_argument("--subjects", default=",".join(SUBJECT_NAMES))
    run_parser.add_argument("--limit", type=int, help="English entries per subject (sampled)")
    run_parser.add_argument("--seed", type=int, default=7)
    # Each call's limit: production's is ``model_reader_timeout_seconds``; this measures
    # how long reads take, so it waits longer and reports p50/p95.
    run_parser.add_argument("--timeout", type=float, default=5.0)
    books_parser = commands.add_parser("books")
    books_parser.add_argument("path", type=Path)
    books_parser.add_argument("--timeout", type=float, default=5.0)
    translate_parser = commands.add_parser("translate")
    translate_parser.add_argument("--per-subject", type=int, default=40)
    translate_parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    if args.command == "run":
        langs, subjects = args.langs.split(","), args.subjects.split(",")
        asyncio.run(run(langs, subjects, args.limit, args.seed, args.timeout))
    elif args.command == "books":
        files = sorted(args.path.glob("*.json"))
        items = [item for file in files for item in json.loads(file.read_text())]
        asyncio.run(books(items, args.timeout))
    else:
        asyncio.run(translate(args.per_subject, args.seed))


if __name__ == "__main__":
    main()
