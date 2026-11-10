"""Measure whether a turn searches the web only when its answer needs live facts.

A script, not a test: it calls the real models through the gateway, so it needs an
OpenRouter key in the environment, and nothing else (no database).

    python -m app.tests.behavior.search_need_eval read --runs 3
    python -m app.tests.behavior.search_need_eval reply --runs 3 --model gpt-6-luna
    python -m app.tests.behavior.search_need_eval turn --runs 3

Every turn of ``search_need_corpus.json`` is labelled ``live`` (its answer needs facts
that change: news, scores, prices, weather, who holds an office, releases, opening hours,
what is near the user) or not (how-to and settled knowledge, advice, writing, maths, the
user's own life, small talk, follow-ups about the conversation). Three ways to run it:

- ``read``: the fast model's read beside the prep (``web_search.live_read``), which has
  its query searched before the reply when it says live;
- ``reply``: the reply's own model call, with the turn's real prompt and tools
  (``harness.route_case``), which may call ``web_search`` itself;
- ``turn``: both, as a turn runs them: the read first, and the reply's call when the read
  gave no answer (a settled answer takes the tool off the reply's call). A turn marked
  ``regenerate`` is answered again: the reply's model thinks one level more.

Each prints, per run: false searches (searched turns the set says need none) and recall
(searched turns of those that need live facts), the same for the held-out turns (written
after the read's instructions, never tuned on), then the turns that missed in any run.
The targets are at most 5% false searches and at least 95% recall.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

CORPUS = Path(__file__).with_name("search_need_corpus.json")
_CONCURRENCY = 6
_REPLY_MAX_TOKENS = 300
# A raised thinking level spends tokens on reasoning before any tool call.
_THINKING_MAX_TOKENS = 4000
# What the measurement aims for (the owner's targets, 2026-11-09).
MAX_FALSE_SEARCHES = 0.05
MIN_RECALL = 0.95


@dataclass(frozen=True)
class Turn:
    """One labelled turn: the message, the conversation before it, and whether its answer
    needs live facts."""

    id: str
    area: str
    live: bool
    prompt: str
    history: tuple[tuple[str, str], ...] = ()
    location: str | None = None
    locale: str = "en"
    # Written after the read's instructions were settled, and never tuned on.
    holdout: bool = False
    # Answered again (Regenerate): the reply's model thinks one level more.
    regenerate: bool = False


def load(path: Path = CORPUS) -> list[Turn]:
    """The corpus's turns. A turn of a ``thread`` takes the thread's messages before its
    own as its history, so a long chat is written out once."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    threads: dict[str, list[list[str]]] = raw["threads"]
    turns: list[Turn] = []
    for item in raw["turns"]:
        history = tuple(tuple(pair) for pair in item.get("history", ()))
        thread = item.get("thread")
        if thread:
            messages = threads[thread]
            at = next(
                index
                for index, (role, text) in enumerate(messages)
                if role == "user" and text == item["prompt"]
            )
            history = tuple((role, text) for role, text in messages[:at])
        turns.append(
            Turn(
                id=item["id"],
                area=item["area"],
                live=bool(item["live"]),
                prompt=item["prompt"],
                history=history,
                location=item.get("location"),
                locale=item.get("locale", "en"),
                holdout=bool(item.get("holdout")),
                regenerate=bool(item.get("regenerate")),
            )
        )
    return turns


def recent_rows(turn: Turn) -> list[SimpleNamespace]:
    """The turn's history as the turn's recent window holds it (oldest first)."""
    return [SimpleNamespace(role=role, content=text) for role, text in turn.history]


@dataclass
class Outcome:
    turn: Turn
    searched: list[bool] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)
    seconds: list[float] = field(default_factory=list)
    # Runs whose read gave no answer (failed or ran out of time): the turn did not wait.
    unread: list[bool] = field(default_factory=list)


