"""Which model should write maths the solver cannot verify: each candidate on the real prompt.

A script, not a test: it streams real replies through the gateway, so it needs an OpenRouter
key in the environment, and nothing else (no database).

    python -m app.tests.behavior.math_lane_eval --runs 2
    python -m app.tests.behavior.math_lane_eval --models smart-chat,glm-5.2 --levels off,hard

The owner asked "How many solutions does $4X^2 + 4 = 6$ have?" with Auto off on each model
(2026-11-10). No solver verified it, so every model got the ```worked block's contract
(``chat.worked_turn``): DeepSeek and Qwen3.7 Flash kept the layout and solved it; GLM 5.2,
GLM 5.3 Flash and GPT-6 Luna answered "two real solutions" with no working. GLM 5.2 is
Auto's maths lane (``ROUTING.math``). Each question here is one the harness routes as maths
with no verified answer (checked before it is asked, ``route_case``); its prompt is the one
the turn builds. Per model and thinking level it prints: the layout kept (the reply opens
with a ```worked block that reads into a solution with an answer), the answer right (every
expected value appears in the block's answers, or, with no block, in the reply), the first
visible text's time, and the cost of the reply.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import statistics
import time
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import patch

_CONCURRENCY = 4
_LEAD_CHARS = 160
_MAX_TOKENS = 6000
MODELS = ("smart-chat", "qwen-3.7-flash", "free-chat", "glm-5.2", "glm-5.3-flash", "gpt-6-luna")

# (question, the values a right answer states). Each value is matched as a number in the
# answer, so "x = 5, L = 13" needs both 5 and 13.
QUESTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("How many solutions does $4X^2 + 4 = 6$ have?", ("2",)),
    (
        "A rectangle's length is 3 more than twice its width. Its perimeter is 36 cm. Find its "
        "dimensions.",
        ("5", "13"),
    ),
    ("Find the maximum area of a rectangle with perimeter 40", ("100",)),
    ("What's the probability of getting at least one 6 in 4 rolls of a die?", ("0.518",)),
    (
        "Jo is twice as old as Sam. In 6 years the sum of their ages will be 39. How old is each "
        "now?",
        ("9", "18"),
    ),
    (
        "A tank fills in 6 hours with pipe A and in 4 hours with pipe B. With both open, how long "
        "does it take?",
        ("2.4",),
    ),
    (
        "A bag has 5 red and 3 blue balls. Two are drawn without replacement. What is the "
        "probability they are different colours?",
        ("15/28",),
    ),
    ("How many ways can 5 people sit in a row if two of them must sit together?", ("48",)),
    ("The sum of three consecutive even numbers is 78. What are they?", ("24", "26", "28")),
    ("A shirt costs $40 after a 20% discount. What was the original price?", ("50",)),
    ("Find the sum of the first 20 terms of 3, 7, 11, ...", ("820",)),
    ("How many diagonals does a decagon have?", ("35",)),
    (
        "In a class, 60% study French, 50% study Spanish and 20% study both. What percent study "
        "neither?",
        ("10",),
    ),
    (
        "A car's value drops 15% a year. It costs $28,000 new. What is it worth after 3 years?",
        ("17195",),
    ),
    (
        "A ladder 10 m long leans against a wall with its foot 6 m from the wall. How high up "
        "the wall does it reach?",
        ("8",),
    ),
    ("The angles of a triangle are in the ratio 2:3:4. Find the largest angle.", ("80",)),
    ("Two numbers add up to 50 and differ by 12. Find them.", ("31", "19")),
    (
        "A train travels 240 km at 60 km/h and returns at 80 km/h. What is its average speed for "
        "the whole trip?",
        ("68.6",),
    ),
    ("If 3 workers build a wall in 12 days, how many days do 4 workers take?", ("9",)),
    (
        "A number is increased by 25% and then decreased by 20%. What is the net change in "
        "percent?",
        ("0",),
    ),
    ("How many solutions does x^2 + 6x + 9 = 0 have?", ("1",)),
    ("A rectangle's area is 48 and its length is 2 more than its width. Find the width.", ("6",)),
    ("What is the probability of rolling a sum of 7 with two dice?", ("0.1667",)),
)

_NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?(?:/\d+)?")
_FRAC = re.compile(r"\\[dt]?frac\{(\d+)\}\{(\d+)\}")
_WORKED = re.compile(r"```worked\s*\n(.*?)```", re.S)


def _value(number: str) -> float | None:
    try:
        top, _, bottom = number.replace(",", "").partition("/")
        return float(top) / float(bottom) if bottom else float(top)
    except (ValueError, ZeroDivisionError):
        return None


_WORDS = {"no": "0", "one": "1", "two": "2", "three": "3", "four": "4"}
_COUNT = re.compile(r"\b(no|one|two|three|four)\b(?=\s+(?:real\s+|distinct\s+)?solution)", re.I)


def _numbers(text: str) -> list[float]:
    plain = _COUNT.sub(lambda m: _WORDS[m.group(1).lower()], _FRAC.sub(r"\1/\2", text))
    return [v for n in _NUMBER.findall(plain) if (v := _value(n)) is not None]


def _has(value: str, numbers: list[float]) -> bool:
    want = _value(value) or 0.0
    return any(abs(got - want) <= max(0.006 * abs(want), 0.006) for got in numbers)


def score(reply: str, expected: tuple[str, ...]) -> tuple[bool, bool]:
    """(layout kept, answer right)."""
    from app.modules.chat.worked_solution import assemble, read_record

    block = _WORKED.search(reply)
    kept = False
    answers = ""
    if block and not reply[: block.start()].strip():
        records = [r for line in block.group(1).splitlines() if (r := read_record(line))]
        solution = assemble(records)
        found = [a for part in solution.parts for a in part.answers]
        kept = bool(found)
        answers = " ".join(f"{a.symbol} {a.value}" for a in found)
    # With no block, the answer is the reply's lead: a number deep in prose may be a step.
    numbers = _numbers(answers if kept else reply[:_LEAD_CHARS])
    return kept, all(_has(value, numbers) for value in expected)


@dataclass
class Result:
    model: str
    level: str
    question: int
    kept: bool
    right: bool
    first_text: float | None
    cost: float
    reply: str = ""


@dataclass
class Prompts:
    by_question: dict[int, list[dict[str, Any]]] = field(default_factory=dict)
    skipped: list[str] = field(default_factory=list)


async def _inline(fn: Any, *args: Any, **_kwargs: Any) -> Any:
    return fn(*args)


async def build_prompts() -> Prompts:
    """Each question's real prompt, as the harness builds it on Pro with Auto on; a question
    a solver verifies is skipped. One the readers do not call maths (a probability, an
    optimisation) gets the worked contract it gets once the turn's read calls it maths."""
    from app.modules.chat.worked_turn import with_worked_contract
    from app.tests.behavior.cases import Case, Expect
    from app.tests.behavior.harness import route_case

    out = Prompts()
    with patch("app.core.sympy_executor.run_sympy", _inline):
        for index, (question, _values) in enumerate(QUESTIONS):
            route = await route_case(Case(f"q{index}", "math", question, Expect(), "", pro=True))
            rules = route.trace.prompt_rules if route.trace else ()
            if route.solved:
                out.skipped.append(f"{question[:60]!r} (a solver verifies it)")
                continue
            messages = [*route.context.prompt_messages, {"role": "user", "content": question}]
            if "subject.worked" not in rules:
                messages = with_worked_contract(messages)
            out.by_question[index] = messages
    return out


