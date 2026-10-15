"""Does the reply already state the verified answer, or ask instead of answering?

These decide whether the solver-owned answer chip is appended after the
stream: the same value already visible in the prose is not repeated, and a
reply that asks for missing information gets no verified answer pinned under
it. A *different* value in the prose never hides the chip; plain numbers are
compared as numbers in ``app.services.answer_check``, and the string checks
here cover expressions that are not plain values.
"""

from __future__ import annotations

import logging
import re

from app.modules.math import solve as math_solve
from app.services.answer_check import asks_without_answering

logger = logging.getLogger(__name__)


def _normalize_answer_token(text: str) -> str:
    """Strip math/markup noise so we can test whether prose already states a value."""
    cleaned = (
        text.replace("$", "")
        .replace("`", "")
        .replace("\u2009", "")
        .replace("\u00a0", "")
        .replace("\u2212", "-")
        .replace("\\", "")
    )
    return "".join(cleaned.split()).lower()


def _answer_numeric_core(answer_body: str) -> str:
    """Strip a leading ``x=`` and trailing latin unit so ``2.02 s`` → ``2.02``."""
    token = _normalize_answer_token(answer_body)
    equals = token.rfind("=")
    if equals >= 0:
        token = token[equals + 1 :]
    end = len(token)
    while end > 0 and token[end - 1].isalpha():
        end -= 1
    return token[:end]


def _math_spans(prose: str) -> list[str]:
    """Read complete dollar or TeX-delimited formulas in one forward scan."""
    spans: list[str] = []
    index = 0
    while index < len(prose):
        if prose.startswith((r"\(", r"\["), index):
            closer = r"\)" if prose[index + 1] == "(" else r"\]"
            start = index + 2
        elif prose[index] == "\\":
            # Escaped dollars and literal backslashes are not math openers.
            index += 2
            continue
        elif prose[index] == "$":
            closer = "$$" if prose.startswith("$$", index) else "$"
            start = index + len(closer)
        else:
            index += 1
            continue
        end = prose.find(closer, start)
        if end < 0:
            break
        spans.append(prose[start:end])
        index = end + len(closer)
    return spans


def _contains_value(haystack: str, needle: str) -> bool:
    """``needle`` in ``haystack`` as a whole value: ``12.75`` is not in ``112.75`` or ``12.755``."""
    start = haystack.find(needle)
    while start >= 0:
        end = start + len(needle)
        before = haystack[start - 1] if start > 0 else ""
        after = haystack[end : end + 2]
        number_start = needle[:1].isdigit() or needle[:1] in ".-"
        number_end = needle[-1:].isdigit()
        clipped_before = number_start and (before.isdigit() or before == ".")
        clipped_after = number_end and (
            after[:1].isdigit() or (after[:1] == "." and after[1:2].isdigit())
        )
        if not clipped_before and not clipped_after:
            return True
        start = haystack.find(needle, start + 1)
    return False


def _span_states_short_int(span: str, core: str) -> bool:
    compact = _normalize_answer_token(span)
    return compact == core or compact.endswith("=" + core)


def _normalize_math_answer_expression(text: str) -> str:
    """Compare harmless TeX spelling differences, preserving grouped powers."""
    # Remove spacing commands before whitespace/command slashes are stripped.
    # Word boundaries keep \quad from binding inside a different command name.
    spaced = re.sub(r"\\(?:qquad|quad)(?![A-Za-z])", "", text)
    for spacing in (r"\,", r"\;", r"\:", r"\!", "\\ "):
        spaced = spaced.replace(spacing, "")
    # Upright unit lettering is presentation only, but unit case is semantic:
    # mJ and MJ must never compare equal. Keep this fallback case-sensitive.
    spaced = re.sub(r"\\mathrm\{([A-Za-z°]{1,24})\}", r"\1", spaced)
    cleaned = (
        spaced.replace(r"\left", "")
        .replace(r"\right", "")
        .replace("$", "")
        .replace("\u2212", "-")
        .replace("\\", "")
    )
    compact = "".join(cleaned.split())
    # Only one literal atom: x^{12} and x^12 are different TeX expressions,
    # as are x^{1/6} and x^1/6. Never remove arbitrary grouping braces.
    return re.sub(r"\^\{([A-Za-z0-9])\}", r"^\1", compact)


def prose_already_states_answer(content: str, answer_body: str) -> bool:
    """True when the verified value is already visible in the assistant prose.

    Short integers (1-2 digits) must appear as a whole math result (``$2$`` or
    a span ending in ``=2``) so a digit inside ``$x^2$`` does not suppress the
    pill. Longer values (``2.02 s``, ``x = 12``) use a normalized substring.
    """
    body = answer_body.strip()
    if not body:
        return False
    core = _answer_numeric_core(body)
    if core.isdigit() and len(core) <= 2:
        return any(_span_states_short_int(span, core) for span in _math_spans(content))
    needle = _normalize_answer_token(body)
    if len(needle) < 2:
        return False
    if r"\mathrm{" not in body and _contains_value(_normalize_answer_token(content), needle):
        return True
    # Formatting equivalence applies to complete math results only. A looser
    # substring check would find canonical x^{1} inside the different x^12.
    expression = _normalize_math_answer_expression(body)
    for span in _math_spans(content):
        stated = _normalize_math_answer_expression(span)
        if stated == expression or stated.endswith("=" + expression):
            return True
    return False


