# ruff: noqa: RUF001 -- textbook formulas use minus signs and multiplication signs.
"""Crystal field, analytical uncertainty, and Michaelis-Menten."""

from __future__ import annotations

import math

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.coordination import parse_complex_formula
from app.modules.chemistry.solvers.common_chem import num, verified
from app.modules.chemistry.solvers.types import ChemistryResult
from app.services.solving import MathServiceError

_STRONG_FIELD = frozenset({"CN", "CO"})
# Valence d+s count for the first-row metals. d electrons = this minus oxidation state.
_D_COUNT = {
    "Sc": 3,
    "Ti": 4,
    "V": 5,
    "Cr": 6,
    "Mn": 7,
    "Fe": 8,
    "Co": 9,
    "Ni": 10,
    "Cu": 11,
    "Zn": 12,
}


def solve_crystal_field(intent: ChemistryIntent) -> ChemistryResult:
    complex_ = parse_complex_formula(intent.formula or "")
    if complex_ is None:
        raise MathServiceError("coordination formula was not recognized")
    valence = _D_COUNT.get(complex_.metal)
    if valence is None:
        raise MathServiceError("crystal field is limited to the first-row metals")
    if complex_.coordination_number == 6:
        geometry = "octahedral"
    elif complex_.coordination_number == 4:
        geometry = "tetrahedral"
    else:
        raise MathServiceError("crystal field needs coordination number 4 or 6")
    electrons = valence - complex_.oxidation_state
    if electrons < 0 or electrons > 10:
        raise MathServiceError("d-electron count is outside 0 to 10")
    strong = bool(complex_.ligands) and all(ligand in _STRONG_FIELD for ligand in complex_.ligands)
    low_spin = geometry == "octahedral" and strong and electrons in {4, 5, 6, 7}
    unpaired = _unpaired(electrons, low_spin=low_spin)
    moment = math.sqrt(unpaired * (unpaired + 2))
    spin = "low-spin" if low_spin else "high-spin"
    shown = f"{geometry} {spin} d{electrons}, {unpaired} unpaired, μ = {num(moment)} BM"
    note = "coordination number 4 is treated as tetrahedral"
    return verified(
        "Verified crystal field",
        (intent.formula or "", note),
        "Spin state, unpaired electrons, and spin-only magnetic moment",
        "Crystal-field spin state",
        "μ = √(n(n+2))",
        (shown,),
        shown,
        shown,
    )


def solve_standard_deviation(intent: ChemistryIntent) -> ChemistryResult:
    values = _samples(intent)
    deviation = _stdev(values)
    shown = f"s = {num(deviation)}"
    return verified(
        "Verified sample standard deviation",
        tuple(num(value) for value in values),
        "Sample standard deviation",
        "Sample standard deviation",
        "s = √(Σ(x − x̄)² / (n − 1))",
        (shown,),
        shown,
        shown,
    )


def solve_standard_error(intent: ChemistryIntent) -> ChemistryResult:
    values = _samples(intent)
    error = _stdev(values) / math.sqrt(len(values))
    shown = f"SE = {num(error)}"
    return verified(
        "Verified standard error",
        tuple(num(value) for value in values),
        "Standard error of the mean",
        "Standard error",
        "SE = s / √n",
        (shown,),
        shown,
        shown,
    )


def solve_percent_error(intent: ChemistryIntent) -> ChemistryResult:
    experimental = intent.params.get("experimental")
    accepted = intent.params.get("accepted")
    if experimental is None or accepted is None or accepted == 0:
        raise MathServiceError(
            "percent error needs an experimental value and a nonzero accepted value"
        )
    value = abs(experimental - accepted) / abs(accepted) * 100
    shown = f"percent error = {num(value)}%"
    return verified(
        "Verified percent error",
        (f"experimental = {num(experimental)}", f"accepted = {num(accepted)}"),
        "Percent error",
        "Percent error",
        "|experimental − accepted| / |accepted| × 100",
        (shown,),
        shown,
        shown,
    )


