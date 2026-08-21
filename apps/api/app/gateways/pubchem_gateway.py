"""PubChem gateway — compound lookup by name or SMILES (server-side only).

Provides:
- name → SMILES (canonical) via the PUG-REST API
- SMILES → properties (molecular formula, weight, CID) via the PUG-REST API
- CID → 3D SDF (for 3Dmol.js rendering) via the PubChem download API

All calls are server-side (Golden Rule 1 — no provider keys in the app).
PubChem is a free public API; no key required.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.gateways.http_client import get_pooled_client

logger = logging.getLogger(__name__)

PUG_REST_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
PUG_VIEW_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view"
DEFAULT_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class PubChemCompound:
    """A compound resolved from PubChem."""

    cid: int  # PubChem Compound ID
    name: str
    smiles: str  # canonical SMILES
    molecular_formula: str
    molecular_weight: float
    error: str | None = None


@dataclass(frozen=True)
class PubChemResult:
    """Result of a PubChem lookup — either a compound or an error."""

    compound: PubChemCompound | None = None
    error: str | None = None


async def _pug_get(url: str, params: dict[str, str]) -> dict[str, Any] | None:
    """GET from PUG-REST with JSON Accept header. Returns None on failure."""
    client = get_pooled_client(DEFAULT_TIMEOUT_SECONDS)
    headers = {"Accept": "application/json"}
    try:
        resp = await client.get(url, params=params, headers=headers)
        if resp.status_code != 200:
            return None
        return resp.json()
    except Exception as exc:
        logger.info("PubChem GET failed url=%s: %s", url, exc)
        return None


async def lookup_by_name(name: str) -> PubChemResult:
    """Resolve a compound name (e.g. 'aspirin') to a PubChem compound.

    Returns PubChemResult with error set when the name is not found.
    """
    name = name.strip()
    if not name:
        return PubChemResult(error="empty name")

    # PUG-REST: /compound/name/<name>/property/CanonicalSMILES,MolecularFormula,'
    # MolecularWeight,IUPACName/JSON
    url = f"{PUG_REST_URL}/compound/name/{name}/property/CanonicalSMILES,MolecularFormula,MolecularWeight/JSON"
    data = await _pug_get(url, {})
    if data is None:
        return PubChemResult(error=f"compound '{name}' not found")

    try:
        props_list = data.get("PropertyTable", {}).get("Properties", [])
        if not props_list:
            return PubChemResult(error=f"no properties for '{name}'")
        props = props_list[0]
        cid = int(props.get("CID", 0))
        smiles = str(props.get("CanonicalSMILES", ""))
        formula = str(props.get("MolecularFormula", ""))
        weight = float(props.get("MolecularWeight", 0.0))
        return PubChemResult(
            compound=PubChemCompound(
                cid=cid,
                name=name,
                smiles=smiles,
                molecular_formula=formula,
                molecular_weight=weight,
            )
        )
    except (KeyError, ValueError, TypeError) as exc:
        return PubChemResult(error=f"PubChem response parse error: {exc}")


async def lookup_by_smiles(smiles: str) -> PubChemResult:
    """Resolve a SMILES string to a PubChem compound (if it exists).

    Returns PubChemResult with error set when the SMILES is not in PubChem.
    """
    smiles = smiles.strip()
    if not smiles:
        return PubChemResult(error="empty SMILES")

    url = f"{PUG_REST_URL}/compound/smiles/{smiles}/property/CanonicalSMILES,MolecularFormula,MolecularWeight/JSON"
    data = await _pug_get(url, {})
    if data is None:
        return PubChemResult(error="SMILES not found in PubChem")

    try:
        props_list = data.get("PropertyTable", {}).get("Properties", [])
        if not props_list:
            return PubChemResult(error="no properties for SMILES")
        props = props_list[0]
        cid = int(props.get("CID", 0))
        canonical = str(props.get("CanonicalSMILES", ""))
        formula = str(props.get("MolecularFormula", ""))
        weight = float(props.get("MolecularWeight", 0.0))
        return PubChemResult(
            compound=PubChemCompound(
                cid=cid,
                name="",
                smiles=canonical,
                molecular_formula=formula,
                molecular_weight=weight,
            )
        )
    except (KeyError, ValueError, TypeError) as exc:
        return PubChemResult(error=f"PubChem response parse error: {exc}")


async def fetch_3d_sdf(cid: int) -> str | None:
    """Fetch the 3D SDF (MOL block) for a PubChem compound by CID.

    Returns the SDF as a string, or None on failure. Used by the
    Molecule3DBlock for 3Dmol.js rendering.
    """
    client = get_pooled_client(DEFAULT_TIMEOUT_SECONDS)
    url = f"{PUG_REST_URL}/compound/cid/{cid}/SDF?record_type=3d"
    try:
        resp = await client.get(url, headers={"Accept": "chemical/x-mdl-sdfile"})
        if resp.status_code != 200:
            return None
        return resp.text
    except Exception as exc:
        logger.info("PubChem 3D SDF fetch failed cid=%s: %s", cid, exc)
        return None