_MAX_SYMBOLIC_ANSWER_CHECKS = 2


def _answer_rhs(text: str) -> str:
    """Right-hand side of the last ``=`` (or the whole body for a bare result)."""
    body = text.strip().strip("$").strip()
    equals = body.rfind("=")
    return body[equals + 1 :].strip() if equals >= 0 else body


def _sympy_expr_or_none(text: str):  # type: ignore[no-untyped-def]
    """Parse a prose/latex answer candidate into a SymPy expression; None on failure."""
    candidate = _answer_rhs(text)
    if not candidate or len(candidate) > 120:
        return None
    try:
        return math_solve._parse_expression(candidate)
    except Exception:
        return None


def prose_symbolically_states_answer(content: str, answer_body: str) -> bool:
    """SymPy-proven equivalence between the canonical answer and a prose math span.

    The string paths above miss harmless value spelling differences — prose
    ``$0.5$`` next to a canonical ``\\frac{1}{2}`` used to earn a duplicate
    answer chip. validate_math_fences runs inside the SymPy worker
    (``validate_math_fences_worker``), so this shares the existing post-stream
    budget; it adds no new latency class. This only ever *suppresses* a
    duplicate chip on proof of equivalence — every failure returns False,
    which appends the chip exactly as today.
    """
    canonical = _sympy_expr_or_none(answer_body)
    if canonical is None:
        return False
    # A bare prose expression (no "=") only counts when the canonical answer is
    # a bare number. Symbolically ``x^12`` == ``x^{12}``, but as *rendered*
    # prose the unbraced grouping displays differently — the chip must stay.
    canonical_is_bare_number = "=" not in answer_body and not any(
        ch.isalpha() for ch in _answer_rhs(answer_body)
    )
    checks = 0
    for span in _math_spans(content):
        if checks >= _MAX_SYMBOLIC_ANSWER_CHECKS:
            break
        if "=" not in span and not canonical_is_bare_number:
            continue
        candidate = _sympy_expr_or_none(span)
        if candidate is None:
            continue
        checks += 1
        if _sympy_equivalent(candidate, canonical):
            return True
    return False


def _sympy_equivalent(a, b) -> bool:  # type: ignore[no-untyped-def]
    """SymPy ``equals`` with the undecidable/exception cases folded to False."""
    try:
        return bool(a.equals(b))
    except Exception:
        logger.debug("symbolic answer comparison failed", exc_info=True)
        return False


# Emphasis and code ticks trailing the question mark: "**...?**", "...?*".
_TRAILING_MARKUP = "*_`~ \t"


def _line_asks(line: str) -> bool:
    return line.rstrip(_TRAILING_MARKUP).endswith("?")


def reply_asks_instead_of_answering(content: str, answer_body: str | None) -> bool:
    """True when the reply requests information rather than giving a result.

    The fences below are solver-owned — the model is told not to emit them, so
    they are attached whenever they are missing. "Missing" was read as "the
    model forgot", because nothing here could tell that apart from a reply that
    deliberately has no answer in it. So when the model correctly answered a 2D
    collision with *"Which ball's final path is at 30°?"*, the pipeline pinned a
    verified ``0.79 m`` and a trajectory chart underneath the question.

    Both halves are needed, and the second is the one that keeps this safe. A
    question mark alone proves nothing: *"The range is about 35.31 m. Would you
    like the maximum height?"* answers first and asks second, and must keep its
    chart. It is the *absence* of an answer beside the question that makes a
    reply a request for more information.

    Position, on the other hand, proves nothing either way, which the incident
    itself showed: its question is the opening line and its closing line is a
    plain statement, so "the reply ends with a question" would have missed the
    very case this exists for. Any line that asks counts.

    A solver that produced no answer at all is the third case, and it is not
    this one. Angles alone fix a triangle's shape but not its size, so the
    solver returns a diagram, no number, and the reply asks for a side length —
    a question and no stated answer, yet the diagram is exactly right. What
    makes the incident wrong is a *verified answer* being pinned to a reply that
    does not make it, so with no such answer there is nothing to withhold.

    "States an answer" means any final value, right or wrong: "Subtract 5,
    then divide: x = 7. Want to try a harder one?" answered (wrongly) and then
    offered more, so it keeps the verified card and gets a correction.
    """
    if not answer_body:
        return False
    numeric = asks_without_answering(content, answer_body)
    if numeric is not None:
        return numeric and not prose_already_states_answer(content, answer_body)
    if not any(_line_asks(line) for line in content.splitlines()):
        return False
    return not prose_already_states_answer(content, answer_body)
