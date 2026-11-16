"""A STEM question written down as maths by a model: what it gives, what it asks, how they relate.

The model reads the question in any wording and any language; it names no catalog law and
matches no phrase. It writes each given value with its unit and the words it came from,
each unknown with its unit, and the equations that join them. The server then checks and
solves that setup (``formal.solve``); the model's own final answer travels with it, so the
two can be compared.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# A setup longer than this is not a school problem; the read is refused rather than solved.
MAX_SYMBOLS = 16
MAX_EQUATIONS = 12


class Given(BaseModel):
    """A value the question states, or a standard constant it relies on (g, c, ...)."""

    symbol: str = Field(max_length=24)
    value: str = Field(max_length=40)
    unit: str = Field(default="", max_length=40)
    # The question's own words for it ("100 km/h", "cien kilómetros por hora"); "" for a
    # constant the question does not state.
    quote: str = Field(default="", max_length=120)
    constant: bool = False


class Unknown(BaseModel):
    """A quantity the equations solve for: the one asked, or one on the way to it."""

    symbol: str = Field(max_length=24)
    unit: str = Field(default="", max_length=40)


class FormalProblem(BaseModel):
    # False when the message is no question with one numeric answer (a concept, an
    # explanation, several separate questions, data missing).
    solvable: bool = True
    givens: list[Given] = Field(default_factory=list, max_length=MAX_SYMBOLS)
    unknowns: list[Unknown] = Field(default_factory=list, max_length=MAX_SYMBOLS)
    # "lhs = rhs" in the symbols above: Python/SymPy syntax (*, /, **, sqrt, sin, cos, tan,
    # asin, acos, atan, exp, log, pi). Angles in trig functions are in radians unless a
    # given is in degrees, which the server converts.
    equations: list[str] = Field(default_factory=list, max_length=MAX_EQUATIONS)
    # The symbol the question asks for, and the unit it asks for it in (or the usual one).
    target: str = Field(default="", max_length=24)
    target_unit: str = Field(default="", max_length=40)
    # The model's own final answer, in ``target_unit``: compared with the server's.
    answer: float | None = None
