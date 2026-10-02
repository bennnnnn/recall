# ruff: noqa: RUF001 -- textbook chemistry uses multiplication and minus signs.
"""Cell potential and the school galvanic-cell table."""

from __future__ import annotations

import math
from dataclasses import replace

from app.models.schemas.chemistry import ChemistryIntent
from app.models.schemas.chemistry.scene import CellScene
from app.modules.chemistry.catalog import stated
from app.modules.chemistry.solvers.common_chem import (
    inp,
    num,
    verified,
)
from app.modules.chemistry.solvers.constants import STANDARD_REDUCTION
from app.modules.chemistry.solvers.types import ChemistryResult
from app.services.solving import SolveServiceError


def solve_cell_potential(intent: ChemistryIntent) -> ChemistryResult:
    cathode = intent.params.get("cathode")
    anode = intent.params.get("anode")
    if cathode is None or anode is None:
        raise SolveServiceError("cell potential needs cathode and anode potentials")
    value = cathode - anode
    shown = f"E°cell = {num(value)} V"
    return verified(
        "Verified cell potential",
        (f"E°cathode = {inp(cathode)} V", f"E°anode = {inp(anode)} V"),
        "Standard cell potential",
        *stated("cell_potential"),
        (f"E°cell = {inp(cathode)} − ({inp(anode)})",),
        shown,
        shown,
    )


def _volts(value: float) -> str:
    """A potential from the reduction table, which lists hundredths of a volt: 1.10 V, not 1.1 V.

    The cell potential is a difference of two table values, so it keeps their two decimals.
    """
    return f"{value:.2f}"


def _ion(symbol: str, electrons: int) -> str:
    return f"{symbol}+" if electrons == 1 else f"{symbol}{electrons}+"


def _coeff(value: int) -> str:
    return "" if value == 1 else f"{value} "


def _half(symbol: str, electrons: int) -> tuple[str, int, str, int, int]:
    """One reduction half-reaction: ``(oxidized, count, reduced, count, electrons)``.

    Hydrogen is ``2 H+ + 2 e- → H2``; every metal is ``Mⁿ⁺ + n e- → M``.
    """
    if symbol == "H":
        return "H+", 2, "H2", 1, electrons
    return _ion(symbol, electrons), 1, symbol, 1, electrons


def solve_galvanic_cell(intent: ChemistryIntent) -> ChemistryResult:
    left = intent.formula or ""
    right = intent.target or ""
    if left not in STANDARD_REDUCTION or right not in STANDARD_REDUCTION or left == right:
        raise SolveServiceError("galvanic cell needs two different metals from the reduction table")
    e_left, n_left = STANDARD_REDUCTION[left]
    e_right, n_right = STANDARD_REDUCTION[right]
    if e_left >= e_right:
        cathode, anode, ec, ea, nc, na = left, right, e_left, e_right, n_left, n_right
    else:
        cathode, anode, ec, ea, nc, na = right, left, e_right, e_left, n_right, n_left
    electrons = math.lcm(nc, na)
    anode_ion, anode_ions, anode_form, anode_forms, _ = _half(anode, na)
    cathode_ion, cathode_ions, cathode_form, cathode_forms, _ = _half(cathode, nc)
    anode_scale = electrons // na
    cathode_scale = electrons // nc
    reaction = (
        f"{_coeff(anode_forms * anode_scale)}{anode_form}"
        f" + {_coeff(cathode_ions * cathode_scale)}{cathode_ion}"
        f" -> {_coeff(anode_ions * anode_scale)}{anode_ion}"
        f" + {_coeff(cathode_forms * cathode_scale)}{cathode_form}"
    )
    potential = ec - ea
    shown = "\n".join(
        (
            f"E°cell = {_volts(potential)} V",
            f"anode: {anode}",
            f"cathode: {cathode}",
            f"n = {electrons} electrons transferred",
            reaction,
            "spontaneous (E°cell > 0)",
        )
    )
    working = [
        f"oxidation at the anode: {anode_form} -> {_coeff(anode_ions)}{anode_ion} + {na} e-",
        f"reduction at the cathode: {_coeff(cathode_ions)}{cathode_ion} + {nc} e- -> "
        f"{cathode_form}",
    ]
    if anode_scale != 1 or cathode_scale != 1:
        working.append(
            f"multiply the anode half by {anode_scale} and the cathode half by "
            f"{cathode_scale} so {electrons} e- cancel"
        )
    working.append(f"E°cell = {_volts(ec)} − ({_volts(ea)})")
    result = verified(
        "Verified galvanic cell",
        (f"{left} E° = {_volts(e_left)} V", f"{right} E° = {_volts(e_right)} V"),
        "Cell potential, electrodes, and net reaction",
        *stated("galvanic_cell"),
        working,
        shown,
        shown,
    )
    return replace(
        result,
        scene=CellScene(
            title="Galvanic cell",
            anode=anode,
            cathode=cathode,
            potential=f"{_volts(potential)} V",
            electrons="anode to cathode",
        ),
    )
