"""A STEM question written down as maths by a model: what it gives, what it asks, how they relate.

The model reads the question in any wording and any language; it names no catalog law and
matches no phrase. It writes each given value with its unit and the words it came from,
each unknown with its unit, the equations that join them, what each part asks, and the
relations the question's own values must keep (a stated balance, an efficiency at most
100%). The server then checks and solves that setup (``formal.solve``); the model's own
answer to each part travels with it, so the two can be compared.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# A setup longer than this is not a school problem; the read is refused rather than solved.
MAX_SYMBOLS = 16
MAX_EQUATIONS = 12
MAX_PARTS = 8
MAX_CHECKS = 4


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


class Asked(BaseModel):
    """One value the question asks for: one part of a question in parts ("a" … "h"), or the
    whole question ("")."""

    part: str = Field(default="", pattern=r"^[a-h]?$")
    symbol: str = Field(max_length=24)
    # The unit the question asks for it in, or the usual one.
    unit: str = Field(default="", max_length=40)
    # The model's own answer, in ``unit``: compared with the server's.
    answer: float | None = None


class Check(BaseModel):
    """A relation the question's values must keep, "lhs = rhs" or with <=, >=, <, >: a
    balance or an equilibrium the question states, or a bound a law sets (a machine's
    efficiency at most 100%, MA <= VR). The server tests it on the values."""

    relation: str = Field(max_length=200)
    # Why it must hold, in a few words in the question's language ("a balanced lever has
    # equal moments on each side"): said to the student when the values break it.
    meaning: str = Field(default="", max_length=160)


class FormalProblem(BaseModel):
    # False when the message asks no value from one setup (a concept, an explanation,
    # unrelated questions, data missing).
    solvable: bool = True
    givens: list[Given] = Field(default_factory=list, max_length=MAX_SYMBOLS)
    unknowns: list[Unknown] = Field(default_factory=list, max_length=MAX_SYMBOLS)
    # "lhs = rhs" in the symbols above: Python/SymPy syntax (*, /, **, sqrt, sin, cos, tan,
    # asin, acos, atan, exp, log, pi). Angles in trig functions are in radians unless a
    # given is in degrees, which the server converts.
    equations: list[str] = Field(default_factory=list, max_length=MAX_EQUATIONS)
    # What the question asks, one entry per part.
    asked: list[Asked] = Field(default_factory=list, max_length=MAX_PARTS)
    checks: list[Check] = Field(default_factory=list, max_length=MAX_CHECKS)
