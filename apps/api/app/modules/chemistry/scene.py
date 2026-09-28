# ruff: noqa: RUF001 -- ICE changes use a minus sign.
"""Server-owned teaching scenes. The phone draws these and does not solve."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import replace

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.equations import balance_equation
from app.modules.chemistry.lewis import lewis_structure
from app.modules.chemistry.solvers.common_chem import KW, STANDARD_REDUCTION, num, weak_dissociation
from app.modules.chemistry.solvers.types import ChemistryResult
from app.modules.chemistry.species import counts_in_mass_action, parse_species
from app.services.solving import MathServiceError

_STOICH_OPS = frozenset({"mass_stoichiometry", "solution_stoichiometry", "gas_stoichiometry"})


def attach_scene(intent: ChemistryIntent, result: ChemistryResult) -> ChemistryResult:
    scene = _scene(intent, result)
    if scene is None:
        return result
    return replace(result, scene=scene)


def _scene(intent: ChemistryIntent, result: ChemistryResult) -> dict[str, object] | None:
    op = intent.chemistry_op
    if op == "balance" and intent.equation:
        return _balance(intent.equation)
    if op in _STOICH_OPS:
        return _stoich(result)
    if op == "vsepr" and intent.formula:
        return _vsepr(intent.formula)
    if op in {"titration_strong", "titration_weak"}:
        return _titration(intent, result)
    if op == "ice_equilibrium":
        return _ice(intent, result)
    if op == "galvanic_cell":
        return _cell(intent)
    return None


def _tally(side: dict[str, int]) -> tuple[dict[str, int], int] | None:
    atoms: dict[str, int] = {}
    charge = 0
    for label, coefficient in side.items():
        species = parse_species(label, coefficient_already_removed=True)
        if species is None:
            return None
        charge += species.charge * coefficient
        for element, count in species.composition.items():
            atoms[element] = atoms.get(element, 0) + count * coefficient
    return atoms, charge


def _balance(equation: str) -> dict[str, object] | None:
    balanced = balance_equation(equation)
    if not balanced.balanced:
        return None
    left = _tally(balanced.reactants)
    right = _tally(balanced.products)
    if left is None or right is None:
        return None
    left_atoms, left_charge = left
    right_atoms, right_charge = right
    elements = list(dict.fromkeys((*left_atoms, *right_atoms)))
    rows = [
        {
            "element": element,
            "left": left_atoms.get(element, 0),
            "right": right_atoms.get(element, 0),
        }
        for element in elements
    ]
    return {
        "kind": "balance",
        "title": "Atom tally",
        "rows": rows,
        "charge": {"left": left_charge, "right": right_charge},
    }


def _stoich(result: ChemistryResult) -> dict[str, object] | None:
    steps: list[dict[str, str]] = []
    for line in (*result.substitution, result.answer):
        if " = " not in line:
            continue
        label, value = line.split(" = ", 1)
        steps.append({"label": label, "value": value})
    if len(steps) < 2:
        return None
    return {"kind": "stoich", "title": "Stoichiometry chain", "steps": steps}


def _vsepr(formula: str) -> dict[str, object] | None:
    structure = lewis_structure(formula)
    if structure is None:
        return None
    return {
        "kind": "vsepr",
        "title": formula,
        "central": structure.central,
        "terminals": list(structure.terminal_elements),
        "lone_pairs": structure.central_lone_pairs,
        "geometry": structure.geometry,
        "bond_angle": structure.bond_angle,
        "electron_geometry": structure.electron_geometry,
        "ideal_angle": structure.ideal_angle,
    }


def _titration(intent: ChemistryIntent, result: ChemistryResult) -> dict[str, object] | None:
    """Labeled anchors only. No sampled curve."""
    region = result.substitution[0] if result.substitution else "solved"
    anchors = [anchor for anchor in (_start(intent), _half(intent), _equivalence(intent)) if anchor]
    anchors.append({"label": "solved", "detail": region, "value": result.answer_value})
    return {"kind": "titration", "title": "Titration", "region": region, "anchors": anchors}


def _amounts(intent: ChemistryIntent) -> tuple[float, float, float] | None:
    ma = intent.params.get("ma")
    va = intent.params.get("va_l")
    mb = intent.params.get("mb")
    if ma is None or va is None or mb is None or min(ma, va, mb) <= 0:
        return None
    return ma, va, mb


def _start(intent: ChemistryIntent) -> dict[str, str] | None:
    amounts = _amounts(intent)
    ka = intent.params.get("ka")
    kb = intent.params.get("kb")
    if amounts is None:
        return None
    ma, _, mb = amounts
    if ka is not None and ka > 0:
        ph = _safe_ph(lambda: weak_dissociation(ka, ma))
    elif kb is not None and kb > 0:
        ph = _safe_ph(lambda: weak_dissociation(kb, mb), basic=True)
    else:
        ph = num(-math.log10(ma))
    return {"label": "start", "ph": ph, "volume": "0 L"} if ph else None


def _half(intent: ChemistryIntent) -> dict[str, str] | None:
    amounts = _amounts(intent)
    ka = intent.params.get("ka")
    kb = intent.params.get("kb")
    if amounts is None:
        return None
    ma, va, mb = amounts
    if ka is not None and ka > 0:
        return {
            "label": "half-equivalence",
            "ph": num(-math.log10(ka)),
            "volume": f"{num(ma * va / (2 * mb))} L",
        }
    base_volume = intent.params.get("vb_l")
    if kb is not None and kb > 0 and base_volume is not None and base_volume > 0:
        return {
            "label": "half-equivalence",
            "ph": num(14 + math.log10(kb)),
            "volume": f"{num(mb * base_volume / (2 * ma))} L",
        }
    return None


def _equivalence(intent: ChemistryIntent) -> dict[str, str] | None:
    amounts = _amounts(intent)
    if amounts is None:
        return None
    ma, va, mb = amounts
    ka = intent.params.get("ka")
    kb = intent.params.get("kb")
    if kb is not None and ka is None:
        base_volume = intent.params.get("vb_l")
        if base_volume is None or base_volume <= 0:
            return None
        titrant = mb * base_volume / ma
        salt = (mb * base_volume) / (titrant + base_volume)
        ph = _safe_ph(lambda: weak_dissociation(KW / kb, salt))
    else:
        titrant = ma * va / mb
        if ka is not None and ka > 0:
            salt = (ma * va) / (va + titrant)
            ph = _safe_ph(lambda: weak_dissociation(KW / ka, salt), basic=True)
        else:
            ph = "7"
    if ph is None:
        return None
    return {"label": "equivalence", "ph": ph, "volume": f"{num(titrant)} L"}


def _safe_ph(root: Callable[[], float], *, basic: bool = False) -> str | None:
    try:
        amount = root()
    except MathServiceError:
        return None
    if amount <= 0:
        return None
    value = 14 + math.log10(amount) if basic else -math.log10(amount)
    return num(value)


def _ice(intent: ChemistryIntent, result: ChemistryResult) -> dict[str, object] | None:
    if not intent.equation:
        return None
    balanced = balance_equation(intent.equation)
    if not balanced.balanced:
        return None
    equilibrium: dict[str, str] = {}
    for line in result.substitution:
        if line.startswith("[") and "] = " in line:
            species = line[1 : line.index("]")]
            equilibrium[species] = line.split("] = ", 1)[1]
    rows: list[dict[str, str]] = []
    for species, coefficient in balanced.reactants.items():
        if not counts_in_mass_action(species):
            continue
        initial = intent.species.get(species, 0.0)
        rows.append(
            {
                "species": species,
                "initial": num(initial),
                "change": f"−{coefficient}x" if coefficient != 1 else "−x",
                "equilibrium": equilibrium.get(species, ""),
            }
        )
    for species, coefficient in balanced.products.items():
        if not counts_in_mass_action(species):
            continue
        initial = intent.species.get(species, 0.0)
        rows.append(
            {
                "species": species,
                "initial": num(initial),
                "change": f"+{coefficient}x" if coefficient != 1 else "+x",
                "equilibrium": equilibrium.get(species, ""),
            }
        )
    if not rows:
        return None
    return {"kind": "equilibrium", "title": "ICE table", "rows": rows}


def _cell(intent: ChemistryIntent) -> dict[str, object] | None:
    left = intent.formula or ""
    right = intent.target or ""
    if left not in STANDARD_REDUCTION or right not in STANDARD_REDUCTION or left == right:
        return None
    e_left = STANDARD_REDUCTION[left][0]
    e_right = STANDARD_REDUCTION[right][0]
    if e_left >= e_right:
        cathode, anode, potential = left, right, e_left - e_right
    else:
        cathode, anode, potential = right, left, e_right - e_left
    return {
        "kind": "cell",
        "title": "Galvanic cell",
        "anode": anode,
        "cathode": cathode,
        "potential": f"{num(potential)} V",
        "electrons": "anode to cathode",
    }
