# ruff: noqa: RUF001 -- textbook formulas use minus signs and multiplication signs.
"""One FormulaSpec per chemistry operation.

Solvers keep region-specific equations, such as a titration before or after
equivalence. This catalog is the identity of each operation: the test fails
when it drifts from ``ChemistryOp`` or from the solver map.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FormulaSpec:
    id: str
    kind: str
    law_name: str
    base_formula: str


def _spec(operation: str, kind: str, law_name: str, base_formula: str) -> FormulaSpec:
    return FormulaSpec(operation, kind, law_name, base_formula)


_ROWS: tuple[tuple[str, str, str, str], ...] = (
    ("balance", "equations", "Conservation of mass", "atoms and charge balance"),
    ("molar_mass", "amounts", "Molar mass", "M = Σ(nᵢ × atomic massᵢ)"),
    ("mass_to_moles", "amounts", "Mass–mole relation", "n = m / M"),
    ("moles_to_mass", "amounts", "Mass–mole relation", "m = nM"),
    ("moles_to_particles", "amounts", "Avogadro's number", "N = nNₐ"),
    ("particles_to_moles", "amounts", "Avogadro's number", "n = N / Nₐ"),
    (
        "percent_composition",
        "amounts",
        "Percent composition",
        "percent = mass of element / M × 100",
    ),
    ("percent_yield", "amounts", "Percent yield", "actual / theoretical × 100"),
    (
        "stoichiometry",
        "stoichiometry",
        "Mole ratio",
        "n(product) = n(reactant) × coefficient ratio",
    ),
    (
        "limiting_reagent",
        "stoichiometry",
        "Limiting reagent",
        "reaction units = moles / coefficient",
    ),
    ("molarity", "solutions", "Molarity", "M = n / V"),
    ("dilution", "solutions", "Dilution", "M1V1 = M2V2"),
    ("molality", "solutions", "Molality", "m = n / kg solvent"),
    ("mass_percent", "solutions", "Mass percent", "mass of solute / mass of solution × 100"),
    ("ph_from_h", "acid_base", "Definition of pH", "pH = −log[H+]"),
    ("ph_from_poh", "acid_base", "pH and pOH", "pH + pOH = 14"),
    ("h_from_ph", "acid_base", "Definition of pH", "[H+] = 10^(−pH)"),
    ("poh_from_oh", "acid_base", "Definition of pOH", "pOH = −log[OH−]"),
    ("buffer_ph", "acid_base", "Henderson–Hasselbalch", "pH = pKa + log([A−]/[HA])"),
    ("ideal_gas", "gases", "Ideal gas law", "PV = nRT"),
    ("heat", "thermochemistry", "Heat capacity", "q = mcΔT"),
    ("gibbs", "thermochemistry", "Gibbs free energy", "ΔG = ΔH − TΔS"),
    (
        "equilibrium_constant",
        "equilibrium",
        "Equilibrium constant",
        "Kc from equilibrium concentrations",
    ),
    ("reaction_quotient", "equilibrium", "Reaction quotient", "Qc with the same form as Kc"),
    ("first_order_half_life", "kinetics", "First-order half-life", "t½ = ln(2) / k"),
    ("first_order_concentration", "kinetics", "First-order integrated law", "ln[A] = ln[A]₀ − kt"),
    ("arrhenius", "kinetics", "Arrhenius equation", "k = Ae^(−Ea/RT)"),
    ("cell_gibbs", "electrochemistry", "Cell free energy", "ΔG° = −nFE°"),
    ("nernst", "electrochemistry", "Nernst equation", "E = E° − (RT/nF) ln Q"),
    ("electrolysis_mass", "electrochemistry", "Faraday electrolysis", "m = (I t M) / (n F)"),
    ("radioactive_decay", "nuclear", "Half-life", "N = N₀ (1/2)^(t/t½)"),
    ("beer_lambert", "spectroscopy", "Beer–Lambert law", "A = εbc"),
    ("empirical_formula", "amounts", "Empirical formula", "mole ratio from percent composition"),
    (
        "molecular_formula",
        "amounts",
        "Molecular formula",
        "integer multiple of the empirical formula",
    ),
    ("mass_stoichiometry", "stoichiometry", "Stoichiometry chain", "mass → moles → moles → mass"),
    (
        "solution_stoichiometry",
        "stoichiometry",
        "Solution stoichiometry",
        "volume and molarity → moles → product",
    ),
    (
        "gas_stoichiometry",
        "stoichiometry",
        "Gas stoichiometry",
        "equal P and T volumes follow the mole ratio",
    ),
    ("limiting_mass", "stoichiometry", "Limiting reagent", "compare reaction units from masses"),
    (
        "limiting_solution",
        "stoichiometry",
        "Limiting reagent",
        "compare reaction units from solution volumes",
    ),
    ("strong_acid_ph", "acid_base", "Strong acid", "pH = −log C"),
    ("strong_base_ph", "acid_base", "Strong base", "pOH = −log C"),
    ("weak_acid_ph", "acid_base", "Weak acid", "Ka = x² / (C − x)"),
    ("weak_base_ph", "acid_base", "Weak base", "Kb = x² / (C − x)"),
    ("ka_kb", "acid_base", "Water equilibrium", "Ka Kb = Kw"),
    ("titration_strong", "acid_base", "Strong titration", "MaVa = MbVb"),
    ("titration_weak", "acid_base", "Weak titration", "region from moles of acid and base"),
    (
        "buffer_addition",
        "acid_base",
        "Buffer after addition",
        "Henderson–Hasselbalch after the strong ion is consumed",
    ),
    ("polyprotic_ph", "acid_base", "Polyprotic first dissociation", "Ka1 = x² / (C − x)"),
    ("combined_gas", "gases", "Combined gas law", "P1V1/T1 = P2V2/T2"),
    ("boyle", "gases", "Boyle's law", "P1V1 = P2V2"),
    ("charles", "gases", "Charles's law", "V1/T1 = V2/T2"),
    ("dalton", "gases", "Dalton's law", "Ptotal = Σ Pi"),
    ("partial_pressure", "gases", "Partial pressure", "Pi = xi Ptotal"),
    ("gas_over_water", "gases", "Gas collected over water", "Pgas = Ptotal − Pwater"),
    ("calorimetry", "thermochemistry", "Calorimetry", "q_rxn = −q_cal"),
    ("hess", "thermochemistry", "Hess's law", "ΔH = Σ ΔH(steps)"),
    (
        "formation_enthalpy",
        "thermochemistry",
        "Formation enthalpy",
        "ΔH° = Σ n ΔHf°(products) − Σ n ΔHf°(reactants)",
    ),
    ("bond_enthalpy", "thermochemistry", "Bond enthalpy", "ΔH = Σ bonds broken − Σ bonds formed"),
    ("ksp", "equilibrium", "Solubility product", "Ksp from the dissolved ions"),
    ("precipitation", "equilibrium", "Ion product", "compare Qsp with Ksp"),
    (
        "common_ion",
        "equilibrium",
        "Common-ion solubility",
        "Ksp with the shared ion already present",
    ),
    ("kp", "equilibrium", "Pressure equilibrium constant", "Kp from partial pressures"),
    ("kc_kp", "equilibrium", "Kc and Kp", "Kp = Kc (RT)^Δn"),
    ("ice_equilibrium", "equilibrium", "ICE table", "K from the extent x"),
    ("zero_order", "kinetics", "Zero-order integrated law", "[A] = [A]₀ − kt"),
    ("second_order", "kinetics", "Second-order integrated law", "1/[A] = 1/[A]₀ + kt"),
    ("zero_order_half_life", "kinetics", "Zero-order half-life", "t½ = [A]₀ / (2k)"),
    ("second_order_half_life", "kinetics", "Second-order half-life", "t½ = 1 / (k[A]₀)"),
    ("rate_law", "kinetics", "Rate law", "rate = k [A]^m from two experiments"),
    ("arrhenius_two_point", "kinetics", "Two-point Arrhenius", "ln(k2/k1) = −Ea/R (1/T2 − 1/T1)"),
    ("cell_potential", "electrochemistry", "Cell potential", "E°cell = E°cathode − E°anode"),
    ("galvanic_cell", "electrochemistry", "Galvanic cell", "E°cell = E°cathode − E°anode"),
    ("decay_constant", "nuclear", "Decay constant", "λ = ln(2) / t½"),
    ("exponential_decay", "nuclear", "Exponential decay", "N = N₀ e^(−λt)"),
    ("nuclear_activity", "nuclear", "Activity", "A = λN"),
    ("nuclear_equation", "nuclear", "Nuclear equation", "mass number and atomic number balance"),
    (
        "oxidation_state",
        "structure",
        "Oxidation numbers",
        "the signed oxidation numbers sum to the charge",
    ),
    ("vsepr", "structure", "VSEPR", "steric number = bonded atoms + lone pairs"),
    ("formal_charge", "structure", "Formal charge", "FC = V − N − B/2"),
    ("functional_groups", "organic", "Functional groups", "specific SMARTS before general ones"),
    ("stereochemistry", "organic", "CIP stereochemistry", "R/S centers and E/Z double bonds"),
    ("isomers", "organic", "Isomer class", "same formula, then canonical SMILES"),
    (
        "coordination_complex",
        "inorganic",
        "Coordination name",
        "oxidation state = complex charge − ligand charges",
    ),
    ("boiling_elevation", "solutions", "Boiling-point elevation", "ΔTb = i Kb m"),
    ("freezing_depression", "solutions", "Freezing-point depression", "ΔTf = i Kf m"),
    ("osmotic_pressure", "solutions", "Osmotic pressure", "Π = iMRT"),
    ("raoult", "solutions", "Raoult's law", "P = x P°"),
    ("calibration", "analytical", "Linear calibration", "signal = slope × c + intercept"),
    ("gravimetric", "analytical", "Gravimetric factor", "analyte = precipitate mass × factor"),
    ("standard_addition", "analytical", "Standard addition", "one-point standard addition"),
    ("mass_defect", "nuclear", "Nuclear mass defect", "Δm = Z m_p + (A − Z) m_n − m"),
    ("crystal_field", "inorganic", "Crystal-field spin state", "μ = √(n(n+2))"),
    ("standard_deviation", "analytical", "Sample standard deviation", "s = √(Σ(x − x̄)² / (n − 1))"),
    ("standard_error", "analytical", "Standard error", "SE = s / √n"),
    (
        "percent_error",
        "analytical",
        "Percent error",
        "|experimental − accepted| / |accepted| × 100",
    ),
    ("relative_uncertainty", "analytical", "Uncertainty propagation", "√((Δa/a)² + (Δb/b)²)"),
    ("chromatography_rf", "analytical", "Chromatography Rf", "Rf = spot distance / solvent front"),
    ("iupac_name", "organic", "IUPAC name", "PubChem IUPACName for a valid SMILES"),
    ("named_reaction", "organic", "Named reaction", "one unique product SMILES"),
    ("ir_ranges", "spectroscopy", "IR correlation", "functional group → wavenumber range"),
    ("ir_peak", "spectroscopy", "IR peak groups", "every group whose range contains the peak"),
    ("nmr_ranges", "spectroscopy", "1H NMR correlation", "functional group → chemical-shift range"),
    (
        "nmr_peak",
        "spectroscopy",
        "1H NMR peak groups",
        "every group whose range contains the shift",
    ),
    ("nmr_splitting", "spectroscopy", "n+1 rule", "lines = neighbors + 1"),
    ("molecular_ion", "spectroscopy", "Molecular ion", "M+ = most abundant isotope masses"),
    ("michaelis_menten", "biochemistry", "Michaelis–Menten equation", "v = Vmax[S] / (Km + [S])"),
)

CATALOG: dict[str, FormulaSpec] = {}
for _operation, _kind, _law, _formula in _ROWS:
    if _operation in CATALOG:
        raise RuntimeError(f"duplicate chemistry formula {_operation}")
    CATALOG[_operation] = _spec(_operation, _kind, _law, _formula)


def formula_spec(operation: str) -> FormulaSpec | None:
    return CATALOG.get(operation)