def solve_relative_uncertainty(intent: ChemistryIntent) -> ChemistryResult:
    left = intent.params.get("a")
    left_uncertainty = intent.params.get("da")
    right = intent.params.get("b")
    right_uncertainty = intent.params.get("db")
    if (
        left is None
        or right is None
        or left_uncertainty is None
        or right_uncertainty is None
        or left == 0
        or right == 0
    ):
        raise MathServiceError(
            "relative uncertainty needs both measurements and their uncertainties"
        )
    value = math.sqrt((left_uncertainty / left) ** 2 + (right_uncertainty / right) ** 2)
    shown = f"relative uncertainty = {num(value)}"
    return verified(
        "Verified relative uncertainty",
        (
            f"a = {num(left)}",
            f"Δa = {num(left_uncertainty)}",
            f"b = {num(right)}",
            f"Δb = {num(right_uncertainty)}",
        ),
        "Relative uncertainty of a product or quotient",
        "Uncertainty propagation",
        "√((Δa/a)² + (Δb/b)²)",
        (shown,),
        shown,
        shown,
    )


def solve_chromatography_rf(intent: ChemistryIntent) -> ChemistryResult:
    spot = intent.params.get("spot")
    front = intent.params.get("front")
    if spot is None or front is None or spot < 0 or front <= 0 or spot > front:
        raise MathServiceError("Rf needs a spot distance that does not pass the solvent front")
    value = spot / front
    shown = f"Rf = {num(value)}"
    return verified(
        "Verified retention factor",
        (f"spot = {num(spot)}", f"solvent front = {num(front)}"),
        "Retention factor",
        "Chromatography Rf",
        "Rf = spot distance / solvent front",
        (shown,),
        shown,
        shown,
    )


def solve_michaelis_menten(intent: ChemistryIntent) -> ChemistryResult:
    velocity = intent.params.get("v")
    maximum = intent.params.get("vmax")
    km = intent.params.get("km")
    substrate = intent.params.get("substrate")
    present = {
        "v": velocity,
        "Vmax": maximum,
        "Km": km,
        "S": substrate,
    }
    missing = [name for name, value in present.items() if value is None]
    if len(missing) != 1:
        raise MathServiceError("Michaelis–Menten needs exactly one of v, Vmax, Km, and S missing")
    if any(value is not None and value < 0 for value in present.values()):
        raise MathServiceError("Michaelis–Menten values cannot be negative")
    target = missing[0]
    if target == "v":
        if maximum is None or km is None or substrate is None or km + substrate == 0:
            raise MathServiceError("Michaelis–Menten denominator is zero")
        value = maximum * substrate / (km + substrate)
        shown = f"v = {num(value)}"
    elif target == "Vmax":
        if velocity is None or km is None or substrate is None or substrate == 0:
            raise MathServiceError("Michaelis–Menten cannot solve Vmax from these values")
        value = velocity * (km + substrate) / substrate
        shown = f"Vmax = {num(value)}"
    elif target == "Km":
        if velocity is None or maximum is None or substrate is None or velocity == 0:
            raise MathServiceError("Michaelis–Menten cannot solve Km from these values")
        if maximum == velocity:
            raise MathServiceError("Km is undefined when v equals Vmax")
        value = substrate * (maximum - velocity) / velocity
        shown = f"Km = {num(value)}"
    else:
        if velocity is None or maximum is None or km is None or maximum == velocity:
            raise MathServiceError("Michaelis–Menten cannot solve S from these values")
        value = velocity * km / (maximum - velocity)
        shown = f"S = {num(value)}"
    given = tuple(
        f"{name} = {num(amount)}" for name, amount in present.items() if amount is not None
    )
    return verified(
        "Verified Michaelis–Menten",
        given,
        target,
        "Michaelis–Menten equation",
        "v = Vmax[S] / (Km + [S])",
        (shown,),
        shown,
        shown,
    )


def solve_iupac_name(_intent: ChemistryIntent) -> ChemistryResult:
    raise MathServiceError("IUPAC names come from PubChem, not a local solver")


def _samples(intent: ChemistryIntent) -> list[float]:
    if len(intent.samples) < 2:
        raise MathServiceError("at least two measurements are required")
    return list(intent.samples)


def _stdev(values: list[float]) -> float:
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return math.sqrt(variance)


def _unpaired(electrons: int, *, low_spin: bool) -> int:
    if not low_spin:
        return electrons if electrons <= 5 else 10 - electrons
    if electrons <= 3:
        return electrons
    if electrons <= 6:
        return 6 - electrons
    if electrons <= 8:
        return electrons - 6
    return 10 - electrons
