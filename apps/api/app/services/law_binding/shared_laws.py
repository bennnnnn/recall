"""A law two subjects teach, written once, by the subject that owns it.

"A law two subjects use has one owner" (docs/ENGINEERING_STANDARDS.md). The gases are
physics' (docs/chemistry.md, Shared laws), but a chemistry class still asks a gas's
density from the gas it names ("the density of CO2 at STP"): only chemistry reads a molar
mass from a formula, and it works in atm, g/mol and g/L. Its rows take the owner's
arithmetic in their own names (``in_names``), and the same law solved for another of its
symbols from the owner's kept rearrangements (``solved_for``), never a copy of either:
the ideal-gas density was written twice, in each subject's catalog (audit, 2026-11-25).

The arithmetic holds in any consistent units, so a row in atm, g/mol and K names the gas
constant in L·atm/(mol·K) (``R_atm``) where physics names it in SI (``R_gas``).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from app.services.law_binding.rearrangements import kept_rearrangements


@dataclass(frozen=True, slots=True)
class SharedLaw:
    """A law in its owner's catalog: its id there and its arithmetic in the owner's names."""

    owner: str
    op: str
    expression: str


# The density of an ideal gas: rho = PM/RT.
IDEAL_GAS_DENSITY = SharedLaw("physics", "ideal_gas_density", "pres*molar_mass/(R_gas*temp)")

_NAME = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")


def in_names(expression: str, names: Mapping[str, str]) -> str:
    """``expression`` with each symbol ``names`` lists written in the other subject's name."""
    return _NAME.sub(lambda match: names.get(match.group(0), match.group(0)), expression)


def solved_for(law: SharedLaw, unknown: str, names: Mapping[str, str]) -> str:
    """``law`` solved for its symbol ``unknown`` (the owner's name), in ``names``; the law's
    own result is named by its op. The owner's rearrangement, kept in ``rearrangements.json``."""
    solution = kept_rearrangements().get((law.expression, law.op, unknown))
    if solution is None:
        raise KeyError(f"{law.op} has no kept rearrangement for {unknown}")
    return in_names(solution, names)
