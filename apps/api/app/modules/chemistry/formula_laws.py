# ruff: noqa: RUF001 -- textbook formulas use minus signs, multiplication signs and Greek.
"""Chemistry laws that are one line of arithmetic, each declared once.

A row is the whole operation: its catalog identity (law name and formula), the arithmetic,
and how its answer reads (the given rows and the substitution). The arithmetic is a
``services.law_binding`` expression in the solver's parameter names, which may name
``R_atm``, ``F`` and ``N_A``; nothing is executed. One generic solver (``solvers/formula.py``)
answers every row, so a new law of this kind is one entry.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FormulaLaw:
    op: str
    kind: str
    law_name: str
    formula: str
    find: str
    # The answer's symbol and unit: "m" in "g".
    result: str
    unit: str
    expression: str
    # Each given: parameter, label as printed, unit as printed. A label, the result and a
    # substitution row may name the intent's "{formula}" and "{target}".
    given: tuple[tuple[str, str, str], ...]
    # Substitution rows: "{name}" is a given's value as typed with its unit ("0.500 L"), and
    # "{name.value}" the bare number, for a row written in numbers alone.
    substitution: tuple[str, ...]
    # Givens that may be negative (an enthalpy); every other one must be positive.
    signed: frozenset[str] = frozenset()
    # Givens that may be zero (an empty solute) but not negative.
    non_negative: frozenset[str] = frozenset()
    # (value, ceiling): the value may not exceed the ceiling.
    not_above: tuple[tuple[str, str], ...] = ()


def _law(
    op: str,
    kind: str,
    law_name: str,
    formula: str,
    find: str,
    result: tuple[str, str],
    expression: str,
    given: tuple[tuple[str, str, str], ...],
    *substitution: str,
    signed: frozenset[str] = frozenset(),
    non_negative: frozenset[str] = frozenset(),
    not_above: tuple[tuple[str, str], ...] = (),
) -> FormulaLaw:
    return FormulaLaw(
        op,
        kind,
        law_name,
        formula,
        find,
        *result,
        expression,
        given,
        substitution,
        signed,
        non_negative,
        not_above,
    )


FORMULA_LAWS: dict[str, FormulaLaw] = {
    law.op: law
    for law in (
        _law(
            "solution_mass",
            "solutions",
            "Mass from molarity",
            "m = cVM",
            "Mass of solute, m",
            ("m", "g"),
            "concentration*volume_l*molar_mass",
            (
                ("concentration", "c", "mol/L"),
                ("volume_l", "V", "L"),
                ("molar_mass", "M({formula})", "g/mol"),
            ),
            "m = ({concentration})({volume_l})({molar_mass})",
        ),
        _law(
            "molality_from_mass",
            "solutions",
            "Molality",
            "b = (m_solute / M) / m_solvent",
            "Molality, b",
            ("b", "mol/kg"),
            "solute_mass/molar_mass/solvent_kg",
            (
                ("solute_mass", "m(solute)", "g"),
                ("molar_mass", "M({formula})", "g/mol"),
                ("solvent_kg", "m(solvent)", "kg"),
            ),
            "b = ({solute_mass} / {molar_mass}) / {solvent_kg}",
        ),
        _law(
            "mass_percent_solvent",
            "solutions",
            "Mass percent",
            "mass % = m_solute / (m_solute + m_solvent) × 100",
            "Mass percent",
            ("Mass percent", "%"),
            "solute_mass/(solute_mass + solvent_mass)*100",
            (("solute_mass", "solute mass", "g"), ("solvent_mass", "solvent mass", "g")),
            "mass % = {solute_mass} / ({solute_mass} + {solvent_mass}) × 100",
        ),
        _law(
            "parts_per_million",
            "solutions",
            "Parts per million",
            "ppm = m_solute / m_solution × 10^6",
            "Concentration, ppm",
            ("ppm", "ppm"),
            "solute_mass/solution_mass*1e6",
            (("solute_mass", "m(solute)", "g"), ("solution_mass", "m(solution)", "g")),
            "ppm = {solute_mass} / {solution_mass} × 10^6",
            non_negative=frozenset({"solute_mass"}),
            not_above=(("solute_mass", "solution_mass"),),
        ),
        _law(
            "parts_per_billion",
            "solutions",
            "Parts per billion",
            "ppb = m_solute / m_solution × 10^9",
            "Concentration, ppb",
            ("ppb", "ppb"),
            "solute_mass/solution_mass*1e9",
            (("solute_mass", "m(solute)", "g"), ("solution_mass", "m(solution)", "g")),
            "ppb = {solute_mass} / {solution_mass} × 10^9",
            non_negative=frozenset({"solute_mass"}),
            not_above=(("solute_mass", "solution_mass"),),
        ),
        _law(
            "volume_percent",
            "solutions",
            "Volume percent",
            "volume % = V_solute / V_solution × 100",
            "Volume percent",
            ("Volume percent", "%"),
            "solute_volume/solution_volume*100",
            (("solute_volume", "V(solute)", "mL"), ("solution_volume", "V(solution)", "mL")),
            "volume % = {solute_volume} / {solution_volume} × 100",
        ),
        _law(
            "mass_volume_percent",
            "solutions",
            "Mass/volume percent",
            "mass/volume % = m_solute / V_solution × 100",
            "Mass/volume percent",
            ("Mass/volume percent", "%"),
            "solute_mass/solution_volume*100",
            (("solute_mass", "m(solute)", "g"), ("solution_volume", "V(solution)", "mL")),
            "mass/volume % = {solute_mass} / {solution_volume} × 100",
        ),
        _law(
            "particles_to_mass",
            "amounts",
            "Avogadro relation",
            "m = (N / Nₐ)M",
            "Mass, m",
            ("m", "g"),
            "particles/N_A*molar_mass",
            (("particles", "N", ""), ("molar_mass", "M({formula})", "g/mol")),
            "m = [{particles} / (6.022 × 10^23 mol⁻¹)]({molar_mass})",
        ),
        _law(
            "mole_fraction",
            "solutions",
            "Mole fraction",
            "χA = nA / (nA + nB)",
            "Mole fraction, χ",
            ("χ", ""),
            "moles_a/(moles_a + moles_b)",
            (("moles_a", "n(A)", "mol"), ("moles_b", "n(B)", "mol")),
            "χA = {moles_a} / ({moles_a} + {moles_b})",
        ),
        _law(
            "binary_vapor_pressure",
            "solutions",
            "Ideal binary vapor pressure",
            "P = X_A P_A° + X_B P_B°",
            "Total vapor pressure, P",
            ("P", "atm"),
            "mole_fraction_a*pressure_a + mole_fraction_b*pressure_b",
            (
                ("mole_fraction_a", "X(A)", ""),
                ("pressure_a", "P°(A)", "atm"),
                ("mole_fraction_b", "X(B)", ""),
                ("pressure_b", "P°(B)", "atm"),
            ),
            "P = {mole_fraction_a.value} × {pressure_a} + {mole_fraction_b.value} × {pressure_b}",
            non_negative=frozenset({"mole_fraction_a", "mole_fraction_b"}),
        ),
        _law(
            "gas_density",
            "gases",
            "Ideal gas density",
            "d = PM / RT",
            "Density, d",
            ("d", "g/L"),
            "pressure*molar_mass/(R_atm*temperature)",
            (
                ("pressure", "P", "atm"),
                ("molar_mass", "M({formula})", "g/mol"),
                ("temperature", "T", "K"),
            ),
            "d = ({pressure})({molar_mass}) / [(0.082057 L·atm/(mol·K))({temperature})]",
        ),
        _law(
            "molar_mass_from_density",
            "gases",
            "Ideal gas density",
            "M = dRT / P",
            "Molar mass, M",
            ("M", "g/mol"),
            "density*R_atm*temperature/pressure",
            (
                ("density", "d", "g/L"),
                ("temperature", "T", "K"),
                ("pressure", "P", "atm"),
            ),
            "M = ({density})(0.082057 L·atm/(mol·K))({temperature}) / {pressure}",
        ),
        _law(
            "percent_ionization",
            "acid_base",
            "Percent ionization",
            "% ionization = [H+] / C × 100",
            "Percent ionization",
            ("Percent ionization", "%"),
            "(-ka + sqrt(ka**2 + 4*ka*concentration))/2/concentration*100",
            (("concentration", "C", "mol/L"), ("ka", "Ka", "")),
            # The quadratic is written in bare numbers; its x is a concentration in mol/L.
            "x = [−{ka.value} + √(({ka.value})^2 + 4({ka.value})({concentration.value}))] / 2",
            "% ionization = x / {concentration} × 100",
        ),
        _law(
            "reaction_heat",
            "thermochemistry",
            "Enthalpy of a reaction amount",
            "q = nΔH",
            "Heat, q",
            ("q", "kJ"),
            "moles*enthalpy",
            (("moles", "n", "mol"), ("enthalpy", "ΔH", "kJ/mol")),
            "q = ({moles})({enthalpy})",
            signed=frozenset({"enthalpy"}),
        ),
        _law(
            "electrolysis_time",
            "electrochemistry",
            "Faraday's law of electrolysis",
            "t = mnF / (IM)",
            "Time, t",
            ("t", "s"),
            "mass*electrons*F/(current*molar_mass)",
            (
                ("mass", "m", "g"),
                ("electrons", "n", ""),
                ("current", "I", "A"),
                ("molar_mass", "M", "g/mol"),
            ),
            "t = ({mass})({electrons})(96485 C/mol) / [({current})({molar_mass})]",
        ),
        _law(
            "titration_concentration",
            "acid_base",
            "Neutralization",
            "C₂ = C₁V₁ × ratio / V₂",
            "Unknown concentration, C₂",
            ("C₂", "mol/L"),
            "known_concentration*known_volume*ratio/unknown_volume",
            (
                ("known_concentration", "C₁", "mol/L"),
                ("known_volume", "V₁", "L"),
                ("unknown_volume", "V₂", "L"),
                ("ratio", "mole ratio", ""),
            ),
            "C₂ = ({known_concentration})({known_volume})({ratio}) / {unknown_volume}",
        ),
        _law(
            "graham_ratio",
            "gases",
            "Graham's law",
            "r₁ / r₂ = √(M₂ / M₁)",
            "Ratio of effusion rates",
            ("rate({formula}) / rate({target})", ""),
            "sqrt(molar_mass_b/molar_mass_a)",
            (
                ("molar_mass_a", "M({formula})", "g/mol"),
                ("molar_mass_b", "M({target})", "g/mol"),
            ),
            "rate({formula}) / rate({target}) = √({molar_mass_b} / {molar_mass_a})",
        ),
        _law(
            "element_mass",
            "amounts",
            "Mass of an element in a sample",
            "m(X) = m × nA(X) / M",
            "Mass of the element",
            ("m({target})", "g"),
            "sample_mass*count*atomic_mass/molar_mass",
            (
                ("sample_mass", "m({formula})", "g"),
                ("count", "atoms of {target} in {formula}", ""),
                ("atomic_mass", "A({target})", "g/mol"),
                ("molar_mass", "M({formula})", "g/mol"),
            ),
            "m({target}) = ({sample_mass})({count})({atomic_mass}) / {molar_mass}",
        ),
    )
}
