"""Direct verified-math replies that skip the LLM when language adds nothing."""

from __future__ import annotations

from app.services.math_tools.block.common import VerifiedMathBlock

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

# Imperative / polite glue around a closed compute. Two leftover English
# words beyond this ("tell" + "joke") keep the LLM.
_MATH_REQUEST_GLUE = frozenset(
    {
        "solve",
        "isolate",
        "factor",
        "expand",
        "simplify",
        "calculate",
        "compute",
        "evaluate",
        "determine",
        "find",
        "please",
        "thanks",
        "thank",
        "now",
        "quickly",
        "briefly",
        "here",
        "what",
        "whats",
        "the",
        "value",
        "of",
        "for",
        "and",
        "then",
        "is",
        "equals",
        "equal",
        "plus",
        "minus",
        "times",
        "can",
        "you",
        "could",
        "this",
        "that",
    }
)

_MAX_DIRECT_ANSWER_CHARS = 400


def wants_math_explanation(text: str) -> bool:
    """True when the user asked for language (steps / teaching), not just the value."""
    lowered = text.lower()
    if any(phrase in lowered for phrase in _EXPLAIN_PHRASES):
        return True
    padded = f" {lowered} "
    return " prove " in padded or " proof " in padded


def _looks_math_token(tok: str) -> bool:
    if not tok:
        return True
    return any(ch.isdigit() or ch in "=^*/+-%" for ch in tok)


def leftover_non_math_request(text: str) -> bool:
    """True when the message asks for something besides the verified value.

    ``Solve x+1=2 and tell me a joke`` must not become an instant ``x = 1``.
    Linear token walk — no regex on user text.
    """
    english = 0
    for raw in text.replace("'", "").split():
        tok = raw.lower().strip(".,?!:;")
        if _looks_math_token(tok) or len(tok) < 3 or tok in _MATH_REQUEST_GLUE:
            continue
        english += 1
        if english >= 2:
            return True
    return False


def _solver_fences(verified: VerifiedMathBlock) -> list[dict[str, object]]:
    fences: list[dict[str, object]] = []
    if verified.canonical_fence is not None:
        fences.append(verified.canonical_fence)
    for fence in verified.canonical_fences:
        if fence is not None and fence not in fences:
            fences.append(fence)
    return fences


def can_direct_verified_math_reply(
    verified: VerifiedMathBlock,
    user_text: str,
    *,
    has_image_attachment: bool = False,
) -> bool:
    """Skip the LLM when SymPy already owns a short closed answer.

    Geometry/graph still need a one-line description. Camera homework is
    usually "show the work". Explanation cues keep the current inject+stream.
    """
    if has_image_attachment:
        return False
    if wants_math_explanation(user_text):
        return False
    if leftover_non_math_request(user_text):
        return False
    answer = (verified.canonical_answer or "").strip()
    if not answer or len(answer) > _MAX_DIRECT_ANSWER_CHARS:
        return False
    fences = _solver_fences(verified)
    if not fences:
        return True
    return all(fence.get("type") == "answer" for fence in fences)


def format_direct_math_reply(verified: VerifiedMathBlock) -> str:
    """Display the verified value in ``$...$`` (or `` ```math ``) plus `` ```answer ``."""
    answer = (verified.canonical_answer or "").strip()
    if "\\begin{aligned}" in answer or "\n" in answer:
        display = f"```math\n{answer}\n```"
    else:
        inner = answer.strip("$")
        display = f"${inner}$"
    return f"{display}\n\n```answer\n{answer}\n```"


def maybe_direct_math_reply(
    verified: VerifiedMathBlock | None,
    user_text: str,
    *,
    has_image_attachment: bool = False,
) -> str | None:
    if verified is None:
        return None
    if not can_direct_verified_math_reply(
        verified, user_text, has_image_attachment=has_image_attachment
    ):
        return None
    return format_direct_math_reply(verified)
