"""Which chat models follow the app's reply instructions: each on the real prompt, twice.

A script, not a test: it streams real replies through the gateway, so it needs an OpenRouter
key in the environment, and nothing else (no database).

    python -m app.tests.behavior.reply_lane_eval --runs 2

The owner's own tests (2026-11-10): "deepseek, glm and qwen are strong on following the
instruction. luna doesn't know about any of the instruction at all! haiku can be correct
when rerun." Each prompt here is routed offline as a Pro user on Auto (``route_case``), so
its system prompt and contracts are the ones the turn builds; every model answers the same
messages with thinking off. Each category has its own check:

- ``worked``: a calculation no solver verifies opens with a ```worked block that reads into
  a solution with an answer (``math_lane_eval.score``);
- ``table``: a comparison across several things on several points comes as a table (a
  Markdown table or a ```compare card), though the message never says "table";
- ``draft``: a message or email to send comes as a copyable card (```email, ```message,
  ```sms, ```reply or ```copy);
- ``clarify``: a question too vague to answer well asks with a ```clarify card;
- ``no meta``: on every reply, no words about the app's instructions, blocks or cards.

It prints, per model, each category's pass rate, how often the two runs of one prompt agree
(stable), the first text's time and the cost.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch

from app.tests.behavior.math_lane_eval import one_reply
from app.tests.behavior.math_lane_eval import score as worked_score

_CONCURRENCY = 4
MODELS = ("free-chat", "qwen-3.7-flash", "smart-chat", "glm-5.2", "glm-5.3-flash", "gpt-6-luna")

PROMPTS: tuple[tuple[str, str], ...] = (
    ("worked", "How many solutions does $4X^2 + 4 = 6$ have?"),
    (
        "worked",
        "A rectangle's length is 3 more than twice its width. Its perimeter is 36 cm. Find "
        "its dimensions.",
    ),
    (
        "worked",
        "Find the equivalent resistance of 10 ohm and 20 ohm in series, then that combination "
        "in parallel with 30 ohm",
    ),
    ("table", "Compare Python, JavaScript and Go on typing, speed, concurrency and main use"),
    (
        "table",
        "What are the differences between a Roth IRA, a traditional IRA and a 401(k) on taxes, "
        "contribution limits and withdrawals?",
    ),
    ("table", "Give me the melting point, boiling point and density of water, ethanol and mercury"),
    (
        "draft",
        "Write a text to my landlord saying the kitchen sink has been leaking since Monday and "
        "asking when someone can come fix it",
    ),
    (
        "draft",
        "Write an email to my professor asking for a 3-day extension on my lab report because I "
        "was sick, keep it short",
    ),
    ("draft", "Write a message to my team saying today's meeting moved to 3 pm"),
    ("clarify", "What is the best country"),
    ("clarify", "how can I understand integrals"),
    ("clarify", "plan my week"),
)

_TABLE = re.compile(r"^\s*\|.*\|\s*$\n^\s*\|?\s*:?-{3,}", re.M)
_CARD = re.compile(r"```(?:compare|comparison|pros)\b")
_DRAFT = re.compile(r"```(?:email|message|sms|reply|copy)\b")
_CLARIFY = re.compile(r"```clarify\b")
# Words about the app's own instructions that a reader should never see.
_META = re.compile(
    r"\b(?:worked block|the worked|```worked block|system prompt|my instructions|the "
    r"instructions|the contract|the app lays|lay out the working|clarify card|copy card|"
    r"draft card|as instructed|per the format|in the block)\b",
    re.I,
)


def passes(category: str, reply: str) -> bool:
    if category == "worked":
        return worked_score(reply, ())[0]
    if category == "table":
        return bool(_TABLE.search(reply) or _CARD.search(reply))
    if category == "draft":
        return bool(_DRAFT.search(reply))
    return bool(_CLARIFY.search(reply))


def leaks_meta(reply: str) -> bool:
    """Meta words outside the fences: inside one they are the card's own data."""
    prose = re.sub(r"```.*?```", "", reply, flags=re.S)
    return bool(_META.search(prose))


@dataclass
class Result:
    model: str
    prompt: int
    run: int
    ok: bool
    meta: bool
    first_text: float | None
    cost: float
    reply: str


