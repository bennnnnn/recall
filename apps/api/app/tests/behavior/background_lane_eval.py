"""Which model should do GPT-6 Luna's jobs behind the reply: each candidate, measured.

A script, not a test: it calls the real models through the gateway, so it needs an
OpenRouter key in the environment, and nothing else (no database).

    python -m app.tests.behavior.background_lane_eval --runs 2

Luna is the lane (``models/routing_lanes.py``) of three jobs no user sees:

- ``word_problems``: a word problem translated into equations (``math.tools.word_problem``);
  right when the translation passes the number guard (``grounded``) and SymPy's solution
  holds every expected value;
- ``math_extract``: a maths line the patterns miss, read into the solver's shapes
  (``math.tools.llm_extract``); right when SymPy's answer for the read equals the expected;
- ``tool_selectors[0]``: the tool loop's first selection round, which picks ``sympy``,
  ``search_image`` or ``generate_image`` for a turn the loop runs (unsolved maths, a photo,
  a picture); right when the call names the expected tool.

The owner (2026-11-10), from his own tests: "luna doesn't know about any of the instruction
at all". Each job's own prompt and schema are used, with no fallback model. It prints, per
job and model: right, no answer, latency p50/p95 and cost per call.
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from dataclasses import dataclass
from typing import Any
from unittest.mock import patch

_CONCURRENCY = 4
MODELS = ("gpt-6-luna", "qwen-3.7-flash", "glm-5.3-flash")

WORD_PROBLEMS: tuple[tuple[str, tuple[float, ...]], ...] = (
    (
        "Jo is twice as old as Sam. In 6 years the sum of their ages will be 39. How old is each "
        "now?",
        (18, 9),
    ),
    (
        "Tickets cost $5 for children and $8 for adults. 20 tickets were sold for $121. How many "
        "adult tickets were sold?",
        (7,),
    ),
    ("The sum of two numbers is 50 and their difference is 12. Find the numbers.", (31, 19)),
    (
        "A father is 3 times as old as his son. In 12 years he will be twice as old as his son. "
        "How old is the son now?",
        (12,),
    ),
    (
        "Pens cost 3 for $2 and notebooks cost $4.50 each. Maya buys 12 pens and some notebooks "
        "and spends $35. How many notebooks did she buy?",
        (6,),
    ),
    ("Three consecutive integers add up to 72. What are they?", (23, 24, 25)),
    (
        "A rectangle's length is 3 more than twice its width. Its perimeter is 36 cm. Find its "
        "dimensions.",
        (13, 5),
    ),
    ("Maria is three times as old as her son; together they are 48. How old is Maria?", (36,)),
    (
        "A shop sold 45 shirts, some at $12 and the rest at $20, for $700 in all. How many $20 "
        "shirts were sold?",
        (20,),
    ),
    (
        "Ben has 4 more marbles than Ana. Together they have 30 marbles. How many does Ana have?",
        (13,),
    ),
)

EXTRACTS: tuple[tuple[str, str], ...] = (
    # (line, the answer SymPy must give for the read, as a SymPy expression or set)
    ("what's x if two x plus three is eleven", "{4}"),
    ("the integral of x squared from zero to three", "9"),
    ("where does x cubed minus 6 x squared plus 9 x hit zero", "{0, 3}"),
    ("limit as x goes to infinity of (3x^2+1)/(x^2-4)", "3"),
    ("x+y=10 and x-y=2, find x and y", "{(6, 4)}"),
    ("simplify (x^2 - 9)/(x - 3)", "x + 3"),
    ("find the roots of 2x² − 8 = 0", "{-2, 2}"),
    ("differentiate x cubed times e to the x", "x**3*exp(x) + 3*x**2*exp(x)"),
    ("what is the antiderivative of 1 over x", "log(x)"),
    ("factorise x squared plus 5x plus 6", "(x + 2)*(x + 3)"),
)

SELECTIONS: tuple[tuple[str, str], ...] = (
    ("show me a photo of a red panda", "search_image"),
    ("what does the Golden Gate Bridge look like?", "search_image"),
    ("show me a picture of Albert Einstein", "search_image"),
    ("draw me a cat wearing a hat", "generate_image"),
    ("make me a logo for my coffee shop app", "generate_image"),
    ("paint a sunset over the mountains in watercolor", "generate_image"),
    ("integrate x^2 sin(x) from 0 to pi", "sympy"),
    ("solve x^3 - 6x^2 + 11x - 6 = 0", "sympy"),
    ("what is the derivative of ln(x^2 + 1)", "sympy"),
    ("find the limit of (1 + 1/n)^n as n goes to infinity", "sympy"),
)


@dataclass
class Call:
    job: str
    model: str
    item: int
    right: bool
    answered: bool
    seconds: float
    cost: float


def _numbers_hold(values: list[Any], expected: tuple[float, ...]) -> bool:
    got = [float(v) for v in values]
    return all(any(abs(g - e) < 1e-6 for g in got) for e in expected)


async def _word(settings: Any, model: str, text: str, expected: tuple[float, ...]) -> bool | None:
    from app.gateways import litellm_gateway
    from app.modules.math.schemas.word_problem import WordProblemSetup
    from app.modules.math.solve.word_problem import solve_word_problem
    from app.modules.math.tools.word_problem import _PROMPT, grounded

    setup = await litellm_gateway.complete_structured(
        settings=settings,
        model_alias=model,
        messages=[{"role": "system", "content": _PROMPT}, {"role": "user", "content": text}],
        schema=WordProblemSetup,
        max_tokens=500,
        timeout_seconds=settings.math_word_problem_timeout_seconds,
        allow_fallback=False,
    )
    if setup is None or not setup.found:
        return None
    if not grounded(setup, text):
        return False
    solution = solve_word_problem(setup)
    if solution is None:
        return False
    return _numbers_hold([value for _name, value in solution.values], expected)


def _sympy_answer(extract: Any) -> Any:
    from sympy import (
        Eq,
        Symbol,
        diff,
        factor,
        integrate,
        limit,
        oo,
        simplify,
        solve,
        solveset,
        sympify,
    )

    def parse(text: str) -> Any:
        return sympify(text.replace("^", "**").replace("ln(", "log("), locals={"e": sympify("E")})

    var = Symbol(extract.variable or "x")
    if extract.kind == "equation":
        return solveset(Eq(parse(extract.lhs), parse(extract.rhs)), var)
    if extract.kind == "system":
        names = [Symbol(v) for v in extract.variables]
        found = solve([Eq(parse(a), parse(b)) for a, b in extract.equations], names, dict=True)
        return {tuple(s[n] for n in names) for s in found}
    if extract.kind == "calculus":
        expr = parse(extract.expr)
        op = extract.operation
        if op == "integrate":
            if extract.lower is not None and extract.upper is not None:
                return integrate(expr, (var, parse(extract.lower), parse(extract.upper)))
            return integrate(expr, var)
        if op == "differentiate":
            return diff(expr, var)
        if op == "factor":
            return factor(expr)
        return simplify(expr)
    if extract.kind == "limit":
        point = extract.point.replace("infinity", "oo")
        return limit(parse(extract.expr), var, oo if point in {"oo", "inf"} else parse(point))
    return None


def _same(got: Any, want: str) -> bool:
    """SymPy's answer for the read equals the expected one: a set of roots or solutions, or
    an expression (up to simplification)."""
    from sympy import simplify, sympify

    if got is None:
        return False
    if want.startswith("{"):
        items = sympify(want.replace("{", "[").replace("}", "]"))
        expected = {tuple(i) if hasattr(i, "__iter__") else i for i in items}
        return {tuple(g) if hasattr(g, "__iter__") else g for g in got} == expected
    try:
        return bool(simplify(got - sympify(want)) == 0)
    except Exception:
        return False


async def _extract(settings: Any, model: str, text: str, want: str) -> bool | None:
    from app.gateways import litellm_gateway
    from app.modules.math.tools.llm_extract import _EXTRACT_PROMPT, LLMMathExtract

    parsed = await litellm_gateway.complete_structured(
        settings=settings,
        model_alias=model,
        messages=[
            {"role": "system", "content": _EXTRACT_PROMPT},
            {"role": "user", "content": text},
        ],
        schema=LLMMathExtract,
        max_tokens=256,
        timeout_seconds=settings.math_llm_extract_timeout_seconds,
        allow_fallback=False,
    )
    if parsed is None or not parsed.found:
        return None
    try:
        return _same(_sympy_answer(parsed), want)
    except Exception:
        return False


async def _select(
    settings: Any, model: str, text: str, want: str, tools: list[dict[str, Any]]
) -> bool | None:
    from app.gateways import litellm_gateway

    messages = [
        {
            "role": "system",
            "content": "You are Recall, a helpful assistant. Use a tool when one fits.",
        },
        {"role": "user", "content": text},
    ]
    result = await litellm_gateway.complete_with_tools(
        settings=settings,
        model_alias=model,
        messages=messages,
        tools=tools,
        max_tokens=max(1, settings.mcp_tool_loop_probe_max_tokens),
        usage={},
        timeout_seconds=settings.mcp_tool_loop_timeout_seconds,
    )
    calls = result.get("tool_calls") or []
    if not calls:
        return None
    return calls[0]["function"]["name"] == want


async def measure(models: list[str], runs: int) -> list[Call]:
    from app.core.config import Settings
    from app.gateways.llm_spend import response_cost_usd
    from app.models.orm import User
    from app.modules.chat.tool_loop.selection import _tools_for_user
    from app.tests.behavior.harness import _production_tools

    settings = Settings()
    calls: list[Call] = []
    gate = asyncio.Semaphore(_CONCURRENCY)
    spent: dict[int, float] = {}

    async def one(job: str, model: str, item: int, work: Any) -> None:
        async with gate:
            key = id(asyncio.current_task())
            spent[key] = 0.0
            started = time.monotonic()
            try:
                right = await work
            except Exception:
                right = None
            calls.append(
                Call(
                    job,
                    model,
                    item,
                    bool(right),
                    right is not None,
                    time.monotonic() - started,
                    spent.pop(key, 0.0),
                )
            )

    def meter(alias: str, response: object) -> None:
        task = asyncio.current_task()
        if task is not None and id(task) in spent:
            spent[id(task)] += response_cost_usd(alias, response)

    async def never_capped(*_args: Any, **_kwargs: Any) -> bool:
        return False

    user = User(email="eval@example.com", plan="pro")
    with (
        patch("app.services.quota.global_spend_exceeded", never_capped),
        patch("app.gateways.llm_spend.meter_model_call", meter),
        _production_tools(settings),
    ):
        jobs = []
        for _ in range(runs):
            for model in models:
                for i, (text, values) in enumerate(WORD_PROBLEMS):
                    jobs.append(
                        one("word_problems", model, i, _word(settings, model, text, values))
                    )
                for i, (text, answer) in enumerate(EXTRACTS):
                    jobs.append(
                        one("math_extract", model, i, _extract(settings, model, text, answer))
                    )
                for i, (text, tool) in enumerate(SELECTIONS):
                    tools = _tools_for_user(settings, user, user_text=text)
                    jobs.append(
                        one("tool_selector", model, i, _select(settings, model, text, tool, tools))
                    )
        await asyncio.gather(*jobs)
    return calls


def report(calls: list[Call]) -> str:
    lines = [
        f"  {'job':15}{'model':16}{'right':>7}{'no answer':>11}{'p50':>7}{'p95':>7}{'cost':>11}"
    ]
    for job in ("word_problems", "math_extract", "tool_selector"):
        for model in sorted({c.model for c in calls}):
            group = [c for c in calls if c.job == job and c.model == model]
            if not group:
                continue
            secs = sorted(c.seconds for c in group)
            p95 = secs[min(len(secs) - 1, int(len(secs) * 0.95))]
            lines.append(
                f"  {job:15}{model:16}{sum(c.right for c in group) / len(group):7.0%}"
                f"{sum(not c.answered for c in group) / len(group):11.0%}"
                f"{statistics.median(secs):6.2f}s{p95:6.2f}s"
                f"  ${statistics.mean(c.cost for c in group):.6f}"
            )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--models", default=",".join(MODELS))
    args = parser.parse_args()
    print(report(asyncio.run(measure(args.models.split(","), args.runs))))


if __name__ == "__main__":
    main()
