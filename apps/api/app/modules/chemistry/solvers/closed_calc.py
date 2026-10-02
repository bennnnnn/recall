# ruff: noqa: RUF001, RUF002, RUF003 -- textbook formulas use minus signs, dashes and multiplication signs.
"""Crystal field, analytical uncertainty, and Michaelis-Menten."""

from __future__ import annotations

import math

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.catalog import stated
from app.modules.chemistry.coordination import CoordinationComplex, parse_complex_formula
from app.modules.chemistry.solvers.common_chem import inp, num, verified
from app.modules.chemistry.solvers.types import ChemistryResult
from app.services.solving import SolveServiceError

# Spectrochemical classes for octahedral d4–d7, where the spin state changes the answer.
_WEAK_FIELD = frozenset({"F", "Cl", "Br", "I", "H2O", "OH"})
_STRONG_FIELD = frozenset({"CN", "CO"})
_INTERMEDIATE_FIELD = frozenset({"NH3", "en", "NO2"})
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
        raise SolveServiceError("coordination formula was not recognized")
    valence = _D_COUNT.get(complex_.metal)
    if valence is None:
        raise SolveServiceError("crystal field is limited to the first-row metals")
    geometry = _crystal_geometry(complex_.coordination_number, intent.geometry)
    electrons = valence - complex_.oxidation_state
    if electrons < 0 or electrons > 10:
        raise SolveServiceError("d-electron count is outside 0 to 10")
    if geometry == "octahedral":
        low_spin, reason = _octahedral_low_spin(complex_, electrons)
        unpaired = _unpaired(electrons, low_spin=low_spin)
        spin = "low-spin" if low_spin else "high-spin"
    elif geometry == "tetrahedral":
        unpaired = _unpaired(electrons, low_spin=False)
        spin = "high-spin"
        reason = "the tetrahedral splitting is small, so electrons stay unpaired"
    else:
        # Square planar uses the large dx2-y2 gap: pair below it before occupying it.
        unpaired = _SQUARE_PLANAR_UNPAIRED[electrons]
        spin = "low-spin"
        reason = "square planar fills dz2, dxz/dyz and dxy before the high dx2-y2 orbital"
    moment = math.sqrt(unpaired * (unpaired + 2))
    label = "square planar" if geometry == "square_planar" else geometry
    shown = f"{label} {spin} d{electrons}, {unpaired} unpaired, μ = {num(moment)} BM"
    note = f"geometry = {label}"
    working = (
        f"{complex_.metal} oxidation state {complex_.oxidation_state:+d}, so "
        f"d electrons = {valence} − ({complex_.oxidation_state}) = {electrons}",
        f"coordination number {complex_.coordination_number} gives {label}; {reason}",
        f"unpaired electrons n = {unpaired}",
        f"μ = √({unpaired}({unpaired} + 2)) = {num(moment)} BM",
    )
    return verified(
        "Verified crystal field",
        (intent.formula or "", note),
        "Spin state, unpaired electrons, and spin-only magnetic moment",
        *stated("crystal_field"),
        working,
        shown,
        shown,
    )


def _octahedral_low_spin(complex_: CoordinationComplex, electrons: int) -> tuple[bool, str]:
    """Spin state of an octahedral d4–d7 complex and why, or a refusal when undecided.

    Only a ligand set that is all weak-field (halide, water, hydroxide) or all strong-field
    (CN⁻, CO) decides it. NH3, en and NO2⁻ sit in the middle: [Co(NH3)6]³⁺ is low-spin but
    [Fe(NH3)6]²⁺ is high-spin, so those need the metal, and everything else declines.
    """
    if electrons not in {4, 5, 6, 7}:
        # d1–d3 and d8–d10 have the same unpaired count in either spin state
        return False, "the unpaired count is the same in a high- or low-spin complex"
    ligands = set(complex_.ligands)
    if not ligands:
        raise SolveServiceError("the ligands are needed to choose the spin state")
    if ligands <= _WEAK_FIELD:
        return False, f"{', '.join(sorted(ligands))} are weak-field ligands, so the gap is small"
    if ligands <= _STRONG_FIELD:
        return True, f"{', '.join(sorted(ligands))} are strong-field ligands, so the gap is large"
    if (
        complex_.metal == "Co"
        and complex_.oxidation_state == 3
        and ligands <= _STRONG_FIELD | _INTERMEDIATE_FIELD
    ):
        return True, "Co(III) with these ligands has a large gap"
    raise SolveServiceError("the spin state of that ligand set depends on the metal")