async def _inline(fn: Any, *args: Any, **_kwargs: Any) -> Any:
    return fn(*args)


async def build_prompts() -> dict[int, list[dict[str, Any]]]:
    from app.modules.chat.worked_turn import with_worked_contract
    from app.tests.behavior.cases import Case, Expect
    from app.tests.behavior.harness import route_case

    built: dict[int, list[dict[str, Any]]] = {}
    with patch("app.core.sympy_executor.run_sympy", _inline):
        for index, (category, text) in enumerate(PROMPTS):
            route = await route_case(Case(f"p{index}", "format", text, Expect(), "", pro=True))
            messages = [*route.context.prompt_messages, {"role": "user", "content": text}]
            rules = route.trace.prompt_rules if route.trace else ()
            # A calculation the readers miss gets the contract once the turn's read calls it
            # maths or physics (``chat.decided_turn``).
            if category == "worked" and "subject.worked" not in rules:
                messages = with_worked_contract(messages)
            built[index] = messages
    return built


async def measure(models: list[str], runs: int) -> list[Result]:
    from app.core.config import Settings

    settings = Settings()
    prompts = await build_prompts()
    results: list[Result] = []
    gate = asyncio.Semaphore(_CONCURRENCY)

    async def one(model: str, index: int, run: int) -> None:
        async with gate:
            try:
                reply, first, cost = await one_reply(settings, model, "off", prompts[index])
            except Exception as exc:  # A failed call is a result: nothing followed.
                reply, first, cost = f"<error {type(exc).__name__}>", None, 0.0
            category = PROMPTS[index][0]
            results.append(
                Result(
                    model,
                    index,
                    run,
                    passes(category, reply),
                    leaks_meta(reply),
                    first,
                    cost,
                    reply,
                )
            )

    async def never_capped(*_args: Any, **_kwargs: Any) -> bool:
        return False

    with (
        patch("app.services.quota.global_spend_exceeded", never_capped),
        patch("app.gateways.llm_spend.meter_model_call", lambda *_args: None),
    ):
        await asyncio.gather(
            *(one(m, i, r) for m in models for i in range(len(PROMPTS)) for r in range(runs))
        )
    return results


def report(results: list[Result]) -> str:
    categories = sorted({c for c, _ in PROMPTS})
    lines = [
        f"  {'model':16}"
        + "".join(f"{c:>9}" for c in categories)
        + f"{'no meta':>9}{'stable':>8}{'1st p50':>9}{'cost':>10}{'errors':>8}"
    ]
    for model in sorted({r.model for r in results}):
        group = [r for r in results if r.model == model]
        cells = []
        for category in categories:
            rows = [r for r in group if PROMPTS[r.prompt][0] == category]
            cells.append(f"{sum(r.ok for r in rows) / max(1, len(rows)):9.0%}")
        by_prompt: dict[int, set[bool]] = {}
        for r in group:
            by_prompt.setdefault(r.prompt, set()).add(r.ok)
        stable = sum(len(oks) == 1 for oks in by_prompt.values()) / max(1, len(by_prompt))
        firsts = [r.first_text for r in group if r.first_text is not None]
        errors = sum(r.reply.startswith("<error") for r in group)
        lines.append(
            f"  {model:16}"
            + "".join(cells)
            + f"{sum(not r.meta for r in group) / len(group):9.0%}{stable:8.0%}"
            + f"{statistics.median(firsts) if firsts else float('nan'):8.1f}s"
            + f"  ${statistics.mean(r.cost for r in group):.5f}{errors:8}"
        )
    for r in sorted(results, key=lambda r: (r.model, r.prompt, r.run)):
        if not r.ok or r.meta:
            lines.append(
                f"    {r.model} {PROMPTS[r.prompt][0]} p{r.prompt} run{r.run} ok={r.ok} "
                f"meta={r.meta}: {r.reply[:120]!r}"
            )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--models", default=",".join(MODELS))
    parser.add_argument("--dump", type=Path)
    args = parser.parse_args()
    results = asyncio.run(measure(args.models.split(","), args.runs))
    print(report(results))
    if args.dump:
        args.dump.write_text(
            json.dumps([r.__dict__ for r in results], ensure_ascii=False, indent=1),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
