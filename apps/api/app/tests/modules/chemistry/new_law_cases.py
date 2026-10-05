# ruff: noqa: RUF002 -- worked answers use the multiplication sign.
"""One school question per law added after the original catalog, with its worked answer.

Each answer was checked by hand to the figures the question's data carry:
- 0.200 M × 0.500 L × 58.44 g/mol = 5.84 g;
- 3.01 × 10^23 / (6.022 × 10^23) × 18.02 g/mol = 9.00 g;
- √(32.00 / 2.016) = 3.984;
- 75.77% × 34.969 u + 24.23% × 36.966 u = 35.45 u;
- 2.50 mg / 1.00 kg = 2.50 ppm = 2500 ppb;
- 25.0 mL / 500.0 mL × 100 = 5.00%;
- 5.00 g / 250 mL × 100 = 2.00 g/100 mL;
- 0.400 × 0.800 atm + 0.600 × 0.400 atm = 0.560 atm.
"""

from __future__ import annotations

NEW_LAW_CASES: tuple[tuple[str, str, str], ...] = (
    (
        "How many grams of NaCl are needed to make 500 mL of a 0.200 M NaCl solution?",
        "solution_mass",
        "m = 5.84 g",
    ),
    (
        "What is the molality of a solution of 18.0 g of glucose dissolved in 500 g of water?",
        "molality_from_mass",
        "b = 0.200 mol/kg",
    ),
    (
        "What is the mass percent of 5.0 g of sugar dissolved in 95.0 g of water?",
        "mass_percent_solvent",
        "Mass percent = 5.0%",
    ),
    (
        "What is the ppm of 2.50 mg of solute in 1.00 kg of solution?",
        "parts_per_million",
        "ppm = 2.50 ppm",
    ),
    (
        "What is the ppb of 2.50 mg of solute in 1.00 kg of solution?",
        "parts_per_billion",
        "ppb = 2500 ppb",
    ),
    (
        "What is the volume percent of 25.0 mL of solute in 500.0 mL of solution?",
        "volume_percent",
        "Volume percent = 5.00%",
    ),
    (
        "What is the mass/volume percent of 5.00 g of solute in 250 mL of solution?",
        "mass_volume_percent",
        "Mass/volume percent = 2.00%",
    ),
    (
        "Balance the half-reaction MnO4- -> Mn2+ in acidic solution.",
        "half_reaction",
        "MnO4- + 8 H+ + 5 e- -> Mn2+ + 4 H2O",
    ),
    (
        "What is the pH of an amphiprotic solution with pKa1 = 4.00 and pKa2 = 9.00?",
        "amphiprotic_ph",
        "pH = 6.50",
    ),
    (
        "What is [A2-] for a diprotic acid with Ka2 = 1.0e-8?",
        "diprotic_a2",
        "[A2-] = 1.0 × 10^-8 mol/L",
    ),
    (
        "What is the atom economy of CH3COOCH3 in CH3COOH + CH3OH -> CH3COOCH3 + H2O?",
        "atom_economy",
        "Atom economy of CH3COOCH3 = 80.44%",
    ),
    (
        "What is the total vapor pressure if the mole fraction of A is 0.400, "
        "the vapor pressure of A is 0.800 atm, the mole fraction of B is 0.600, "
        "and the vapor pressure of B is 0.400 atm?",
        "binary_vapor_pressure",
        "P = 0.560 atm",
    ),
    (
        "Find the mole fraction of NaCl when 1.0 mol of NaCl is dissolved in 9.0 mol of water.",
        "mole_fraction",
        "χ = 0.10",
    ),
    (
        "How many grams do 3.01 × 10^23 molecules of H2O weigh?",
        "particles_to_mass",
        "m = 9.00 g",
    ),
    ("What is the density of CO2 gas at 1.00 atm and 273 K?", "gas_density", "d = 1.96 g/L"),
    (
        "A gas has a density of 1.25 g/L at 1.00 atm and 273 K. What is its molar mass?",
        "molar_mass_from_density",
        "M = 28.0 g/mol",
    ),
    (
        "What is the percent ionization of 0.10 M acetic acid? Ka = 1.8e-5",
        "percent_ionization",
        "Percent ionization = 1.3%",
    ),
    (
        "How much heat is released when 2.00 mol of CH4 burns? ΔH = -890 kJ/mol",
        "reaction_heat",
        "q = -1780 kJ",
    ),
    (
        "How long does it take to deposit 10.0 g of Cu from Cu2+ with a current of 2.00 A?",
        "electrolysis_time",
        "t = 1.52 × 10^4 s",
    ),
    (
        "25.0 mL of NaOH is neutralized by 20.0 mL of 0.100 M HCl. "
        "Find the concentration of the NaOH.",
        "titration_concentration",
        "C₂ = 0.0800 mol/L",
    ),
    (
        "Compare the rates of effusion of H2 and O2.",
        "graham_ratio",
        "rate(H2) / rate(O2) = 3.984",
    ),
    ("How many grams of oxygen are in 10.0 g of H2O?", "element_mass", "m(O) = 8.88 g"),
    (
        "Chlorine has isotopes 35Cl (75.77%) and 37Cl (24.23%). Find its average atomic mass.",
        "average_atomic_mass",
        "A(Cl) = 35.45 u",
    ),
    (
        "What is the electron configuration of Fe?",
        "electron_configuration",
        "Fe: [Ar] 3d6 4s2",
    ),
    (
        "Use the van 't Hoff equation. K1 = 1.00, T1 = 300 K, T2 = 350 K, "
        "and ΔH = 50.0 kJ/mol. What is K2?",
        "vant_hoff_constant",
        "K2 = 17.5",
    ),
    (
        "Use the van 't Hoff equation. K1 = 0.10, T1 = 300 K, K2 = 0.50, "
        "and T2 = 350 K. What is ΔH?",
        "vant_hoff_enthalpy",
        "ΔH° = 28 kJ/mol",
    ),
    (
        "K = 10 at 298.15 K. What is ΔG°?",
        "gibbs_from_equilibrium",
        "ΔG° = -5.7 kJ/mol",
    ),
    (
        "ΔG° = -5.708 kJ/mol at 298.15 K. What is the equilibrium constant?",
        "equilibrium_from_gibbs",
        "K = 10.00",
    ),
    (
        "Combustion of a 0.60052 g sample of a compound containing only C, H, and O "
        "produced 0.88018 g of CO2 and 0.36030 g of H2O. What is the empirical formula?",
        "combustion_analysis",
        "CH2O",
    ),
    (
        "A 2.49677 g sample of a hydrate of CuSO4 leaves 1.59602 g of anhydrous CuSO4. "
        "How many waters of hydration?",
        "hydrate_water",
        "CuSO4\u00b75H2O",
    ),
    (
        "What is the LOD when m = 2.00 and s = 0.060?",
        "lod",
        "LOD = 0.090",
    ),
    (
        "What is the LOQ when m = 2.00 and s = 0.060?",
        "loq",
        "LOQ = 0.30",
    ),
    (
        "What is the capacity factor when tR = 5.00 and tM = 1.00?",
        "capacity_factor",
        "k' = 4.00",
    ),
    (
        "What is the selectivity when k1 = 2.00 and k2 = 4.00?",
        "selectivity",
        "α = 2.00",
    ),
    (
        "What is Rs when tR1 = 4.00, tR2 = 5.20, w1 = 0.40, and w2 = 0.40?",
        "resolution",
        "Rs = 3.0",
    ),
    (
        "What is the plate number when tR = 10.0 and w = 1.00?",
        "plate_number",
        "N = 1600",
    ),
    (
        "What is the plate height when L = 16.0 and N = 1600?",
        "plate_height",
        "H = 0.0100",
    ),
    (
        "The cation concentration is 0.10 M and the cation charge is 2. "
        "The anion concentration is 0.20 M and the anion charge is 1. Find the ionic strength.",
        "ionic_strength",
        "I = 0.30 mol/L",
    ),
    (
        "The transmittance is 0.100. Find the absorbance.",
        "absorbance_transmittance",
        "A = 1.00",
    ),
    (
        "The percent transmittance is 10.0%. Find the absorbance.",
        "absorbance_percent_transmittance",
        "A = 1.00",
    ),
    (
        "Use Kirchhoff's law. delta H = -50.0 kJ/mol, T1 = 298 K, T2 = 398 K, "
        "and the heat capacity is 0.0400 kJ/(mol·K). Find the enthalpy.",
        "kirchhoff",
        "ΔH(T2) = -46.0 kJ/mol",
    ),
    (
        "The observed specific rotation is 8.50 and the pure specific rotation is 17.0. "
        "Find the optical purity.",
        "optical_purity",
        "Optical purity = 50.0%",
    ),
    (
        "The organic concentration is 0.400 M and the aqueous concentration is 0.100 M. "
        "Find the partition coefficient.",
        "partition_coefficient",
        "KD = 4.00",
    ),
    (
        "The freezing point depression is 0.372 °C, Kf is 1.86 °C/m, "
        "and the molality is 0.200 m. Find the van 't Hoff factor.",
        "vant_hoff_factor",
        "i = 1.00",
    ),
    (
        "The carbon count is 5.00, the hydrogen count is 8.00, the nitrogen count is 1.00, "
        "and the halogen count is 1.00. Find the index of hydrogen deficiency.",
        "hydrogen_deficiency",
        "IHD = 2.00",
    ),
    (
        "The observed rotation is 10.0, the path length is 2.00 dm, "
        "and the concentration is 0.500 g/mL. Find the specific rotation.",
        "specific_rotation",
        "[α] = 10.0 °·mL/(g·dm)",
    ),
    (
        "The major amount is 0.700 mol and the minor amount is 0.300 mol. "
        "Find the enantiomeric excess.",
        "enantiomeric_excess",
        "ee = 40.0%",
    ),
    (
        "The standard Gibbs energy is -10.0 kJ/mol, the temperature is 298 K, "
        "and the reaction quotient is 0.100. Find the Gibbs energy.",
        "gibbs_reaction",
        "ΔG = -15.7 kJ/mol",
    ),
    (
        "Use the van der Waals equation. n = 1.00 mol, T = 300 K, V = 2.00 L, "
        "a = 1.00, and b = 0.0500. Find the pressure.",
        "van_der_waals_pressure",
        "P = 12.4 atm",
    ),
    (
        "Find the compressibility factor. The pressure is 2.00 atm, the volume is 1.00 L, "
        "n = 1.00 mol, and the temperature is 300 K.",
        "compressibility",
        "Z = 0.0812",
    ),
    (
        "Use the phase rule. The component count is 2 and the phase count is 2. "
        "Find the degrees of freedom.",
        "phase_rule",
        "F = 2.0",
    ),
    (
        "The first concentration is 1.00 M, the first volume is 100 mL, "
        "the second concentration is 0.200 M, and the second volume is 300 mL. "
        "Find the concentration after mixing.",
        "mixture_concentration",
        "C = 0.400 mol/L",
    ),
    (
        "Find the entropy change of an ideal gas. n = 1.00 mol, "
        "the initial volume is 1.00 L, and the final volume is 2.00 L.",
        "entropy_volume",
        "ΔS = 5.76 J/K",
    ),
    (
        "Find the entropy change. n = 2.00 mol, the molar heat capacity is 30.0 J/(mol·K), "
        "T1 = 300 K, and T2 = 600 K.",
        "entropy_temperature",
        "ΔS = 41.6 J/K",
    ),
    (
        "Use the Clapeyron equation. The temperature is 373 K, "
        "the volume change is 0.0300 m^3/mol, the pressure change is 1000 Pa, "
        "and the temperature change is 1.00 K. Find the enthalpy.",
        "clapeyron",
        "ΔH = 11.2 kJ/mol",
    ),
    (
        "Use the Langmuir isotherm. The Langmuir constant is 2.00 atm^-1 "
        "and the pressure is 1.00 atm. Find the surface coverage.",
        "langmuir",
        "θ = 0.667",
    ),
    (
        "Use the Eyring equation. The temperature is 300 K, "
        "the activation enthalpy is 50.0 kJ/mol, and the activation entropy is 0 J/(mol·K). "
        "Find the rate constant.",
        "eyring",
        "k = 1.2 × 10^4 1/s",
    ),
    (
        "The t2g count is 6.00, the eg count is 0.00, and delta_o is 100.0 kJ/mol. "
        "Find the crystal field stabilization energy.",
        "crystal_field_stabilization",
        "CFSE = -240 kJ/mol",
    ),
    (
        "The conductivity is 1.00 S/m and the concentration is 0.100 M. "
        "Find the molar conductivity.",
        "molar_conductivity",
        "Λm = 0.0100 S·m²/mol",
    ),
)
