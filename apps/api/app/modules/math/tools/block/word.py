"""Word-problem block: the translation shown, the solve verified, a reply to send.

The reply leads with the setup (what each letter stands for, and the words
each equation comes from) so a student can see how the problem was read, then
the verified steps and the answer. Text from the translation is stripped to
plain words before it is shown.
"""

from __future__ import annotations

import re
from typing import Any

from sympy import latex

from app.core.config import Settings
from app.models.schemas.math import MathIntent
from app.models.schemas.math.word_problem import WordProblemSetup
from app.modules.math.solve.word_problem import WordSolution, solve_word_problem
from app.services.solving import VerifiedMathBlock, _answer_canonical

_PLAIN = re.compile(r"[^A-Za-z0-9 ,.'()%/-]")
_UNIT = re.compile(r"[^A-Za-z ]")
_MONEY = frozenset({"$", "dollar", "dollars", "usd"})


def _verified_block_word_problem(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    setup = intent.word_problem
    if setup is None:
        return None
    solution = solve_word_problem(setup)
    if solution is None:
        return None
    answer = r",\ ".join(
        _value_tex(value, target.unit)
        for target, value in zip(setup.targets, solution.answers, strict=True)
    )
    lines.append("Word problem, translated and solved with SymPy:")
    lines.extend(f"{unknown.symbol} = {_plain(unknown.meaning)}" for unknown in setup.unknowns)
    lines.extend(f"Equation: {equation}" for equation in solution.equations)
    lines.extend(f"{name} = {latex(value)}" for name, value in solution.values)
    lines.append(f"Verified result: {answer}")
    return VerifiedMathBlock(
        text="\n".join(lines),
        canonical_fence=_answer_canonical(answer),
        canonical_answer=answer,
        direct_reply=format_word_problem_reply(setup, solution, answer),
    )


def _plain(text: str | None) -> str:
    return " ".join(_PLAIN.sub("", text or "").split())


def _unit(unit: str | None) -> str:
    return " ".join(_UNIT.sub("", unit or "").split())


def _money(value: Any) -> str:
    amount = float(value)
    return f"{amount:.0f}" if amount == int(amount) else f"{amount:.2f}"


def _value_tex(value: Any, unit: str | None) -> str:
    if (unit or "").strip().lower() in _MONEY:
        return rf"\${_money(value)}"
    name = _unit(unit)
    return f"{latex(value)}\\ \\text{{{name}}}" if name else str(latex(value))


def _answer_sentence(setup: WordProblemSetup, solution: WordSolution) -> str:
    """``the son's age now: $12$ years``: words outside the math, no bare ``$``."""
    parts = []
    for target, value in zip(setup.targets, solution.answers, strict=True):
        meaning = _plain(target.meaning) or _plain(target.expr)
        unit = "dollars" if (target.unit or "").strip().lower() in _MONEY else _unit(target.unit)
        shown = f"${_money(value)}$" if unit == "dollars" else f"${latex(value)}$"
        parts.append(f"{meaning}: {shown}" + (f" {unit}" if unit else ""))
    return "; ".join(parts)


def format_word_problem_reply(setup: WordProblemSetup, solution: WordSolution, answer: str) -> str:
    unknowns = "\n".join(
        f"${unknown.symbol}$ = {_plain(unknown.meaning)}"
        + (f" ({_unit(unknown.unit)})" if _unit(unknown.unit) else "")
        for unknown in setup.unknowns
    )
    equations = "\n".join(
        f"${tex}$" + (f' (from "{_plain(item.source)}")' if _plain(item.source) else "")
        for tex, item in zip(solution.equations, setup.equations, strict=True)
    )
    chunks = [f"**Let**\n{unknowns}", f"**Equations**\n{equations}"]
    if solution.steps:
        chunks.append("**Solve**")
        chunks.extend(
            f"**{index}. {step.label}**\n${step.formula}$"
            for index, step in enumerate(solution.steps, start=1)
        )
    else:
        values = ", ".join(f"${name} = {latex(value)}$" for name, value in solution.values)
        chunks.append(f"**Solution**\n{values}")
    if solution.check:
        chunks.append(f"Check: ${solution.check}$")
    chunks.append(f"**Answer:** {_answer_sentence(setup, solution)}")
    chunks.append(f"```answer\n{answer}\n```")
    return "\n\n".join(chunks) + "\n"
