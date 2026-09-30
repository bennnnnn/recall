# ruff: noqa: RUF001 -- spectral ranges use minus signs and superscripts.
"""Named reactions, spectral ranges, and the molecular ion."""

from __future__ import annotations

from dataclasses import replace

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.organic import organic_facts
from app.modules.chemistry.reactions import named_product
from app.modules.chemistry.solvers.common_chem import num, verified
from app.modules.chemistry.solvers.types import ChemistryResult
from app.modules.chemistry.stoichiometry import monoisotopic_mass
from app.services.solving import SolveServiceError

# Textbook correlation ranges. A peak lists every group that contains it.
_IR: dict[str, tuple[tuple[str, int, int], ...]] = {
    "alcohol": (("O–H", 3200, 3600),),
    "phenol": (("O–H", 3200, 3600),),
    "carboxylic acid": (("O–H", 2500, 3300), ("C=O", 1700, 1725)),
    "aldehyde": (("C=O", 1720, 1740),),
    "ketone": (("C=O", 1705, 1725),),
    "ester": (("C=O", 1735, 1750),),
    "amide": (("C=O", 1630, 1690),),
    "alkene": (("C=C", 1620, 1680),),
    "alkyne": (("C≡C", 2100, 2260),),
    "nitrile": (("C≡N", 2210, 2260),),
    "amine": (("N–H", 3300, 3500),),
}
_NMR: dict[str, tuple[str, float, float]] = {
    "alcohol": ("H–C–O", 3.2, 4.5),
    "ether": ("H–C–O", 3.2, 4.5),
    "ester": ("H–C–O", 3.2, 4.5),
    "alkene": ("=C–H", 4.5, 6.5),
    "aromatic": ("Ar–H", 6.5, 8.5),
    "aldehyde": ("CHO", 9.0, 10.0),
    "carboxylic acid": ("COOH", 10.0, 13.0),
    "amine": ("N–H", 0.5, 5.0),
}
_SPLITTING = {
    1: "singlet",
    2: "doublet",
    3: "triplet",
    4: "quartet",
    5: "quintet",
    6: "sextet",
    7: "septet",
}


def solve_named_reaction(intent: ChemistryIntent) -> ChemistryResult:
    product = named_product(intent.target or "", intent.formula or "", intent.equation)
    if product is None:
        raise SolveServiceError("the reaction did not give one product")
    shown = f"product SMILES {product}"
    result = verified(
        "Verified named reaction",
        (intent.target or "", intent.formula or ""),
        "Product",
        "One-product reaction table",
        "one SMARTS or atom change with a single product",
        (shown,),
        shown,
        shown,
    )
    return replace(result, structure_smiles=product)


def solve_ir_ranges(intent: ChemistryIntent) -> ChemistryResult:
    return _ranges(intent, kind="ir")


def solve_nmr_ranges(intent: ChemistryIntent) -> ChemistryResult:
    return _ranges(intent, kind="nmr")


def solve_ir_peak(intent: ChemistryIntent) -> ChemistryResult:
    return _peak(intent, kind="ir")


def solve_nmr_peak(intent: ChemistryIntent) -> ChemistryResult:
    return _peak(intent, kind="nmr")


def solve_nmr_splitting(intent: ChemistryIntent) -> ChemistryResult:
    neighbors = intent.params.get("neighbors")
    if (
        neighbors is None
        or neighbors < 0
        or neighbors != int(neighbors)
        or int(neighbors) + 1 not in _SPLITTING
    ):
        raise SolveServiceError("NMR splitting needs a neighbor count from 0 to 6")
    lines = int(neighbors) + 1
    shown = f"n+1 = {lines} ({_SPLITTING[lines]})"
    return verified(
        "Verified NMR splitting",
        (f"neighbors = {int(neighbors)}",),
        "Splitting",
        "n+1 rule",
        "lines = neighbors + 1",
        (shown,),
        shown,
        shown,
    )


def _halogen_pattern(counts: dict[str, int]) -> str | None:
    chlorine, bromine = counts.get("Cl", 0), counts.get("Br", 0)
    if chlorine == 1 and not bromine:
        return "one Cl adds an M+2 peak about a third the height of M+ (35Cl : 37Cl = 3 : 1)"
    if bromine == 1 and not chlorine:
        return "one Br adds an M+2 peak about as tall as M+ (79Br : 81Br = 1 : 1)"
    if chlorine or bromine:
        return "several Cl or Br atoms give M+2, M+4, ... peaks"
    return None


def solve_molecular_ion(intent: ChemistryIntent) -> ChemistryResult:
    formula = intent.formula or ""
    try:
        peak = monoisotopic_mass(formula)
    except (ValueError, SolveServiceError) as exc:
        raise SolveServiceError("molecular ion needs a formula or SMILES") from exc
    shown = f"M+ = {peak.exact:.4f} (nominal m/z {peak.nominal})"
    substitution = [shown]
    pattern = _halogen_pattern(peak.counts)
    if pattern is not None:
        substitution.append(pattern)
    return verified(
        "Verified molecular ion",
        (formula,),
        "Molecular ion m/z",
        "Molecular ion",
        "M+ = sum of the most abundant isotope masses (not the average molar mass)",
        substitution,
        shown,
        shown,
    )


def _ranges(intent: ChemistryIntent, *, kind: str) -> ChemistryResult:
    facts = organic_facts(intent.formula or "")
    if facts is None or not facts.groups:
        raise SolveServiceError("no functional group recognized")
    lines = _lines_for(facts.groups, kind=kind)
    if not lines:
        raise SolveServiceError("no correlation range for those groups")
    shown = "; ".join(lines)
    title = "IR ranges" if kind == "ir" else "1H NMR ranges"
    return verified(
        f"Verified {title}",
        (facts.canonical_smiles,),
        title,
        "Functional-group correlation",
        "each recognized group maps to a textbook range",
        tuple(lines),
        shown,
        shown,
    )


def _peak(intent: ChemistryIntent, *, kind: str) -> ChemistryResult:
    value = intent.params.get("peak")
    if value is None:
        raise SolveServiceError("a peak position is required")
    groups = []
    if kind == "ir":
        for name, bands in _IR.items():
            if any(low <= value <= high for _label, low, high in bands):
                groups.append(name)
    else:
        for name, (_label, low, high) in _NMR.items():
            if low <= value <= high:
                groups.append(name)
    if not groups:
        raise SolveServiceError("no functional group contains that peak")
    shown = ", ".join(groups)
    unit = "cm⁻¹" if kind == "ir" else "ppm"
    return verified(
        "Verified peak groups",
        (f"peak = {num(value)} {unit}",),
        "Groups whose range contains the peak",
        "Functional-group correlation",
        "list every group that contains the peak; do not choose a structure",
        (shown,),
        shown,
        shown,
    )


def _lines_for(groups: tuple[str, ...], *, kind: str) -> list[str]:
    lines: list[str] = []
    for group in groups:
        if kind == "ir":
            for label, low, high in _IR.get(group, ()):
                lines.append(f"{group} {label} {low}–{high} cm⁻¹")
        else:
            band = _NMR.get(group)
            if band is not None:
                name, low_ppm, high_ppm = band
                lines.append(f"{group} {name} {num(low_ppm)}–{num(high_ppm)} ppm")
    return lines
