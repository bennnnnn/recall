"""Chemistry context — PubChem turn_prep injection and intent detection."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import chemistry_context

# ---------------------------------------------------------------------------
# is_chemistry_question
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("what is the structure of aspirin?", True),
        ("draw the molecule caffeine", True),
        ("molecular formula of ethanol", True),
        ("what is the SMILES for glucose", True),
        ("tell me about water as a compound", True),
        ("balance the equation H2 + O2 -> H2O", False),  # no compound cue
        ("what is 2 + 2?", False),
        ("", False),
    ],
)
def test_is_chemistry_question(text: str, expected: bool) -> None:
    assert chemistry_context.is_chemistry_question(text) is expected


# ---------------------------------------------------------------------------
# extract_compound_name
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("what is aspirin?", "aspirin"),
        ("structure of caffeine", "caffeine"),
        ("molecular formula of ethanol", "ethanol"),
        ("draw the molecule glucose", "glucose"),
        ("what is 2 + 2?", None),
        ("", None),
    ],
)
def test_extract_compound_name(text: str, expected: str | None) -> None:
    assert chemistry_context.extract_compound_name(text) == expected


# ---------------------------------------------------------------------------
# build_chemistry_context — PubChem lookup
# ---------------------------------------------------------------------------


async def test_build_chemistry_context_pubchem_success() -> None:
    """When PubChem returns a compound, the context block includes SMILES + formula."""
    fake_compound = MagicMock()
    fake_compound.smiles = "CC(=O)Oc1ccccc1C(=O)O"
    fake_compound.molecular_formula = "C9H8O4"
    fake_compound.molecular_weight = 180.16
    fake_compound.cid = 2244
    fake_result = MagicMock()
    fake_result.error = None
    fake_result.compound = fake_compound

    with patch.object(
        chemistry_context.pubchem_gateway, "lookup_by_name", new_callable=AsyncMock
    ) as mock_lookup:
        mock_lookup.return_value = fake_result
        block = await chemistry_context.build_chemistry_context("what is aspirin?", MagicMock())
    assert block is not None
    assert "Canonical SMILES: CC(=O)Oc1ccccc1C(=O)O" in block
    assert "Molecular formula: C9H8O4" in block
    assert "PubChem CID: 2244" in block


async def test_build_chemistry_context_pubchem_includes_3d_sdf() -> None:
    """When PubChem lookup succeeds with a CID, 3D SDF is fetched and included."""
    fake_compound = MagicMock()
    fake_compound.smiles = "CC(=O)Oc1ccccc1C(=O)O"
    fake_compound.molecular_formula = "C9H8O4"
    fake_compound.molecular_weight = 180.16
    fake_compound.cid = 2244
    fake_result = MagicMock()
    fake_result.error = None
    fake_result.compound = fake_compound

    fake_sdf = "fake SDF content with M  END"

    with (
        patch.object(
            chemistry_context.pubchem_gateway,
            "lookup_by_name",
            new_callable=AsyncMock,
        ) as mock_lookup,
        patch.object(
            chemistry_context.pubchem_gateway,
            "fetch_3d_sdf",
            new_callable=AsyncMock,
        ) as mock_sdf,
    ):
        mock_lookup.return_value = fake_result
        mock_sdf.return_value = fake_sdf
        block = await chemistry_context.build_chemistry_context("what is aspirin?", MagicMock())
    assert block is not None
    assert "3D SDF" in block
    assert "molecule3d" in block
    assert fake_sdf in block


async def test_build_chemistry_context_pubchem_not_found() -> None:
    """When PubChem returns an error, no context block is produced."""
    fake_result = MagicMock()
    fake_result.error = "not found"
    fake_result.compound = None

    with patch.object(
        chemistry_context.pubchem_gateway, "lookup_by_name", new_callable=AsyncMock
    ) as mock_lookup:
        mock_lookup.return_value = fake_result
        block = await chemistry_context.build_chemistry_context("what is xyzcompound?", MagicMock())
    assert block is None


async def test_build_chemistry_context_non_chemistry() -> None:
    """Non-chemistry questions return None."""
    block = await chemistry_context.build_chemistry_context("what is 2 + 2?", MagicMock())
    assert block is None


# ---------------------------------------------------------------------------
# build_chemistry_context — equation balancing
# ---------------------------------------------------------------------------


async def test_build_chemistry_context_balance_equation() -> None:
    """When the user asks to balance an equation, the context block includes the balanced form."""
    block = await chemistry_context.build_chemistry_context(
        "balance the equation H2 + O2 -> H2O", MagicMock()
    )
    assert block is not None
    assert "Verified balanced equation" in block
    assert "2 H2" in block or "2  H2" in block
    assert "2 H2O" in block or "2  H2O" in block


# ---------------------------------------------------------------------------
# build_chemistry_context — molar mass
# ---------------------------------------------------------------------------


async def test_build_chemistry_context_molar_mass() -> None:
    """When the user asks for molar mass, the context block includes the verified mass."""
    block = await chemistry_context.build_chemistry_context(
        "what is the molar mass of H2O?", MagicMock()
    )
    assert block is not None
    assert "Verified molar mass" in block
    assert "18" in block


# ---------------------------------------------------------------------------
# build_chemistry_context — stoichiometry
# ---------------------------------------------------------------------------


async def test_build_chemistry_context_stoichiometry() -> None:
    """When the user asks 'how much product' with an equation, stoichiometry context is injected."""
    block = await chemistry_context.build_chemistry_context(
        "how much H2O is produced from H2 + O2 -> H2O?",
        MagicMock(),
    )
    assert block is not None
    assert "Verified stoichiometry" in block
    assert "Balanced equation" in block


# ---------------------------------------------------------------------------
# build_chemistry_context — pH
# ---------------------------------------------------------------------------


async def test_build_chemistry_context_ph() -> None:
    """When the user asks about pH with [H+], the verified pH is injected."""
    block = await chemistry_context.build_chemistry_context(
        "what is the pH if [H+] = 0.001?",
        MagicMock(),
    )
    assert block is not None
    assert "Verified pH calculation" in block
    assert "3.00" in block


# ---------------------------------------------------------------------------
# build_chemistry_context — gas law
# ---------------------------------------------------------------------------


async def test_build_chemistry_context_gas_law() -> None:
    """When the user asks about gas laws, a hint is injected."""
    block = await chemistry_context.build_chemistry_context(
        "use PV=nRT to find the pressure of an ideal gas",
        MagicMock(),
    )
    assert block is not None
    assert "Gas law hint" in block
    assert "PV=nRT" in block


# ---------------------------------------------------------------------------
# build_chemistry_context — solution chemistry
# ---------------------------------------------------------------------------


async def test_build_chemistry_context_solution() -> None:
    """When the user asks about molarity, a hint is injected."""
    block = await chemistry_context.build_chemistry_context(
        "calculate the molarity of the solution",
        MagicMock(),
    )
    assert block is not None
    assert "Solution chemistry hint" in block
    assert "Molarity" in block
