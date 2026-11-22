"""How much a chat's prompt costs, and how much of it a provider can serve from its cache.

Two commands:

``sim`` replays chats through the history window and the compaction rule, turn by turn,
and prints what each policy sends: input tokens per turn, how many messages go verbatim,
and the share of every prompt that repeats the previous turn's prompt from its start (the
part a prefix cache can serve). No model, database or network: the fixed prompt parts are
measured sizes, the history is the real code's (``context_window``), and a fold's summary
is a new text of the measured size.

    uv run python -m app.tests.behavior.context_cache_eval sim

``logs`` reads ``turn_cost`` lines (the API log) and prints, per model, the tokens sent,
the share the provider read from its cache and wrote to it, and the app's estimate
against the provider's count.

    fly logs -a recall-api | uv run python -m app.tests.behavior.context_cache_eval logs
    uv run python -m app.tests.behavior.context_cache_eval logs tmp/api.log
"""

from __future__ import annotations

import argparse
import json
import random
import re
import statistics
import sys
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.modules.chat.context_window import (
    UNSUMMARIZED_GAP_MAX_MESSAGES,
    FoldRule,
    estimate_tokens,
    fits_whole,
    messages_within_token_budget,
    select_recent_window,
    trim_message_for_summary,
)

_HERE = Path(__file__).parent

# Measured on 2026-11-22 (``render_rules`` of each table, characters / 4) for an ordinary
# question: the rules every turn shares, this kind of turn's rules, and the context after
# the history (the clock, to-dos, integrations).
STABLE_TOKENS = 1_723
TURN_RULES_TOKENS = 6_469
CONTEXT_TOKENS = 1_305
# Each fold adds its facts and topic lines; ``SUMMARY_MAX_CHARS`` (6000) holds it to ~1.5k.
SUMMARY_FOLD_TOKENS = 120
SUMMARY_MAX_TOKENS = 1_500
INPUT_PRICE_PER_M = 0.15


@dataclass(frozen=True)
class Policy:
    """One way to choose a turn's history.

    ``anchored`` False is the window as it was: the newest ``count`` rows the budget keeps,
    then the unsummarized gap before them, folding as soon as three rows wait. True starts
    the history at the summary's edge while it fits, and folds back to ``target`` rows only
    when it passes ``trigger``, so the history's start holds still between folds.
    """

    name: str
    budget: int
    count: int
    anchored: bool = False
    trigger_tokens: int = 0
    trigger_count: int = 0
    target_tokens: int = 0
    target_count: int = 0


def shipped_policy(settings: Settings | None = None) -> Policy:
    """The history policy the settings ship (``core/settings/chat.py``)."""
    s = settings or Settings()
    return Policy(
        f"shipped: anchored {s.context_token_budget // 1000}k "
        f"(fold {s.history_fold_trigger_tokens // 1000}k→{s.history_fold_target_tokens // 1000}k)",
        budget=s.context_token_budget,
        count=s.history_max_messages,
        anchored=True,
        trigger_tokens=s.history_fold_trigger_tokens,
        trigger_count=s.history_fold_trigger_messages,
        target_tokens=s.history_fold_target_tokens,
        target_count=s.history_fold_target_messages,
    )


POLICIES = (
    Policy("before: 20 msgs / 16k, slides", budget=16_000, count=20),
    Policy("60 msgs / 16k, slides", budget=16_000, count=60),
    Policy(
        "anchored 16k (fold 12k→6k)",
        budget=16_000,
        count=60,
        anchored=True,
        trigger_tokens=12_000,
        trigger_count=48,
        target_tokens=6_000,
        target_count=20,
    ),
    shipped_policy(),
    Policy(
        "anchored 48k (fold 36k→16k)",
        budget=48_000,
        count=100,
        anchored=True,
        trigger_tokens=36_000,
        trigger_count=80,
        target_tokens=16_000,
        target_count=30,
    ),
)


@dataclass
class _Row:
    id: int
    role: str
    content: str

    @property
    def tokens(self) -> int:
        return estimate_tokens(self.content)


@dataclass
class _Chat:
    rows: list[_Row] = field(default_factory=list)
    summarized: int = 0
    summary_version: int = 0
    summary_tokens: int = 0

    def fold_to(self, summarized: int) -> None:
        if summarized <= self.summarized:
            return
        self.summarized = summarized
        self.summary_version += 1
        self.summary_tokens = min(SUMMARY_MAX_TOKENS, self.summary_tokens + SUMMARY_FOLD_TOKENS)


def _tokens(rows: Iterable[_Row]) -> int:
    return sum(row.tokens for row in rows)


