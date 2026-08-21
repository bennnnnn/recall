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
