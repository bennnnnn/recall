"""A terse follow-up that points back at the problem before it.

"how?" after a solved equation, "check my answer: x = 6", "what about 2 moles?"
after a stoichiometry question, "how far does it go?" after a projectile. Each one
goes back through its subject's verified solver instead of asking the language
model to invent a fresh method. Maths is asked first, then chemistry, then physics;
the first subject that claims the line owns the turn.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from app.modules.chat.continuation_subject import (
    blocks_math_followup,
    chemistry_working_followup_problem,
    effective_presentation_subject,
    exchange_pairs,
)
from app.modules.chemistry.followup import chemistry_followup_problem
from app.modules.math.followup import (
    answer_claim_problem,
    is_math_followup,
    math_working_followup_problem,
    offered_equation_problem,
    pronoun_math_problem,
    restated_math_problem,
)
from app.modules.physics.followup import physics_followup_problem
from app.services.problem_followup import message_role_content

FollowupSubject = Literal["math", "chemistry", "physics"]


@dataclass(frozen=True)
class SubjectFollowup:
    """The problem to solve again; at most one subject is set."""

    math: str | None = None
    chemistry: str | None = None
    physics: str | None = None

    @property
    def found(self) -> bool:
        return self.math is not None or self.chemistry is not None or self.physics is not None


def resolve_subject_followup(
    content: str, prompt_messages: list[dict[str, str]]
) -> SubjectFollowup:
    # build_prompt_messages has already loaded and adjacency-checked the recent
    # exchange; drop the current user row before reading that pair.
    history = prompt_messages
    if (
        prompt_messages
        and prompt_messages[-1].get("role") == "user"
        and prompt_messages[-1].get("content") == content
    ):
        history = prompt_messages[:-1]
    math = math_working_followup_problem(content, history, blocked=blocks_math_followup)
    # "Do it" after the assistant wrote a new equation is not a request to
    # re-solve the user's earlier line. Solve the offered equation instead.
    if math is None:
        math = offered_equation_problem(content, history)
    # "check my answer: x = 6" is checked against the open problem, and
    # "simplify it" works on the user's last expression. Alone, each one used
    # to be solved as typed: ``x = 6`` verified itself and "it" was ``i t``.
    if math is None:
        math = (
            answer_claim_problem(content, history, blocked=blocks_math_followup)
            or pronoun_math_problem(content, history, blocked=blocks_math_followup)
            or restated_math_problem(content, history, blocked=blocks_math_followup)
        )
    if math is not None:
        return SubjectFollowup(math=math)
    chemistry = chemistry_working_followup_problem(content, history)
    if chemistry is None:
        chemistry = chemistry_followup_problem(content, history)
    if chemistry is not None:
        return SubjectFollowup(chemistry=chemistry)
    return SubjectFollowup(physics=physics_followup_problem(content, history))


def followup_subject(query_text: str | None, exchange: Sequence[Any]) -> FollowupSubject | None:
    """The subject whose problem in ``exchange`` this turn only continues, or None."""
    if is_math_followup(query_text, exchange, blocked=blocks_math_followup):
        return "math"
    if chemistry_followup_problem(query_text, exchange) is not None:
        return "chemistry"
    if physics_followup_problem(query_text, exchange) is not None:
        return "physics"
    return None


def role_content_dicts(messages: Sequence[Any]) -> list[dict[str, str]]:
    """Messages as plain ``role``/``content`` dicts, to read in a SymPy pool worker."""
    out: list[dict[str, str]] = []
    for message in messages:
        role, content = message_role_content(message)
        if role is not None and content is not None:
            out.append({"role": role, "content": content})
    return out


def read_prompt_inputs(
    query_text: str | None, exchange: list[dict[str, str]]
) -> FollowupSubject | None:
    """What the prompt's sections read of the query and the last exchange, in a pool worker.

    Returns ``followup_subject``. The query's subject (the memory scope and the task
    rules ask it) and the presentation subject the style hints read are kept for the
    turn (``core/readings``).
    """
    from app.services.subject_solving import detect_subject

    if query_text:
        detect_subject(query_text)
    effective_presentation_subject(query_text, exchange_pairs(exchange))
    return followup_subject(query_text, exchange)
