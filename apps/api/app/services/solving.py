"""Verified-solve primitives shared by every subject that solves and verifies
homework (math, physics, and any solver-backed subject after them).

This module deliberately holds no subject's business logic — no equation
solving, no physics formulas, no chemistry stoichiometry. It holds only the
vocabulary subjects use to hand a verified result to the chat turn: the
error a solve raises when it declines, and the block that carries a verified
answer (plus optional fence/trajectory data) into the system prompt.

Math and physics both import from here directly instead of one importing
through the other's package — see docs/SUBJECT_SEPARATION_TICKETS.md (S2).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

# TYPE_CHECKING only: `math.solve` imports `MathServiceError` from this module
# (see below), so a real import of `math.solve.key_steps` here — which would
# run `math/solve/__init__.py` first, like any submodule import does — would
# cycle straight back before this module finishes defining that name. Every
# use of KeyStep below is an annotation (`from __future__ import annotations`
# makes them lazy strings), so no runtime import is needed at all.
if TYPE_CHECKING:
    from app.models.schemas.math import NewtonMethodInput, NewtonMethodResult
    from app.models.schemas.physics import PhysicsIntent
    from app.modules.math.response_intent import MathResponseIntent
    from app.modules.math.solve.key_steps import KeyStep

VERIFIED_MATH_BEGIN = "[BEGIN VERIFIED MATH]"
VERIFIED_MATH_END = "[END VERIFIED MATH]"
VERIFIED_PHYSICS_BEGIN = "[BEGIN VERIFIED PHYSICS]"
VERIFIED_PHYSICS_END = "[END VERIFIED PHYSICS]"
_VERIFIED_MARKERS = (
    VERIFIED_MATH_BEGIN,
    VERIFIED_MATH_END,
    VERIFIED_PHYSICS_BEGIN,
    VERIFIED_PHYSICS_END,
)


class SolveServiceError(ValueError):
    """A deterministic subject solve declined invalid or unsupported input."""


@dataclass(frozen=True)
class VerifiedSolveBlock:
    """Subject-neutral transport for one deterministic, verified solve.

    Subject algorithms own extraction, solving, traces, and presentation.
    Chat owns only this canonical transport: prompt text, exact result fences,
    and optional subject-rendered direct output.  Subject-specific state lives
    on the subclasses below rather than turning math into physics' container.

    ``canonical_fences`` collects fences across multiple tool-loop rounds
    (e.g. a geometry fence from round 1 and a graph fence from round 2) so
    ``validate_math_fences`` can match each by type instead of only using
    the last round's fence. ``canonical_fence`` stays the primary/first for
    backward compatibility."""

    text: str
    subject: Literal["math", "physics", "chemistry"]
    canonical_fence: dict[str, Any] | None = None
    canonical_answer: str | None = None
    # Optional user-facing spelling of the same verified value. Geometry uses
    # this to retain a numeric canonical value for guards while showing the
    # correct linear/square unit in the checked answer card.
    display_answer: str | None = None
    canonical_fences: list[dict[str, Any]] = field(default_factory=list)
    # Some results need language around the canonical data; closed requests
    # may return a subject-rendered reply without asking a model to recalculate.
    allow_direct: bool = True
    direct_reply: str | None = None
    direct_request_text: str | None = None
    direct_answer_binding: str | None = None
    domain_conditions: tuple[str, ...] = ()
    excluded_values: tuple[str, ...] = ()


@dataclass(frozen=True)
class VerifiedMathBlock(VerifiedSolveBlock):
    """Math-only verified state and deterministic teaching traces."""

    subject: Literal["math"] = "math"
    # The one line that shows where the answer came from — e.g. the
    # factorization behind a quadratic's roots. Shown on the direct-reply
    # path for the balanced/detailed response styles, omitted for short.
    key_step: str | None = None
    # Ordered inverse-operation (or factor / formula) trace for equation lessons.
    key_steps: tuple[KeyStep, ...] = ()
    given_latex: str | None = None
    # "Given" for an equation; "Find" when the problem line is the question
    # itself (a derivative or an integral to evaluate).
    given_label: str = "Given"
    check_latex: str | None = None
    alternate_method_note: str | None = None
    # Paired snapshots of the actual Newton solve; never reconstruct iterations.
    newton_input: NewtonMethodInput | None = None
    newton_result: NewtonMethodResult | None = None
    # Standard derivatives/integrals additionally use the strict calculus
    # whole-request grammar; calculus applications have their own extractors
    # and therefore leave this false.
    direct_requires_calculus_guard: bool = False
    # Presentation is classified once for the turn, then enforced by direct
    # routing, prompt guidance, and final fence attachment. In particular,
    # ``reveal_answer=False`` is a hard policy boundary for tutoring hints.
    response_intent: MathResponseIntent | None = None


@dataclass(frozen=True)
class VerifiedPhysicsBlock(VerifiedSolveBlock):
    """Physics-only verified state used by physics presentation guards."""

    subject: Literal["physics"] = "physics"
    physics_intent: PhysicsIntent | None = None
    physics_working: str | None = None
    physics_formulas: tuple[str, ...] = ()
    physics_substitutions: tuple[str, ...] = ()


# Compatibility for solver modules and downstream integrations while callers
# migrate to the subject-neutral name. New cross-subject code uses
# SolveServiceError; the alias contains no math behavior.
MathServiceError = SolveServiceError


def wrap_verified_math(text: str) -> str:
    body = text.strip()
    if VERIFIED_MATH_BEGIN in body or VERIFIED_PHYSICS_BEGIN in body:
        return body
    return f"{VERIFIED_MATH_BEGIN}\n{body}\n{VERIFIED_MATH_END}"


def wrap_verified_physics(text: str) -> str:
    body = text.strip()
    if VERIFIED_PHYSICS_BEGIN in body or VERIFIED_MATH_BEGIN in body:
        return body
    return f"{VERIFIED_PHYSICS_BEGIN}\n{body}\n{VERIFIED_PHYSICS_END}"


def strip_verified_solve_markers(text: str) -> str:
    """Remove the verified-math sentinels if a model echoed them into its reply.

    ``wrap_verified_math`` puts these around the block injected into the
    prompt. They are scaffolding: the model is told never to mention a system
    block, but instruction is not enforcement, and the same class of leak has
    already reached a user once (the SymPy note under an anatomy answer).

    The text *between* the markers is kept. A model that echoed the block
    usually put the real answer inside it, and an empty reply is worse than a
    slightly formal one — stripping the scaffolding is enough to make it read
    as prose. Blank runs left behind are collapsed so removing a marker that
    sat on its own line does not leave a gap.
    """
    if not any(marker in text for marker in _VERIFIED_MARKERS):
        return text
    stripped = text
    for marker in _VERIFIED_MARKERS:
        stripped = stripped.replace(marker, "")
    return re.sub(r"\n{3,}", "\n\n", stripped).strip()


strip_verified_math_markers = strip_verified_solve_markers


def _answer_canonical(content: str) -> dict[str, str]:
    return {"type": "answer", "content": content}


def _finish_with_answer(
    lines: list[str],
    answer: str,
    *,
    preface: str | None = None,
    allow_direct: bool = True,
    key_step: str | None = None,
    key_steps: tuple[KeyStep, ...] | list[KeyStep] = (),
    given_latex: str | None = None,
    check_latex: str | None = None,
    alternate_method_note: str | None = None,
) -> VerifiedMathBlock:
    """Record the verified answer for post-stream attach; do not put a fence in the hint."""
    if preface:
        lines.append(preface)
    lines.append(f"Verified result: {answer}")
    return VerifiedMathBlock(
        text="\n".join(lines),
        subject="math",
        canonical_fence=_answer_canonical(answer),
        canonical_answer=answer,
        allow_direct=allow_direct,
        key_step=key_step,
        key_steps=tuple(key_steps),
        given_latex=given_latex,
        check_latex=check_latex,
        alternate_method_note=alternate_method_note,
    )


def _diagram_block(
    lines: list[str],
    spec: Any,
    answer: str | None = None,
    *,
    display_answer: str | None = None,
) -> VerifiedMathBlock:
    """Diagram JSON on canonical_fence; optional numeric answer for post-stream attach."""
    if answer:
        lines.append(f"Verified result: {answer}")
    dump = spec.model_dump() if hasattr(spec, "model_dump") else spec
    return VerifiedMathBlock(
        text="\n".join(lines),
        subject="math",
        canonical_fence=dump,
        canonical_answer=answer,
        display_answer=display_answer,
    )