def _spread(values: list[float]) -> tuple[float, float, float]:
    """``(mean, sum of squared deviations, sample standard deviation)``."""
    mean = sum(values) / len(values)
    squares = sum((value - mean) ** 2 for value in values)
    return mean, squares, math.sqrt(squares / (len(values) - 1))


def _data_lines(values: list[float]) -> tuple[str, ...]:
    return (f"data: {', '.join(inp(value) for value in values)}", f"n = {len(values)}")


def solve_standard_deviation(intent: ChemistryIntent) -> ChemistryResult:
    values = _samples(intent)
    mean, squares, deviation = _spread(values)
    shown = f"s = {num(deviation)}"
    return verified(
        "Verified sample standard deviation",
        _data_lines(values),
        "Sample standard deviation",
        *stated("standard_deviation"),
        (
            f"x̄ = ({' + '.join(inp(value) for value in values)}) / {len(values)} = {num(mean)}",
            f"Σ(x − x̄)^2 = {num(squares)}",
            f"s = √({num(squares)} / {len(values) - 1})",
        ),
        shown,
        shown,
    )


def solve_standard_error(intent: ChemistryIntent) -> ChemistryResult:
    values = _samples(intent)
    mean, squares, deviation = _spread(values)
    error = deviation / math.sqrt(len(values))
    shown = f"SE = {num(error)}"
    return verified(
        "Verified standard error",
        _data_lines(values),
        "Standard error of the mean",
        *stated("standard_error"),
        (
            f"x̄ = {num(mean)}, Σ(x − x̄)^2 = {num(squares)}",
            f"s = √({num(squares)} / {len(values) - 1}) = {num(deviation)}",
            f"SE = {num(deviation)} / √{len(values)}",
        ),
        shown,
        shown,
    )


