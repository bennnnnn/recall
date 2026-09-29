# ruff: noqa: RUF001 -- textbook formulas use minus signs and multiplication signs.
"""Nuclear mass defect from a user-supplied nuclear mass."""

from __future__ import annotations

import re

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.elements import BY_SYMBOL
from app.modules.chemistry.solvers.common_chem import num, verified
from app.modules.chemistry.solvers.types import ChemistryResult
from app.services.solving import SolveServiceError

PROTON_U = 1.007276466621
NEUTRON_U = 1.00866491595
MEV_PER_U = 931.494
_NUCLIDE = re.compile(r"^(?:([A-Z][a-z]?)-(\d+)|(\d+)([A-Z][a-z]?))$")


def solve_mass_defect(intent: ChemistryIntent) -> ChemistryResult:
    label = intent.formula or ""
    mass = intent.params.get("nuclear_mass")
    parsed = _nuclide(label)
    if parsed is None or mass is None or mass <= 0:
        raise SolveServiceError("mass defect needs a nuclide and its nuclear mass in u")
    symbol, mass_number, protons = parsed
    neutrons = mass_number - protons
    if neutrons < 0:
        raise SolveServiceError("mass number is smaller than the atomic number")
    defect = protons * PROTON_U + neutrons * NEUTRON_U - mass
    energy = defect * MEV_PER_U
    per_nucleon = energy / mass_number
    shown = f"Δm = {num(defect)} u; E = {num(energy)} MeV; E/A = {num(per_nucleon)} MeV/nucleon"
    return verified(
        "Verified mass defect",
        (
            f"{mass_number}{symbol}",
            f"Z = {protons}",
            f"nuclear mass = {num(mass)} u",
        ),
        "Mass defect, binding energy, and binding energy per nucleon",
        "Nuclear mass defect",
        "Δm = Z m_p + (A − Z) m_n − m",
        (
            f"Δm = {protons}({num(PROTON_U)}) + {neutrons}({num(NEUTRON_U)}) − {num(mass)}",
            f"E = Δm × {num(MEV_PER_U)}",
        ),
        shown,
        shown,
    )


def _nuclide(label: str) -> tuple[str, int, int] | None:
    match = _NUCLIDE.fullmatch(label.strip())
    if match is None:
        return None
    if match.group(1):
        symbol, mass_number = match.group(1), int(match.group(2))
    else:
        mass_number, symbol = int(match.group(3)), match.group(4)
    element = BY_SYMBOL.get(symbol)
    if element is None:
        return None
    return symbol, mass_number, element.number
