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
    # Coefficients should be in the ratio 4:3:2
    r = result.reactants
    p = result.products
    assert r["Fe"] / r["O2"] == pytest.approx(4 / 3)
    assert p["Fe2O3"] / r["O2"] == pytest.approx(2 / 3)


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
