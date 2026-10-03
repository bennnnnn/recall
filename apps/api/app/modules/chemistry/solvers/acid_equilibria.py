# ruff: noqa: RUF001
"""Weak acids and bases: the quadratic for [H+], polyprotic acids, a buffer after added acid."""

from __future__ import annotations

import math

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.catalog import stated
from app.modules.chemistry.solvers.common_chem import (
    inp,
    num,
    p_value,
    verified,
    weak_dissociation,
)
from app.modules.chemistry.solvers.constants import PKW
from app.modules.chemistry.solvers.params import require
from app.modules.chemistry.solvers.types import ChemistryResult
from app.services.solving import SolveServiceError


def _weakph_text(constant: float, concentration: float, *, acid: bool) -> tuple[float, float, str]:
    amount = weak_dissociation(constant, concentration)
    share = amount / concentration * 100
    note = (
        f"x/C = {num(share)}% > 5%, so the exact quadratic is used, not x ≈ √(KC)"
        if share > 5
        else ""
    )
    if acid:
        return amount, -math.log10(amount), note
    poh = -math.log10(amount)
    return amount, PKW - poh, note


def _quadratic_lines(constant: float, concentration: float, amount: float) -> list[str]:
    """The weak-electrolyte quadratic x^2 + Kx - KC = 0 with the numbers put in."""
    k, c = inp(constant), inp(concentration)
    return [
        f"x^2 + ({k})x − ({k})({c}) = 0",
        f"x = [−({k}) + √(({k})^2 + 4({k})({c}))] / 2 = {num(amount)}",
    ]


def solve_weak_acid(intent: ChemistryIntent) -> ChemistryResult:
    concentration = require(intent, "concentration", positive=True)
    constant = require(intent, "ka", positive=True)
    amount, ph, note = _weakph_text(constant, concentration, acid=True)
    ph_text = p_value(ph)
    lines = [
        *_quadratic_lines(constant, concentration, amount),
        f"[H+] = x = {num(amount)} mol/L",
    ]
    if note:
        lines.append(note)
    lines.append(f"pH = −log10({num(amount)}) = {ph_text}")
    return verified(
        "Verified weak-acid pH",
        (f"C = {inp(concentration)} mol/L", f"Ka = {inp(constant)}"),
        "pH",
        *stated("weak_acid_ph"),
        lines,
        f"pH = {ph_text}",
        ph_text,
    )


def solve_weak_base(intent: ChemistryIntent) -> ChemistryResult:
    concentration = require(intent, "concentration", positive=True)
    constant = require(intent, "kb", positive=True)
    amount, ph, note = _weakph_text(constant, concentration, acid=False)
    ph_text = p_value(ph)
    lines = [
        *_quadratic_lines(constant, concentration, amount),
        f"[OH-] = x = {num(amount)} mol/L",
    ]
    if note:
        lines.append(note)
    lines.append(f"pOH = −log10({num(amount)}) = {p_value(-math.log10(amount))}")
    lines.append(f"pH = {PKW} − {p_value(-math.log10(amount))} = {ph_text}")
    return verified(
        "Verified weak-base pH",
        (f"C = {inp(concentration)} mol/L", f"Kb = {inp(constant)}"),
        "pH",
        *stated("weak_base_ph"),
        lines,
        f"pH = {ph_text}",
        ph_text,
    )


def solve_buffer_addition(intent: ChemistryIntent) -> ChemistryResult:
    pka = intent.params.get("pka")
    ha = intent.params.get("ha_moles")
    base = intent.params.get("a_moles")
    added = intent.params.get("added_moles")
    if pka is None or ha is None or base is None or added is None:
        raise SolveServiceError("buffer addition needs pKa, both amounts, and the added moles")
    if ha <= 0 or base <= 0 or added < 0:
        raise SolveServiceError("buffer amounts must be positive")
    kind = (intent.target or "acid").lower()
    ha0, base0 = ha, base
    if kind == "acid":
        ha += added
        base -= added
        steps = (
            f"HA = {inp(ha0)} + {inp(added)} = {num(ha)} mol",
            f"A- = {inp(base0)} − {inp(added)} = {num(base)} mol",
        )
    elif kind == "base":
        base += added
        ha -= added
        steps = (
            f"A- = {inp(base0)} + {inp(added)} = {num(base)} mol",
            f"HA = {inp(ha0)} − {inp(added)} = {num(ha)} mol",
        )
    else:
        raise SolveServiceError("added reagent must be acid or base")
    if ha <= 0 or base <= 0:
        raise SolveServiceError("the addition left the buffer region")
    ph = p_value(pka + math.log10(base / ha))
    return verified(
        "Verified buffer after addition",
        (
            f"pKa = {inp(pka)}",
            f"HA = {inp(ha0)} mol",
            f"A- = {inp(base0)} mol",
            f"added {kind} = {inp(added)} mol",
        ),
        "pH",
        *stated("buffer_addition"),
        (*steps, f"pH = {inp(pka)} + log10({num(base)} / {num(ha)})"),
        f"pH = {ph}",
        ph,
    )


def solve_polyprotic(intent: ChemistryIntent) -> ChemistryResult:
    concentration = require(intent, "concentration", positive=True)
    ka1 = require(intent, "ka1", positive=True)
    amount = weak_dissociation(ka1, concentration)
    ph = p_value(-math.log10(amount))
    return verified(
        "Verified polyprotic pH",
        (f"C = {inp(concentration)} mol/L", f"Ka1 = {inp(ka1)}"),
        "pH",
        *stated("polyprotic_ph"),
        (
            *_quadratic_lines(ka1, concentration, amount),
            f"[H+] = x = {num(amount)} mol/L, from the first dissociation only",
            f"pH = −log10({num(amount)}) = {ph}",
            "Later dissociations are omitted because Ka1 dominates.",
        ),
        f"pH = {ph}",
        ph,
    )
