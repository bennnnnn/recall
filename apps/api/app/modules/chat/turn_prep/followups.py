"""A terse follow-up that points back at the problem before it.

"how?" after a solved equation, "check my answer: x = 6", "what about 2 moles?"
after a stoichiometry question, "how far does it go?" after a projectile. Each one
goes back through its subject's verified solver instead of asking the language
model to invent a fresh method. Maths is asked first, then chemistry, then physics;
the first subject that claims the line owns the turn.
"""

from __future__ import annotations

import re
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
from app.services.latex_markup import without_markup
from app.services.problem_followup import changes_relatively, message_role_content
from app.services.subjects.registry import SUBJECTS, SubjectName, subject_adapter


@dataclass(frozen=True)
class SubjectFollowup:
    """The problem to solve again; at most one subject is set. ``asked``: a problem the
    line asks solved whole, as if the user had typed it ("Do it" after the assistant posed
    "A car travels 120 m in 20 s. What is its speed?"); the turn solves and answers it so."""

    math: str | None = None
    chemistry: str | None = None
    physics: str | None = None
    asked: str | None = None

    def problem_of(self, subject: SubjectName) -> str | None:
        """The earlier problem a follow-up solves again with ``subject``, if any."""
        problems: dict[str, str | None] = {
            "math": self.math,
            "chemistry": self.chemistry,
            "physics": self.physics,
        }
        return problems.get(subject)

    @property
    def subject(self) -> SubjectName | None:
        """The subject of the earlier problem the follow-up solves again."""
        return next(
            (adapter.name for adapter in SUBJECTS if self.problem_of(adapter.name) is not None),
            None,
        )

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
    figures: bool = False,
) -> SubjectFollowup:
    """``referent``: the earlier problem a model read as the "it" of "draw it" or "show it"
    (``chat.referent_read``). A curve or a shape is drawn by maths, a scene by physics; a
    maths follow-up of the line's own (the working of the solve before it) comes first.
    ``figures``: the server's figure read draws what a line asks to see of a shape
    (``chat.figure_turn``), so the shape's problem is not solved again for its picture.
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
        shown = _shown(content, history, referent, figures=figures)
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


Change = tuple[str | None, str | None]


def resolve_posed_followup(
    content: str, problem: str, reply: str, changes: Sequence[Change] | None
) -> SubjectFollowup:
    """The follow-up to a problem a model read the line as referring to (``chat.posed_read``):
    solved whole, as typed. ``changes`` (each the given as the problem writes it, and the
    line's new value: "20 seconds", "10 s") are first read by the subject's follow-up readers,
    as if the user had stated the problem; else the problem's subject puts each new value in
    place of the one given of its kind, each found in the problem as stated, every other given
    kept, and the rewrite is solved as typed. "Take the charges as 3.0 pC and 2.0 μC" changes both charges of a
    Coulomb's law problem (live, 2026-11-16). Changes no subject can put in place exactly,
    every one of them, are no solve."""
    if changes is None:
        return SubjectFollowup(asked=problem)
    stated = [{"role": "user", "content": problem}, {"role": "assistant", "content": reply}]
    rewritten = resolve_subject_followup(content, [*stated, {"role": "user", "content": content}])
    # "What if it took 5 s longer?" adds to the time: 25 s, never 5 s. The typed path
    # declines it the same way, and the model answers.
    if rewritten.found or not changes or changes_relatively(content):
        return rewritten
    if any(not new for _given, new in changes):
        return rewritten
    from app.modules.chat.turn_prep.reading import subject_of

    subject = subject_of(problem)
    if subject is None:
        return rewritten
    followups = subject_adapter(subject).followups
    named = [(given, new) for given, new in changes if new]
    changed = followups.changed_problem(problem, named)
    # Every value the line states, not only those the read named, and no question of its own.
    news = [new for _given, new in named]
    if changed is None or not followups.takes_every_change(problem, changed, content, news):
        return rewritten
    # A line that is only the change ("What if T_C = 200 K?") is the problem, as typed, and
    # its card answers it. A line that says more ("... Give the answer in nN and explain why
    # it is so small.") keeps its own words: the change is the subject's follow-up problem,
    # as a typed what-if's is, and the turn's plan, units and whole-question checks read the
    # user's line, never the rewrite in its place.
    if _only_the_change(content, problem, news):
        return SubjectFollowup(asked=changed)
    return SubjectFollowup(**{subject: changed})


# The grammar a what-if is framed in, which says nothing of the problem.
# What maths' "draw it" of a curve begins with (``graph_followup.drawing_of``).
_GRAPH = "graph "
_FRAME = frozenset(
    "what if were was would the then instead and now with into for its this that".split()
)
_CONTENT_WORD = re.compile(r"[^\W\d_]{3,}")


def _only_the_change(line: str, problem: str, news: Sequence[str]) -> bool:
    """``line`` says nothing besides its changed values: with them taken out, every content
    word left is the problem's own ("What if T_C = 200 K?"). A medium, a unit or an ask of
    its own ("in water", "giving the answer in nN", "explaining why") is more than the change,
    and the line keeps its words."""
    rest = without_markup(line)
    for new in news:
        rest = rest.replace(without_markup(new), " ")
    known = {_singular(word) for word in _CONTENT_WORD.findall(without_markup(problem))}
    return all(
        word.lower() in _FRAME or _singular(word) in known for word in _CONTENT_WORD.findall(rest)
    )


def _singular(word: str) -> str:
    """A word, whole, plural or singular alike ("charges" is "charge"): never a stem, so
    "frictionless" is no "friction" and "without" no "with"."""
    lower = word.lower()
    if lower.endswith("es") and len(lower) > 4 and lower[-3] in "sxz":
        return lower[:-2]
    return lower[:-1] if lower.endswith("s") and not lower.endswith("ss") else lower


def _shown(
    content: str, history: Sequence[Any], referent: str, *, figures: bool = False
) -> SubjectFollowup:
    """What the subject of the earlier problem a line asks to see draws it as. With the
    figure read on, a shape is its figure, never its problem solved again: "Draw it" after
    a rectangle's area and then its diagonal repeated the area's card and drew the area's
    rectangle beside the figure (live, 2026-11-20). A curve is still maths' graph."""
    if not blocks_math_followup(referent):
        drawn = subject_adapter("math").followups.shown_problem(content, history, referent)
        if drawn is not None and not (figures and not drawn.startswith(_GRAPH)):
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
