"""A molecule's caption name is looked up before the drawing, never trusted as written.

A model's "Caffeine" over ethanol's SMILES was drawn as caffeine (audit CHEM-04, 2026-11-13).
A name the chemistry tables give is read from them; any other is looked up on PubChem within
the chemistry context's 2 s budget, and a miss or a timeout leaves no name. No network here.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings
from app.gateways.pubchem_gateway import PubChemCompound, PubChemResult
from app.modules.chemistry.caption_lookup import checked_names
from app.modules.chemistry.caption_names import caption_name, checked_name

_CAFFEINE = PubChemCompound(
    cid=2519,
    name="caffeine",
    smiles="CN1C=NC2=C1C(=O)N(C(=O)N2C)C",
    molecular_formula="C8H10N4O2",
    molecular_weight=194.19,
)
_REPLY = "Here:\n\n```smiles\nCaffeine\nCCO\n```\n\n```smiles\nWater\nO\n```\n"


async def test_caption_names_a_name_the_tables_lack_is_looked_up() -> None:
    lookup = AsyncMock(return_value=PubChemResult(compound=_CAFFEINE))
    with patch("app.gateways.pubchem_gateway.lookup_by_name", lookup):
        found = await checked_names(_REPLY, Settings())
    # Water is the tables'; only caffeine goes to PubChem.
    assert [call.args[0] for call in lookup.await_args_list] == ["Caffeine"]
    assert found == {"caffeine": _CAFFEINE.smiles}


@pytest.mark.parametrize(
    "lookup",
    [
        AsyncMock(return_value=PubChemResult(error="compound 'Caffeine' not found")),
        AsyncMock(side_effect=RuntimeError("PubChem is down")),
    ],
)
async def test_caption_names_a_miss_or_an_outage_gives_no_name(lookup: AsyncMock) -> None:
    with patch("app.gateways.pubchem_gateway.lookup_by_name", lookup):
        assert await checked_names(_REPLY, Settings()) == {}


async def test_caption_names_a_slow_lookup_gives_no_name() -> None:
    async def slow(*_args: Any, **_kwargs: Any) -> PubChemResult:
        await asyncio.sleep(1)
        return PubChemResult(compound=_CAFFEINE)

    with (
        patch("app.gateways.pubchem_gateway.lookup_by_name", slow),
        patch("app.modules.chemistry.context.PUBCHEM_BUDGET_SECONDS", 0.01),
    ):
        assert await checked_names(_REPLY, Settings()) == {}


async def test_caption_names_chemistry_off_looks_nothing_up() -> None:
    lookup = AsyncMock()
    with patch("app.gateways.pubchem_gateway.lookup_by_name", lookup):
        assert await checked_names(_REPLY, Settings(chemistry_enabled=False)) == {}
    lookup.assert_not_awaited()


@pytest.mark.parametrize(
    ("written", "name"),
    [
        ("Caffeine", "Caffeine"),
        ("**Caffeine** · C8H10N4O2 · 194.19 g/mol", "Caffeine"),
        ("H₂O · 999.00 g/mol", "H₂O"),
        ("", None),
        ("123", None),
    ],
)
def test_caption_name_reads_the_name_a_caption_starts_with(written: str, name: str | None) -> None:
    assert caption_name(written) == name


@pytest.mark.parametrize(
    ("written", "drawn", "named", "kept"),
    [
        # A stereo name is held to the stereo marks: cis over trans, (R) over (S) (review).
        ("cis-2-butene", "C/C=C/C", {"cis-2-butene": "C/C=C\\C"}, None),
        ("(R)-alanine", "C[C@H](N)C(=O)O", {"(r)-alanine": "C[C@@H](N)C(=O)O"}, None),
        ("cis-2-butene", "C/C=C\\C", {"cis-2-butene": "C/C=C\\C"}, "cis-2-butene"),
        ("L-alanine", "C[C@@H](C(=O)O)N", {"l-alanine": "C[C@@H](C(=O)O)N"}, "L-alanine"),
        # A stereo name over a drawing with no marks: the drawing does not show it.
        ("cis-2-butene", "CC=CC", {"cis-2-butene": "C/C=C\\C"}, None),
        # A name with no descriptor is held to the connections alone (third review).
        ("Alanine", "C[C@@H](C(=O)O)N", {"alanine": "C[C@@H](C(=O)O)N"}, "Alanine"),
        ("2-butene", "C/C=C/C", {"2-butene": "CC=CC"}, "2-butene"),
        ("Ethanol", "OCC", {"ethanol": "CCO"}, "Ethanol"),
        ("Caffeine", "CCO", {"caffeine": "CN1C=NC2=C1C(=O)N(C(=O)N2C)C"}, None),
    ],
)
def test_caption_names_a_name_keeps_only_its_own_stereo(
    written: str, drawn: str, named: dict[str, str], kept: str | None
) -> None:
    assert checked_name(written, drawn, named) == kept


async def test_caption_names_a_lookup_gives_the_structure_with_its_stereo_marks() -> None:
    alanine = PubChemCompound(
        cid=5950,
        name="L-alanine",
        smiles="CC(C(=O)O)N",
        molecular_formula="C3H7NO2",
        molecular_weight=89.09,
        isomeric_smiles="C[C@@H](C(=O)O)N",
    )
    reply = "Here:\n\n```smiles\nL-alanine\nC[C@@H](C(=O)O)N\n```\n"
    lookup = AsyncMock(return_value=PubChemResult(compound=alanine))
    with patch("app.gateways.pubchem_gateway.lookup_by_name", lookup):
        assert await checked_names(reply, Settings()) == {"l-alanine": "C[C@@H](C(=O)O)N"}
