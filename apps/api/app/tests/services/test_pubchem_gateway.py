"""PubChem gateway — name/SMILES lookup (mocked, no real network)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.gateways import pubchem_gateway


def _mock_response(status_code: int, json_data: dict | None = None, text: str = "") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    return resp


@pytest.mark.asyncio
async def test_lookup_by_name_success() -> None:
    mock_resp = _mock_response(
        200,
        {
            "PropertyTable": {
                "Properties": [
                    {
                        "CID": 2244,
                        "CanonicalSMILES": "CC(=O)OC1=CC=CC=C1C(=O)O",
                        "MolecularFormula": "C9H8O4",
                        "MolecularWeight": "180.16",
                    }
                ]
            }
        },
    )
    client = AsyncMock()
    client.get = AsyncMock(return_value=mock_resp)
    with patch.object(pubchem_gateway, "get_pooled_client", return_value=client):
        result = await pubchem_gateway.lookup_by_name("aspirin")
    assert result.error is None
    assert result.compound is not None
    assert result.compound.cid == 2244
    assert result.compound.name == "aspirin"
    assert result.compound.smiles == "CC(=O)OC1=CC=CC=C1C(=O)O"
    assert result.compound.molecular_formula == "C9H8O4"
    assert result.compound.molecular_weight == 180.16


@pytest.mark.asyncio
async def test_lookup_by_name_not_found() -> None:
    mock_resp = _mock_response(404)
    client = AsyncMock()
    client.get = AsyncMock(return_value=mock_resp)
    with patch.object(pubchem_gateway, "get_pooled_client", return_value=client):
        result = await pubchem_gateway.lookup_by_name("nonexistent_compound_xyz")
    assert result.compound is None
    assert result.error is not None
    assert "not found" in result.error


@pytest.mark.asyncio
async def test_lookup_by_name_empty() -> None:
    result = await pubchem_gateway.lookup_by_name("")
    assert result.compound is None
    assert result.error == "empty name"


@pytest.mark.asyncio
async def test_lookup_by_name_network_error() -> None:
    client = AsyncMock()
    client.get = AsyncMock(side_effect=Exception("network error"))
    with patch.object(pubchem_gateway, "get_pooled_client", return_value=client):
        result = await pubchem_gateway.lookup_by_name("aspirin")
    assert result.compound is None
    assert result.error is not None


@pytest.mark.asyncio
async def test_lookup_by_smiles_success() -> None:
    mock_resp = _mock_response(
        200,
        {
            "PropertyTable": {
                "Properties": [
                    {
                        "CID": 2244,
                        "CanonicalSMILES": "CC(=O)OC1=CC=CC=C1C(=O)O",
                        "MolecularFormula": "C9H8O4",
                        "MolecularWeight": "180.16",
                    }
                ]
            }
        },
    )
    client = AsyncMock()
    client.get = AsyncMock(return_value=mock_resp)
    with patch.object(pubchem_gateway, "get_pooled_client", return_value=client):
        result = await pubchem_gateway.lookup_by_smiles("CC(=O)OC1=CC=CC=C1C(=O)O")
    assert result.error is None
    assert result.compound is not None
    assert result.compound.cid == 2244
    assert result.compound.molecular_formula == "C9H8O4"


@pytest.mark.asyncio
async def test_lookup_by_smiles_empty() -> None:
    result = await pubchem_gateway.lookup_by_smiles("")
    assert result.compound is None
    assert result.error == "empty SMILES"


@pytest.mark.asyncio
async def test_fetch_3d_sdf_success() -> None:
    sdf_content = "aspirin\n     RDKit\n\n  9  9  0  0  0  0  0  0  0  0999 V2000\nM  END\n"
    mock_resp = _mock_response(200, text=sdf_content)
    client = AsyncMock()
    client.get = AsyncMock(return_value=mock_resp)
    with patch.object(pubchem_gateway, "get_pooled_client", return_value=client):
        result = await pubchem_gateway.fetch_3d_sdf(2244)
    assert result == sdf_content


@pytest.mark.asyncio
async def test_fetch_3d_sdf_not_found() -> None:
    mock_resp = _mock_response(404)
    client = AsyncMock()
    client.get = AsyncMock(return_value=mock_resp)
    with patch.object(pubchem_gateway, "get_pooled_client", return_value=client):
        result = await pubchem_gateway.fetch_3d_sdf(999999999)
    assert result is None


@pytest.mark.asyncio
async def test_fetch_3d_sdf_network_error() -> None:
    client = AsyncMock()
    client.get = AsyncMock(side_effect=Exception("network error"))
    with patch.object(pubchem_gateway, "get_pooled_client", return_value=client):
        result = await pubchem_gateway.fetch_3d_sdf(2244)
    assert result is None
