"""Measure correct answers: today's app, the model alone, and the model's setup solved by the server.

A script, not a test: it calls the real models, so it needs an OpenRouter key.

    python -m app.tests.behavior.formal_eval --limit 0

The questions are the physics holdout's (``stem_corpus/physics/holdout.json``: written after
the fixes, never tuned on) with one numeric answer, and 30 of them in Spanish, French,
Amharic and Russian (``formal_corpus/physics_translated.json``). The measure is a correct
final number (1%, any unit of the same kind, ``stem_sweep.same_quantity``), not whether a
check stood behind it. Paths, for each reply model:

- today: the app's own solver when it answers, else the model alone;
- model: the reply model alone, asked for its final answer;
- formal: the setup a model writes (``physics.formal_read``) solved by the server
  (``services.formal.solve``), shown when the server's answer and the model's own agree;
  otherwise today's answer;
- formal+: as formal, and on a disagreement the stronger model writes the setup again.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel

HERE = Path(__file__).parent
HOLDOUT = HERE / "stem_corpus" / "physics" / "holdout.json"
TRANSLATED = HERE / "formal_corpus" / "physics_translated.json"
# Holdout questions reworded the way students type (casual, values reordered, an aside).
REWORDED = HERE / "formal_corpus" / "physics_reworded.json"
# 600 STEM corpus questions translated into Amharic, Arabic, Spanish, French and Hindi (40
# each of maths, physics and chemistry a language), from the model reader experiment: each
# entry names its corpus id, whose answer is the corpus's (``translated_questions``).
TRANSLATED_DIR = HERE / "formal_corpus" / "translated"


def translated_questions(subject: str) -> list[Question]:
    """The translated questions of one subject whose corpus entry has one numeric answer,
    each in a set named ``<locale>-reader``."""
    from app.tests.behavior.stem_sweep import load

    answers = {
        entry.id: entry.answers[0]
        for entry in load(subject)
        if entry.expect == "answer" and len(entry.answers) == 1 and not entry.parts
    }
    found: list[Question] = []
    for path in sorted(TRANSLATED_DIR.glob("*.json")):
        for item in json.loads(path.read_text(encoding="utf-8")):
            if item["subject"] == subject and item["id"] in answers:
                found.append(
                    Question(
                        f"{item['id']}-{path.stem}",
                        f"{path.stem}-reader",
                        item["prompt"],
                        answers[item["id"]],
                    )
                )
    return found


_CONCURRENCY = 6
READERS = ("gpt-6-luna", "smart-chat")
REPLIES = ("qwen-3.7-flash", "smart-chat")


class FinalAnswer(BaseModel):
    value: float | None = None
    unit: str = ""


@dataclass
class Question:
    id: str
    set: str
    prompt: str
    answer: tuple[float, str]


@dataclass
class Row:
    question: Question
    today_solved: bool | None = None  # the app's own solver answered (None: not run)
    today_right: bool | None = None
    model: dict[str, bool | None] = field(default_factory=dict)  # None: no number
    # The reply model's own final answer, as (value, unit), for the disagreement table.
    model_answer: dict[str, tuple[float | None, str]] = field(default_factory=dict)
    formal: dict[str, dict[str, Any]] = field(default_factory=dict)


def questions(limit: int) -> list[Question]:
    english = [
        Question(e["id"], "en", e["prompt"], (float(e["answer"][0]), str(e["answer"][1])))
        for e in json.loads(HOLDOUT.read_text(encoding="utf-8"))
        if e["expect"] == "answer" and e.get("answer")
    ]
    translated = [
        Question(t["id"], t["locale"], t["prompt"], (float(t["answer"][0]), str(t["answer"][1])))
        for t in json.loads(TRANSLATED.read_text(encoding="utf-8"))
    ]
    reworded = [
        Question(r["id"], "en-reworded", r["prompt"], (float(r["answer"][0]), str(r["answer"][1])))
        for r in json.loads(REWORDED.read_text(encoding="utf-8"))
    ]
    reader = translated_questions("physics")
    if limit:
        english, translated, reworded = english[:limit], translated[: limit * 4], reworded[:limit]
        reader = reader[: limit * 5]
    return english + reworded + translated + reader


def right(value: float | None, unit: str, want: tuple[float, str]) -> bool | None:
    from app.tests.behavior.stem_sweep import same_quantity

    if value is None:
        return None
    ok, detail = same_quantity((value, unit), want)
    if not ok and "UndefinedUnitError" in detail:
        # A unit in the question's own script (Cyrillic m/s): judged on its number alone, in the
        # unit the answer key uses (the eval's grading, not what a reply would be held to).
        return math.isclose(abs(value), abs(want[0]), rel_tol=0.01)
    return ok


async def today(question: Question) -> tuple[bool, bool | None]:
    """(the app's solver answered, its answer is right) on the offline chat path."""
    from app.tests.behavior.stem_sweep import Entry, run_entry

    entry = Entry(
        id=question.id,
        area="formal",
        prompt=question.prompt,
        expect="answer",
        answers=(question.answer,),
        locale=question.set if question.set != "en" else "en",
    )
    outcome = await run_entry(entry, "physics")
    kinds = {p.kind for p in outcome.problems}
    if "unsolved" in kinds or "missed" in kinds:
        return False, None
    return True, "wrong" not in kinds


async def model_alone(
    settings: Any, alias: str, question: Question, row: Row | None = None
) -> bool | None:
    from app.gateways.structured_completion import complete_structured

    reply = await complete_structured(
        settings=settings,
        model_alias=alias,
        messages=[
            {
                "role": "system",
                "content": "Solve the student's physics question. Reply as JSON "
                '{"value": <the final numeric answer>, "unit": "<its unit, in standard '
                'symbols, in the unit the question asks for>"}.',
            },
            {"role": "user", "content": question.prompt},
        ],
        schema=FinalAnswer,
        max_tokens=1500,
        timeout_seconds=60,
        allow_fallback=False,
    )
    if row is not None:
        row.model_answer[alias] = (reply.value, reply.unit) if reply else (None, "")
    return right(reply.value, reply.unit, question.answer) if reply else None


async def formal(settings: Any, alias: str, question: Question) -> dict[str, Any]:
    import time

    from app.core.sympy_executor import run_sympy
    from app.models.model_catalog import estimate_cost_usd
    from app.modules.physics.formal_read import read_physics_setup
    from app.services.formal.solve import solve_formal

    usage: dict[str, int] = {}
    started = time.monotonic()
    setup = await read_physics_setup(settings, question.prompt, model_alias=alias, usage=usage)
    seconds = time.monotonic() - started
    cost = estimate_cost_usd(
        alias, input_tokens=usage.get("input", 0), output_tokens=usage.get("output", 0)
    )
    timing = {"seconds": seconds, "cost": cost or 0.0, "tokens": dict(usage)}
    if setup is None:
        return {"solved": False, "reason": "no read", **timing}
    try:
        result = json.loads(
            await run_sympy(solve_formal, setup.model_dump_json(), question.prompt, timeout=10)
        )
    except Exception as exc:
        return {"solved": False, "reason": f"solve {type(exc).__name__}"}
    model_right = right(setup.answer, setup.target_unit, question.answer)
    result["model_right"] = model_right
    result.update(timing)
    if result["solved"]:
        result["right"] = right(result["value"], result["unit"], question.answer)
    return result


def choose(row: Row, reply: str, reader: str, escalate: bool) -> bool | None:
    """The answer a student would get on a path: True right, False wrong, None no number."""
    fallback = row.today_right if row.today_solved else row.model.get(reply)
    if row.today_solved:
        return row.today_right
    first = row.formal.get(reader, {})
    if first.get("solved") and first.get("agrees"):
        return bool(first.get("right"))
    if escalate and first.get("solved") and not first.get("agrees"):
        second = row.formal.get(READERS[-1], {})
        if second.get("solved") and second.get("agrees"):
            return bool(second.get("right"))
    return fallback


async def run(limit: int, sets: set[str] | None = None) -> None:
    from app.core.config import get_settings

    settings = get_settings()
    rows = [Row(q) for q in questions(limit) if not sets or q.set in sets]
    gate = asyncio.Semaphore(_CONCURRENCY)

    async def fill(row: Row) -> None:
        async with gate:
            for alias in REPLIES:
                row.model[alias] = await model_alone(settings, alias, row.question, row)
            for alias in READERS:
                row.formal[alias] = await formal(settings, alias, row.question)

    for row in rows:  # the harness patches module state: one question at a time
        row.today_solved, row.today_right = await today(row.question)
    await asyncio.gather(*(fill(row) for row in rows))
    report(rows)
    disagreements(rows)
    costs(rows)


def _tally(outcomes: list[bool | None]) -> str:
    counts = Counter(outcomes)
    total = len(outcomes) or 1
    return (
        f"{counts[True]:3d} right ({counts[True] / total:4.0%}), {counts[False]:2d} wrong, "
        f"{counts[None]:2d} none"
    )


def report(rows: list[Row]) -> None:
    sets = sorted({r.question.set for r in rows}, key=lambda s: (not s.startswith("en"), s))
    for name in [*sets, "all"]:
        group = [r for r in rows if name in {"all", r.question.set}]
        print(f"\n== {name} ({len(group)} questions)")
        solved = sum(1 for r in group if r.today_solved)
        print(f"  app's solver answered {solved}/{len(group)}")
        for reply in REPLIES:
            print(f"  model alone {reply:15}: {_tally([r.model.get(reply) for r in group])}")
            today_answers = [r.today_right if r.today_solved else r.model.get(reply) for r in group]
            print(f"  today       {reply:15}: {_tally(today_answers)}")
            for reader in READERS:
                print(
                    f"  formal {reader:10} {reply:15}: "
                    f"{_tally([choose(r, reply, reader, False) for r in group])}"
                )
            print(
                f"  formal+ escalate   {reply:15}: "
                f"{_tally([choose(r, reply, READERS[0], True) for r in group])}"
            )
        for reader in READERS:
            results = [r.formal.get(reader, {}) for r in group]
            solved_n = sum(1 for x in results if x.get("solved"))
            agree = [x for x in results if x.get("solved") and x.get("agrees")]
            wrong_agree = sum(1 for x in agree if not x.get("right"))
            reasons = Counter(x.get("reason", "") for x in results if not x.get("solved"))
            print(
                f"  setup {reader}: solved {solved_n}, agreed {len(agree)} "
                f"(wrong while agreeing {wrong_agree}); refused: {dict(reasons.most_common(6))}"
            )
    misses = [r for r in rows if choose(r, REPLIES[0], READERS[0], True) is not True]
    print("\nwrong or none on formal+ (qwen):")
    for r in misses[:40]:
        f = r.formal.get(READERS[0], {})
        print(
            f"  {r.question.id}: {f.get('reason') or ('agrees' if f.get('agrees') else 'disagrees')} | {r.question.prompt[:70]}"
        )


def _same(value: float, unit: str, other: tuple[float | None, str]) -> bool | None:
    """Whether the reply model's answer is the server's (1%, any unit of the same kind)."""
    from app.tests.behavior.stem_sweep import same_quantity

    if other[0] is None:
        return None
    ok, detail = same_quantity((other[0], other[1]), (value, unit))
    if not ok and "UndefinedUnitError" in detail:
        return math.isclose(abs(other[0]), abs(value), rel_tol=0.01)
    return ok


def disagreements(rows: list[Row]) -> None:
    """Where the server's answer and the reply model's differ, who was right.

    Only turns the app's own solver did not answer: the rest never ask the server. A server
    answer counts when its setup's own answer agreed with it (the answer finalize would use);
    the setups that disagreed with themselves are listed apart."""
    for reader in READERS:
        for reply in REPLIES:
            tally: Counter[str] = Counter()
            cases: list[str] = []
            for row in rows:
                if row.today_solved:
                    continue
                formal_result = row.formal.get(reader, {})
                if not formal_result.get("solved"):
                    tally["server: no answer"] += 1
                    continue
                accepted = "accepted" if formal_result.get("agrees") else "self-disagreeing"
                same = _same(
                    formal_result["value"],
                    formal_result["unit"],
                    row.model_answer.get(reply, (None, "")),
                )
                if same is None:
                    tally[f"{accepted}: reply gave no number"] += 1
                    continue
                if same:
                    tally[f"{accepted}: same answer"] += 1
                    continue
                server_right = bool(formal_result.get("right"))
                model_right = bool(row.model.get(reply))
                verdict = (
                    "server right"
                    if server_right and not model_right
                    else "reply right"
                    if model_right and not server_right
                    else "both wrong"
                    if not server_right
                    else "both right"
                )
                tally[f"{accepted}: differ, {verdict}"] += 1
                cases.append(
                    f"    {accepted:16} {verdict:12} {row.question.id}: server "
                    f"{formal_result['value']:.4g} {formal_result['unit']}, reply "
                    f"{row.model_answer[reply][0]:.4g} {row.model_answer[reply][1]}, "
                    f"want {row.question.answer[0]:.4g} {row.question.answer[1]}"
                )
            print(f"\n== disagreements: setup by {reader}, reply by {reply}")
            for key, count in sorted(tally.items()):
                print(f"  {key}: {count}")
            print("\n".join(cases))


def costs(rows: list[Row]) -> None:
    """The setup read's wait and price, per reader, over the turns that would ask it."""
    import statistics

    for reader in READERS:
        asked = [r.formal.get(reader, {}) for r in rows if not r.today_solved]
        seconds = sorted(x.get("seconds", 0.0) for x in asked if "seconds" in x)
        prices = [x.get("cost", 0.0) for x in asked if "seconds" in x]
        if not seconds:
            continue
        p90 = seconds[int(0.9 * (len(seconds) - 1))]
        print(
            f"\n== cost, setup by {reader} ({len(seconds)} turns): median "
            f"{statistics.median(seconds):.2f} s, p90 {p90:.2f} s, max {seconds[-1]:.2f} s; "
            f"mean ${statistics.mean(prices) * 1000:.3f} per 1,000 turns"
            f" (${statistics.mean(prices):.6f} a turn)"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, default=0, help="questions per set; 0 for all")
    parser.add_argument("--sets", default="", help="comma-separated: en,en-reworded,es,fr,am,ru")
    args = parser.parse_args()
    asyncio.run(run(args.limit, {s for s in args.sets.split(",") if s} or None))


if __name__ == "__main__":
    main()
