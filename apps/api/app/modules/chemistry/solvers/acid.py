# ruff: noqa: RUF001 -- textbook chemistry uses multiplication and minus signs.
"""Strong and weak acids, titrations, and buffers."""

from __future__ import annotations

import math

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.solvers.common_chem import KW, num, verified, weak_dissociation
from app.modules.chemistry.solvers.types import ChemistryResult
from app.services.solving import MathServiceError

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


def _ph(value: float) -> str:
    return num(-math.log10(value))


def _require_positive(value: float | None, name: str) -> float:
    if value is None or value <= 0:
        raise MathServiceError(f"{name} must be positive")
    return value


def solve_strong_acid(intent: ChemistryIntent) -> ChemistryResult:
    formula = intent.formula or ""
    if formula == "H2SO4":
        raise MathServiceError("H2SO4 is not a simple strong monoprotic acid")
    if formula not in _STRONG_ACIDS:
        raise MathServiceError(
            f"{formula or 'that acid'} is not a supported strong monoprotic acid"
        )
    concentration = _require_positive(intent.params.get("concentration"), "concentration")
    if concentration < _DILUTE:
        raise MathServiceError("water's contribution is required for this dilute strong acid")
    ph = _ph(concentration)
    return verified(
        "Verified strong-acid pH",
        (f"{formula} = {num(concentration)} M",),
        "pH",
        "Strong monoprotic acid",
        "[H+] = C",
        (f"[H+] = {num(concentration)}", f"pH = −log({num(concentration)})"),
        f"pH = {ph}",
        ph,
    )


def solve_strong_base(intent: ChemistryIntent) -> ChemistryResult:
    formula = intent.formula or ""
    factor = _STRONG_BASES.get(formula)
    if factor is None:
        raise MathServiceError(f"{formula or 'that base'} is not a supported strong base")
    concentration = _require_positive(intent.params.get("concentration"), "concentration")
    hydroxide = factor * concentration
    if hydroxide < _DILUTE:
        raise MathServiceError("water's contribution is required for this dilute strong base")
    poh = _ph(hydroxide)
    ph = num(14 + math.log10(hydroxide))
    return verified(
        "Verified strong-base pH",
        (f"{formula} = {num(concentration)} M",),
        "pH",
        "Strong base",
        "[OH−] = (hydroxide factor) × C",
        (
            f"[OH−] = {factor} × {num(concentration)} = {num(hydroxide)}",
            f"pOH = {poh}",
            "pH = 14 − pOH",
        ),
        f"pH = {ph}",
        ph,
    )


def _weak_ph(constant: float, concentration: float, *, acid: bool) -> tuple[float, float, str]:
    amount = weak_dissociation(constant, concentration)
    if acid:
        return amount, -math.log10(amount), "5% approximation would fail"
    poh = -math.log10(amount)
    return amount, 14 - poh, "5% approximation would fail"


def solve_weak_acid(intent: ChemistryIntent) -> ChemistryResult:
    concentration = _require_positive(intent.params.get("concentration"), "concentration")
    constant = _require_positive(intent.params.get("ka"), "Ka")
    amount, ph, note = _weak_ph(constant, concentration, acid=True)
    lines = [
        f"x² + ({num(constant)})x − ({num(constant)})({num(concentration)}) = 0",
        f"[H+] = {num(amount)}",
    ]
    if amount / concentration > 0.05:
        lines.append(note)
    ph_text = num(ph)
    return verified(
        "Verified weak-acid pH",
        (f"C = {num(concentration)} M", f"Ka = {num(constant)}"),
        "pH",
        "Weak-acid quadratic",
        "Ka = x² / (C − x)",
        lines,
        f"pH = {ph_text}",
        ph_text,
    )


