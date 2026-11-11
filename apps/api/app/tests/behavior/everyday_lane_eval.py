"""Which model should answer Pro's everyday turns: Haiku, GPT-6 Luna or Qwen3.7 Flash.

A script, not a test: it streams real replies, and a judge model scores them, so it needs
an OpenRouter key in the environment and nothing else (no database).

    python -m app.tests.behavior.everyday_lane_eval --runs 2

The owner asked (2026-11-10) why Haiku is Pro's everyday model when Luna was faster (0.6 s
against 0.9 s to the first word in ``math_lane_eval``). Thirty everyday prompts from the
check-up's categories (advice, writing, facts, how-to, plans, comparisons, explanations), each
routed offline as a Pro user on Auto so its system prompt is the turn's own, are answered by
each model with thinking off. Per model: first-word and total time, cost, the instruction
checks of ``reply_lane_eval`` (a draft card for a message to send, a table for a comparison,
a clarify card for a vague ask, no meta text) plus no leaked reasoning, and a judge's
correctness and 1-5 quality against a ChatGPT-level bar (DeepSeek, thinking off; a model
judging others is an estimate, read with the replies).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch

from pydantic import BaseModel, Field

from app.tests.behavior.reply_lane_eval import leaks_meta

MODELS = ("free-chat", "gpt-6-luna", "qwen-3.7-flash")
JUDGE = "smart-chat"
_CONCURRENCY = 4
_MAX_TOKENS = 1500

# (category, prompt, the check it must pass, or "" for none)
PROMPTS: tuple[tuple[str, str, str], ...] = (
    ("how-to", "How do I get rid of fruit flies in my kitchen?", ""),
    (
        "writing",
        "Write a text to my landlord saying the kitchen sink has been leaking since "
        "Monday and asking when someone can come fix it",
        "draft",
    ),
    (
        "writing",
        "Write an email to my professor asking for a 3-day extension on my lab report "
        "because I was sick, keep it short",
        "draft",
    ),
    ("writing", "Write an Instagram caption for a photo of my first half marathon finish", "draft"),
    (
        "writing",
        "Write a thesis paragraph arguing that remote work increases productivity for "
        "software engineers",
        "",
    ),
    ("how-to", "Give me a simple recipe for chicken tikka masala for 4 people", ""),
    ("plan", "Plan a 3 day trip to Tokyo in March for a first-timer on a mid budget", ""),
    ("advice", "How do I negotiate a higher salary for a job offer?", ""),
    ("explain", "Explain how compound interest works with an example", ""),
    ("advice", "My 4 year old won't sleep in her own bed. What should I try?", ""),
    (
        "writing",
        "Write a LinkedIn post announcing I got a new job as a data analyst at a hospital",
        "draft",
    ),
    ("facts", "What's the difference between a Roth IRA and a traditional IRA?", ""),
    ("how-to", "How do I fix git push rejected non-fast-forward?", ""),
    ("writing", "Help me write a polite message declining a wedding invitation", "draft"),
    ("advice", "What should I pack for a week in Iceland in December?", ""),
    ("how-to", "How long should I boil an egg for a jammy yolk?", ""),
    (
        "comparison",
        "Summarize the pros and cons of electric cars vs hybrids for someone who "
        "drives 60 miles a day",
        "table",
    ),
    ("advice", "I have chicken thighs, rice, spinach and a lemon. What can I make tonight?", ""),
    ("writing", "Write a cover letter opening paragraph for a junior UX designer role", ""),
    ("advice", "How do I tell my manager I'm burned out?", ""),
    (
        "facts",
        "Translate 'where is the train station and how much is a ticket' into Spanish and Japanese",
        "",
    ),
    ("plan", "Make me a weekly workout plan, 3 days a week, beginner, no gym", ""),
    (
        "comparison",
        "Compare Python, JavaScript and Go on typing, speed, concurrency and main use",
        "table",
    ),
    (
        "comparison",
        "What are the differences between a Roth IRA, a traditional IRA and a "
        "401(k) on taxes, contribution limits and withdrawals?",
        "table",
    ),
    ("writing", "Write an email to my landlord about a broken heater", "draft"),
    ("vague", "What is the best country", "clarify"),
    ("vague", "plan my week", "clarify"),
    ("explain", "explain recursion like I'm 10", ""),
    ("advice", "give me 5 tips to sleep better", ""),
    ("facts", "summarize the french revolution in 3 sentences", ""),
)

_TABLE = re.compile(r"^\s*\|.*\|\s*$\n^\s*\|?\s*:?-{3,}", re.M)
_CHECKS = {
    "draft": re.compile(r"```(?:email|message|sms|reply|copy)\b"),
    "clarify": re.compile(r"```clarify\b"),
}
# Reasoning written as the reply: "We need to...", "The user wants...", "Let me think".
_REASONING = re.compile(
    r"^(?:we need|we must|need to|the user (?:wants|asks|is asking)|let me think|okay,? so)\b",
    re.I | re.M,
)


def passes(check: str, reply: str) -> bool:
    if not check:
        return True
    if check == "table":
        return bool(_TABLE.search(reply) or re.search(r"```(?:compare|comparison|pros)\b", reply))
    return bool(_CHECKS[check].search(reply))


class Verdict(BaseModel):
    correct: bool
    quality: int = Field(ge=1, le=5)


_JUDGE_PROMPT = (
    "You grade an assistant's reply for a phone chat app. The bar is ChatGPT's best reply to "
    "the same message. Reply with JSON only: correct is false when the reply states anything "
    "wrong or misses what was asked; quality is 1 to 5 (5: as good as ChatGPT's best, right "
    "length and format; 3: usable but clearly weaker; 1: wrong or useless). Fenced blocks "
    "(```email, ```message, ```clarify, tables) are cards the app renders; judge their "
    'content. Example: {"correct": true, "quality": 4}.'
)


@dataclass
class Result:
    model: str
    prompt: int
    run: int
    reply: str
    first_text: float | None
    total: float
    cost: float
    checked: bool
    meta: bool
    reasoning: bool
    correct: bool | None = None
    quality: int | None = None


async def _inline(fn: Any, *args: Any, **_kwargs: Any) -> Any:
    return fn(*args)


async def build_prompts() -> dict[int, list[dict[str, Any]]]:
    from app.tests.behavior.cases import Case, Expect
    from app.tests.behavior.harness import route_case

    built: dict[int, list[dict[str, Any]]] = {}
    with patch("app.core.sympy_executor.run_sympy", _inline):
        for index, (_category, text, _check) in enumerate(PROMPTS):
            route = await route_case(Case(f"e{index}", "format", text, Expect(), "", pro=True))
            built[index] = [*route.context.prompt_messages, {"role": "user", "content": text}]
    return built


async def _judge(settings: Any, text: str, reply: str) -> Verdict | None:
    from app.gateways.structured_completion import complete_structured

    return await complete_structured(
        settings=settings,
        model_alias=JUDGE,
        messages=[
            {"role": "system", "content": _JUDGE_PROMPT},
            {"role": "user", "content": f"Message: {text}\n\nReply:\n{reply[:6000]}"},
        ],
        schema=Verdict,
        max_tokens=60,
        timeout_seconds=30,
        allow_fallback=False,
    )


async def measure(models: list[str], runs: int) -> list[Result]:
    from app.core.config import Settings
    from app.tests.behavior.math_lane_eval import one_reply

    settings = Settings()
    prompts = await build_prompts()
    results: list[Result] = []
    gate = asyncio.Semaphore(_CONCURRENCY)

    async def one(model: str, index: int, run: int) -> None:
        async with gate:
            started = time.monotonic()
            try:
                reply, first, cost = await one_reply(settings, model, "off", prompts[index])
            except Exception as exc:  # A failed call is a result.
                reply, first, cost = f"<error {type(exc).__name__}>", None, 0.0
            total = time.monotonic() - started
            text, check = PROMPTS[index][1], PROMPTS[index][2]
            result = Result(
                model,
                index,
                run,
                reply,
                first,
                total,
                cost,
                passes(check, reply),
                leaks_meta(reply),
                bool(_REASONING.search(reply)),
            )
            try:
                verdict = await _judge(settings, text, reply)
            except Exception:
                verdict = None
            if verdict is not None:
                result.correct, result.quality = verdict.correct, verdict.quality
            results.append(result)

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
    lines = [
        f"  {'model':16}{'1st p50':>8}{'1st p90':>8}{'total':>7}{'cost':>10}{'checks':>8}"
        f"{'no meta':>8}{'no CoT':>8}{'correct':>8}{'quality':>8}{'stable':>8}"
    ]
    for model in sorted({r.model for r in results}):
        group = [r for r in results if r.model == model]
        firsts = sorted(r.first_text for r in group if r.first_text is not None)
        checked = [r for r in group if PROMPTS[r.prompt][2]]
        judged = [r for r in group if r.quality is not None]
        by_prompt: dict[int, set[bool]] = {}
        for r in checked:
            by_prompt.setdefault(r.prompt, set()).add(r.checked)
        stable = sum(len(v) == 1 for v in by_prompt.values()) / max(1, len(by_prompt))
        lines.append(
            f"  {model:16}{statistics.median(firsts):7.1f}s"
            f"{firsts[int(len(firsts) * 0.9)]:7.1f}s{statistics.median(r.total for r in group):6.1f}s"
            f"  ${statistics.mean(r.cost for r in group):.5f}"
            f"{sum(r.checked for r in checked) / max(1, len(checked)):8.0%}"
            f"{sum(not r.meta for r in group) / len(group):8.0%}"
            f"{sum(not r.reasoning for r in group) / len(group):8.0%}"
            f"{sum(bool(r.correct) for r in judged) / max(1, len(judged)):8.0%}"
            f"{statistics.mean(r.quality or 0 for r in judged):8.2f}{stable:8.0%}"
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
