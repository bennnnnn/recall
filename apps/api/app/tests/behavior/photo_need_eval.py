"""Measure whether a reply opens with a photo only when it is about one real thing worth seeing.

A script, not a test: ``read`` and ``reply`` call the real models through their gateways,
so they need an OpenRouter key in the environment, and nothing else (no database).

    python -m app.tests.behavior.photo_need_eval rules
    python -m app.tests.behavior.photo_need_eval read --runs 3
    python -m app.tests.behavior.photo_need_eval read --runs 3 --at 0.5
    python -m app.tests.behavior.photo_need_eval reply --runs 2 --model free-chat

Every turn of ``photo_need_corpus.json`` is labelled ``photo`` (a place, a landmark, an
animal, a named person, a dish, a product, an artwork) or not (the assistant itself, the
user, small talk, advice, health, a concept, maths, writing). Three ways to run it:

- ``rules``: the word rule that names the turn's subject in its own photo hint
  (``answer_subject.asked_about_subject``, ``visuals.where_is_place``);
- ``read``: the Decider's ``seen`` question (``decider_read.PHOTO_QUESTION``), at each
  threshold on the tuning turns, then on the held-out ones (written beside them, never tuned
  on) at ``--at``;
- ``reply``: the reply's own model with the turn's real prompt (``harness.route_case``, the
  photo hints as the rules give them): whether it opens with a ```photo fence, and, with
  ``--at``, whether it still would once the read takes the hints away from a turn it calls
  unseen.

The ship rule, held out: false photos at most 5%, recall at least 90%.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import patch

CORPUS = Path(__file__).with_name("photo_need_corpus.json")
_CONCURRENCY = 6
_REPLY_MAX_TOKENS = 60
MIN_RECALL = 0.90
MAX_FALSE_PHOTOS = 0.05


@dataclass(frozen=True)
class PhotoTurn:
    """One labelled message, the chat before it, and whether its answer earns a photo."""

    id: str
    photo: bool
    prompt: str
    history: tuple[tuple[str, str], ...] = ()
    holdout: bool = False


def load(path: Path = CORPUS) -> list[PhotoTurn]:
    return [
        PhotoTurn(
            id=item["id"],
            photo=bool(item["photo"]),
            prompt=item["prompt"],
            history=tuple((role, text) for role, text in item.get("history", ())),
            holdout=bool(item.get("holdout")),
        )
        for item in json.loads(path.read_text(encoding="utf-8"))
    ]


def rules_photo(turn: PhotoTurn) -> bool:
    """The word rule that names the turn's subject in a photo hint of its own."""
    from app.modules.turn_reading.answer_subject import asked_about_subject
    from app.modules.turn_reading.visuals import where_is_place

    return bool(where_is_place(turn.prompt) or asked_about_subject(turn.prompt))


@dataclass
class Outcome:
    turn: PhotoTurn
    odds: list[float] = field(default_factory=list)
    seconds: list[float] = field(default_factory=list)
    replied: list[bool] = field(default_factory=list)


def rates(outcomes: list[Outcome], at: float) -> tuple[float, float]:
    """(recall on the photo set, false photos on the rest) over every answered run."""
    seen = [odds >= at for o in outcomes if o.turn.photo for odds in o.odds]
    plain = [odds >= at for o in outcomes if not o.turn.photo for odds in o.odds]
    return sum(seen) / max(1, len(seen)), sum(plain) / max(1, len(plain))


async def measure_read(turns: list[PhotoTurn], runs: int) -> tuple[list[Outcome], list[float]]:
    """The Decider's ``seen`` odds on each turn, ``runs`` times, and each call's cost."""
    from app.core.config import Settings
    from app.gateways.decider_gateway import decide
    from app.models import model_catalog
    from app.models.routing_lanes import ROUTING
    from app.modules.chat.decider_read import PHOTO_QUESTION
    from app.modules.chat.turn_decision import decision_messages

    settings = Settings()
    model = model_catalog.get(ROUTING.decider).model.removeprefix("openrouter/")
    outcomes = {turn.id: Outcome(turn) for turn in turns}
    costs: list[float] = []
    gate = asyncio.Semaphore(_CONCURRENCY)

    async def one(turn: PhotoTurn) -> None:
        async with gate:
            state = decision_messages(turn.prompt, list(turn.history))[-1]["content"]
            started = time.monotonic()
            try:
                reply = await decide(
                    settings,
                    model=model,
                    state=state,
                    questions=dict(PHOTO_QUESTION),
                    seconds=5.0,
                )
            except Exception as exc:  # A failed call is counted, never retried.
                print(f"  unread [{turn.id}] {type(exc).__name__}")
                return
            outcome = outcomes[turn.id]
            outcome.seconds.append(time.monotonic() - started)
            outcome.odds.append(float(reply.answers["seen"].noul or 0.0))
            costs.append(reply.usage.cost)

    for _ in range(runs):
        await asyncio.gather(*(one(turn) for turn in turns))
    return list(outcomes.values()), costs


async def _inline(fn: Any, *args: Any, **_kwargs: Any) -> Any:
    return fn(*args)