async def read_once(settings: Any, turn: Turn) -> tuple[bool, str, float, bool]:
    """The read as a turn starts it: (searches, query, seconds, answered)."""
    from app.modules.web_search import live_read

    started = time.monotonic()
    task = live_read.start_live_read(settings, turn.prompt, recent=recent_rows(turn))
    read = await task if task is not None else None
    seconds = time.monotonic() - started
    if read is None:
        return False, "", seconds, False
    return read.searches, read.query, seconds, True


async def _inline(fn: Any, *args: Any, **_kwargs: Any) -> Any:
    return fn(*args)


async def reply_prompts(turns: list[Turn]) -> dict[str, tuple[str, list[Any], list[Any]]]:
    """Each turn's real prompt, reply tools and Auto's model, built offline, one at a time
    (the harness patches module state)."""
    from app.tests.behavior.cases import Case, Expect
    from app.tests.behavior.harness import route_case

    built: dict[str, tuple[str, list[Any], list[Any]]] = {}
    with patch("app.core.sympy_executor.run_sympy", _inline):
        for turn in turns:
            route = await route_case(
                Case(
                    turn.id,
                    "web search",
                    turn.prompt,
                    Expect(),
                    "",
                    history=turn.history,
                    location=turn.location,
                    locale=turn.locale,
                )
            )
            ctx = route.context
            # The harness's window is the history alone; a turn's prompt ends with the
            # user's own line, after the turn's context (``prompt_inject``).
            messages = [*ctx.prompt_messages, {"role": "user", "content": turn.prompt}]
            built[turn.id] = (route.model, messages, list(ctx.reply_tools or []))
    return built


async def reply_searches(
    settings: Any, model: str, messages: list[Any], tools: list[Any], *, again: bool = False
) -> tuple[bool, str]:
    """Whether the reply's model call, offered these tools, calls ``web_search``. ``again``:
    the line is answered again, with the thinking a regenerate raises (``thinking_level``)."""
    from app.gateways import litellm_gateway as gateway
    from app.gateways.stream_tool_calls import ToolOffer

    if not any((tool.get("function") or {}).get("name") == "web_search" for tool in tools):
        return False, ""
    route = gateway.resolve_route(model)
    thinking = "escalate" if again else False
    kwargs, _calls = gateway._call_kwargs(settings, route, thinking, ToolOffer(tools, None))
    max_tokens = _THINKING_MAX_TOKENS if again else _REPLY_MAX_TOKENS
    response = await gateway.acompletion(
        model=route.model, messages=messages, max_tokens=max_tokens, **kwargs
    )
    message = response.choices[0].message
    for call in getattr(message, "tool_calls", None) or []:
        if call.function.name == "web_search":
            return True, str(json.loads(call.function.arguments or "{}").get("query") or "")
    return False, ""


async def measure(
    mode: str, turns: list[Turn], runs: int, model: str | None, read_model: str | None = None
) -> list[Outcome]:
    from dataclasses import replace

    from app.core.config import Settings
    from app.models.routing_lanes import ROUTING

    settings = Settings()
    outcomes = {turn.id: Outcome(turn) for turn in turns}
    prompts = await reply_prompts(turns) if mode in {"reply", "turn"} else {}
    gate = asyncio.Semaphore(_CONCURRENCY)

    async def one(turn: Turn) -> None:
        async with gate:
            outcome = outcomes[turn.id]
            searched, query, settled = False, "", False
            if mode in {"read", "turn"}:
                live, query, seconds, answered = await read_once(settings, turn)
                outcome.seconds.append(seconds)
                outcome.unread.append(not answered)
                # A live read with no query makes the reply's call search.
                searched, settled = live, answered and not live
            # A read that found nothing that changes takes web_search off the reply's call.
            if mode == "reply" or (mode == "turn" and not searched and not settled):
                auto, messages, tools = prompts[turn.id]
                searched, query = await reply_searches(
                    settings, model or auto, messages, tools, again=turn.regenerate
                )
            outcome.searched.append(searched)
            outcome.queries.append(query)

    lanes = replace(ROUTING, live_read=read_model) if read_model else ROUTING
    # A measurement is not the product's spend: nothing is added to the day's counter.
    with (
        patch("app.services.quota.global_spend_exceeded", _never_capped),
        patch("app.gateways.llm_spend.meter_model_call", lambda *_args: None),
        patch("app.modules.web_search.live_read.ROUTING", lanes),
    ):
        for _ in range(runs):
            await asyncio.gather(*(one(turn) for turn in turns))
    return list(outcomes.values())


