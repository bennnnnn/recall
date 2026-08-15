"""Verified-block helpers (fence + answer)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class VerifiedMathBlock:
    """The system-prompt hint text plus the exact fence (if any) it asked
    the model to reuse verbatim — canonical_fence lets a post-stream check
    correct the model's actual output rather than only trusting compliance.
    Geometry/graph turns keep the diagram JSON on canonical_fence and the
    numeric final on canonical_answer so ```answer can be rewritten too."""

    text: str
    canonical_fence: dict[str, Any] | None = None
    canonical_answer: str | None = None


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
        "End with this final-answer fence (copy verbatim):"
    ),
) -> VerifiedMathBlock:
    """Attach a canonical ```answer fence the post-stream rewriter can enforce."""
    lines.append(f"{preface}\n```answer\n{answer}\n```")
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
    """Diagram JSON on canonical_fence; optional numeric ```answer rewrite."""
    if answer:
        lines.append(f"End with this final-answer fence (copy verbatim):\n```answer\n{answer}\n```")
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
    if solutions_latex:
        return ", ".join(solutions_latex)
    if solution_kind == "infinite":
        return r"\text{all real numbers}"
    return r"\text{no solution}"


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