def _sliding_history(chat: _Chat, budget: int, count: int) -> list[tuple[str, int]]:
    """The window as ``prompt_window.load_prompt_window`` builds it: the kept tail verbatim,
    the newest unsummarized rows before it trimmed, all within the budget."""
    loaded = chat.rows[-count:]
    keep = select_recent_window(loaded, budget, count)
    recent = loaded[-keep:] if keep else []
    start = len(chat.rows) - len(recent)
    left = max(0, budget - _tokens(recent))
    waiting = chat.rows[min(chat.summarized, start) : start][-UNSUMMARIZED_GAP_MAX_MESSAGES:]
    gap = messages_within_token_budget(waiting, left, max_messages=UNSUMMARIZED_GAP_MAX_MESSAGES)
    return [
        *((f"gap{row.id}", estimate_tokens(trim_message_for_summary(row.content))) for row in gap),
        *((f"row{row.id}", row.tokens) for row in recent),
    ]


def _history(chat: _Chat, policy: Policy) -> list[tuple[str, int]]:
    """``load_anchored_history`` when the policy anchors, else the sliding window."""
    if policy.anchored:
        unsummarized = chat.rows[chat.summarized :]
        if fits_whole(unsummarized, policy.budget, policy.count):
            return [(f"row{row.id}", row.tokens) for row in unsummarized]
    return _sliding_history(chat, policy.budget, policy.count)


def _compact(chat: _Chat, policy: Policy) -> None:
    """The post-turn fold, finished before the next turn (the job's best case): the real
    ``FoldRule`` for an anchored policy; the rule it replaced otherwise (fold whatever the
    window left out once three such messages wait)."""
    total = len(chat.rows)
    if policy.anchored:
        rule = FoldRule(
            trigger_tokens=policy.trigger_tokens,
            trigger_count=policy.trigger_count,
            target_tokens=policy.target_tokens,
            target_count=policy.target_count,
        )
        chat.fold_to(chat.summarized + rule.to_fold(chat.rows[chat.summarized :]))
        return
    keep = select_recent_window(chat.rows[-policy.count :], policy.budget, policy.count)
    if total - keep - chat.summarized >= 3:
        chat.fold_to(total - keep)


def _prompt(chat: _Chat, policy: Policy, turn: int) -> list[tuple[str, int]]:
    """The prompt as segments: a provider's cache serves the run that repeats the last
    prompt's from the start. The summary lives in the turn's system message, so a fold
    changes it; the context after the history carries the clock, new on every turn."""
    rules = TURN_RULES_TOKENS + chat.summary_tokens
    return [
        ("stable", STABLE_TOKENS),
        (f"rules+summary{chat.summary_version}", rules),
        *_history(chat, policy),
        (f"context{turn}", CONTEXT_TOKENS),
    ]


def _common_prefix(a: list[tuple[str, int]], b: list[tuple[str, int]]) -> int:
    shared = 0
    for left, right in zip(a, b, strict=False):
        if left != right:
            break
        shared += left[1]
    return shared


@dataclass
class Result:
    policy: str
    turns: int
    total_input: int
    max_input: int
    cacheable: int
    verbatim_median: float
    verbatim_tokens_median: float

    def cost(self, cached_price_share: float) -> float:
        paid = (self.total_input - self.cacheable) + self.cacheable * cached_price_share
        return paid / 1_000_000 * INPUT_PRICE_PER_M


def simulate(turns: list[tuple[str, str]], policy: Policy) -> Result:
    chat = _Chat()
    previous: list[tuple[str, int]] = []
    totals: list[int] = []
    cacheable = 0
    verbatim: list[int] = []
    verbatim_tokens: list[int] = []
    for index, (user, reply) in enumerate(turns):
        chat.rows.append(_Row(len(chat.rows), "user", user))
        prompt = _prompt(chat, policy, index)
        history = [seg for seg in prompt if seg[0].startswith(("row", "gap"))]
        verbatim.append(sum(1 for seg in history if seg[0].startswith("row")))
        verbatim_tokens.append(sum(seg[1] for seg in history))
        totals.append(sum(seg[1] for seg in prompt))
        cacheable += _common_prefix(previous, prompt)
        previous = prompt
        chat.rows.append(_Row(len(chat.rows), "assistant", reply))
        _compact(chat, policy)
    return Result(
        policy=policy.name,
        turns=len(turns),
        total_input=sum(totals),
        max_input=max(totals),
        cacheable=cacheable,
        verbatim_median=statistics.median(verbatim),
        verbatim_tokens_median=statistics.median(verbatim_tokens),
    )


def replay_turns(repeat: int = 1) -> list[tuple[str, str]]:
    """The owner's 80-message chat (``replays/friend_getting_married.json``)."""
    data = json.loads((_HERE / "replays" / "friend_getting_married.json").read_text())
    turns = [(turn["user"], turn["before"]) for turn in data["turns"]]
    return turns * repeat