def solve_weak_base(intent: ChemistryIntent) -> ChemistryResult:
    concentration = _require_positive(intent.params.get("concentration"), "concentration")
    constant = _require_positive(intent.params.get("kb"), "Kb")
    amount, ph, note = _weak_ph(constant, concentration, acid=False)
    lines = [
        f"x² + ({num(constant)})x − ({num(constant)})({num(concentration)}) = 0",
        f"[OH−] = {num(amount)}",
    ]
    if amount / concentration > 0.05:
        lines.append(note)
    ph_text = num(ph)
    return verified(
        "Verified weak-base pH",
        (f"C = {num(concentration)} M", f"Kb = {num(constant)}"),
        "pH",
        "Weak-base quadratic",
        "Kb = x² / (C − x)",
        lines,
        f"pH = {ph_text}",
        ph_text,
    )


def solve_ka_kb(intent: ChemistryIntent) -> ChemistryResult:
    target = (intent.target or "Kb").strip()
    ka = intent.params.get("ka")
    kb = intent.params.get("kb")
    if target == "Kb" and ka is not None:
        value = KW / _require_positive(ka, "Ka")
        shown = f"Kb = {num(value)}"
        formula = "Kb = Kw / Ka"
    elif target == "Ka" and kb is not None:
        value = KW / _require_positive(kb, "Kb")
        shown = f"Ka = {num(value)}"
        formula = "Ka = Kw / Kb"
    elif target == "pKa" and ka is not None:
        value = -math.log10(_require_positive(ka, "Ka"))
        shown = f"pKa = {num(value)}"
        formula = "pKa = −log Ka"
    elif target == "pKb" and kb is not None:
        value = -math.log10(_require_positive(kb, "Kb"))
        shown = f"pKb = {num(value)}"
        formula = "pKb = −log Kb"
    else:
        raise MathServiceError("Ka/Kb conversion needs the matching constant and target")
    return verified(
        "Verified Ka/Kb conversion",
        tuple(f"{key} = {num(item)}" for key, item in intent.params.items()),
        target,
        "Water autoionization link",
        formula,
        (f"Kw = {num(KW)}", shown),
        shown,
        num(value),
    )


def solve_buffer_addition(intent: ChemistryIntent) -> ChemistryResult:
    pka = intent.params.get("pka")
    ha = intent.params.get("ha_moles")
    base = intent.params.get("a_moles")
    added = intent.params.get("added_moles")
    if pka is None or ha is None or base is None or added is None:
        raise MathServiceError("buffer addition needs pKa, both amounts, and the added moles")
    if ha <= 0 or base <= 0 or added < 0:
        raise MathServiceError("buffer amounts must be positive")
    kind = (intent.target or "acid").lower()
    if kind == "acid":
        ha += added
        base -= added
    elif kind == "base":
        base += added
        ha -= added
    else:
        raise MathServiceError("added reagent must be acid or base")
    if ha <= 0 or base <= 0:
        raise MathServiceError("the addition left the buffer region")
    ph = num(pka + math.log10(base / ha))
    return verified(
        "Verified buffer after addition",
        (
            f"pKa = {num(pka)}",
            f"HA = {num(intent.params['ha_moles'])} mol",
            f"A− = {num(intent.params['a_moles'])} mol",
            f"added {kind} = {num(added)} mol",
        ),
        "pH",
        "Henderson–Hasselbalch after addition",
        "pH = pKa + log([A−]/[HA])",
        (f"HA = {num(ha)} mol", f"A− = {num(base)} mol"),
        f"pH = {ph}",
        ph,
    )


def solve_polyprotic(intent: ChemistryIntent) -> ChemistryResult:
    concentration = _require_positive(intent.params.get("concentration"), "concentration")
    ka1 = _require_positive(intent.params.get("ka1"), "Ka1")
    amount = weak_dissociation(ka1, concentration)
    ph = num(-math.log10(amount))
    return verified(
        "Verified polyprotic pH",
        (f"C = {num(concentration)} M", f"Ka1 = {num(ka1)}"),
        "pH",
        "First dissociation of a polyprotic acid",
        "Ka1 = x² / (C − x)",
        (
            f"[H+] ≈ {num(amount)} from the first dissociation",
            "Later dissociations are omitted because Ka1 dominates.",
        ),
        f"pH = {ph}",
        ph,
    )
