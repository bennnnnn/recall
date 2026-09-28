# ruff: noqa: RUF001 -- textbook chemistry uses multiplication and minus signs.
"""Cell potential and the school galvanic-cell table."""

from __future__ import annotations

import math

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.solvers.common_chem import (
    STANDARD_REDUCTION,
    num,
    verified,
)
from app.modules.chemistry.solvers.types import ChemistryResult
from app.services.solving import MathServiceError


def solve_cell_potential(intent: ChemistryIntent) -> ChemistryResult:
    cathode = intent.params.get("cathode")
    anode = intent.params.get("anode")
    if cathode is None or anode is None:
        raise MathServiceError("cell potential needs cathode and anode potentials")
    value = cathode - anode
    shown = f"E°cell = {num(value)} V"
    return verified(
        "Verified cell potential",
        (f"E°cathode = {num(cathode)} V", f"E°anode = {num(anode)} V"),
        "Standard cell potential",
        "Galvanic cell potential",
        "E°cell = E°cathode − E°anode",
        (shown,),
        shown,
        shown,
    )


def _ion(symbol: str, electrons: int) -> str:
    return f"{symbol}+" if electrons == 1 else f"{symbol}{electrons}+"


def _coeff(value: int) -> str:
    return "" if value == 1 else f"{value} "


def solve_galvanic_cell(intent: ChemistryIntent) -> ChemistryResult:
    left = intent.formula or ""
    right = intent.target or ""
    if left not in STANDARD_REDUCTION or right not in STANDARD_REDUCTION or left == right:
        raise MathServiceError("galvanic cell needs two different metals from the reduction table")
    e_left, n_left = STANDARD_REDUCTION[left]
    e_right, n_right = STANDARD_REDUCTION[right]
    if e_left >= e_right:
        cathode, anode, ec, ea, nc, na = left, right, e_left, e_right, n_left, n_right
    else:
        cathode, anode, ec, ea, nc, na = right, left, e_right, e_left, n_right, n_left
    electrons = math.lcm(nc, na)
    anode_coeff = electrons // na
    cathode_coeff = electrons // nc
    reaction = (
        f"{_coeff(anode_coeff)}{anode} + {_coeff(cathode_coeff)}{_ion(cathode, nc)}"
        f" → {_coeff(anode_coeff)}{_ion(anode, na)} + {_coeff(cathode_coeff)}{cathode}"
    )
    potential = ec - ea
    direction = "spontaneous" if potential > 0 else "not spontaneous"
    shown = (
        f"E°cell = {num(potential)} V; anode {anode}; cathode {cathode}; "
        f"n = {electrons}; {reaction}; {direction}"
    )
    return verified(
        "Verified galvanic cell",
        (f"{left} E° = {num(e_left)} V", f"{right} E° = {num(e_right)} V"),
        "Cell potential, electrodes, and net reaction",
        "Standard reduction potentials",
        "E°cell = E°cathode − E°anode",
        (shown,),
        shown,
        shown,
    )
