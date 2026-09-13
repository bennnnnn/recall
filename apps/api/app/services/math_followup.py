"""Presentation-only context for a short follow-up to the immediately prior math turn."""

from collections.abc import Sequence
from typing import Any

from app.services.math_tools.prompt import needs_symbolic_math

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

# Whole messages only: do not let an old math question capture a new "how ..." topic.
_REFERENTIAL_REQUESTS = frozenset(
    {
        "how",
        "why",
        "how so",
        "why is that",
        "how does that work",
        "how did you get that",
        "how did you get this",
        "how did you get that answer",
        "how did you calculate that",
        "how is that calculated",
        "explain",
        "explain it",
        "explain that",
        "explain this",
        "explain the answer",
        "explain the result",
        "explain the steps",
        "show the steps",
        "show me the steps",
        "show your work",
        "show me how",
        "show me why",
        "walk me through it",
        "explain step by step",
        "prove it",
        "prove that",
        "show the proof",
        "show me the proof",
        "hint",
        "hint only",
        "a hint",
        "give a hint",
        "give me a hint",
        "give an example",
        "give me an example",
        "show an example",
        "show me an example",
        "give examples",
        "give me examples",
        "show examples",
        "show me examples",
        "explain with an example",
        "explain with examples",
    }
)


def is_math_followup(query: str | None, recent: Sequence[Any]) -> bool:
    """Require one complete adjacent user/assistant math exchange; never scan older topics."""
    if not query or len(query) > 120 or len(recent) < 2:
        return False
    cleaned = " ".join(query.lower().split()).strip(".!?")
    for prefix in ("please ", "can you ", "could you ", "would you "):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :]
    if cleaned.endswith(" please"):
        cleaned = cleaned[:-7]
    if cleaned not in _REFERENTIAL_REQUESTS:
        return False
    question, answer = recent[-2:]
    if getattr(question, "role", None) != "user" or getattr(answer, "role", None) != "assistant":
        return False
    prior = getattr(question, "content", None)
    reply = getattr(answer, "content", None)
    return bool(
        isinstance(prior, str)
        and prior.strip()
        and isinstance(reply, str)
        and reply.strip()
        and needs_symbolic_math(prior)
    )


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
