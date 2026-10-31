"""Translate, then read with the patterns, measured (docs/MODEL_READER.md).

A script, not a test: it calls the real models through the gateway (``apps/api/.env``).

    uv run python -m app.tests.behavior.reader_translate run --books <sets> --dump t.jsonl
    uv run python -m app.tests.behavior.reader_translate recheck t.jsonl

``run`` puts every question of ``reader_corpus/<lang>.json`` (and, with ``--books``, textbook
sets in another language) into English twice, with two companies' models
(``ROUTING.reader_translation`` and ``reader_translation_check``), and reads each English
with today's patterns (``stem_sweep.run_entry``), judged as the sweep judges. Per subject
and language it prints the patterns on the original, then four ways of keeping the English:

- ``numbers``: ``check_translation`` with no ask check (values, signs, units);
- ``ask``: and the same kind of quantity asked, when the tables read the original's ask;
- ``strict``: and an original whose ask the tables cannot read is refused;
- ``agree``: ``strict``, and the second model's English (also ``strict``) reads to the same
  solve: the same operation and the same card.

``recheck`` repeats the checks and the pattern reads on a dump's translations, with no
model call: for changing a check and measuring it again.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.models.routing_lanes import ROUTING
from app.modules.chemistry.given_units import CHEMISTRY_UNITS
from app.modules.model_reader.translation import (
    Translated,
    TranslationReason,
    check_translation,
    english_for_patterns,
)
from app.modules.physics import PHYSICS_UNITS
from app.tests.behavior.decisions import decision_record
from app.tests.behavior.reader_eval import (
    _CONCURRENCY,
    LANGUAGES,
    Row,
    _book_rows,
    _prices,
    _read_sets,
    _regex,
    _translated,
    _with_prompt,
)
from app.tests.behavior.stem_sweep import SUBJECT_NAMES, Entry, run_entry

_TABLES = (PHYSICS_UNITS, CHEMISTRY_UNITS)
_MODES = ("numbers", "ask", "strict")
_MODELS = (ROUTING.reader_translation, ROUTING.reader_translation_check)


@dataclass
class English:
    """One model's English for a question, how each check mode judged it, and its read."""

    candidate: str | None
    ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    reasons: dict[str, TranslationReason] = field(default_factory=dict)
    card: str | None = None
    wrong: bool = False
    op: str | None = None

    def kept(self, mode: str) -> bool:
        return self.reasons.get(mode) == "ok"


@dataclass
class Question:
    row: Row
    language: str
    english: list[English] = field(default_factory=list)

    def card(self, mode: str) -> tuple[str | None, bool]:
        """The card this mode shows, and whether it is wrong."""
        if mode == "agree":
            first, second = [*self.english, English(None), English(None)][:2]
            if not (first.kept("strict") and second.kept("strict")):
                return None, False
            if first.op != second.op or first.card != second.card:
                return None, False
            return first.card, first.wrong
        first = self.english[0] if self.english else English(None)
        return (first.card, first.wrong) if first.kept(mode) else (None, False)


async def _read(question: Question, english: English) -> None:
    """Today's turn on the English, if any mode keeps it."""
    if english.candidate is None or not english.kept("numbers"):
        return
    entry = _with_prompt(question.row.entry, english.candidate)
    try:
        outcome = await run_entry(entry, SUBJECT_NAMES[question.row.subject])
    except Exception as exc:  # A crash is a finding, as in the sweep.
        print(f"patterns crashed on {entry.id}: {type(exc).__name__}", file=sys.stderr)
        return
    route = outcome.route
    if route is not None and route.solved:
        english.card = route.verified_answer or outcome.got or "card"
        solver = decision_record(route).get("solver") or {}
        english.op = solver.get("op") if isinstance(solver, dict) else None
    english.wrong = any(problem.kind == "wrong" for problem in outcome.problems)


