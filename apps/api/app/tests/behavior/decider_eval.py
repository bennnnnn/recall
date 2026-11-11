"""Measure how Auto handles a message: the word rules against the turn's model read.

A script, not a test. ``read`` calls the real read model through the gateway, so it needs an
OpenRouter key in the environment, and nothing else (no database). ``rules`` runs offline.

    python -m app.tests.behavior.decider_eval rules
    python -m app.tests.behavior.decider_eval read --runs 2
    python -m app.tests.behavior.decider_eval read --runs 2 --read-model gpt-6-luna

Every turn of ``decider_corpus.json`` (the 100-chat check-up of 2026-11-10 with its earlier
turns, the behaviour battery, the think corpus, and new hard cases: everyday reasoning, easy
STEM in odd words, "draw it" in each subject, Amharic, Spanish and French) is labelled by
hand with four fields, each a choice; a field may name two right answers ("none|low") where
the turn is borderline:

- ``subject``: everyday, maths, physics, chemistry, money or code;
- ``effort``: none, low or high, how much the answer must be reasoned out first;
- ``picture``: none, graph, diagram, molecule, photo or image, what the user asks to see;
- ``follow``: none, solve, explain, change, draw or answer, how it follows the turn before.

``rules`` asks what a turn decides with no read, as the harness routes it (``route_case``):
the subject its readers, Auto's route and the money reader found; whether it thinks
(``thinking_level``, which has no "low", so effort is compared as think or not); the picture
the composer's intent, the photo lookup, image generation and the subject's drawing give
(a scene the app draws under a solved problem nobody asked to see is not held against
them); and the follow-up the deterministic gates read (``asks_for_a_referent``,
``adds_to_problem``, a short confirmation). ``read`` asks the turn's read
(``chat.turn_decision``). Each prints per-field accuracy, the confusion of each field, the
turns either got wrong, and for the read its latency, output tokens and cost per call.
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import json
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

CORPUS = Path(__file__).with_name("decider_corpus.json")
FIELDS = ("subject", "effort", "picture", "follow")
_CONCURRENCY = 6


@dataclass(frozen=True)
class DeciderTurn:
    """One labelled message, the chat before it, and how it should be handled."""

    id: str
    source: str
    prompt: str
    history: tuple[tuple[str, str], ...]
    labels: dict[str, str]
    note: str = ""


def load(path: Path = CORPUS) -> list[DeciderTurn]:
    return [
        DeciderTurn(
            id=item["id"],
            source=item["source"],
            prompt=item["prompt"],
            history=tuple((role, text) for role, text in item.get("history", ())),
            labels={name: item[name] for name in FIELDS},
            note=item.get("note", ""),
        )
        for item in json.loads(path.read_text(encoding="utf-8"))
    ]


def right(label: str, value: str | None) -> bool:
    """The value is one of the label's right answers ("none|low" takes either)."""
    return value is not None and value in label.split("|")


def thinks(label: str) -> set[bool]:
    """Whether a turn should think, as the label's efforts allow."""
    return {effort != "none" for effort in label.split("|")}


def _rows(turn: DeciderTurn) -> list[SimpleNamespace]:
    return [SimpleNamespace(role=role, content=text, model=None) for role, text in turn.history]


# --- the word rules ---------------------------------------------------------------------

_MATH_ROUTES = {"auto.math", "auto.math_verified", "auto.inherit_math", "auto.rate_problem"}
_SUBJECT_NAMES = {"math": "maths", "physics": "physics", "chemistry": "chemistry"}
_DRAWN = {"graph": "graph", "geometry": "diagram", "simulation": "diagram"}


def _rules_subject(record: dict[str, Any], route: Any) -> str:
    solver = record.get("solver") or {}
    verified = solver.get("verified")
    if record.get("money"):
        return "money"
    if verified in _SUBJECT_NAMES:
        return _SUBJECT_NAMES[verified]
    if route.subject in _SUBJECT_NAMES:
        return _SUBJECT_NAMES[route.subject]
    reason = record.get("route") or ""
    if reason in _MATH_ROUTES:
        return "maths"
    if reason == "auto.physics":
        return "physics"
    if reason == "auto.chemistry":
        return "chemistry"
    if reason in {"auto.code", "auto.strong_task"}:
        return "code"
    return "everyday"


def _rules_picture(turn: DeciderTurn, record: dict[str, Any], route: Any) -> str:
    from app.modules.images.intent import composer_image_intent

    # The phone asks the composer's intent before it sends ("Draw the circuit" painted).
    composer = composer_image_intent(turn.prompt, _rows(turn))
    if composer.lookup_query or route.photo:
        return "photo"
    if composer.request is not None or route.image_gen:
        return "image"
    if turn.labels["picture"] == "none":
        # A scene drawn under a solved problem is the app's design, not a misread.
        return "none"
    op = ((record.get("solver") or {}).get("op")) or ""
    if op == "structure":
        return "molecule"
    return _DRAWN.get(route.drawn, "none")


