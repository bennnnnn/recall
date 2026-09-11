"""Chemistry service — RDKit SMILES validation, properties, coordinates."""

from __future__ import annotations

import pytest

from app.services import chemistry_service

# ---------------------------------------------------------------------------
# validate_smiles
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "smiles,expected_formula,min_weight",
    [
        ("CCO", "C2H6O", 46.0),
        ("O=C=O", "CO2", 44.0),
        ("N#N", "N2", 28.0),
        ("c1ccccc1", "C6H6", 78.0),
        ("O", "H2O", 18.0),
        ("H2", "H2", 2.0),
        ("O2", "O2", 31.0),
    ],
)
def test_validate_valid_smiles(smiles: str, expected_formula: str, min_weight: float) -> None:
    props = chemistry_service.validate_smiles(smiles)
    assert props.valid, f"expected valid for {smiles}, got error: {props.error}"
    assert props.formula == expected_formula
    assert props.molecular_weight >= min_weight
    assert props.atom_count > 0
    assert props.bond_count >= 0


@pytest.mark.parametrize(
    "smiles",
    [
        "",
        "not_a_smiles",
        "C(((",
        "xyz123",
    ],
)
def test_validate_invalid_smiles(smiles: str) -> None:
    props = chemistry_service.validate_smiles(smiles)
    assert not props.valid
    assert props.error is not None


def test_validate_canonicalizes_smiles() -> None:
    # Different notations of ethanol should canonicalize to the same SMILES.
    props1 = chemistry_service.validate_smiles("CCO")
    props2 = chemistry_service.validate_smiles("OCC")
    assert props1.valid and props2.valid
    assert props1.smiles == props2.smiles


def test_validate_too_long_smiles() -> None:
    long_smiles = "C" * 600
    props = chemistry_service.validate_smiles(long_smiles)
    assert not props.valid


# ---------------------------------------------------------------------------
# generate_2d_coordinates
# ---------------------------------------------------------------------------


def test_generate_2d_coordinates_valid() -> None:
    coords = chemistry_service.generate_2d_coordinates("CCO")
    assert coords.error is None
    assert len(coords.coords_2d) == 3  # 3 heavy atoms (C, C, O)
    # Each coordinate is a (x, y) tuple
    for point in coords.coords_2d:
        assert len(point) == 2
        assert all(isinstance(v, float) for v in point)


def test_generate_2d_coordinates_invalid() -> None:
    coords = chemistry_service.generate_2d_coordinates("not_a_smiles")
    assert coords.error is not None
    assert len(coords.coords_2d) == 0


# ---------------------------------------------------------------------------
# generate_3d_coordinates
# ---------------------------------------------------------------------------


def test_generate_3d_coordinates_valid() -> None:
    coords = chemistry_service.generate_3d_coordinates("CCO")
    assert coords.error is None
    assert len(coords.sdf) > 0
    # SDF should contain atom coordinates
    assert "M  END" in coords.sdf


def test_generate_3d_coordinates_diatomic_formula() -> None:
    coords = chemistry_service.generate_3d_coordinates("H2")
    assert coords.error is None
    assert "M  END" in coords.sdf
    assert coords.sdf.count(" H ") == 2


def test_generate_3d_coordinates_water_keeps_hydrogens() -> None:
    coords = chemistry_service.generate_3d_coordinates("O")
    assert coords.error is None
    assert coords.sdf.count(" O ") == 1
    assert coords.sdf.count(" H ") == 2


def test_generate_3d_coordinates_invalid() -> None:
    coords = chemistry_service.generate_3d_coordinates("not_a_smiles")
    assert coords.error is not None
    assert coords.sdf == ""


# ---------------------------------------------------------------------------
# enrich_smiles_fence
# ---------------------------------------------------------------------------


def test_enrich_smiles_fence_valid() -> None:
    result = chemistry_service.enrich_smiles_fence("CCO")
    assert result["valid"] is True
    assert result["formula"] == "C2H6O"
    assert result["molecular_weight"] == pytest.approx(46.07, abs=0.5)
    assert result["atom_count"] == 3
    assert result["error"] is None


def test_enrich_smiles_fence_invalid() -> None:
    result = chemistry_service.enrich_smiles_fence("not_a_smiles")
    assert result["valid"] is False
    assert result["error"] is not None
    assert result["formula"] == ""


# ---------------------------------------------------------------------------
# balance_equation
# ---------------------------------------------------------------------------