def solve_percent_error(intent: ChemistryIntent) -> ChemistryResult:
    experimental = intent.params.get("experimental")
    accepted = intent.params.get("accepted")
    if experimental is None or accepted is None or accepted == 0:
        raise SolveServiceError(
            "percent error needs an experimental value and a nonzero accepted value"
        )
    value = abs(experimental - accepted) / abs(accepted) * 100
    shown = f"percent error = {num(value)}%"
    return verified(
        "Verified percent error",
        (f"experimental = {inp(experimental)}", f"accepted = {inp(accepted)}"),
        "Percent error",
        *stated("percent_error"),
        (f"|{inp(experimental)} − {inp(accepted)}| / |{inp(accepted)}| × 100",),
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
        raise SolveServiceError(
            "relative uncertainty needs both measurements and their uncertainties"
        )
    value = math.sqrt((left_uncertainty / left) ** 2 + (right_uncertainty / right) ** 2)
    shown = f"relative uncertainty = {num(value)}"
    return verified(
        "Verified relative uncertainty",
        (
            f"a = {inp(left)}",
            f"Δa = {inp(left_uncertainty)}",
            f"b = {inp(right)}",
            f"Δb = {inp(right_uncertainty)}",
        ),
        "Relative uncertainty of a product or quotient",
        *stated("relative_uncertainty"),
        (
            f"√(({inp(left_uncertainty)}/{inp(left)})^2 + "
            f"({inp(right_uncertainty)}/{inp(right)})^2)",
        ),
        shown,
        shown,
    )


def solve_chromatography_rf(intent: ChemistryIntent) -> ChemistryResult:
    spot = intent.params.get("spot")
    front = intent.params.get("front")
    if spot is None or front is None or spot < 0 or front <= 0 or spot > front:
        raise SolveServiceError("Rf needs a spot distance that does not pass the solvent front")
    value = spot / front
    shown = f"Rf = {num(value)}"
    return verified(
        "Verified retention factor",
        (f"spot distance = {inp(spot)}", f"solvent front = {inp(front)}"),
        "Retention factor",
        *stated("chromatography_rf"),
        (f"Rf = {inp(spot)} / {inp(front)}",),
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
        raise SolveServiceError("Michaelis–Menten needs exactly one of v, Vmax, Km, and S missing")
    if any(value is not None and value < 0 for value in present.values()):
        raise SolveServiceError("Michaelis–Menten values cannot be negative")
    target = missing[0]
    if target == "v":
        if maximum is None or km is None or substrate is None or km + substrate == 0:
            raise SolveServiceError("Michaelis–Menten denominator is zero")
        value = maximum * substrate / (km + substrate)
        shown = f"v = {num(value)}"
        working = f"v = ({inp(maximum)})({inp(substrate)}) / ({inp(km)} + {inp(substrate)})"
    elif target == "Vmax":
        if velocity is None or km is None or substrate is None or substrate == 0:
            raise SolveServiceError("Michaelis–Menten cannot solve Vmax from these values")
        value = velocity * (km + substrate) / substrate
        shown = f"Vmax = {num(value)}"
        working = f"Vmax = ({inp(velocity)})({inp(km)} + {inp(substrate)}) / {inp(substrate)}"
    elif target == "Km":
        if velocity is None or maximum is None or substrate is None or velocity <= 0:
            raise SolveServiceError("Michaelis–Menten cannot solve Km from these values")
        if not maximum > velocity:
            raise SolveServiceError("Michaelis–Menten needs Vmax greater than v")
        value = substrate * (maximum - velocity) / velocity
        shown = f"Km = {num(value)}"
        working = f"Km = ({inp(substrate)})({inp(maximum)} − {inp(velocity)}) / {inp(velocity)}"
    else:
        if velocity is None or maximum is None or km is None or velocity <= 0:
            raise SolveServiceError("Michaelis–Menten cannot solve S from these values")
        if not maximum > velocity:
            raise SolveServiceError("Michaelis–Menten needs Vmax greater than v")
        value = velocity * km / (maximum - velocity)
        shown = f"S = {num(value)}"
        working = f"S = ({inp(velocity)})({inp(km)}) / ({inp(maximum)} − {inp(velocity)})"
    given = tuple(
        f"{name} = {inp(amount)}" for name, amount in present.items() if amount is not None
    )
    return verified(
        "Verified Michaelis–Menten",
        given,
        target,
        *stated("michaelis_menten"),
        (working,),
        shown,
        shown,
    )


def solve_iupac_name(_intent: ChemistryIntent) -> ChemistryResult:
    raise SolveServiceError("IUPAC names come from PubChem, not a local solver")


def _samples(intent: ChemistryIntent) -> list[float]:
    if len(intent.samples) < 2:
        raise SolveServiceError("at least two measurements are required")
    return list(intent.samples)


# Unpaired electrons for square planar filling:
# dz2, then dxz/dyz, then dxy, then dx2-y2. d8 is diamagnetic.
_SQUARE_PLANAR_UNPAIRED = (0, 1, 0, 1, 2, 1, 0, 1, 0, 1, 0)


def _crystal_geometry(coordination_number: int, stated: str | None) -> str:
    if coordination_number == 6:
        if stated in {None, "octahedral"}:
            return "octahedral"
        raise SolveServiceError("coordination number 6 is octahedral, not the stated geometry")
    if coordination_number == 4:
        if stated == "tetrahedral":
            return "tetrahedral"
        if stated == "square_planar":
            return "square_planar"
        raise SolveServiceError(
            "coordination number 4 needs an explicit tetrahedral or square planar geometry"
        )
    raise SolveServiceError("crystal field needs coordination number 4 or 6")


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