def _judge(question: Question, english: English) -> None:
    original = question.row.entry.prompt
    if english.candidate is None:
        english.reasons = dict.fromkeys(_MODES, "no_read")
        return
    english.reasons = {
        "numbers": check_translation(
            original, english.candidate, _TABLES, question.language, ask="off"
        ),
        "ask": check_translation(
            original, english.candidate, _TABLES, question.language, ask="lenient"
        ),
        "strict": check_translation(original, english.candidate, _TABLES, question.language),
    }


def _language(lang: str) -> str:
    return lang.split("-", 1)[1] if lang.startswith(("book-", "heldout-")) else lang


HELDOUT = Path(__file__).with_name("reader_corpus") / "heldout.json"


def heldout_entries() -> list[tuple[str, str, Entry, str]]:
    """The held-out questions, written naturally by a reviewer after the tables were filled
    (2026-10-31): (language, subject, the original, its faithful English)."""
    found: list[tuple[str, str, Entry, str]] = []
    for raw in json.loads(HELDOUT.read_text()):
        check = raw.get("check")
        answers = (tuple(raw["answer"]),) if raw.get("answer") else ()
        entry = Entry(
            raw["id"],
            "heldout",
            raw["prompt"],
            "answer",
            answers=tuple((float(value), str(unit)) for value, unit in answers),
            check=(check[0], check[1]) if check else None,
        )
        found.append((raw["lang"], raw["subject"], entry, raw["english"]))
    return found


async def _translate(question: Question, settings: Settings, gate: asyncio.Semaphore) -> None:
    async def one(alias: str) -> Translated:
        async with gate:
            return await english_for_patterns(
                question.row.entry.prompt, settings, _TABLES, question.language, model_alias=alias
            )

    done = await asyncio.gather(*(one(alias) for alias in _MODELS))
    question.english = [
        English(item.candidate, item.ms, item.input_tokens, item.output_tokens) for item in done
    ]


async def _measure(questions: list[Question]) -> None:
    for question in questions:
        await _regex(question.row)
        for english in question.english:
            _judge(question, english)
            await _read(question, english)


def _line(label: str, questions: list[Question]) -> str:
    answerable = [q for q in questions if q.row.entry.expect == "answer"]

    def reach(mode: str) -> str:
        cards = sum(1 for q in answerable if q.card(mode)[0])
        wrong = sum(1 for q in questions if q.card(mode)[1] and q.card(mode)[0])
        return f"{cards:>3} w{wrong}"

    original = sum(1 for q in answerable if q.row.regex_card)
    original_wrong = sum(1 for q in questions if q.row.regex_wrong)
    kept = "/".join(
        str(sum(1 for q in questions if q.english and q.english[0].kept(mode))) for mode in _MODES
    )
    return (
        f"{label:<18} n={len(questions):<4} original {original:>3} w{original_wrong} | "
        + " | ".join(f"{mode} {reach(mode)}" for mode in (*_MODES, "agree"))
        + f" | kept {kept}"
    )


def _cost(questions: list[Question], index: int) -> tuple[float, float, float]:
    """p50 and p95 seconds and dollars per 1,000 turns of one model's translations."""
    done = [q.english[index] for q in questions if len(q.english) > index]
    times = sorted(item.ms for item in done) or [0.0]
    price = _prices(_MODELS[index])
    dollars = sum(item.input_tokens * price[0] + item.output_tokens * price[1] for item in done)
    return (
        statistics.median(times) / 1000,
        times[min(len(times) - 1, int(0.95 * len(times)))] / 1000,
        1000 * dollars / max(len(done), 1) / 1e6,
    )