def _rules_follow(turn: DeciderTurn) -> str:
    from app.modules.chat.referent_read import asks_for_a_referent
    from app.modules.turn_reading.continued_problem import adds_to_problem
    from app.modules.turn_reading.routing import is_short_confirmation

    if not turn.history:
        return "none"
    if asks_for_a_referent(turn.prompt):
        return "draw"
    if adds_to_problem(turn.prompt):
        return "answer" if turn.prompt.strip().replace(".", "", 1).isdigit() else "change"
    if is_short_confirmation(turn.prompt):
        return "answer"
    return "none"


def _rules_think(turn: DeciderTurn) -> bool:
    """The word rules' level, as a turn with no read gets it (``thinking_level``)."""
    from app.core.config import Settings
    from app.modules.chat.model_routing.thinking import thinking_level

    prior = next((text for role, text in reversed(turn.history) if role == "user"), None)
    return thinking_level(turn.prompt, prior_user=prior, settings=Settings()) != "off"


async def _inline(fn: Any, *args: Any, **_kwargs: Any) -> Any:
    return fn(*args)


async def rules_decisions(turns: list[DeciderTurn]) -> dict[str, dict[str, Any]]:
    """Each turn's decisions with no read, routed offline one at a time (the harness patches
    module state). Pro, Auto on, as in the check-up."""
    from app.tests.behavior.cases import Case, Expect
    from app.tests.behavior.decisions import decision_record
    from app.tests.behavior.harness import route_case

    out: dict[str, dict[str, Any]] = {}
    with patch("app.core.sympy_executor.run_sympy", _inline):
        for turn in turns:
            route = await route_case(
                Case(turn.id, "decider", turn.prompt, Expect(), "", history=turn.history, pro=True)
            )
            record = decision_record(route)
            out[turn.id] = {
                "subject": _rules_subject(record, route),
                "think": _rules_think(turn),
                "picture": _rules_picture(turn, record, route),
                "follow": _rules_follow(turn),
                "model": route.model,
                "route": record.get("route"),
            }
    return out


# --- the read ---------------------------------------------------------------------------


@dataclass
class ReadOutcome:
    turn: DeciderTurn
    reads: list[dict[str, Any] | None] = field(default_factory=list)
    seconds: list[float] = field(default_factory=list)


async def read_decisions(
    turns: list[DeciderTurn], runs: int, read_model: str | None
) -> tuple[list[ReadOutcome], list[tuple[float, int]]]:
    """The read on each turn, ``runs`` times, and each call's (cost, output tokens)."""
    from app.core.config import Settings
    from app.gateways.llm_spend import response_cost_usd
    from app.modules.chat import turn_decision

    settings = Settings()
    outcomes = {turn.id: ReadOutcome(turn) for turn in turns}
    calls: list[tuple[float, int]] = []
    gate = asyncio.Semaphore(_CONCURRENCY)

    async def one(turn: DeciderTurn) -> None:
        async with gate:
            started = time.monotonic()
            read = await turn_decision.read_decision(
                settings,
                turn.prompt,
                earlier=turn_decision.earlier_turns(_rows(turn)),
                model_alias=read_model,
            )
            outcome = outcomes[turn.id]
            outcome.seconds.append(time.monotonic() - started)
            outcome.reads.append(None if read is None else read.model_dump())

    def meter(alias: str, response: object) -> None:
        # A measurement is not the product's spend: priced here, never counted.
        usage = getattr(response, "usage", None)
        calls.append(
            (response_cost_usd(alias, response), int(getattr(usage, "completion_tokens", 0) or 0))
        )

    async def never_capped(*_args: Any, **_kwargs: Any) -> bool:
        return False

    with (
        patch("app.services.quota.global_spend_exceeded", never_capped),
        patch("app.gateways.llm_spend.meter_model_call", meter),
    ):
        for _ in range(runs):
            await asyncio.gather(*(one(turn) for turn in turns))
    return list(outcomes.values()), calls


# --- the report -------------------------------------------------------------------------


def _field_value(read: dict[str, Any] | None, name: str) -> str | None:
    return None if read is None else read.get(name)


def _accuracy(pairs: list[tuple[str, str | None]]) -> float:
    return sum(right(label, value) for label, value in pairs) / max(1, len(pairs))


def _confusion(pairs: list[tuple[str, str | None]]) -> str:
    """Wrong answers only: label -> what was said, with counts."""
    wrong = collections.Counter(
        f"{label}->{value}" for label, value in pairs if not right(label, value)
    )
    return ", ".join(f"{key} {count}" for key, count in wrong.most_common(12)) or "none"


