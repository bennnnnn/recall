"""A follow-up that changes an amount of a reaction problem, or asks for another substance.

Live failure (2026-10-25): after "how much water do i get if i burn like 4g of h2", the student
asked "ok back to the first one. what if i only had 16g of o2": 4 g of H2 with only 16 g of O2,
so the oxygen runs out first and limits the water to 18 g. The free model opened with "8 g of
hydrogen", wrote "Wait, I made a mistake" and answered another question. The line keeps the
reaction and changes one thing:

- an amount of a substance the problem states replaces it ("what if it was 10 g of h2");
- an amount of another reactant joins it, and the limiting reagent decides ("what if i only had
  16g of o2");
- another substance of the reaction is asked ("and how much o2 do i need", "what about the
  co2").

The problem is read from its own text, written out again whole (balanced equation first) and
used only when it verifies (``followup.py``). It is the latest earlier problem whose reaction
holds the substance the line names, so "back to the first one" after another question finds
it. Each shape is the whole line: "how much co2 does a car emit" asks something new.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Any

from app.modules.chemistry.equations import balance_equation, format_balanced
from app.modules.chemistry.extract import extract_chemistry_intent
from app.modules.chemistry.species_words import substance_mentions, with_formulas
from app.services.number_text import TEXT_NUMBER
from app.services.problem_followup import message_role_content

_MAX_LINE = 120
# Earlier user lines searched for the reaction the line continues.
_MAX_PROBLEMS = 6
_UNITS = {"g": "g", "gram": "g", "grams": "g", "mol": "mol", "mole": "mol", "moles": "mol"}
_UNIT_WORDS = {"g": "grams", "mol": "moles"}
# The operations whose stated amounts, in grams or moles, a follow-up can change.
_READ_AMOUNTS = {"mass_stoichiometry", "limiting_mass", "stoichiometry"}

_LEAD = r"(?:[^.\d]{0,40}[.!]\s+)?(?:(?:and|but|so|ok(?:ay)?|now|then)[ ,]+)*"
_AMOUNT = rf"(?P<value>{TEXT_NUMBER})\s*(?P<unit>g|grams?|mol|moles?)\s+(?:of\s+)?(?:the\s+)?"
_IF_HAD = (
    r"(?:(?:(?:what|how)\s+about|what\s+if|if|with|try|using|use)\s+)?"
    r"(?:(?:i|we|you|they|it|there)\s+(?:only\s+)?"
    r"(?:had|have|has|used|use|start(?:ed)?\s+with|was|were|is|are)\s+)?(?:only\s+|just\s+)?"
)
_ASK_HEAD = (
    r"(?:(?:(?:what|how)\s+about\s+)|(?:how\s+(?:much|many)(?:\s+(?P<asked>grams?|g|moles?|mol))?"
    r"(?:\s+of)?|what\s+(?P<mass>mass|amount)\s+of)\s+)?(?:the\s+)?"
)
_ASK_TAIL = (
    r"(?:\s+(?:do|does|would|will|is|are|was|were)(?:\s+(?:i|we|you|it|they))?"
    r"(?:\s+(?:need|needed|use|used|get|make|made|produce|produced|form|formed|required|"
    r"consumed))?)?"
)
_END = r"(?:\s+(?:instead|then|now|too))?\s*\??"


@dataclass(frozen=True, slots=True)
class _Reaction:
    """An earlier reaction problem: its equation, stated amounts and what it asked."""

    equation: str
    reactants: frozenset[str]
    products: frozenset[str]
    amounts: dict[str, str]
    unit: str
    target: str
    find: str

    def problem(self, amounts: dict[str, str], unit: str, target: str, find: str) -> str:
        given = " and ".join(f"{typed} {unit} of {formula}" for formula, typed in amounts.items())
        return f"{self.equation}. {given}. How many {_UNIT_WORDS[find]} of {target}?"

    def with_amount(self, formula: str, typed: str, unit: str) -> str | None:
        """The problem with this amount in place of the stated one, or beside it."""
        if set(self.amounts) == {formula}:
            # The one stated amount, now in grams or in moles.
            return self.problem({formula: typed}, unit, self.target, self.find)
        if unit != self.unit:
            return None
        if formula in self.amounts:
            return self.problem({**self.amounts, formula: typed}, unit, self.target, self.find)
        # A second reactant weighed: the limiting reagent decides how much product forms.
        if unit != "g" or formula not in self.reactants or self.target not in self.products:
            return None
        return self.problem({**self.amounts, formula: typed}, unit, self.target, "g")

    def asking(self, formula: str, unit: str | None) -> str | None:
        """The same amounts, another substance asked; never one the problem states."""
        if formula == self.target or formula in self.amounts:
            return None
        return self.problem(self.amounts, self.unit, formula, unit or self.find)


def _reaction(problem: str) -> _Reaction | None:
    intent = extract_chemistry_intent(problem)
    if intent is None or intent.chemistry_op not in _READ_AMOUNTS or not intent.equation:
        return None
    balanced = balance_equation(intent.equation)
    unit = intent.units.get("known", "mol" if intent.chemistry_op == "stoichiometry" else "g")
    find = intent.units.get("find", "g" if intent.chemistry_op == "limiting_mass" else unit)
    if not balanced.balanced or intent.target is None or unit not in _UNIT_WORDS:
        return None
    if find not in _UNIT_WORDS:
        return None
    amounts = {
        formula: intent.written.get(repr(value), f"{value:g}")
        for formula, value in intent.species.items()
    }
    return _Reaction(
        format_balanced(balanced),
        frozenset(balanced.reactants),
        frozenset(balanced.products),
        amounts,
        unit,
        intent.target,
        find,
    )


def _earlier_problems(recent: Sequence[Any]) -> Iterator[str]:
    """The user's earlier lines, latest first."""
    seen = 0
    for message in reversed(recent):
        role, content = message_role_content(message)
        if role != "user" or not content or not content.strip():
            continue
        yield content
        seen += 1
        if seen == _MAX_PROBLEMS:
            return


