"""A word problem translated into unknowns and equations (LLM-extracted).

The translation is never trusted: every number must appear in the problem,
and SymPy must find exactly one solution that fits the stated domain before
anything reaches the user. Text fields are shown in the reply, so they are
short and later stripped of markup.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class WordUnknown(BaseModel):
    symbol: str = Field(pattern=r"^[a-z]$")
    meaning: str = Field(min_length=1, max_length=80)
    unit: str | None = Field(default=None, max_length=24)


class WordEquation(BaseModel):
    # Plain ASCII math with one "=": "m = 3*s".
    equation: str = Field(min_length=3, max_length=160)
    # The words of the problem this equation says, shown beside it.
    source: str | None = Field(default=None, max_length=160)


class WordTarget(BaseModel):
    # What the question asks for: an unknown ("s") or an expression in them.
    expr: str = Field(min_length=1, max_length=64)
    meaning: str = Field(min_length=1, max_length=80)
    unit: str | None = Field(default=None, max_length=24)


class WordProblemSetup(BaseModel):
    found: bool = False
    unknowns: list[WordUnknown] = Field(default_factory=list, max_length=3)
    equations: list[WordEquation] = Field(default_factory=list, max_length=4)
    targets: list[WordTarget] = Field(default_factory=list, max_length=3)
    # Counts of people or things: a fractional solution is a misreading.
    whole_numbers: bool = False
    # Ages, lengths, prices: a negative solution is a misreading.
    positive: bool = False