def report_rules(turns: list[DeciderTurn], rules: dict[str, dict[str, Any]]) -> str:
    lines = [f"rules: {len(turns)} turns"]
    for name in ("subject", "picture", "follow"):
        pairs = [(t.labels[name], rules[t.id][name]) for t in turns]
        lines.append(f"  {name:8} {_accuracy(pairs):6.1%}   wrong: {_confusion(pairs)}")
    think = [rules[t.id]["think"] in thinks(t.labels["effort"]) for t in turns]
    lines.append(f"  think    {sum(think) / len(turns):6.1%}   (effort none vs low/high)")
    for name in ("subject", "picture", "follow"):
        for t in turns:
            if not right(t.labels[name], rules[t.id][name]):
                lines.append(
                    f"    {name}: [{t.id}] want {t.labels[name]} got {rules[t.id][name]}"
                    f"  {t.prompt[:70]!r}"
                )
    for t in turns:
        if rules[t.id]["think"] not in thinks(t.labels["effort"]):
            lines.append(
                f"    think: [{t.id}] want {t.labels['effort']} got "
                f"{'think' if rules[t.id]['think'] else 'none'} ({rules[t.id]['route']})"
                f"  {t.prompt[:70]!r}"
            )
    return "\n".join(lines)


def report_read(
    outcomes: list[ReadOutcome], runs: int, calls: list[tuple[float, int]], by_source: bool = True
) -> str:
    lines = [f"read: {len(outcomes)} turns x {runs} runs"]
    for run in range(runs):
        parts = []
        for name in FIELDS:
            pairs = [(o.turn.labels[name], _field_value(o.reads[run], name)) for o in outcomes]
            parts.append(f"{name} {_accuracy(pairs):.1%}")
        think = [
            o.reads[run] is not None
            and (o.reads[run] or {}).get("effort") is not None
            and ((o.reads[run] or {})["effort"] != "none") in thinks(o.turn.labels["effort"])
            for o in outcomes
        ]
        parts.append(f"think {sum(think) / len(outcomes):.1%}")
        unread = sum(o.reads[run] is None for o in outcomes)
        lines.append(f"  run {run + 1}: " + "  ".join(parts) + f"  unread {unread}")
    if by_source:
        sources = sorted({o.turn.source for o in outcomes})
        for source in sources:
            group = [o for o in outcomes if o.turn.source == source]
            parts = []
            for name in FIELDS:
                pairs = [
                    (o.turn.labels[name], _field_value(read, name))
                    for o in group
                    for read in o.reads
                ]
                parts.append(f"{name} {_accuracy(pairs):.1%}")
            lines.append(f"  {source} ({len(group)}): " + "  ".join(parts))
    for name in FIELDS:
        pairs = [(o.turn.labels[name], _field_value(r, name)) for o in outcomes for r in o.reads]
        lines.append(f"  {name} wrong: {_confusion(pairs)}")
    seconds = sorted(s for o in outcomes for s in o.seconds)
    if seconds:
        p95 = seconds[min(len(seconds) - 1, int(len(seconds) * 0.95))]
        lines.append(f"  latency: p50 {statistics.median(seconds):.2f}s  p95 {p95:.2f}s")
    if calls:
        costs = [cost for cost, _tokens in calls]
        tokens = [out for _cost, out in calls]
        lines.append(
            f"  cost ${statistics.mean(costs):.6f} a call  output tokens mean "
            f"{statistics.mean(tokens):.0f}  max {max(tokens)}"
        )
    for o in outcomes:
        for name in FIELDS:
            said = [_field_value(r, name) for r in o.reads]
            wrong = sum(not right(o.turn.labels[name], value) for value in said)
            if wrong:
                lines.append(
                    f"    {name}: {wrong}/{runs} [{o.turn.id}] want {o.turn.labels[name]} "
                    f"got {said}  {o.turn.prompt[:70]!r}"
                )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mode", choices=("rules", "read"))
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--read-model", help="the read's model alias (default: its lane)")
    parser.add_argument("--only", help="comma-separated turn ids")
    parser.add_argument("--dump", type=Path, help="write each turn's decisions as JSON")
    args = parser.parse_args()
    turns = load()
    if args.only:
        wanted = {item.strip() for item in args.only.split(",")}
        turns = [turn for turn in turns if turn.id in wanted]
    if args.mode == "rules":
        rules = asyncio.run(rules_decisions(turns))
        print(report_rules(turns, rules))
        dumped: Any = rules
    else:
        outcomes, calls = asyncio.run(read_decisions(turns, args.runs, args.read_model))
        print(report_read(outcomes, args.runs, calls))
        dumped = {o.turn.id: {"reads": o.reads, "seconds": o.seconds} for o in outcomes}
    if args.dump:
        args.dump.write_text(json.dumps(dumped, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