def test_balance_equation_water() -> None:
    """H2 + O2 -> H2O should balance to 2 H2 + 1 O2 -> 2 H2O."""
    result = chemistry_service.balance_equation("H2 + O2 -> H2O")
    assert result.balanced is True
    assert result.reactants["H2"] == 2
    assert result.reactants["O2"] == 1
    assert result.products["H2O"] == 2


def test_balance_equation_methane() -> None:
    """CH4 + O2 -> CO2 + H2O should balance to 1 CH4 + 2 O2 -> 1 CO2 + 2 H2O."""
    result = chemistry_service.balance_equation("CH4 + O2 -> CO2 + H2O")
    assert result.balanced is True
    assert result.reactants["CH4"] == 1
    assert result.reactants["O2"] == 2
    assert result.products["CO2"] == 1
    assert result.products["H2O"] == 2


def test_balance_equation_no_arrow() -> None:
    result = chemistry_service.balance_equation("H2 O2")
    assert result.balanced is False
    assert result.error is not None


def test_balance_equation_iron_oxide() -> None:
    """Fe + O2 -> Fe2O3 should balance to 4 Fe + 3 O2 -> 2 Fe2O3."""
    result = chemistry_service.balance_equation("Fe + O2 -> Fe2O3")
    assert result.balanced is True
    assert result.reactants["Fe"] == 4
    assert result.reactants["O2"] == 3
    assert result.products["Fe2O3"] == 2


@pytest.mark.parametrize(
    "equation,reactants,products",
    [
        ("H2 + O2 -> H2O", {"H2": 2, "O2": 1}, {"H2O": 2}),
        ("CH4 + O2 -> CO2 + H2O", {"CH4": 1, "O2": 2}, {"CO2": 1, "H2O": 2}),
        ("C2H6 + O2 -> CO2 + H2O", {"C2H6": 2, "O2": 7}, {"CO2": 4, "H2O": 6}),
        ("Al + HCl -> AlCl3 + H2", {"Al": 2, "HCl": 6}, {"AlCl3": 2, "H2": 3}),
        (
            "KMnO4 + HCl -> KCl + MnCl2 + H2O + Cl2",
            {"KMnO4": 2, "HCl": 16},
            {"KCl": 2, "MnCl2": 2, "H2O": 8, "Cl2": 5},
        ),
        ("Ca(OH)2 + HCl -> CaCl2 + H2O", {"Ca(OH)2": 1, "HCl": 2}, {"CaCl2": 1, "H2O": 2}),
        (
            "Fe2(SO4)3 + NaOH -> Fe(OH)3 + Na2SO4",
            {"Fe2(SO4)3": 1, "NaOH": 6},
            {"Fe(OH)3": 2, "Na2SO4": 3},
        ),
        (
            "NaCl(aq) + AgNO3(aq) -> AgCl(s) + NaNO3(aq)",
            {"NaCl(aq)": 1, "AgNO3(aq)": 1},
            {"AgCl(s)": 1, "NaNO3(aq)": 1},
        ),
    ],
)
def test_balance_equation_standard(
    equation: str, reactants: dict[str, int], products: dict[str, int]
) -> None:
    result = chemistry_service.balance_equation(equation)
    assert result.balanced is True, result.error
    assert result.reactants == reactants
    assert result.products == products


@pytest.mark.parametrize(
    "equation",
    [
        "H2 + O2 + N2 -> H2O",
        "Fe + Cl2 -> FeCl3 + NaCl",
        "H2 + O2 -> H2O2 + H2O",
    ],
)
def test_balance_equation_impossible_or_underdetermined(equation: str) -> None:
    result = chemistry_service.balance_equation(equation)
    assert result.balanced is False
    assert result.error is not None


# ---------------------------------------------------------------------------
# stoichiometry
# ---------------------------------------------------------------------------


def test_stoichiometry_basic() -> None:
    """2 H2 + O2 -> 2 H2O: 4 mol H2 should produce 4 mol H2O."""
    result = chemistry_service.stoichiometry("H2 + O2 -> H2O", "H2", 4.0, "H2O")
    assert result.error is None
    assert result.product_amount == pytest.approx(4.0, rel=0.01)


def test_stoichiometry_unknown_reactant() -> None:
    result = chemistry_service.stoichiometry("H2 + O2 -> H2O", "XYZ", 1.0)
    assert result.error is not None
    assert "not found" in result.error


# ---------------------------------------------------------------------------
# molar_mass
# ---------------------------------------------------------------------------


def test_molar_mass_smiles() -> None:
    """CCO (ethanol) should give ~46.07 g/mol."""
    mass = chemistry_service.molar_mass("CCO")
    assert mass == pytest.approx(46.07, abs=0.5)


