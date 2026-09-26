"""Server-rendered equation lessons from verified ``key_steps``."""

from __future__ import annotations

import json

from app.services.solving import VerifiedMathBlock

# Linear phrase scan — do not put user text through nested-optional regex
# (CodeQL py/polynomial-redos). Substrings are enough: "explain every step"
# should keep the LLM; "1+1=x" should not.
_EXPLAIN_PHRASES: tuple[str, ...] = (
    "explain",
    "teach",
    "show work",
    "show your work",
    "show me your work",
    "show me work",
    "show the steps",
    "show me the steps",
    "show steps",
    "show me how",
    "show working",
    "step by step",
    "step-by-step",
    "walk me",
    "why is",
    "why does",
    "how do",
    "how does",
    "how to",
    "how can",
    "how would",
)

_ANSWER_ONLY_PHRASES: tuple[str, ...] = (
    "just the answer",
    "just the number",
    "without steps",
    "no steps",
    "answer only",
    "only the answer",
)

# "Show steps" is a short lesson. These ask for the extra why-sentence.
_DETAILED_EXPLAIN_PHRASES: tuple[str, ...] = (
    "explain",
    "teach",
    "walk me",
    "why is",
    "why does",
    "how do",
    "how does",
    "how to",
    "how can",
    "how would",
    "show me how",
)

_METHOD_PHRASES: tuple[str, ...] = (
    "using the quadratic formula",
    "with the quadratic formula",
    "using factoring",
    "by factoring",
    "with factoring",
)

# Prefixes that wrap a closed equation without changing it. Do not include
# "explain" / "why" — those are conversational asks, not lesson metadata.
_LESSON_PREFIX_PHRASES: tuple[str, ...] = tuple(
    sorted(
        {
            "show work",
            "show your work",
            "show me your work",
            "show me work",
            "show the steps",
            "show me the steps",
            "show steps",
            "show working",
            "step by step",
            "step-by-step",
            *_ANSWER_ONLY_PHRASES,
            *_METHOD_PHRASES,
        },
        key=len,
        reverse=True,
    )
)

_STRIP_PHRASES: tuple[str, ...] = tuple(
    sorted(
        {*_EXPLAIN_PHRASES, *_ANSWER_ONLY_PHRASES, *_METHOD_PHRASES},
        key=len,
        reverse=True,
    )
)


def wants_math_explanation(text: str) -> bool:
    """True when the user asked for language (steps / teaching), not just the value."""
    lowered = text.lower()
    if any(phrase in lowered for phrase in _EXPLAIN_PHRASES):
        return True
    padded = f" {lowered} "
    return " prove " in padded or " proof " in padded


def wants_answer_only(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in _ANSWER_ONLY_PHRASES)


def wants_detailed_math_explanation(text: str) -> bool:
    """True for 'explain' / 'why' — not for 'show steps'."""
    lowered = text.lower()
    return any(phrase in lowered for phrase in _DETAILED_EXPLAIN_PHRASES)


def strip_teaching_signals(text: str) -> str:
    """Drop teaching/answer-only metadata so leftover-English still sees the math."""
    return _strip_phrases(text, _STRIP_PHRASES)


def lesson_math_text(text: str) -> str:
    """The math left after teaching words: "show steps for 2x+3<7" → "2x+3<7"."""
    stripped = strip_teaching_signals(text).strip().lstrip(":").strip()
    for filler in ("for ", "of ", "me "):
        if stripped.lower().startswith(filler):
            stripped = stripped[len(filler) :].lstrip()
    return stripped


def strip_lesson_prefixes(text: str) -> str:
    """Drop show-steps / just-the-answer wrappers before equation extraction."""
    return _strip_phrases(text, _LESSON_PREFIX_PHRASES)


def _strip_phrases(text: str, phrases: tuple[str, ...]) -> str:
    result = text
    lower = result.lower()
    while True:
        hit: tuple[int, int] | None = None
        for phrase in phrases:
            idx = lower.find(phrase)
            if idx >= 0:
                hit = (idx, idx + len(phrase))
                break
        if hit is None:
            break
        start, end = hit
        result = f"{result[:start]} {result[end:]}"
        lower = result.lower()
    return " ".join(result.split())


def should_render_equation_lesson(
    verified: VerifiedMathBlock,
    user_text: str,
    response_style: str,
) -> bool:
    if not verified.key_steps or not (verified.canonical_answer or "").strip():
        return False
    if wants_answer_only(user_text):
        return False
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
    reply = f"{body}\n\n```answer\n{answer}\n```\n" if body else f"```answer\n{answer}\n```\n"
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
