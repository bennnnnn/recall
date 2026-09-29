"""Presentation-only context for a short follow-up to the immediately prior math turn."""

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from app.modules.math.response_intent import (
    MathResponseMode,
    classify_math_response_intent,
)
from app.modules.math.tools.prompt import needs_symbolic_math

MATH_FOLLOWUP_HINT = (
    "This short request refers to the immediately preceding math exchange. Give only "
    "the requested reasoning, proof, hint, or examples, then stop. For 'how' or 'why', "
    "show the calculation or mathematical argument connecting the preceding problem "
    "to its result, stating any theorem needed and showing how it applies. "
    "A request for a proof, hint, or examples "
    "keeps its requested scope; a hint must not reveal the solution. Do not add "
    "unrequested comparisons, unit conversions, real-world applications, history, "
    "trivia, fun facts, or a second "
    "recap/explanation section. Retain units, conditions, and mathematical distinctions "
    "needed for correctness. Previous results are conversation context, not fresh "
    "solver verification."
)


def _message_field(message: Any, field: str) -> Any:
    if isinstance(message, Mapping):
        return message.get(field)
    return getattr(message, field, None)


def _referenced_math_problem(
    query: str | None,
    recent: Sequence[Any],
    *,
    working_only: bool,
    blocked: Callable[[str], bool] | None = None,
) -> str | None:
    """Return the problem from an adjacent chain of math follow-ups.

    A learner may naturally say ``What?`` → ``Show me`` → ``Do it again``.
    Walk backward only through those short, explicitly referential exchanges;
    any unrelated or incomplete exchange still stops the lookup immediately.
    """
    response = classify_math_response_intent(query or "")
    if not response.referential or len(recent) < 2:
        return None
    if working_only and response.mode not in {
        MathResponseMode.EXPLAIN,
        MathResponseMode.STEPS,
        MathResponseMode.DETAILED,
    }:
        return None
    # Four complete exchanges are enough for a natural clarification chain
    # without turning this into a search over stale chat history.
    cursor = len(recent) - 2
    checked = 0
    while cursor >= 0 and checked < 4:
        question, answer = recent[cursor : cursor + 2]
        if (
            _message_field(question, "role") != "user"
            or _message_field(answer, "role") != "assistant"
        ):
            return None
        prior = _message_field(question, "content")
        reply = _message_field(answer, "content")
        if not (
            isinstance(prior, str) and prior.strip() and isinstance(reply, str) and reply.strip()
        ):
            return None
        if blocked is not None and blocked(prior):
            return None
        if needs_symbolic_math(prior):
            return prior
        if not classify_math_response_intent(prior).referential:
            return None
        cursor -= 2
        checked += 1
    return None


def open_math_problem(text: str, prior_user_messages: list[str] | None) -> str | None:
    """The equation still in progress when this message is only a fragment.

    ``5`` or ``x`` after ``3x^2 + 3 = 5`` is the same problem, not a new chat.
    A greeting or a new equation does not reopen it.
    """
    if not prior_user_messages:
        return None
    cleaned = " ".join(text.split())
    if not cleaned or len(cleaned) > 24:
        return None
    from app.services.chat.prompt_constants.routing import is_lightweight_chat_turn

    if is_lightweight_chat_turn(cleaned):
        return None
    if needs_symbolic_math(text):
        return None
    for prior in reversed(prior_user_messages):
        if prior and prior.strip() and needs_symbolic_math(prior):
            return prior
    return None


def is_math_followup(
    query: str | None,
    recent: Sequence[Any],
    *,
    blocked: Callable[[str], bool] | None = None,
) -> bool:
    """Require one complete adjacent user/assistant math exchange; never scan older topics."""
    return _referenced_math_problem(query, recent, working_only=False, blocked=blocked) is not None


def math_working_followup_problem(
    query: str | None,
    recent: Sequence[Any],
    *,
    blocked: Callable[[str], bool] | None = None,
) -> str | None:
    """Return the adjacent problem when a follow-up asks for its verified working."""
    return _referenced_math_problem(query, recent, working_only=True, blocked=blocked)


def readable_standalone_answer(content: str) -> str | None:
    """Keep only a complete, standalone owned answer as math, never fenced payloads.

    General prose/mixed fences retain the existing prompt-history stripping path.
    No truncation or symbolic re-evaluation: preserve a supported answer body intact.
    """
    lines = content.strip().splitlines()
    if len(lines) < 3 or lines[0] != "```answer" or lines[-1] != "```":
        return None
    body = "\n".join(lines[1:-1]).strip()
    if not body or len(body) > 4000 or "`" in body or "$" in body:
        return None
    # JSON/tool data is not a mathematical answer. Preserve such unfamiliar
    # content through neither this narrow exception nor a raw owned fence.
    if body.startswith(("{", "[")):
        return None
    return f"Previous result:\n\\[\n{body}\n\\]"
