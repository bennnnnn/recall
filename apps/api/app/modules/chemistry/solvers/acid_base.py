# ruff: noqa: RUF001
"""pH, pOH and the acid and base constants: strong, weak, polyprotic and buffered solutions."""

from __future__ import annotations

import math

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.catalog import stated
from app.modules.chemistry.solvers.common_chem import (
    inp,
    num,
    p_value,
    verified,
)
from app.modules.chemistry.solvers.constants import KW, PKW
from app.modules.chemistry.solvers.params import positive, require
from app.modules.chemistry.solvers.types import ChemistryResult
from app.modules.chemistry.species_facts import STRONG_ACIDS, STRONG_BASES
from app.services.solving import SolveServiceError


def solve_acid_base(intent: ChemistryIntent) -> ChemistryResult:
    op = intent.chemistry_op
    if op == "ph_from_h":
        concentration = require(intent, "h", positive=True)
        ph = -math.log10(concentration)
        value = p_value(ph)
        return verified(
            "Verified pH calculation",
            (f"[H+] = {inp(concentration)} mol/L",),
            "pH",
            *stated("ph_from_h"),
            (f"pH = −log10({inp(concentration)})",),
            f"pH = {value}",
            value,
        )
    if op == "ph_from_poh":
        poh = require(intent, "poh")
        ph = PKW - poh
        value = p_value(ph)
        return verified(
            "Verified pH calculation",
            (f"pOH = {inp(poh)}", f"pKw = {PKW} at 25 °C"),
            "pH",
            *stated("ph_from_poh"),
            (f"pH = {PKW} − {inp(poh)}",),
            f"pH = {value}",
            value,
        )
    if op == "h_from_ph":
        ph = require(intent, "ph")
        concentration = 10 ** (-ph)
        value = f"{num(concentration)} mol/L"
        return verified(
            "Verified pH calculation",
            (f"pH = {inp(ph)}",),
            "[H+]",
            *stated("h_from_ph"),
            (f"[H+] = 10^(-{inp(ph)})",),
            f"[H+] = {value}",
            value,
        )
    if op == "poh_from_oh":
        concentration = require(intent, "oh", positive=True)
        poh = -math.log10(concentration)
        value = p_value(poh)
        return verified(
            "Verified pOH calculation",
            (f"[OH-] = {inp(concentration)} mol/L",),
            "pOH",
            *stated("poh_from_oh"),
            (f"pOH = −log10({inp(concentration)})",),
            f"pOH = {value}",
            value,
        )
    if op == "buffer_ph":
        pka = require(intent, "pka")
        base = require(intent, "base", positive=True)
        acid = require(intent, "acid", positive=True)
        ph = pka + math.log10(base / acid)
        value = p_value(ph)
        return verified(
            "Verified buffer pH",
            (
                f"pKa = {inp(pka)}",
                f"[A-] = {inp(base)} mol/L",
                f"[HA] = {inp(acid)} mol/L",
            ),
            "Buffer pH",
            *stated("buffer_ph"),
            (f"pH = {inp(pka)} + log10({inp(base)}/{inp(acid)})",),
            f"pH = {value}",
            value,
        )
    raise SolveServiceError(f"unsupported acid-base operation: {op}")


# Below this, water's own ions are no longer a small correction.
_DILUTE = 1e-6


def ph_text(value: float) -> str:
    return p_value(-math.log10(value))


def solve_strong_acid(intent: ChemistryIntent) -> ChemistryResult:
    formula = intent.formula or ""
    if formula == "H2SO4":
        raise SolveServiceError("H2SO4 is not a simple strong monoprotic acid")
    if formula not in STRONG_ACIDS:
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
    factor = STRONG_BASES.get(formula)
    if factor is None:
        raise SolveServiceError(f"{formula or 'that base'} is not a supported strong base")
    concentration = require(intent, "concentration", positive=True)
    hydroxide = factor * concentration
    if hydroxide < _DILUTE:
        raise SolveServiceError("water's contribution is required for this dilute strong base")
    poh = ph_text(hydroxide)
    ph = p_value(PKW + math.log10(hydroxide))
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
    shown = f"{target} = {p_value(value) if target.startswith('p') else num(value)}"
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