def coding_turns(count: int = 150, seed: int = 7) -> list[tuple[str, str]]:
    """A long build-a-page chat: short asks, replies of a few hundred tokens, and one in
    eight a whole page of code (~3-6k tokens)."""
    rng = random.Random(seed)  # noqa: S311 - a repeatable synthetic chat, not a secret

    def text(tokens: int) -> str:
        return " ".join("abcd" for _ in range(max(1, int(tokens / 1.35))))

    turns = []
    for _ in range(count):
        ask = text(int(rng.lognormvariate(3.6, 0.6)))
        heavy = rng.random() < 0.125
        size = rng.randint(3_000, 6_000) if heavy else int(rng.lognormvariate(5.8, 0.5))
        turns.append((ask, text(size)))
    return turns


def _print_table(title: str, results: list[Result]) -> None:
    print(f"\n## {title} ({results[0].turns} turns)\n")
    print(
        "| policy | input/turn (avg) | max | verbatim msgs (median) | history tokens "
        "(median) | cacheable | chat cost, no cache | cached at 25% | cached at 10% |"
    )
    print("|---|---|---|---|---|---|---|---|---|")
    for r in results:
        print(
            f"| {r.policy} | {r.total_input // r.turns:,} | {r.max_input:,} | "
            f"{r.verbatim_median:.0f} | {r.verbatim_tokens_median:,.0f} | "
            f"{r.cacheable / r.total_input:.0%} | ${r.cost(1.0):.3f} | ${r.cost(0.25):.3f} | "
            f"${r.cost(0.10):.3f} |"
        )


def run_sim(policies: Iterable[Policy] = POLICIES) -> dict[str, list[Result]]:
    scenarios: dict[str, Callable[[], list[tuple[str, str]]]] = {
        "Real chat (friend getting married)": replay_turns,
        "Real chat, three times as long": lambda: replay_turns(3),
        "Coding chat with long replies": coding_turns,
    }
    out: dict[str, list[Result]] = {}
    for title, make in scenarios.items():
        turns = make()
        out[title] = [simulate(turns, policy) for policy in policies]
    return out


# ``turn_cost user_id=… model=… input_tokens=… …`` (``modules/chat/turn_settle``).
_FIELD = re.compile(r"(\w+)=(\S+)")


@dataclass
class _ModelLog:
    turns: int = 0
    input: int = 0
    cached: int = 0
    written: int = 0
    ratios: list[float] = field(default_factory=list)


def read_logs(lines: Iterable[str]) -> dict[str, _ModelLog]:
    by_model: dict[str, _ModelLog] = defaultdict(_ModelLog)
    for line in lines:
        if "turn_cost " not in line:
            continue
        fields = dict(_FIELD.findall(line.split("turn_cost ", 1)[1]))

        def number(name: str, fields: dict[str, Any] = fields) -> int:
            value = fields.get(name, "0")
            return int(value) if value.isdigit() else 0

        entry = by_model[fields.get("model", "?")]
        entry.turns += 1
        entry.input += number("input_tokens")
        entry.cached += number("cached_input_tokens")
        entry.written += number("cache_write_tokens")
        estimated = number("est_prompt_tokens")
        if estimated and number("input_tokens"):
            entry.ratios.append(estimated / number("input_tokens"))
    return dict(by_model)


def _share(part: int, whole: int) -> str:
    return f"{part / whole:.0%}" if whole else "n/a"


def _print_logs(by_model: dict[str, _ModelLog]) -> None:
    if not by_model:
        print("No turn_cost lines found.")
        return
    print(
        "| model | turns | input/turn | read from cache | written to cache | "
        "estimate / provider (median) |"
    )
    print("|---|---|---|---|---|---|")
    for model, e in sorted(by_model.items(), key=lambda item: -item[1].input):
        ratio = f"{statistics.median(e.ratios):.2f}" if e.ratios else "n/a"
        print(
            f"| {model} | {e.turns} | {e.input // max(1, e.turns):,} | "
            f"{_share(e.cached, e.input)} | {_share(e.written, e.input)} | {ratio} |"
        )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("sim", help="replay chats through each history policy")
    logs = sub.add_parser("logs", help="read turn_cost lines from a log (or stdin)")
    logs.add_argument("path", nargs="?", help="log file; stdin when omitted")
    args = parser.parse_args(argv)
    if args.command == "sim":
        for title, results in run_sim().items():
            _print_table(title, results)
        return
    stream = open(args.path, encoding="utf-8") if args.path else sys.stdin
    with stream:
        _print_logs(read_logs(stream))


if __name__ == "__main__":
    main()