async def measure_reply(turns: list[PhotoTurn], runs: int, model: str | None) -> list[Outcome]:
    """Whether the reply's model, given the turn's real prompt, opens with a photo fence."""
    from app.core.config import Settings
    from app.gateways import litellm_gateway as gateway
    from app.tests.behavior.cases import Case, Expect
    from app.tests.behavior.harness import route_case

    settings = Settings()
    built: dict[str, tuple[str, list[Any]]] = {}
    with patch("app.core.sympy_executor.run_sympy", _inline):
        for turn in turns:
            route = await route_case(
                Case(turn.id, "photo", turn.prompt, Expect(), "", history=turn.history)
            )
            messages = [*route.context.prompt_messages, {"role": "user", "content": turn.prompt}]
            built[turn.id] = (model or route.model, messages)
    outcomes = {turn.id: Outcome(turn) for turn in turns}
    gate = asyncio.Semaphore(_CONCURRENCY)

    async def one(turn: PhotoTurn) -> None:
        alias, messages = built[turn.id]
        route = gateway.resolve_route(alias)
        kwargs, _calls = gateway._call_kwargs(settings, route, False, None)
        async with gate:
            try:
                response = await gateway.acompletion(
                    model=route.model, messages=messages, max_tokens=_REPLY_MAX_TOKENS, **kwargs
                )
            except Exception as exc:  # A failed call is counted, never retried.
                print(f"  unanswered [{turn.id}] {type(exc).__name__}")
                return
        text = response.choices[0].message.content or ""
        outcomes[turn.id].replied.append("```photo" in text)

    with patch("app.gateways.llm_spend.meter_model_call", lambda *_args: None):
        for _ in range(runs):
            await asyncio.gather(*(one(turn) for turn in turns))
    return list(outcomes.values())


def report_read(outcomes: list[Outcome], costs: list[float], at: float | None) -> str:
    tuning = [o for o in outcomes if not o.turn.holdout]
    held = [o for o in outcomes if o.turn.holdout]
    lines = [f"{len(tuning)} tuning turns, {len(held)} held out"]
    for threshold in (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8):
        recall, false = rates(tuning, threshold)
        lines.append(f"  tuning at {threshold:.1f}: recall {recall:.1%}  false photos {false:.1%}")
    if at is not None and held:
        recall, false = rates(held, at)
        verdict = "ship" if recall >= MIN_RECALL and false <= MAX_FALSE_PHOTOS else "hold"
        lines.append(
            f"  HELD OUT at {at:.2f}: recall {recall:.1%}  false photos {false:.1%}  ({verdict}; "
            f"rule: recall >= {MIN_RECALL:.0%}, false <= {MAX_FALSE_PHOTOS:.0%})"
        )
    seconds = sorted(s for o in outcomes for s in o.seconds)
    if seconds:
        p95 = seconds[min(len(seconds) - 1, int(len(seconds) * 0.95))]
        lines.append(f"  read: p50 {statistics.median(seconds):.2f}s  p95 {p95:.2f}s")
    if costs:
        lines.append(f"  read cost: ${statistics.mean(costs):.7f} a turn")
    for o in outcomes:
        if at is None and o.turn.holdout:
            continue
        mean = statistics.mean(o.odds) if o.odds else float("nan")
        mark = "PHOTO" if o.turn.photo else "none "
        lines.append(f"  {o.turn.id:14} {mark} odds {mean:.2f} {o.turn.prompt[:70]!r}")
    return "\n".join(lines)


def report_reply(outcomes: list[Outcome], read: dict[str, list[float]], at: float | None) -> str:
    def share(rows: list[bool]) -> str:
        return f"{sum(rows) / max(1, len(rows)):.1%}"

    shown = [r for o in outcomes if o.turn.photo for r in o.replied]
    false = [r for o in outcomes if not o.turn.photo for r in o.replied]
    lines = [f"reply: photo on the photo set {share(shown)}, false photos {share(false)}"]
    if at is not None:
        # The read takes the hints and the photo away from a turn it calls unseen.
        def kept(o: Outcome) -> list[bool]:
            seen = statistics.mean(read.get(o.turn.id) or [1.0]) >= at
            return [r and seen for r in o.replied]

        shown = [r for o in outcomes if o.turn.photo for r in kept(o)]
        false = [r for o in outcomes if not o.turn.photo for r in kept(o)]
        lines.append(
            f"reply with the read at {at:.2f}: photo on the photo set {share(shown)}, "
            f"false photos {share(false)}"
        )
    for o in outcomes:
        if any(o.replied) != o.turn.photo:
            label = "photo on" if any(o.replied) else "no photo on"
            lines.append(
                f"  {label} {sum(o.replied)}/{len(o.replied)} [{o.turn.id}] {o.turn.prompt!r}"
            )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mode", choices=("rules", "read", "reply"))
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--at", type=float, help="the threshold to judge held-out turns at")
    parser.add_argument("--model", help="the reply's model alias (default: Auto's pick)")
    args = parser.parse_args()
    turns = load()
    if args.mode == "rules":
        outcomes = [Outcome(turn, odds=[1.0 if rules_photo(turn) else 0.0]) for turn in turns]
        recall, false = rates(outcomes, 0.5)
        print(f"rules on {len(turns)} turns: recall {recall:.1%}  false photos {false:.1%}")
        for o in outcomes:
            if (o.odds[0] >= 0.5) != o.turn.photo:
                label = "missed" if o.turn.photo else "photo hint"
                print(f"  {label} [{o.turn.id}] {o.turn.prompt[:80]!r}")
        return
    if args.mode == "reply":
        outcomes = asyncio.run(measure_reply(turns, args.runs, args.model))
        read: dict[str, list[float]] = {}
        if args.at is not None:
            read = {o.turn.id: o.odds for o in asyncio.run(measure_read(turns, 1))[0]}
        print(report_reply(outcomes, read, args.at))
        return
    if args.at is None:
        # Tuning: the held-out turns are not read at all until a threshold is chosen.
        turns = [turn for turn in turns if not turn.holdout]
    read_outcomes, costs = asyncio.run(measure_read(turns, args.runs))
    print(report_read(read_outcomes, costs, args.at))


if __name__ == "__main__":
    main()