def test_molar_mass_formula() -> None:
    """H2O formula should give ~18.015 g/mol."""
    mass = chemistry_service.molar_mass("H2O")
    assert mass == pytest.approx(18.015, abs=0.5)


def test_molar_mass_glucose() -> None:
    """C6H12O6 (glucose) should give ~180.16 g/mol."""
    mass = chemistry_service.molar_mass("C6H12O6")
    assert mass == pytest.approx(180.16, abs=1.0)


def test_molar_mass_invalid() -> None:
    with pytest.raises(ValueError):
        chemistry_service.molar_mass("not_a_formula")


@pytest.mark.parametrize(
    "formula,expected",
    [
        ("CO", 28.01),
        ("NO", 30.01),
        ("C", 12.011),
        ("N", 14.007),
        ("O", 15.999),
        ("S", 32.06),
        ("P", 30.974),
        ("H2O", 18.02),
        ("CO2", 44.01),
        ("CH4", 16.04),
        ("NH3", 17.03),
        ("NaCl", 58.44),
    ],
)
def test_molar_mass_formulas_are_not_hydrides(formula: str, expected: float) -> None:
    assert chemistry_service.molar_mass(formula) == pytest.approx(expected, abs=0.05)


def test_molar_mass_hydrate() -> None:
    mass = chemistry_service.molar_mass("CuSO4.5H2O")
    assert mass == pytest.approx(249.68, abs=0.2)


def test_parse_formula_hydrate_atoms() -> None:
    from app.services.chemistry.equations import _parse_formula_atoms

    assert _parse_formula_atoms("CuSO4.5H2O") == {"Cu": 1, "S": 1, "O": 9, "H": 10}
    assert _parse_formula_atoms("KAl(SO4)2.12H2O") == {
        "K": 1,
        "Al": 1,
        "S": 2,
        "O": 20,
        "H": 24,
    }


# ---------------------------------------------------------------------------
# compute_descriptors
# ---------------------------------------------------------------------------


def test_compute_descriptors_ethanol() -> None:
    desc = chemistry_service.compute_descriptors("CCO")
    assert desc.error is None
    assert desc.molecular_weight == pytest.approx(46.07, abs=0.5)
    assert desc.h_bond_donors == 1  # OH
    assert desc.h_bond_acceptors == 1  # O
    assert desc.ring_count == 0


def test_compute_descriptors_benzene() -> None:
    desc = chemistry_service.compute_descriptors("c1ccccc1")
    assert desc.error is None
    assert desc.ring_count == 1
    assert desc.rotatable_bonds == 0


def test_compute_descriptors_invalid() -> None:
    desc = chemistry_service.compute_descriptors("not_a_smiles")
    assert desc.error is not None
    assert desc.molecular_weight == 0


# ---------------------------------------------------------------------------
# pH / acid-base
# ---------------------------------------------------------------------------


def test_ph_from_concentration() -> None:
    # [H+] = 1e-7 → pH = 7 (neutral)
    result = chemistry_service.ph_from_concentration(1e-7)
    assert result.error is None
    assert result.ph == pytest.approx(7.0, abs=0.01)
    assert result.poh == pytest.approx(7.0, abs=0.01)


def test_ph_from_concentration_acidic() -> None:
    # [H+] = 1e-2 → pH = 2
    result = chemistry_service.ph_from_concentration(1e-2)
    assert result.ph == pytest.approx(2.0, abs=0.01)


def test_ph_from_concentration_invalid() -> None:
    result = chemistry_service.ph_from_concentration(0)
    assert result.error is not None


def test_ph_from_poh() -> None:
    result = chemistry_service.ph_from_poh(4.0)
    assert result.ph == pytest.approx(10.0, abs=0.01)


def test_h_from_ph() -> None:
    result = chemistry_service.h_from_ph(3.0)
    assert result.ph == pytest.approx(3.0, abs=0.01)
    # [H+] = 10^-3 = 1e-3
    assert "e-03" in result.answer or "0.001" in result.answer


# ---------------------------------------------------------------------------
# Gas laws
# ---------------------------------------------------------------------------


def test_ideal_gas_law_solve_pressure() -> None:
    # P = nRT/V with n=1, T=273, V=22.4 → ~1 atm
    result = chemistry_service.ideal_gas_law(volume=22.4, moles=1, temperature=273)
    assert result.error is None
    assert result.value == pytest.approx(1.0, abs=0.05)


def test_ideal_gas_law_solve_volume() -> None:
    result = chemistry_service.ideal_gas_law(pressure=1, moles=1, temperature=273)
    assert result.error is None
    assert result.value == pytest.approx(22.4, abs=0.5)


