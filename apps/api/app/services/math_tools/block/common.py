"""Verified-block helpers (fence + answer)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

VERIFIED_MATH_BEGIN = "[BEGIN VERIFIED MATH]"
VERIFIED_MATH_END = "[END VERIFIED MATH]"


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
    # Force/energy answers are unlabeled quantities — keep the LLM so
    # MATH_SOLVER_HINT can name the symbol. Geometry/graph already skip
    # direct reply via their fence type.
    allow_direct: bool = True


def _answer_canonical(content: str) -> dict[str, str]:
    return {"type": "answer", "content": content}


def wrap_verified_math(text: str) -> str:
    body = text.strip()
    if VERIFIED_MATH_BEGIN in body:
        return body
    return f"{VERIFIED_MATH_BEGIN}\n{body}\n{VERIFIED_MATH_END}"


def _finish_with_answer(
    lines: list[str],
    answer: str,
    *,
    preface: str | None = None,
    allow_direct: bool = True,
) -> VerifiedMathBlock:
    """Record the verified answer for post-stream attach; do not put a fence in the hint."""
    if preface:
        lines.append(preface)
    lines.append(f"Verified result: {answer}")
    return VerifiedMathBlock(
        text="\n".join(lines),
        canonical_fence=_answer_canonical(answer),
        canonical_answer=answer,
        allow_direct=allow_direct,
    )


def _diagram_block(
    lines: list[str],
    spec: Any,
    answer: str | None = None,
) -> VerifiedMathBlock:
    """Diagram JSON on canonical_fence; optional numeric answer for post-stream attach."""
    if answer:
        lines.append(f"Verified result: {answer}")
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
    # Two real roots in an aligned KaTeX pill: the gray box was 48px tall
    # (one stacked frac) and overflow:hidden clipped the second row — live
    # "x = 1/2" with "x = 3" hidden. Join with "or" so both stay on native
    # MathText and wrap. Three+ compact roots (x^6=1) still need aligned
    # so they don't clip off the side of the box.
    if len(solutions_latex) == 2:
        return r" \text{ or } ".join(solutions_latex)
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
