"""What a subject reads in a question for the graph a reply draws of it.

A physics question writes its quantities in words ("with acceleration 3.5t m/s². When
t = 2 s ... velocity 15 m/s"); the curves that follow from them (v(t), s(t)) are the
subject's to work out, and maths' plot checks a described curve against them as against a
formula the question writes. Formulas cross as SymPy text, so the reading stays the
subject's and the drawing maths' (``services/subjects`` hands a subject's reader over).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class GraphFormula:
    """One quantity as a formula of the graph's across: "v", "7*t**2/4 + 8", "m/s"."""

    name: str
    formula: str
    unit: str = ""


@dataclass(frozen=True)
class GraphFacts:
    """The formulas a question's words give, and the stretch of the across it asks about
    (low and high as SymPy text), when it names one."""

    formulas: tuple[GraphFormula, ...] = ()
    interval: tuple[str, str] | None = None


# A subject's reader of a question's words (picklable: it runs in the SymPy pool).
GraphFactReader = Callable[[str], GraphFacts]


def first_facts(texts: Sequence[str], reader: GraphFactReader) -> GraphFacts | None:
    """The facts of the first text whose words give any (the last message first): a
    follow-up ("Now draw the velocity-time graph.") takes the question's, as the plot takes
    the formulas of the first message that writes one."""
    for text in texts:
        found = reader(text)
        if found.formulas or found.interval is not None:
            return found
    return None
