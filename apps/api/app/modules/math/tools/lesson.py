"""Server-rendered equation lessons from verified ``key_steps``."""

from __future__ import annotations

import json

from app.modules.math.response_intent import (
    MathResponseMode,
    classify_math_response_intent,
    strip_math_response_wrappers,
)
from app.services.solving import VerifiedMathBlock


def wants_math_explanation(text: str) -> bool:
    """True when the user asked for language (steps / teaching), not just the value."""
    return classify_math_response_intent(text).wants_explanation


def wants_answer_only(text: str) -> bool:
    return classify_math_response_intent(text).mode == MathResponseMode.ANSWER_ONLY


def wants_detailed_math_explanation(text: str) -> bool:
    """True for 'explain' / 'why' — not for 'show steps'."""
    return classify_math_response_intent(text).wants_detailed_explanation


def strip_teaching_signals(text: str) -> str:
    """Drop teaching/answer-only metadata so leftover-English still sees the math."""
    return strip_math_response_wrappers(text)


def lesson_math_text(text: str) -> str:
    """The math left after teaching words: "show steps for 2x+3<7" → "2x+3<7"."""
    stripped = strip_teaching_signals(text).strip().lstrip(":").strip()
    for filler in ("for ", "of ", "me "):
        if stripped.lower().startswith(filler):
            stripped = stripped[len(filler) :].lstrip()
    return stripped


def strip_lesson_prefixes(text: str) -> str:
    """Drop show-steps / just-the-answer wrappers before equation extraction."""
    return strip_math_response_wrappers(text)


def should_render_equation_lesson(
    verified: VerifiedMathBlock,
    user_text: str,
    response_style: str,
) -> bool:
    if not verified.key_steps or not (verified.canonical_answer or "").strip():
        return False
    if wants_answer_only(user_text):
        return False
    # A closed equation/system/inequality should teach, regardless of the
    # global prose-length preference. ``key_steps`` is a short,
    # server-rendered, SymPy-checked trace; hiding it in Short mode is what
    # reduced homework to a bare chip. Calculus keeps its existing compact
    # style rules unless the learner explicitly asks how/why/for steps.
    if verified.given_label == "Given":
        return True
    if wants_math_explanation(user_text):
        return True
    if response_style == "short":
        return False
    if response_style == "detailed":
        return True
    return len(verified.key_steps) >= 2


def format_equation_lesson_reply(
    verified: VerifiedMathBlock,
    *,
    include_check: bool = False,
    include_reasons: bool = False,
) -> str:
    """GOLD layout: Given, one transformation per step, chip last.

    Labels are bold ``**1. …**`` (not ``1.`` lists). The formula is the next
    line of that same paragraph so the app can indent it under the label.
    """
    chunks: list[str] = []
    if verified.given_latex:
        # Same line as the label. A blank line made Given its own paragraph,
        # so the equation sat a full gap below the word.
        chunks.append(f"**{verified.given_label}:** ${verified.given_latex}$")
    for index, step in enumerate(verified.key_steps, start=1):
        heading = f"**{index}. {step.label}**"
        if include_reasons and step.reason:
            heading = f"{heading} — {step.reason}"
        chunks.append(_labelled_formula(heading, step.formula))
    body = "\n\n".join(chunks)
    # The same verified value; an inequality spells it as its clean last line.
    answer = (verified.display_answer or verified.canonical_answer or "").strip()
    # A lesson names the final line. A bare chip (no steps) stays unlabeled.
    reply = (
        f"{body}\n\n**Answer**\n\n```answer\n{answer}\n```\n"
        if body
        else f"```answer\n{answer}\n```\n"
    )
    fence = verified.canonical_fence
    if isinstance(fence, dict) and fence.get("type") == "number_line":
        # An inequality lesson keeps its solution set on the number line.
        reply += f"\n```graph\n{json.dumps(fence, separators=(',', ':'))}\n```\n"
    if include_check and verified.check_latex:
        reply += f"\nCheck: ${verified.check_latex}$\n"
    if verified.alternate_method_note:
        reply += f"\n{verified.alternate_method_note}\n"
    return reply


def _labelled_formula(label: str, formula: str) -> str:
    # One newline keeps the formula in the step paragraph so the app can
    # indent it under the label. A blank line was a second paragraph that
    # lined the equation up with the step number.
    return f"{label}\n${formula}$"
