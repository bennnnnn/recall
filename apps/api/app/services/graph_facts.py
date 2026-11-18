"""What a subject reads in a question for the graph a reply draws of it.

A physics question writes its quantities in words ("with acceleration 3.5t m/s². When
t = 2 s ... velocity 15 m/s"); the curves that follow from them (v(t), s(t)) are the
subject's to work out, and maths' plot checks a described curve against them as against a
formula the question writes. Formulas cross as SymPy text, so the reading stays the
subject's and the drawing maths' (``services/subjects`` hands a subject's reader over).
"""

from __future__ import annotations

from collections.abc import Callable
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
    (low and high as SymPy text), when it names one, with the letter it is of ("t" for a
    motion's time, "x" for a force's displacement): a stretch of x grounds no v-t graph."""

    formulas: tuple[GraphFormula, ...] = ()
    interval: tuple[str, str] | None = None
    letter: str = ""


# A subject's reader of a question's words (picklable: it runs in the SymPy pool).
GraphFactReader = Callable[[str], GraphFacts]
