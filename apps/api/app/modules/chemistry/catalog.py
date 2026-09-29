# ruff: noqa: RUF001 -- textbook formulas use minus signs and multiplication signs.
"""One FormulaSpec per chemistry operation.

Solvers keep region-specific equations, such as a titration before or after
equivalence. This catalog is the identity of each operation: the test fails
when it drifts from ``ChemistryOp`` or from the solver map.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VariableSpec:
    """One numeric input a chemistry operation accepts."""

    name: str
    symbol: str
    required: bool = False
    # ``dh`` accepts ``dh1``, ``dh2``, and so on.
    indexed: bool = False


@dataclass(frozen=True, slots=True)
class FormulaSpec:
    id: str
    kind: str
    law_name: str
    base_formula: str
    assumptions: tuple[str, ...] = ()
    variables: tuple[VariableSpec, ...] = ()
    # Molarities keyed by the reactant formula, as in a limiting-solution problem.
    formula_params: bool = False

    def accepts_param(self, name: str) -> bool:
        for variable in self.variables:
            if variable.indexed:
                suffix = name[len(variable.name) :]
                if name.startswith(variable.name) and suffix.isdigit():
                    return True
            elif variable.name == name:
                return True
        return self.formula_params and bool(name) and name[0].isupper()


def _variables(operation: str) -> tuple[VariableSpec, ...]:
    required = _REQUIRED.get(operation, frozenset())
    specs = [
        VariableSpec(name, name, required=name in required) for name in _INPUTS.get(operation, ())
    ]
    specs.extend(
        VariableSpec(prefix, prefix, indexed=True) for prefix in _INDEXED.get(operation, ())
    )
    return tuple(specs)


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
    ("molecular_ion", "spectroscopy", "Molecular ion", "M+ equals the molar mass"),
    ("michaelis_menten", "biochemistry", "Michaelis–Menten equation", "v = Vmax[S] / (Km + [S])"),
)

# Names the extractors actually store. A name absent from this map is rejected
# on the intent, including for operations that carry their data in formula,
# equation, species, or samples instead of params.
_INPUTS: dict[str, tuple[str, ...]] = {
    "mass_to_moles": ("mass",),
    "moles_to_mass": ("moles",),
    "moles_to_particles": ("moles",),
    "particles_to_moles": ("particles",),
    "percent_yield": ("actual", "theoretical"),
    "molecular_formula": ("molar_mass",),
    "solution_stoichiometry": ("molarity",),
    "gas_stoichiometry": ("pressure", "temperature"),
    "molarity": ("moles", "volume_l"),
    "dilution": ("m1", "v1", "m2", "v2"),
    "molality": ("moles", "solvent_kg"),
    "mass_percent": ("solute_mass", "solution_mass"),
    "boiling_elevation": ("i", "kb", "molality"),
    "freezing_depression": ("i", "kf", "molality"),
    "osmotic_pressure": ("i", "molarity", "temperature"),
    "raoult": ("mole_fraction", "pure_pressure"),
    "ph_from_h": ("h",),
    "ph_from_poh": ("poh",),
    "h_from_ph": ("ph",),
    "poh_from_oh": ("oh",),
    "buffer_ph": ("pka", "base", "acid"),
    "weak_acid_ph": ("concentration", "ka"),
    "weak_base_ph": ("concentration", "kb"),
    "polyprotic_ph": ("concentration", "ka1"),
    "strong_acid_ph": ("concentration",),
    "strong_base_ph": ("concentration",),
    "ka_kb": ("ka", "kb"),
    "titration_strong": ("ma", "va_l", "mb", "vb_l"),
    "titration_weak": ("ma", "va_l", "mb", "vb_l", "ka", "kb"),
    "buffer_addition": ("pka", "ha_moles", "a_moles", "added_moles"),
    "ideal_gas": ("pressure", "volume", "moles", "temperature"),
    "combined_gas": ("p1", "v1", "t1", "p2", "v2", "t2"),
    "boyle": ("p1", "v1", "p2", "v2"),
    "charles": ("v1", "t1", "v2", "t2"),
    "partial_pressure": ("mole_fraction", "total_pressure"),
    "gas_over_water": ("total_pressure", "temperature_c"),
    "heat": ("mass", "specific_heat", "delta_t"),
    "gibbs": ("delta_h", "delta_s", "temperature"),
    "calorimetry": ("c_cal", "delta_t"),
    "bond_enthalpy": ("broken", "formed"),
    "equilibrium_constant": (),
    "reaction_quotient": (),
    "precipitation": ("qsp", "ksp"),
    "common_ion": ("ksp",),
    "ksp": ("ksp",),
    "kc_kp": ("temperature", "kc", "kp", "delta_n"),
    "ice_equilibrium": ("k",),
    "first_order_half_life": ("rate_constant",),
    "first_order_concentration": ("initial", "rate_constant", "time"),
    "zero_order_half_life": ("initial", "rate_constant"),
    "zero_order": ("initial", "rate_constant", "time"),
    "second_order_half_life": ("initial", "rate_constant"),
    "second_order": ("initial", "rate_constant", "time"),
    "arrhenius": ("pre_exponential", "activation_energy", "temperature"),
    "arrhenius_two_point": ("k1", "t1", "k2", "t2"),
    "rate_law": ("a1", "rate1", "a2", "rate2", "b1", "b2"),
    "cell_gibbs": ("electrons", "potential"),
    "nernst": ("standard_potential", "electrons", "quotient", "temperature"),
    "electrolysis_mass": ("molar_mass", "current", "time", "electrons"),
    "cell_potential": ("cathode", "anode"),
    "radioactive_decay": ("initial", "elapsed", "half_life"),
    "decay_constant": ("half_life",),
    "exponential_decay": ("initial", "decay_constant", "time"),
    "nuclear_activity": ("decay_constant", "particles"),
    "mass_defect": ("nuclear_mass",),
    "formal_charge": ("valence", "nonbonding", "bonding"),
    "beer_lambert": ("absorbance", "epsilon", "path", "concentration"),
    "calibration": ("slope", "intercept", "signal"),
    "gravimetric": ("precipitate_mass", "factor"),
    "standard_addition": (
        "sample_signal",
        "spiked_signal",
        "standard_concentration",
        "standard_volume",
        "sample_volume",
    ),
    "percent_error": ("experimental", "accepted"),
    "relative_uncertainty": ("a", "da", "b", "db"),
    "chromatography_rf": ("spot", "front"),
    "ir_peak": ("peak",),
    "nmr_peak": ("peak",),
    "nmr_splitting": ("neighbors",),
    "michaelis_menten": ("v", "vmax", "km", "substrate"),
}
_INDEXED: dict[str, tuple[str, ...]] = {"hess": ("dh", "m")}
_FORMULA_PARAMS = frozenset({"limiting_solution"})
_REQUIRED: dict[str, frozenset[str]] = {
    "mass_to_moles": frozenset({"mass"}),
    "moles_to_mass": frozenset({"moles"}),
    "percent_yield": frozenset({"actual", "theoretical"}),
    "molarity": frozenset({"moles", "volume_l"}),
    "dilution": frozenset({"m1", "v1"}),
    "gibbs": frozenset({"delta_h", "delta_s", "temperature"}),
    "heat": frozenset({"mass", "specific_heat", "delta_t"}),
    "buffer_ph": frozenset({"pka", "base", "acid"}),
    "titration_strong": frozenset({"ma", "va_l", "mb"}),
    "first_order_half_life": frozenset({"rate_constant"}),
    "cell_gibbs": frozenset({"electrons", "potential"}),
    "mass_defect": frozenset({"nuclear_mass"}),
    "michaelis_menten": frozenset(),
}
_ASSUMPTIONS: dict[str, tuple[str, ...]] = {
    "ideal_gas": ("the gas behaves ideally",),
    "dilution": ("the amount of solute does not change",),
    "gibbs": ("temperature is constant",),
    "beer_lambert": ("absorptivity and path length stay constant",),
    "hess": ("enthalpy depends only on the initial and final states",),
    "first_order_concentration": ("the reaction is first order in one reactant",),
    "radioactive_decay": ("the decay constant does not change",),
    "molarity": ("volume is the volume of the solution",),
}

CATALOG: dict[str, FormulaSpec] = {}
for _operation, _kind, _law, _formula in _ROWS:
    if _operation in CATALOG:
        raise RuntimeError(f"duplicate chemistry formula {_operation}")
    CATALOG[_operation] = FormulaSpec(
        _operation,
        _kind,
        _law,
        _formula,
        assumptions=_ASSUMPTIONS.get(_operation, ()),
        variables=_variables(_operation),
        formula_params=_operation in _FORMULA_PARAMS,
    )


def formula_spec(operation: str) -> FormulaSpec | None:
    return CATALOG.get(operation)