async def _never_capped(*_args: Any, **_kwargs: Any) -> bool:
    return False


def rates(outcomes: list[Outcome], run: int) -> tuple[float, float]:
    """(false searches, recall) in one run."""
    settled = [o for o in outcomes if not o.turn.live]
    live = [o for o in outcomes if o.turn.live]
    false = sum(o.searched[run] for o in settled) / max(1, len(settled))
    recall = sum(o.searched[run] for o in live) / max(1, len(live))
    return false, recall


def _means(outcomes: list[Outcome], runs: int) -> str:
    falses, recalls = zip(*(rates(outcomes, run) for run in range(runs)), strict=True)
    return f"false searches {statistics.mean(falses):.1%}  recall {statistics.mean(recalls):.1%}"


def report(outcomes: list[Outcome], runs: int) -> str:
    settled = sum(not o.turn.live for o in outcomes)
    lines = [f"{len(outcomes)} turns: {len(outcomes) - settled} need live facts, {settled} don't"]
    for run in range(runs):
        false, recall = rates(outcomes, run)
        lines.append(f"  run {run + 1}: false searches {false:.1%}  recall {recall:.1%}")
    lines.append(f"  mean:  {_means(outcomes, runs)}  ")
    lines[-1] += f"(targets: <= {MAX_FALSE_SEARCHES:.0%}, >= {MIN_RECALL:.0%})"
    held = [o for o in outcomes if o.turn.holdout]
    if held:
        lines.append(f"  held-out ({len(held)} turns), mean: {_means(held, runs)}")
    seconds = [s for o in outcomes for s in o.seconds]
    if seconds:
        ordered = sorted(seconds)
        p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
        unread = sum(sum(o.unread) for o in outcomes)
        lines.append(
            f"  read: p50 {statistics.median(seconds):.2f}s  p95 {p95:.2f}s  unread {unread}"
        )
    for outcome in outcomes:
        wrong = [run for run, s in enumerate(outcome.searched) if s != outcome.turn.live]
        if wrong:
            label = "missed" if outcome.turn.live else "searched"
            unread = sum(outcome.unread[run] for run in wrong if run < len(outcome.unread))
            queries = sorted({q for q in outcome.queries if q})
            lines.append(
                f"  {label} {len(wrong)}/{runs} [{outcome.turn.id}] {outcome.turn.prompt!r}"
                + (f" ({unread} unread)" if unread else "")
                + (f"  queries={queries}" if queries else "")
            )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mode", choices=("read", "reply", "turn"))
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--model", help="the reply's model alias (default: Auto's pick)")
    parser.add_argument("--read-model", help="the read's model alias (default: its lane)")
    parser.add_argument("--only", help="comma-separated turn ids")
    parser.add_argument("--dump", type=Path, help="write each turn's results as JSON")
    args = parser.parse_args()
    turns = load()
    if args.only:
        wanted = {item.strip() for item in args.only.split(",")}
        turns = [turn for turn in turns if turn.id in wanted]
    outcomes = asyncio.run(measure(args.mode, turns, args.runs, args.model, args.read_model))
    print(report(outcomes, args.runs))
    if args.dump:
        args.dump.write_text(
            json.dumps(
                [
                    {
                        "id": o.turn.id,
                        "live": o.turn.live,
                        "searched": o.searched,
                        "queries": o.queries,
                    }
                    for o in outcomes
                ],
                ensure_ascii=False,
                indent=1,
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
