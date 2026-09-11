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
        ("Draw the structure of carbon dioxide.", True),
        ("molecular formula of ethanol", True),
        ("what is the SMILES for glucose", True),
        ("tell me about water as a compound", True),
        ("balance the equation H2 + O2 -> H2O", True),
        ("Balance H2 + O2 -> H2O", True),
        ("Molar mass of C6H12O6", True),
        ("Calculate the molar mass of H2SO4", True),
        ("What is the pH when [H+] = 0.001?", True),
        ("Calculate the molarity of 0.5 mol in 2 L", True),
        ("A gas at 2 atm and 300 K occupies what volume? PV=nRT", True),
        ("How many moles of H2O from 4 mol H2 in H2 + O2 -> H2O?", True),
        ("What is the LogP of CC(=O)OC1=CC=CC=C1C(=O)O?", True),
        ("how many days until the trip", False),
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
        ("Draw the structure of carbon dioxide.", "carbon dioxide"),
        ("show the lewis structure of carbon dioxide", "carbon dioxide"),
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


async def test_build_chemistry_context_does_not_teach_molecule3d() -> None:
    """PubChem 3D SDF in the prompt taught a second ```molecule3d fence on top
    of the server-appended one — two molecule cards, one of them empty."""
    fake_compound = MagicMock()
    fake_compound.smiles = "CCO"
    fake_compound.molecular_formula = "C2H6O"
    fake_compound.molecular_weight = 46.07
    fake_compound.cid = 702
    fake_result = MagicMock()
    fake_result.error = None
    fake_result.compound = fake_compound

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
        mock_sdf.return_value = "fake SDF content with M  END"
        block = await chemistry_context.build_chemistry_context(
            "Show the molecular structure of ethanol. Include 2D and 3D.",
            MagicMock(),
        )
    assert block is not None
    assert "molecule3d" not in block
    assert "3D SDF" not in block
    mock_sdf.assert_not_called()


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


async def test_build_chemistry_context_stoichiometry_with_amount() -> None:
    block = await chemistry_context.build_chemistry_context(
        "How many moles of H2O from 4 mol H2 in H2 + O2 -> H2O?",
        MagicMock(),
    )
    assert block is not None
    assert "Verified stoichiometry" in block
    assert "mol H2" in block
    assert "H2O" in block


async def test_build_chemistry_context_limiting_reagent() -> None:
    block = await chemistry_context.build_chemistry_context(
        "limiting reagent: 1 mol H2 and 1 mol O2 in H2 + O2 -> H2O",
        MagicMock(),
    )
    assert block is not None
    assert "Verified limiting reagent" in block
    assert "H2" in block


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
    """Gas-law questions without enough numbers do not fake a verified block."""
    block = await chemistry_context.build_chemistry_context(
        "use PV=nRT to find the pressure of an ideal gas",
        MagicMock(),
    )
    assert block is None


async def test_build_chemistry_context_gas_law_verified() -> None:
    block = await chemistry_context.build_chemistry_context(
        "A gas at 1 atm and 273 K with 1 mol occupies what volume? PV=nRT",
        MagicMock(),
    )
    assert block is not None
    assert "Verified gas law" in block
    assert "22.4" in block


async def test_build_chemistry_context_gas_law_does_not_steal_pubchem() -> None:
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
        block = await chemistry_context.build_chemistry_context(
            "what is aspirin? the pressure and volume of the bottle are unknown",
            MagicMock(),
        )
    assert block is not None
    assert "Canonical SMILES" in block
    assert "Verified gas law" not in block
    mock_lookup.assert_awaited()


# ---------------------------------------------------------------------------
# build_chemistry_context — solution chemistry
# ---------------------------------------------------------------------------


async def test_build_chemistry_context_solution() -> None:
    """Molarity without numbers does not fake a verified block."""
    block = await chemistry_context.build_chemistry_context(
        "calculate the molarity of the solution",
        MagicMock(),
    )
    assert block is None


async def test_build_chemistry_context_molarity_verified() -> None:
    block = await chemistry_context.build_chemistry_context(
        "Calculate the molarity of 0.5 mol in 2 L",
        MagicMock(),
    )
    assert block is not None
    assert "Verified molarity" in block
    assert "0.2500" in block or "0.25" in block


async def test_build_chemistry_context_poh() -> None:
    block = await chemistry_context.build_chemistry_context(
        "what is the pH when pOH = 4?",
        MagicMock(),
    )
    assert block is not None
    assert "Verified pH calculation" in block
    assert "10.00" in block or "10" in block


async def test_build_chemistry_context_element() -> None:
    block = await chemistry_context.build_chemistry_context(
        "what is the atomic mass of Fe?",
        MagicMock(),
    )
    assert block is not None
    assert "Verified element data" in block
    assert "55.845" in block
    assert "Verified molar mass" not in block


async def test_build_chemistry_context_h_from_ph() -> None:
    block = await chemistry_context.build_chemistry_context(
        "what is [H+] when pH = 3?",
        MagicMock(),
    )
    assert block is not None
    assert "Verified pH calculation" in block
    assert "e-03" in block or "0.001" in block


async def test_build_chemistry_context_dilution() -> None:
    block = await chemistry_context.build_chemistry_context(
        "dilute a solution: M1=2 V1=1 M2=1",
        MagicMock(),
    )
    assert block is not None
    assert "Verified dilution" in block
    assert "2.0000" in block or "2" in block