async def one_reply(
    settings: Any, model: str, level: str, messages: list[dict[str, Any]]
) -> tuple[str, float | None, float]:
    from app.gateways import litellm_gateway as gateway
    from app.models import model_catalog

    usage: dict[str, int] = {}
    started = time.monotonic()
    first: float | None = None
    parts: list[str] = []
    async for token in gateway.stream_chat_completion(
        settings=settings,
        model_alias=model,
        messages=messages,
        max_tokens=_MAX_TOKENS,
        usage=usage,
        thinking=level,
    ):
        if first is None and token.strip():
            first = time.monotonic() - started
        parts.append(token)
    cost = model_catalog.estimate_cost_usd(
        model, input_tokens=usage.get("input", 0), output_tokens=usage.get("output", 0)
    )
    return "".join(parts), first, cost or 0.0


async def measure(models: list[str], levels: list[str], runs: int) -> tuple[list[Result], Prompts]:
    from app.core.config import Settings

    settings = Settings()
    prompts = await build_prompts()
    results: list[Result] = []
    gate = asyncio.Semaphore(_CONCURRENCY)

    async def one(model: str, level: str, index: int) -> None:
        async with gate:
            try:
                reply, first, cost = await one_reply(
                    settings, model, level, prompts.by_question[index]
                )
            except Exception as exc:  # A failed call is a result: no layout, no answer.
                reply, first, cost = f"<error {type(exc).__name__}>", None, 0.0
            kept, right = score(reply, QUESTIONS[index][1])
            results.append(Result(model, level, index, kept, right, first, cost, reply))

    with (
        patch("app.services.quota.global_spend_exceeded", _never_capped),
        patch("app.gateways.llm_spend.meter_model_call", lambda *_args: None),
    ):
        for _ in range(runs):
            await asyncio.gather(
                *(
                    one(model, level, index)
                    for model in models
                    for level in levels
                    for index in prompts.by_question
                )
            )
    return results, prompts


async def _never_capped(*_args: Any, **_kwargs: Any) -> bool:
    return False


def report(results: list[Result], prompts: Prompts) -> str:
    lines = [f"{len(prompts.by_question)} questions (skipped: {len(prompts.skipped)})"]
    lines += [f"  skipped {item}" for item in prompts.skipped]
    lines.append(
        f"  {'model':16}{'level':7}{'layout':>8}{'right':>8}{'1st p50':>9}{'1st p90':>9}"
        f"{'cost/turn':>11}"
    )
    keys = sorted({(r.model, r.level) for r in results})
    for model, level in keys:
        group = [r for r in results if r.model == model and r.level == level]
        firsts = sorted(r.first_text for r in group if r.first_text is not None)
        p50 = statistics.median(firsts) if firsts else float("nan")
        p90 = firsts[min(len(firsts) - 1, int(len(firsts) * 0.9))] if firsts else float("nan")
        lines.append(
            f"  {model:16}{level:7}{sum(r.kept for r in group) / len(group):8.0%}"
            f"{sum(r.right for r in group) / len(group):8.0%}{p50:8.1f}s{p90:8.1f}s"
            f"  ${statistics.mean(r.cost for r in group):.5f}"
        )
    for r in sorted(results, key=lambda r: (r.model, r.level, r.question)):
        if not (r.kept and r.right):
            lines.append(
                f"    {r.model} {r.level} q{r.question} kept={r.kept} right={r.right}: "
                f"{r.reply[:140]!r}"
            )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--models", default=",".join(MODELS))
    parser.add_argument("--levels", default="off,hard")
    parser.add_argument("--dump", help="write every reply as JSON")
    args = parser.parse_args()
    results, prompts = asyncio.run(
        measure(args.models.split(","), args.levels.split(","), args.runs)
    )
    print(report(results, prompts))
    if args.dump:
        import json
        from pathlib import Path

        Path(args.dump).write_text(
            json.dumps([r.__dict__ for r in results], ensure_ascii=False, indent=1),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
