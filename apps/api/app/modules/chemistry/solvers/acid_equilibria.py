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


# [A2-] = Ka2 is the school step for a weak second dissociation, not for H2SO4 (Ka2 ≈ 0.012).
_WEAK_SECOND_KA = 1e-3


def solve_amphiprotic(intent: ChemistryIntent) -> ChemistryResult:
    pka1 = require(intent, "pka1")
    pka2 = require(intent, "pka2")
    if pka2 <= pka1:
        raise SolveServiceError("pKa2 must be greater than pKa1")
    ph = (pka1 + pka2) / 2
    ph_text = p_value(ph)
    shown = []
    for index in ("1", "2"):
        ka = intent.params.get(f"ka{index}")
        if ka is not None:
            shown.append(
                f"pKa{index} = −log10({inp(ka)}) = {p_value(intent.params[f'pka{index}'])}"
            )
    left = p_value(pka1) if "ka1" in intent.params else inp(pka1)
    right = p_value(pka2) if "ka2" in intent.params else inp(pka2)
    shown.append(f"pH = ({left} + {right}) / 2 = {ph_text}")
    return verified(
        "Verified amphiprotic pH",
        tuple(shown[:-1]) or (f"pKa1 = {inp(pka1)}", f"pKa2 = {inp(pka2)}"),
        "pH",
        *stated("amphiprotic_ph"),
        shown,
        f"pH = {ph_text}",
        ph_text,
    )


def solve_diprotic_a2(intent: ChemistryIntent) -> ChemistryResult:
    ka2 = require(intent, "ka2", positive=True)
    if ka2 >= _WEAK_SECOND_KA:
        raise SolveServiceError("the second dissociation is not weak enough for [A2-] = Ka2")
    amount = num(ka2)
    return verified(
        "Verified diprotic [A2-]",
        (f"Ka2 = {inp(ka2)}",),
        "[A2-]",
        *stated("diprotic_a2"),
        (f"[A2-] = {inp(ka2)}",),
        f"[A2-] = {amount} mol/L",
        amount,
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