def reaction_followup_problem(line: str, recent: Sequence[Any]) -> str | None:
    """The earlier reaction problem with this line's change, written whole; None otherwise."""
    if len(line) > _MAX_LINE:
        return None
    mentions = substance_mentions(line)
    formulas = {mention.formula for mention in mentions or ()}
    if len(formulas) != 1:
        return None
    formula = formulas.pop()
    written = with_formulas(line, mentions or ())
    substance = rf"(?-i:{re.escape(formula)})(?![A-Za-z0-9])"
    amount = re.fullmatch(rf"{_LEAD}{_IF_HAD}{_AMOUNT}{substance}{_END}", written, re.IGNORECASE)
    asked = re.fullmatch(rf"{_LEAD}{_ASK_HEAD}{substance}{_ASK_TAIL}{_END}", written, re.IGNORECASE)
    if amount is None and (asked is None or not _asks(asked)):
        return None
    for problem in _earlier_problems(recent):
        reaction = _reaction(problem)
        if reaction is None or formula not in reaction.reactants | reaction.products:
            continue
        if amount is not None:
            unit = _UNITS[amount.group("unit").lower()]
            return reaction.with_amount(formula, amount.group("value"), unit)
        return None if asked is None else reaction.asking(formula, _asked_unit(asked))
    return None


def _asks(match: re.Match[str]) -> bool:
    """A substance alone is no question: "what about", "how much" or "and the" asks it."""
    return bool(re.search(r"\b(?:about|how|what|and)\b", match.group(0), re.IGNORECASE))


def _asked_unit(match: re.Match[str]) -> str | None:
    if match.group("mass"):
        return "g" if match.group("mass").lower() == "mass" else None
    word = match.group("asked")
    return None if word is None else _UNITS[word.lower()]
