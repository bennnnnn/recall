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
from typing import Any

from app.modules.chat.continuation_subject import (
    blocks_math_followup,
    chemistry_working_followup_problem,
    effective_presentation_subject,
    exchange_pairs,
)
from app.modules.chat.prompt_inject import conversation_turns
from app.services.problem_followup import message_role_content
from app.services.subjects.registry import SubjectName, subject_adapter


@dataclass(frozen=True)
class SubjectFollowup:
    """The problem to solve again; at most one subject is set. ``asked``: a problem the
    line asks solved whole, as if the user had typed it ("Do it" after the assistant posed
    "A car travels 120 m in 20 s. What is its speed?"); the turn solves and answers it so."""

    math: str | None = None
    chemistry: str | None = None
    physics: str | None = None
    asked: str | None = None

    @property
    def found(self) -> bool:
        return any(
            problem is not None for problem in (self.math, self.chemistry, self.physics, self.asked)
        )


def resolve_subject_followup(
    content: str,
    prompt_messages: list[dict[str, str]],
    referent: str | None = None,
    continued: str | None = None,
) -> SubjectFollowup:
    """``referent``: the earlier problem a model read as the "it" of "draw it" or "show it"
    (``chat.referent_read``). A curve or a shape is drawn by maths, a scene by physics; a
    maths follow-up of the line's own (the working of the solve before it) comes first.
    ``continued``: the problem a model read "3" or "the area" as continuing, whole."""
    # build_prompt_messages has already loaded and adjacency-checked the recent
    # exchange; drop the current user row before reading that pair. The turn's own
    # context sits between them, so only the conversation is read.
    history = conversation_turns(prompt_messages)
    if history and history[-1].get("role") == "user" and history[-1].get("content") == content:
        history = history[:-1]
    math = subject_adapter("math").followups.problem(content, history, blocked=blocks_math_followup)
    if math is not None:
        # "Show me that" after a solve is its working, as before: before any drawing.
        return SubjectFollowup(math=math)
    if referent is not None:
        shown = _shown(content, history, referent)
        if shown.found:
            return shown
    if continued is not None and not blocks_math_followup(continued):
        if subject_adapter("math").asks(continued):
            return SubjectFollowup(math=continued)
    chemistry = chemistry_working_followup_problem(content, history)
    if chemistry is None:
        chemistry = subject_adapter("chemistry").followups.problem(content, history)
    if chemistry is not None:
        return SubjectFollowup(chemistry=chemistry)
    return SubjectFollowup(physics=subject_adapter("physics").followups.problem(content, history))


def resolve_posed_followup(
    content: str, problem: str, reply: str, change: tuple[str | None, str | None] | None
) -> SubjectFollowup:
    """The follow-up to a problem a model read the line as referring to (``chat.posed_read``):
    solved whole, as typed. A ``change`` (the given as the problem writes it, and the line's
    new value: "20 seconds", "10 s") is first read by the subject's follow-up readers, as if
    the user had stated the problem; else the problem's subject puts the new value in place
    of the one given of its kind, every other given kept, and the rewrite is solved as
    typed. A change no subject can put in place exactly is no solve."""
    if change is None:
        return SubjectFollowup(asked=problem)
    stated = [{"role": "user", "content": problem}, {"role": "assistant", "content": reply}]
    rewritten = resolve_subject_followup(content, [*stated, {"role": "user", "content": content}])
    given, new = change
    if rewritten.found or not new:
        return rewritten
    from app.modules.chat.turn_prep.reading import subject_of

    subject = subject_of(problem)
    if subject is None:
        return rewritten
    changed = subject_adapter(subject).followups.changed_problem(problem, given, new)
    return rewritten if changed is None else SubjectFollowup(asked=changed)


def _shown(content: str, history: Sequence[Any], referent: str) -> SubjectFollowup:
    """What the subject of the earlier problem a line asks to see draws it as."""
    if not blocks_math_followup(referent):
        drawn = subject_adapter("math").followups.shown_problem(content, history, referent)
        if drawn is not None:
            return SubjectFollowup(math=drawn)
    return SubjectFollowup(
        physics=subject_adapter("physics").followups.shown_problem(content, history, referent)
    )


def followup_subject(query_text: str | None, exchange: Sequence[Any]) -> SubjectName | None:
    """The subject whose problem in ``exchange`` this turn only continues, or None."""
    if subject_adapter("math").followups.continues(
        query_text, exchange, blocked=blocks_math_followup
    ):
        return "math"
    if subject_adapter("chemistry").followups.continues(query_text, exchange):
        return "chemistry"
    if subject_adapter("physics").followups.continues(query_text, exchange):
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
    query_text: str | None,
    exchange: list[dict[str, str]],
    part_texts: tuple[str, ...] = (),
) -> SubjectName | None:
    """What the prompt's sections read of the query and the last exchange, in a pool worker.

    Returns ``followup_subject``. The query's subject (the memory scope and the task
    rules ask it), each request's subject (a part's own layout asks it) and the
    presentation subject the style hints read are kept for the turn (``core/readings``).
    """
    from app.services.subjects.dispatch import detect_subject

    for text in dict.fromkeys((query_text, *part_texts)):
        if text:
            detect_subject(text)
    effective_presentation_subject(query_text, exchange_pairs(exchange))
    return followup_subject(query_text, exchange)
