"""Chemistry turn preparation: deterministic solve first, PubChem second."""

from __future__ import annotations

import logging
import re

from redis.asyncio import Redis

from app.core.config import Settings
from app.gateways import pubchem_gateway
from app.services import chemistry as chemistry_service
from app.services.chemistry.block import VerifiedChemistry, build_verified_chemistry
from app.services.chemistry.extract import extract_chemistry_intent
from app.services.chemistry.request import (
    EQUATION_RE,
    extract_compound_name,
    is_chemistry_question,
)
from app.services.chemistry.stoichiometry import PERIODIC_TABLE

logger = logging.getLogger(__name__)

_DESCRIPTOR_CUE = re.compile(
    r"\b(?:logp|log\s*p|tpsa|polar\s+surface\s+area|drug[-\s]?likeness|"
    r"hydrogen\s+bond|h[-\s]?bond|lipinski|ro5|bioavailability)\b",
    re.IGNORECASE,
)
_ELEMENT_CUE = re.compile(
    r"\b(?:atomic\s+mass|atomic\s+number|electronegativity|periodic\s+table|element)\b",
    re.IGNORECASE,
)
_STOICH_CUE = re.compile(
    r"\b(?:how\s+much|how\s+many|amount\s+of|moles\s+of|grams?\s+of|limiting\s+reagent)\b",
    re.IGNORECASE,
)
_ELEMENT_NAMES = tuple(
    sorted(
        ((str(info["name"]).lower(), symbol) for symbol, info in PERIODIC_TABLE.items()),
        key=lambda pair: len(pair[0]),
        reverse=True,
    )
)


def _format_balanced(equation: str) -> str | None:
    balanced = chemistry_service.balance_equation(equation)
    if not balanced.balanced:
        return None
    reactants = " + ".join(
        f"{coefficient} {species}" for species, coefficient in balanced.reactants.items()
    )
    products = " + ".join(
        f"{coefficient} {species}" for species, coefficient in balanced.products.items()
    )
    return f"{reactants} -> {products}"


def _stoichiometry_ratio_hint(content: str) -> str | None:
    """Preserve the useful verified ratio when a numeric amount is missing."""
    equation_match = EQUATION_RE.search(content)
    if equation_match is None or _STOICH_CUE.search(content) is None:
        return None
    equation = equation_match.group(1).strip()
    try:
        balanced = _format_balanced(equation)
    except Exception:
        logger.info("stoichiometry ratio hint failed", exc_info=True)
        return None
    if balanced is None:
        return None
    return (
        "[Verified stoichiometry]\n"
        f"Balanced equation: {balanced}\n"
        "Use mole ratios from the balanced coefficients. No numerical yield is verified "
        "because the question does not supply a complete amount and target pair."
    )


def _descriptor_context(content: str) -> str | None:
    if _DESCRIPTOR_CUE.search(content) is None:
        return None
    match = re.search(r"\b([A-Z][A-Za-z0-9@\[\]\(\)=#\\/\\.]{4,60})\b", content)
    if match is None:
        return None
    smiles = match.group(1)
    try:
        desc = chemistry_service.compute_descriptors(smiles)
    except Exception:
        logger.info("descriptor context failed for %r", smiles, exc_info=True)
        return None
    if desc.error is not None:
        return None
    return (
        f"[Verified molecular descriptors for {desc.smiles}]\n"
        f"MW: {desc.molecular_weight} g/mol\n"
        f"LogP: {desc.log_p}\n"
        f"TPSA: {desc.tpsa}\n"
        f"H-bond donors: {desc.h_bond_donors}\n"
        f"H-bond acceptors: {desc.h_bond_acceptors}\n"
        f"Rotatable bonds: {desc.rotatable_bonds}\n"
        f"Rings: {desc.ring_count}\n"
        "Use these values verbatim in your answer."
    )


def _element_context(content: str) -> str | None:
    if _ELEMENT_CUE.search(content) is None:
        return None
    lower = f" {content.lower()} "
    info: dict[str, float | int | str] | None = None
    for name, symbol in _ELEMENT_NAMES:
        if f" {name} " in lower or lower.strip().endswith(name):
            info = chemistry_service.get_element_info(symbol)
            break
    if info is None:
        padded = f" {content} "
        for symbol in PERIODIC_TABLE:
            if f" {symbol} " in padded or f" {symbol}?" in padded:
                info = chemistry_service.get_element_info(symbol)
                break
    if info is None:
        return None
    element_name = str(info.get("name", "element"))
    lines = [f"[Verified element data for {element_name}]"]
    if "mass" in info:
        lines.append(f"Atomic mass: {info['mass']} g/mol")
    if "group" in info:
        lines.append(f"Group: {info['group']}")
    if "period" in info:
        lines.append(f"Period: {info['period']}")
    if "electronegativity" in info:
        lines.append(f"Electronegativity: {info['electronegativity']}")
    lines.append("Use these values verbatim in your answer.")
    return "\n".join(lines)


async def build_chemistry_augmentation(
    content: str,
    settings: Settings,
    redis: Redis | None = None,
) -> tuple[str | None, VerifiedChemistry | None]:
    """Return prompt context plus the typed verified solve, when available."""
    _ = settings
    intent = extract_chemistry_intent(content)
    if intent is not None:
        verified = build_verified_chemistry(intent)
        if verified is not None:
            return verified.prompt_text, verified

    for local_context in (
        _stoichiometry_ratio_hint(content),
        _descriptor_context(content),
        _element_context(content),
    ):
        if local_context is not None:
            return local_context, None

    if not is_chemistry_question(content):
        return None, None
    name = extract_compound_name(content)
    if name is None:
        return None, None
    lookup = await pubchem_gateway.lookup_by_name(name, redis=redis)
    if lookup.error is not None or lookup.compound is None:
        logger.info("PubChem lookup failed for %r: %s", name, lookup.error)
        return None, None
    compound = lookup.compound
    return (
        "\n".join(
            [
                f"[Chemistry context for {name}]",
                f"Canonical SMILES: {compound.smiles}",
                f"Molecular formula: {compound.molecular_formula}",
                f"Molecular weight: {compound.molecular_weight:.2f} g/mol",
                f"PubChem CID: {compound.cid}",
                "Use the SMILES above verbatim in a ```smiles fence if you show the structure.",
            ]
        ),
        None,
    )


async def build_chemistry_context(
    content: str,
    settings: Settings,
    redis: Redis | None = None,
) -> str | None:
    """Backward-compatible context-only facade."""
    block, _verified = await build_chemistry_augmentation(content, settings, redis=redis)
    return block


__all__ = [
    "build_chemistry_augmentation",
    "build_chemistry_context",
    "extract_compound_name",
    "is_chemistry_question",
]