def _report(questions: list[Question]) -> None:
    print("cards wN = cards on questions with an answer, N of all cards wrong")
    labels = sorted({(q.row.lang, q.row.subject) for q in questions})
    for lang, subject in labels:
        picked = [q for q in questions if q.row.lang == lang and q.row.subject == subject]
        print(_line(f"{subject} {lang}", picked))
    for subject in SUBJECT_NAMES:
        corpus = [q for q in questions if q.row.subject == subject and q.row.lang in LANGUAGES]
        if corpus:
            print(_line(f"{subject} all 5", corpus))
    heldout = [q for q in questions if q.row.lang.startswith("heldout-")]
    if heldout:
        print(_line("held out (all)", heldout))
    for index, alias in enumerate(_MODELS):
        p50, p95, dollars = _cost(questions, index)
        print(f"{alias}: p50 {p50:.2f}s p95 {p95:.2f}s ${dollars:.3f}/1k turns")
    reasons: dict[str, int] = {}
    for q in questions:
        for english in q.english:
            reason = english.reasons.get("strict", "no_read")
            reasons[reason] = reasons.get(reason, 0) + 1
    print("strict reasons (both models):", json.dumps(dict(sorted(reasons.items()))))
    for mode in (*_MODES, "agree"):
        for q in questions:
            card, wrong = q.card(mode)
            if card and wrong:
                print(f"  {mode} wrong {q.row.lang} {q.row.subject}:{q.row.entry.id} {card!r}")


def _dump(questions: list[Question], path: Path) -> None:
    with path.open("w") as out:
        for q in questions:
            item = {
                "lang": q.row.lang,
                "subject": q.row.subject,
                "id": q.row.entry.id,
                "prompt": q.row.entry.prompt,
                "answers": [list(answer) for answer in q.row.entry.answers],
                "english": [
                    {
                        "candidate": e.candidate,
                        "ms": e.ms,
                        "input_tokens": e.input_tokens,
                        "output_tokens": e.output_tokens,
                    }
                    for e in q.english
                ],
            }
            out.write(json.dumps(item, ensure_ascii=False) + "\n")


async def run(langs: list[str], books: list[dict[str, Any]] | None, dump: Path | None) -> None:
    settings = Settings()
    rows = [Row(subject, lang, entry) for lang in langs for subject, entry in _translated(lang)]
    rows += _book_rows(books or [])[0]
    rows += [
        Row(subject, f"heldout-{lang}", entry) for lang, subject, entry, _ in heldout_entries()
    ]
    questions = [Question(row, _language(row.lang)) for row in rows]
    gate = asyncio.Semaphore(_CONCURRENCY)
    await asyncio.gather(*(_translate(q, settings, gate) for q in questions))
    if dump is not None:
        _dump(questions, dump)
    await _measure(questions)
    _report(questions)


async def recheck(lines: list[str]) -> None:
    corpus = {
        (lang, subject, entry.id): entry
        for lang in LANGUAGES
        for subject, entry in _translated(lang)
    }
    corpus |= {
        (f"heldout-{lang}", subject, entry.id): entry
        for lang, subject, entry, _ in heldout_entries()
    }
    questions: list[Question] = []
    for line in lines:
        item = json.loads(line)
        entry = corpus.get((item["lang"], item["subject"], item["id"])) or Entry(
            item["id"],
            "book",
            item["prompt"],
            "answer",
            answers=tuple((float(value), str(unit)) for value, unit in item["answers"]),
        )
        question = Question(Row(item["subject"], item["lang"], entry), _language(item["lang"]))
        question.english = [
            English(e["candidate"], e["ms"], e["input_tokens"], e["output_tokens"])
            for e in item["english"]
        ]
        questions.append(question)
    await _measure(questions)
    _report(questions)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    run_parser = commands.add_parser("run")
    run_parser.add_argument("--langs", default=",".join(LANGUAGES))
    run_parser.add_argument("--books", type=Path, action="append")
    run_parser.add_argument("--dump", type=Path)
    recheck_parser = commands.add_parser("recheck")
    recheck_parser.add_argument("dump", type=Path)
    args = parser.parse_args()
    if args.command == "run":
        books = [item for path in args.books or [] for item in _read_sets(path)] or None
        asyncio.run(run(args.langs.split(","), books, args.dump))
    else:
        asyncio.run(recheck(args.dump.read_text().splitlines()))


if __name__ == "__main__":
    main()
