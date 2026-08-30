"""Verified-block helpers (fence + answer)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

# The model explains; Recall attaches ```answer / ```graph / ```geometry
# after the stream from canonical_fence / canonical_answer. Do not put those
# fences in the system hint — that is what taught Qwen/GLM to invent JSON.
SOLVER_OWNED_FENCES_NOTE = (
    "Do NOT emit ```answer, ```graph, or ```geometry fences — "
    "Recall attaches the verified result after your answer."
)

DIAGRAM_OWNED_NOTE = (
    "Recall will attach the verified diagram. Describe it in words using $...$ "
    "where helpful. Do NOT emit ```geometry or ```graph JSON."
)


@dataclass(frozen=True)
class VerifiedMathBlock:
    """System-prompt hint (numbers and steps) plus the exact fence Recall
    will attach after the stream. The model is not asked to copy fences.
    Geometry/graph turns keep the diagram JSON on canonical_fence and the
    numeric final on canonical_answer.

    ``canonical_fences`` collects fences across multiple tool-loop rounds
    (e.g. a geometry fence from round 1 and a graph fence from round 2) so
    ``validate_math_fences`` can match each by type instead of only using
    the last round's fence. ``canonical_fence`` stays the primary/first for
    backward compatibility."""

    text: str
    canonical_fence: dict[str, Any] | None = None
    canonical_answer: str | None = None
    canonical_fences: list[dict[str, Any]] = field(default_factory=list)


def _fence(kind: str, spec: Any) -> str:
    return f"```{kind}\n{json.dumps(spec.model_dump(), separators=(',', ':'))}\n```"


def _answer_canonical(content: str) -> dict[str, str]:
    return {"type": "answer", "content": content}


def _finish_with_answer(
    lines: list[str],
    answer: str,
    *,
    preface: str = (
        "Do NOT recompute. Explain in plain language with $...$ for formulas. "
        + SOLVER_OWNED_FENCES_NOTE
    ),
) -> VerifiedMathBlock:
    """Record the verified answer for post-stream attach; do not put a fence in the hint."""
    lines.append(preface)
    lines.append(f"Verified result: {answer}")
    return VerifiedMathBlock(
        text="\n".join(lines),
        canonical_fence=_answer_canonical(answer),
        canonical_answer=answer,
    )


def _diagram_block(
    lines: list[str],
    spec: Any,
    answer: str | None = None,
) -> VerifiedMathBlock:
    """Diagram JSON on canonical_fence; optional numeric answer for post-stream attach."""
    lines.append(DIAGRAM_OWNED_NOTE)
    if answer:
        lines.append(f"Verified result: {answer}")
        lines.append(SOLVER_OWNED_FENCES_NOTE)
    dump = spec.model_dump() if hasattr(spec, "model_dump") else spec
    return VerifiedMathBlock(
        text="\n".join(lines),
        canonical_fence=dump,
        canonical_answer=answer,
    )


def _format_equation_answer(
    solutions_latex: list[str],
    solution_kind: str,
) -> str:
    if not solutions_latex:
        if solution_kind == "infinite":
            return r"\text{all real numbers}"
        return r"\text{no solution}"
    if len(solutions_latex) == 1:
        return solutions_latex[0]
    # One root per line in a display environment so the gray answer pill
    # uses KaTeX and wraps. A comma-joined native MathText run clips.
    rows: list[str] = []
    for item in solutions_latex:
        if " = " in item:
            left, right = item.split(" = ", 1)
            rows.append(f"{left} &= {right}")
        else:
            rows.append(item)
    return "\\begin{aligned}\n" + " \\\\\n".join(rows) + "\n\\end{aligned}"


def _format_system_answer(
    solutions: list[dict[str, str]],
    solution_kind: str,
) -> str:
    if solutions:
        sets = [", ".join(f"{k} = {v}" for k, v in sol.items()) for sol in solutions]
        return "; ".join(sets)
    if solution_kind == "infinite":
        return r"\text{infinitely many solutions}"
    return r"\text{no solution}"
