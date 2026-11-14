"""One step of a verified trace, and the pieces every trace writes: an equation, its roots.

Below the traces (``key_steps``, ``key_steps_special``, ``log_key_steps``) and the
real-domain check (``real_domain``), so a module that writes steps need not import the
dispatcher that calls it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sympy import latex

from app.modules.math.solve.root_latex import compact_root_answer_lines


@dataclass(frozen=True)
class KeyStep:
    """One justified transformation. Formula is LaTeX without ``$`` wrappers."""

    label: str
    formula: str
    reason: str | None = None
    conditions: str | None = None
    branch: str | None = None


def canonical_root_formula(var: Any, solutions: list[Any]) -> str:
    lines = compact_root_answer_lines(str(var), solutions)
    return lines[0] if len(lines) == 1 else r" \text{ or } ".join(lines)


def equation_tex(left: Any, right: Any) -> str:
    return f"{latex(left)} = {latex(right)}"
