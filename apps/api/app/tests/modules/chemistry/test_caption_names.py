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
from app.modules.chemistry.caption_names import caption_name

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
