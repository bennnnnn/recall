# ruff: noqa: RUF001 -- textbook chemistry uses multiplication and minus signs.
"""Strong and weak acids, titrations, and buffers."""

from __future__ import annotations

import math

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.catalog import stated
from app.modules.chemistry.solvers.common_chem import (
    inp,
    num,
    verified,
    weak_dissociation,
)
from app.modules.chemistry.solvers.constants import KW, PKW
from app.modules.chemistry.solvers.params import positive, require
from app.modules.chemistry.solvers.types import ChemistryResult
from app.services.solving import SolveServiceError

_STRONG_ACIDS = frozenset({"HCl", "HBr", "HI", "HNO3", "HClO4", "HClO3"})
_STRONG_BASES = {
    "LiOH": 1,
    "NaOH": 1,
    "KOH": 1,
    "RbOH": 1,
    "CsOH": 1,
    "Ca(OH)2": 2,
    "Sr(OH)2": 2,
    "Ba(OH)2": 2,
}
# Below this, water's own ions are no longer a small correction.
_DILUTE = 1e-6


def ph_text(value: float) -> str:
    return num(-math.log10(value))


def solve_strong_acid(intent: ChemistryIntent) -> ChemistryResult:
    formula = intent.formula or ""
    if formula == "H2SO4":
        raise SolveServiceError("H2SO4 is not a simple strong monoprotic acid")
    if formula not in _STRONG_ACIDS:
        raise SolveServiceError(
            f"{formula or 'that acid'} is not a supported strong monoprotic acid"
        )
    concentration = require(intent, "concentration", positive=True)
    if concentration < _DILUTE:
        raise SolveServiceError("water's contribution is required for this dilute strong acid")
    ph = ph_text(concentration)
    return verified(
        "Verified strong-acid pH",
        (f"{formula} = {inp(concentration)} mol/L",),
        "pH",
        *stated("strong_acid_ph"),
        (f"[H+] = {inp(concentration)} mol/L", f"pH = −log10({inp(concentration)})"),
        f"pH = {ph}",
        ph,
    )


def solve_strong_base(intent: ChemistryIntent) -> ChemistryResult:
    formula = intent.formula or ""
    factor = _STRONG_BASES.get(formula)
    if factor is None:
        raise SolveServiceError(f"{formula or 'that base'} is not a supported strong base")
    concentration = require(intent, "concentration", positive=True)
    hydroxide = factor * concentration
    if hydroxide < _DILUTE:
        raise SolveServiceError("water's contribution is required for this dilute strong base")
    poh = ph_text(hydroxide)
    ph = num(PKW + math.log10(hydroxide))
    hydroxide_law = "[OH-] = C" if factor == 1 else f"[OH-] = {factor}C"
    return verified(
        "Verified strong-base pH",
        (f"{formula} = {inp(concentration)} mol/L",),
        "pH",
        stated("strong_base_ph")[0],
        hydroxide_law,
        (
            f"[OH-] = {factor} × {inp(concentration)} = {num(hydroxide)} mol/L",
            f"pOH = −log10({num(hydroxide)}) = {poh}",
            f"pH = {PKW} − {poh} = {ph}",
        ),
        f"pH = {ph}",
        ph,
    )


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
    ph_text = num(ph)
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
    ph_text = num(ph)
    lines = [
        *_quadratic_lines(constant, concentration, amount),
        f"[OH-] = x = {num(amount)} mol/L",
    ]
    if note:
        lines.append(note)
    lines.append(f"pOH = −log10({num(amount)}) = {num(-math.log10(amount))}")
    lines.append(f"pH = {PKW} − {num(-math.log10(amount))} = {ph_text}")
    return verified(
        "Verified weak-base pH",
        (f"C = {inp(concentration)} mol/L", f"Kb = {inp(constant)}"),
        "pH",
        *stated("weak_base_ph"),
        lines,
        f"pH = {ph_text}",
        ph_text,
    )


_CONSTANT_LABELS = {"ka": "Ka", "kb": "Kb", "pka": "pKa", "pkb": "pKb"}


def solve_ka_kb(intent: ChemistryIntent) -> ChemistryResult:
    target = (intent.target or "Kb").strip()
    ka = intent.params.get("ka")
    kb = intent.params.get("kb")
    law_name, base_formula = stated("ka_kb")
    if target == "Kb" and ka is not None:
        source = positive(ka, "Ka")
        value = KW / source
        formula = base_formula
        working = f"Kb = ({num(KW)}) / ({inp(source)})"
    elif target == "Ka" and kb is not None:
        source = positive(kb, "Kb")
        value = KW / source
        formula = "Ka = Kw / Kb"
        working = f"Ka = ({num(KW)}) / ({inp(source)})"
    elif target == "pKa" and ka is not None:
        source = positive(ka, "Ka")
        value = -math.log10(source)
        formula = "pKa = −log10 Ka"
        working = f"pKa = −log10({inp(source)})"
    elif target == "pKb" and kb is not None:
        source = positive(kb, "Kb")
        value = -math.log10(source)
        formula = "pKb = −log10 Kb"
        working = f"pKb = −log10({inp(source)})"
    else:
        raise SolveServiceError("Ka/Kb conversion needs the matching constant and target")
    shown = f"{target} = {num(value)}"
    uses_kw = target in {"Ka", "Kb"}
    return verified(
        "Verified Ka/Kb conversion",
        tuple(
            f"{_CONSTANT_LABELS.get(key, key)} = {inp(item)}" for key, item in intent.params.items()
        ),
        target,
        law_name,
        formula,
        (f"Kw = {num(KW)} at 25 °C", working) if uses_kw else (working,),
        shown,
        num(value),
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
    ph = num(pka + math.log10(base / ha))
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
    ph = num(-math.log10(amount))
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
