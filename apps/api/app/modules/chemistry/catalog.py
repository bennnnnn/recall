# ruff: noqa: RUF001 -- textbook formulas use minus signs and multiplication signs.
"""One FormulaSpec per chemistry operation.

The catalog is the identity of each operation: the law's name and its formula exactly as an
answer prints them. Solvers keep region-specific working, such as a titration before or
after equivalence. Tests fail when the catalog drifts from ``ChemistryOp``, from the solver
map, or from what a solver prints.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.chemistry.formula_laws import FORMULA_LAWS


@dataclass(frozen=True, slots=True)
class FormulaSpec:
    id: str
    kind: str
    law_name: str
    base_formula: str


def _spec(operation: str, kind: str, law_name: str, base_formula: str) -> FormulaSpec:
    return FormulaSpec(operation, kind, law_name, base_formula)


_ROWS: tuple[tuple[str, str, str, str], ...] = (
    (
        "balance",
        "equations",
        "Law of conservation of mass",
        "Atoms of each element on reactant side = atoms on product side",
    ),
    ("molar_mass", "amounts", "Molar mass from atomic masses", "M = Σ(nᵢ × atomic massᵢ)"),
    ("mass_to_moles", "amounts", "Mass–mole relation", "n = m / M"),
    ("moles_to_mass", "amounts", "Mass–mole relation", "m = nM"),
    ("moles_to_particles", "amounts", "Avogadro relation", "N = nNₐ"),
    ("particles_to_moles", "amounts", "Avogadro relation", "n = N / Nₐ"),
    (
        "percent_composition",
        "amounts",
        "Percent composition",
        "% element = (mass of element in 1 mol compound / molar mass) × 100",
    ),
    (
        "percent_yield",
        "amounts",
        "Percent yield formula",
        "% yield = (actual yield / theoretical yield) × 100",
    ),
    (
        "stoichiometry",
        "stoichiometry",
        "Stoichiometric mole ratio",
        "n(product) = n(reactant) × (product coefficient / reactant coefficient)",
    ),
    (
        "limiting_reagent",
        "stoichiometry",
        "Stoichiometric limiting-reagent comparison",
        "reaction units = available moles / stoichiometric coefficient",
    ),
    ("molarity", "solutions", "Molar concentration", "c = n / V"),
    ("dilution", "solutions", "Dilution equation", "M1V1 = M2V2"),
    ("molality", "solutions", "Molality formula", "b = moles of solute / kilograms of solvent"),
    (
        "mass_percent",
        "solutions",
        "Mass-percent concentration",
        "mass % = (mass of solute / mass of solution) × 100",
    ),
    ("ph_from_h", "acid_base", "Definition of pH", "pH = −log10[H+]"),
    ("ph_from_poh", "acid_base", "Water ion-product relation", "pH + pOH = 14"),
    ("h_from_ph", "acid_base", "Inverse pH relation", "[H+] = 10^(-pH)"),
    ("poh_from_oh", "acid_base", "Definition of pOH", "pOH = −log10[OH-]"),
    ("buffer_ph", "acid_base", "Henderson–Hasselbalch equation", "pH = pKa + log10([A-]/[HA])"),
    ("gibbs", "thermochemistry", "Gibbs equation", "ΔG = ΔH − TΔS"),
    (
        "equilibrium_constant",
        "equilibrium",
        "Law of mass action",
        "Kc = Π [products]^ν / Π [reactants]^ν",
    ),
    (
        "reaction_quotient",
        "equilibrium",
        "Law of mass action",
        "Qc = Π [products]^ν / Π [reactants]^ν",
    ),
    ("first_order_half_life", "kinetics", "First-order half-life", "t₁/₂ = ln(2) / k"),
    (
        "first_order_concentration",
        "kinetics",
        "Integrated first-order rate law",
        "[A]ₜ = [A]₀e^(−kt)",
    ),
    ("arrhenius", "kinetics", "Arrhenius equation", "k = Ae^(−Eₐ/(RT))"),
    ("cell_gibbs", "electrochemistry", "Electrochemical Gibbs relation", "ΔG° = −nFE°cell"),
    ("nernst", "electrochemistry", "Nernst equation", "E = E° − (RT/nF)ln Q"),
    ("electrolysis_mass", "electrochemistry", "Faraday's law of electrolysis", "m = MIt / nF"),
    ("beer_lambert", "spectroscopy", "Beer–Lambert law", "A = εbc"),
    (
        "empirical_formula",
        "amounts",
        "Empirical formula from percent composition",
        "n = (percent / atomic mass) / smallest",
    ),
    (
        "molecular_formula",
        "amounts",
        "Molecular formula from the empirical formula",
        "n = M_molecular / M_empirical",
    ),
    (
        "mass_stoichiometry",
        "stoichiometry",
        "Mass–mole–particle stoichiometry",
        "n(product) = n(reactant) × (product coefficient / reactant coefficient)",
    ),
    (
        "solution_stoichiometry",
        "stoichiometry",
        "Mass–mole–particle stoichiometry",
        "n(product) = n(reactant) × (product coefficient / reactant coefficient)",
    ),
    (
        "gas_stoichiometry",
        "stoichiometry",
        "Mass–mole–particle stoichiometry",
        "n(product) = n(reactant) × (product coefficient / reactant coefficient)",
    ),
    (
        "limiting_mass",
        "stoichiometry",
        "Limiting reagent from amounts",
        "reaction units = available moles / coefficient",
    ),
    (
        "limiting_solution",
        "stoichiometry",
        "Limiting reagent from amounts",
        "reaction units = available moles / coefficient",
    ),
    ("strong_acid_ph", "acid_base", "Strong monoprotic acid", "[H+] = C"),
    ("strong_base_ph", "acid_base", "Strong base", "[OH-] = nC"),
    ("weak_acid_ph", "acid_base", "Weak-acid quadratic", "Ka = x^2 / (C − x)"),
    ("weak_base_ph", "acid_base", "Weak-base quadratic", "Kb = x^2 / (C − x)"),
    ("ka_kb", "acid_base", "Water autoionization link", "Kb = Kw / Ka"),
    (
        "titration_strong",
        "acid_base",
        "Strong acid–strong base titration",
        "[H+] = (n(H+) − n(OH-)) / (Va + Vb)",
    ),
    ("titration_weak", "acid_base", "Weak acid–strong base titration", "pH = pKa"),
    (
        "buffer_addition",
        "acid_base",
        "Henderson–Hasselbalch after addition",
        "pH = pKa + log10([A-]/[HA])",
    ),
    (
        "polyprotic_ph",
        "acid_base",
        "First dissociation of a polyprotic acid",
        "Ka1 = x^2 / (C − x)",
    ),
    ("dalton", "gases", "Dalton's law", "Ptotal = Σ Pi"),
    ("partial_pressure", "gases", "Mole fraction", "Pi = Xi Ptotal"),
    ("gas_over_water", "gases", "Dalton's law with water vapor", "Pdry = Ptotal − Pwater"),
    ("calorimetry", "thermochemistry", "Calorimetry", "q_rxn = −Ccal ΔT"),
    ("hess", "thermochemistry", "Hess's law", "ΔH = Σ mi ΔHi"),
    (
        "formation_enthalpy",
        "thermochemistry",
        "Formation enthalpies",
        "ΔH°rxn = Σ n ΔHf°(products) − Σ n ΔHf°(reactants)",
    ),
    ("bond_enthalpy", "thermochemistry", "Bond enthalpies", "ΔH ≈ Σ broken − Σ formed"),
    ("ksp", "equilibrium", "Solubility product", "Ksp = Π (νᵢ s)^νᵢ"),
    (
        "precipitation",
        "equilibrium",
        "Ion product versus solubility product",
        "precipitate forms when Qsp > Ksp",
    ),
    ("common_ion", "equilibrium", "Common-ion effect", "Ksp = Π [ion]^ν"),
    (
        "kp",
        "equilibrium",
        "Partial-pressure equilibrium constant",
        "Kp = Π P(products)^ν / Π P(reactants)^ν",
    ),
    ("kc_kp", "equilibrium", "Concentration and pressure equilibrium constants", "Kp = Kc (RT)^Δn"),
    (
        "ice_equilibrium",
        "equilibrium",
        "ICE table, quadratic or linear",
        "K = Π (initial + νx)^ν / Π (initial − νx)^ν",
    ),
    ("zero_order", "kinetics", "Integrated zero-order rate law", "[A]ₜ = [A]₀ − kt"),
    ("second_order", "kinetics", "Integrated second-order rate law", "1/[A]ₜ = 1/[A]₀ + kt"),
    ("zero_order_half_life", "kinetics", "Zero-order half-life", "t₁/₂ = [A]₀ / (2k)"),
    ("second_order_half_life", "kinetics", "Second-order half-life", "t₁/₂ = 1 / (k[A]₀)"),
    (
        "rate_law",
        "kinetics",
        "Order from two experiments",
        "order = log(rate2/rate1) / log(conc2/conc1)",
    ),
    (
        "arrhenius_two_point",
        "kinetics",
        "Two-point Arrhenius equation",
        "ln(k2/k1) = −(Ea/R)(1/T2 − 1/T1)",
    ),
    (
        "cell_potential",
        "electrochemistry",
        "Galvanic cell potential",
        "E°cell = E°cathode − E°anode",
    ),
    (
        "galvanic_cell",
        "electrochemistry",
        "Standard reduction potentials",
        "E°cell = E°cathode − E°anode",
    ),
    (
        "nuclear_equation",
        "nuclear",
        "Nucleon and charge balance",
        "ΣA(reactants) = ΣA(products) and ΣZ(reactants) = ΣZ(products)",
    ),
    (
        "oxidation_state",
        "structure",
        "School oxidation-number rules",
        "Σ (oxidation number × atoms) = charge",
    ),
    (
        "vsepr",
        "structure",
        "VSEPR from the central-atom Lewis structure",
        "steric number = bonded atoms + lone pairs",
    ),
    ("formal_charge", "structure", "Formal charge", "FC = V − N − B/2"),
    (
        "functional_groups",
        "organic",
        "RDKit SMARTS groups",
        "each group is a SMARTS pattern matched atom by atom",
    ),
    ("stereochemistry", "organic", "RDKit CIP labels", "R/S centers and E/Z double bonds"),
    (
        "isomers",
        "organic",
        "Formula and canonical SMILES",
        "same formula, then isomeric versus non-isomeric SMILES",
    ),
    (
        "coordination_complex",
        "inorganic",
        "Additive coordination name",
        "oxidation state = complex charge − ligand charges",
    ),
    ("boiling_elevation", "solutions", "Boiling-point elevation", "ΔTb = i Kb m"),
    ("freezing_depression", "solutions", "Freezing-point depression", "ΔTf = i Kf m"),
    ("osmotic_pressure", "solutions", "van 't Hoff equation", "Π = iMRT"),
    ("raoult", "solutions", "Raoult's law", "P = X P°"),
    ("calibration", "analytical", "Linear calibration", "c = (signal − intercept) / slope"),
    ("gravimetric", "analytical", "Gravimetric factor", "mass = precipitate × factor"),
    (
        "standard_addition",
        "analytical",
        "One-point standard addition",
        "C = (Ix / (Ispike − Ix)) × Cstd × Vstd / Vsample",
    ),
    ("mass_defect", "nuclear", "Nuclear mass defect", "Δm = Z m_p + (A − Z) m_n − m"),
    ("crystal_field", "inorganic", "Crystal-field spin state", "μ = √(n(n + 2))"),
    (
        "standard_deviation",
        "analytical",
        "Sample standard deviation",
        "s = √(Σ(x − x̄)^2 / (n − 1))",
    ),
    ("standard_error", "analytical", "Standard error", "SE = s / √n"),
    (
        "percent_error",
        "analytical",
        "Percent error",
        "% error = |experimental − accepted| / |accepted| × 100",
    ),
    (
        "relative_uncertainty",
        "analytical",
        "Uncertainty propagation",
        "Δz/z = √((Δa/a)^2 + (Δb/b)^2)",
    ),
    ("chromatography_rf", "analytical", "Chromatography Rf", "Rf = spot distance / solvent front"),
    ("iupac_name", "organic", "IUPAC name", "PubChem IUPACName for a valid SMILES"),
    (
        "named_reaction",
        "organic",
        "One-product reaction table",
        "one SMARTS or atom change with a single product",
    ),
    (
        "ir_ranges",
        "spectroscopy",
        "Functional-group correlation",
        "each recognized group maps to a textbook range",
    ),
    (
        "ir_peak",
        "spectroscopy",
        "Functional-group correlation",
        "list every group that contains the peak; do not choose a structure",
    ),
    (
        "nmr_ranges",
        "spectroscopy",
        "Functional-group correlation",
        "each recognized group maps to a textbook range",
    ),
    (
        "nmr_peak",
        "spectroscopy",
        "Functional-group correlation",
        "list every group that contains the peak; do not choose a structure",
    ),
    ("nmr_splitting", "spectroscopy", "n+1 rule", "lines = neighbors + 1"),
    (
        "molecular_ion",
        "spectroscopy",
        "Molecular ion",
        "M+ = sum of the most abundant isotope masses (not the average molar mass)",
    ),
    ("michaelis_menten", "biochemistry", "Michaelis–Menten equation", "v = Vmax[S] / (Km + [S])"),
    (
        "average_atomic_mass",
        "amounts",
        "Average atomic mass",
        "A = Σ mᵢ × (abundanceᵢ / 100)",
    ),
    (
        "electron_configuration",
        "structure",
        "Aufbau principle",
        "fill 1s 2s 2p 3s 3p 4s 3d 4p 5s 4d 5p 6s 4f 5d 6p; the table keeps exceptions (Cr, Cu)",
    ),
)

# A one-line law declares its identity with its arithmetic (formula_laws), once.
_FORMULA_ROWS = tuple(
    (law.op, law.kind, law.law_name, law.formula) for law in FORMULA_LAWS.values()
)

CATALOG: dict[str, FormulaSpec] = {}
for _operation, _kind, _law, _formula in (*_ROWS, *_FORMULA_ROWS):
    if _operation in CATALOG:
        raise RuntimeError(f"duplicate chemistry formula {_operation}")
    CATALOG[_operation] = _spec(_operation, _kind, _law, _formula)


def formula_spec(operation: str) -> FormulaSpec | None:
    return CATALOG.get(operation)


def law_name(operation: str) -> str:
    """The law an operation's answer names, e.g. ``Dilution equation`` for ``dilution``."""
    return stated(operation)[0]


def stated(operation: str) -> tuple[str, str]:
    """Law name and base formula printed for an operation whose formula does not change."""
    spec = formula_spec(operation)
    if spec is None:
        raise KeyError(operation)
    return spec.law_name, spec.base_formula
