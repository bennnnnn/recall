"""Measure what memory extraction saves: real facts kept, made-up and passing ones not.

A script, not a test: it calls the real memory model through the gateway, so it needs an
OpenRouter key in the environment, and nothing else (no database, no writes).

    python -m app.tests.behavior.memory_extract_eval --runs 2
    python -m app.tests.behavior.memory_extract_eval --extra private_cases.json --show

Each case of ``memory_extract_corpus.json`` is one live pass: the unread user lines, the
chat before them and the saved facts. It runs the way ``extraction_workflow`` runs it (the
small-talk skip, the model call, ``compose_writes``) and reads the facts it would write.

- ``expect``: keyword sets; each must be matched by a saved fact (every word of the set
  appears in it, any case). Recall is the share matched.
- ``optional``: sets a saved fact may match without counting either way.
- Every other saved fact is a false one. Precision is right facts over saved facts.

``--extra`` adds cases of the same shape from a file kept outside the repo (a user's own
chats are not committed).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CORPUS = Path(__file__).with_name("memory_extract_corpus.json")
_CONCURRENCY = 6


@dataclass
class Case:
    id: str
    lines: list[str]
    context: list[tuple[str, str]] = field(default_factory=list)
    existing: list[dict[str, str]] = field(default_factory=list)
    expect: list[list[str]] = field(default_factory=list)
    optional: list[list[str]] = field(default_factory=list)


@dataclass
class Score:
    saved: int = 0
    right: int = 0
    expected: int = 0
    found: int = 0
    false_facts: list[tuple[str, str]] = field(default_factory=list)
    missed: list[tuple[str, list[str]]] = field(default_factory=list)

    def add(self, other: Score) -> None:
        self.saved += other.saved
        self.right += other.right
        self.expected += other.expected
        self.found += other.found
        self.false_facts.extend(other.false_facts)
        self.missed.extend(other.missed)

    def line(self, label: str) -> str:
        precision = self.right / self.saved if self.saved else 1.0
        recall = self.found / self.expected if self.expected else 1.0
        return (
            f"{label}: precision {precision:.0%} ({self.right}/{self.saved} saved facts right), "
            f"recall {recall:.0%} ({self.found}/{self.expected} expected facts saved)"
        )


def _load(path: Path) -> list[Case]:
    raw = json.loads(path.read_text())
    items = raw["cases"] if isinstance(raw, dict) else raw
    cases: list[Case] = []
    for item in items:
        lines = [
            line[1] if isinstance(line, list) else line for line in item.get("lines", [])
        ]
        cases.append(
            Case(
                id=item["id"],
                lines=lines,
                context=[(role, text) for role, text in item.get("context", [])],
                existing=item.get("existing", []),
                expect=item.get("expect", []),
                optional=item.get("optional", []),
            )
        )
    return cases


def _matches(text: str, words: list[str]) -> bool:
    folded = text.casefold()
    return all(word.casefold() in folded for word in words)


def score_case(case: Case, saved: list[str]) -> Score:
    score = Score(saved=len(saved), expected=len(case.expect))
    for text in saved:
        if any(_matches(text, words) for words in case.expect + case.optional):
            score.right += 1
        else:
            score.false_facts.append((case.id, text))
    for words in case.expect:
        if any(_matches(text, words) for text in saved):
            score.found += 1
        else:
            score.missed.append((case.id, words))
    return score


async def saved_facts(settings: Any, case: Case) -> list[str]:
    """The texts one pass over ``case`` would add or rewrite (no database)."""
    from app.modules.memory import extract_backlog
    from app.modules.memory import llm as memory_llm
    from app.modules.memory.extraction_workflow import _small_talk
    from app.modules.memory.pass_writes import Asks, MemorySnapshot, compose_writes

    lines = extract_backlog.format_user_memory_transcript(case.lines)
    asks = Asks.of(lines)
    if not lines or _small_talk(lines, asks):
        return []
    prompt_facts = [
        {key: str(value) for key, value in fact.items() if value} for fact in case.existing
    ]
    snapshot = MemorySnapshot(
        memory_enabled=True,
        include_sensitive=True,
        existing_facts={uuid.uuid4(): fact["text"] for fact in case.existing},
        prompt_facts=prompt_facts,
        prompt_areas=[],
    )
    earlier = extract_backlog.format_context(case.context)
    result = await memory_llm.revise_memory_facts(
        settings,
        lines,
        existing_facts=prompt_facts,
        existing_areas=[],
        earlier=earlier,
        today="Thursday, Nov 19, 2026",
    )
    if result is None:
        return ["<model failed>"]
    writes, _ = compose_writes(
        snapshot,
        lines,
        asks,
        result.ops,
        chat_id=uuid.uuid4(),
        from_history=False,
        min_confidence=settings.memory_min_confidence,
        sources=extract_backlog.source_lines(
            [(uuid.uuid4(), text) for text in case.lines]
        ),
        earlier=earlier,
    )
    return [write.text for write in writes if write.op in {"add", "update", "supersede"}]


async def _run(cases: list[Case], settings: Any) -> dict[str, list[str]]:
    gate = asyncio.Semaphore(_CONCURRENCY)

    async def one(case: Case) -> tuple[str, list[str]]:
        async with gate:
            return case.id, await saved_facts(settings, case)

    return dict(await asyncio.gather(*(one(case) for case in cases)))


def _report(label: str, cases: list[Case], runs: list[dict[str, list[str]]], show: bool) -> None:
    total = Score()
    for saved in runs:
        for case in cases:
            total.add(score_case(case, saved.get(case.id, [])))
    print(total.line(f"{label} ({len(cases)} cases x {len(runs)} runs)"))
    if show:
        for case_id, text in total.false_facts:
            print(f"  false  {case_id}: {text}")
        for case_id, words in total.missed:
            print(f"  missed {case_id}: {' '.join(words)}")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--extra", type=Path, action="append", default=[])
    parser.add_argument("--only", default="", help="run case ids containing this text")
    parser.add_argument("--show", action="store_true", help="list false and missed facts")
    parser.add_argument("--out", type=Path, help="write every run's saved facts here")
    args = parser.parse_args()

    from app.core.config import Settings

    settings = Settings()
    sets = [("look-alikes", _load(CORPUS))] + [(path.stem, _load(path)) for path in args.extra]
    dump: dict[str, list[dict[str, list[str]]]] = {}
    for label, cases in sets:
        chosen = [case for case in cases if args.only in case.id]
        runs = [await _run(chosen, settings) for _ in range(args.runs)]
        _report(label, chosen, runs, args.show)
        dump[label] = runs
    if args.out:
        args.out.write_text(json.dumps(dump, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    asyncio.run(main())