def test_ideal_gas_law_solve_moles() -> None:
    result = chemistry_service.ideal_gas_law(pressure=1, volume=22.4, temperature=273)
    assert result.error is None
    assert result.value == pytest.approx(1.0, abs=0.05)


def test_ideal_gas_law_solve_temperature() -> None:
    result = chemistry_service.ideal_gas_law(pressure=1, volume=22.4, moles=1)
    assert result.error is None
    assert result.value == pytest.approx(273, abs=2)


def test_ideal_gas_law_no_unknown() -> None:
    result = chemistry_service.ideal_gas_law(pressure=1, volume=1, moles=1, temperature=273)
    assert result.error is not None


def test_ideal_gas_law_two_unknown() -> None:
    result = chemistry_service.ideal_gas_law(pressure=1, volume=1)
    assert result.error is not None


# ---------------------------------------------------------------------------
# Solution chemistry
# ---------------------------------------------------------------------------


def test_molarity() -> None:
    result = chemistry_service.molarity(2.0, 1.0)
    assert result.error is None
    assert result.value == pytest.approx(2.0)


def test_molarity_zero_volume() -> None:
    result = chemistry_service.molarity(2.0, 0.0)
    assert result.error is not None


def test_dilution_solve_v2() -> None:
    # M1V1 = M2V2 → V2 = M1V1/M2 = (2*1)/1 = 2
    result = chemistry_service.dilution(m1=2.0, v1=1.0, m2=1.0)
    assert result.error is None
    assert result.value == pytest.approx(2.0)


def test_dilution_solve_m2() -> None:
    # M2 = M1V1/V2 = (2*1)/4 = 0.5
    result = chemistry_service.dilution(m1=2.0, v1=1.0, v2=4.0)
    assert result.error is None
    assert result.value == pytest.approx(0.5)


def test_dilution_no_unknown() -> None:
    result = chemistry_service.dilution(m1=2.0, v1=1.0, v2=4.0, m2=0.5)
    assert result.error is not None


def test_dilution_two_unknown() -> None:
    result = chemistry_service.dilution(m1=2.0, v1=1.0)
    assert result.error is not None


# ---------------------------------------------------------------------------
# Periodic table
# ---------------------------------------------------------------------------


def test_get_element_info_carbon() -> None:
    info = chemistry_service.get_element_info("C")
    assert info is not None
    assert info["name"] == "Carbon"
    assert info["mass"] == pytest.approx(12.011)
    assert info["electronegativity"] == pytest.approx(2.55)


def test_get_element_info_unknown() -> None:
    info = chemistry_service.get_element_info("Xx")
    assert info is None


def test_get_element_info_helium_has_no_zero_electronegativity() -> None:
    info = chemistry_service.get_element_info("He")
    assert info is not None
    assert "electronegativity" not in info


def test_get_element_info_covers_extended_symbols() -> None:
    assert chemistry_service.get_element_info("Ba") is not None
    assert chemistry_service.get_element_info("Hg") is not None
    assert chemistry_service.get_element_info("U") is not None


# ---------------------------------------------------------------------------
# Limiting reagent
# ---------------------------------------------------------------------------


def test_limiting_reagent_basic() -> None:
    # 2H2 + O2 -> 2H2O
    # If we have 1 mol H2 and 1 mol O2:
    # H2 can make 1*(2/2) = 1 mol H2O
    # O2 can make 1*(2/1) = 2 mol H2O
    # H2 is limiting
    result = chemistry_service.limiting_reagent(
        "H2 + O2 -> H2O",
        {"H2": 1.0, "O2": 1.0},
        target_product="H2O",
    )
    assert result.error is None
    assert result.limiting_reagent == "H2"
    assert result.product_amount == pytest.approx(1.0, abs=0.01)


def test_limiting_reagent_o2_limiting() -> None:
    # If we have 3 mol H2 and 1 mol O2:
    # H2 can make 3*(2/2) = 3 mol H2O
    # O2 can make 1*(2/1) = 2 mol H2O
    # O2 is limiting
    result = chemistry_service.limiting_reagent(
        "H2 + O2 -> H2O",
        {"H2": 3.0, "O2": 1.0},
        target_product="H2O",
    )
    assert result.error is None
    assert result.limiting_reagent == "O2"
    assert result.product_amount == pytest.approx(2.0, abs=0.01)


def test_limiting_reagent_unknown_reactant() -> None:
    result = chemistry_service.limiting_reagent(
        "H2 + O2 -> H2O",
        {"N2": 1.0},
        target_product="H2O",
    )
    assert result.error is not None
