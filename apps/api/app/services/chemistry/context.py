"""Chemistry context — detect chemistry questions and fetch PubChem data.

When a user asks about a compound by name (e.g. "what is aspirin?"),
this fetches the compound from PubChem and injects the SMILES + properties
into the prompt context so the model can render a verified ```smiles fence
and discuss real properties.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from redis.asyncio import Redis

from app.core.config import Settings
from app.gateways import pubchem_gateway
from app.services import chemistry as chemistry_service
from app.services.chemistry.stoichiometry import PERIODIC_TABLE

logger = logging.getLogger(__name__)

# Detect chemical equations: "H2 + O2 -> H2O" or "H2 + O2 → H2O"
# Match a sequence of chemical formulas separated by +, with an arrow.
# A formula is a sequence of element symbols (uppercase + optional lowercase)
# each optionally followed by digits, with optional parenthesized groups.
_EQ_FORMULA = (
    r"[A-Z][a-z]?[0-9]*(?:\([A-Za-z0-9]+\)[0-9]*)*"
    r"(?:[A-Z][a-z]?[0-9]*(?:\([A-Za-z0-9]+\)[0-9]*)?)*"
)
_EQUATION_RE = re.compile(
    rf"((?:{_EQ_FORMULA}\s*\+\s*)*{_EQ_FORMULA}\s*(?:->|→)\s*(?:{_EQ_FORMULA}\s*\+\s*)*{_EQ_FORMULA})"
)
# Cues that indicate the user wants the equation balanced.
_BALANCE_CUE = re.compile(
    r"\b(?:balance|balanced|coefficient|stoichiometr)\b",
    re.IGNORECASE,
)
# Detect molar mass questions: "molar mass of H2O", "molecular weight of C6H12O6"
_MOLAR_MASS_RE = re.compile(
    r"\b(?:molar\s+mass\s+of|molecular\s+weight\s+of|mass\s+of)\s+"
    r"([A-Za-z0-9\(\)\[\]\.]+)",
    re.IGNORECASE,
)

# Detect stoichiometry questions: "how much product", "how many moles of"
_STOICH_CUE = re.compile(
    r"\b(?:how\s+much|how\s+many|amount\s+of|moles\s+of|grams?\s+of|limiting\s+reagent)\b",
    re.IGNORECASE,
)

# Detect descriptor questions: "LogP", "TPSA", "polar surface area", "drug-likeness"
_DESCRIPTOR_CUE = re.compile(
    r"\b(?:logp|log\s*p|tpsa|polar\s+surface\s+area|drug[-\s]?likeness|"
    r"hydrogen\s+bond|h[-\s]?bond|lipinski|ro5|bioavailability)\b",
    re.IGNORECASE,
)

# Detect pH questions: "pH", "pOH", "acidic", "basic", "neutralize"
# Note: "pH" is matched case-sensitively to avoid false positives on "phase", "photo".
_PH_CUE = re.compile(
    r"(?:\bpH\b|\bpOH\b|acidic|basic|neutralize|"
    r"\[H\+?\]|\[OH-?\]|hydrogen\s+ion)",
)

# Detect gas law questions. No pressure.*volume — that stole PubChem lookups.
_GAS_LAW_CUE = re.compile(
    r"\b(?:pv\s*=\s*nrt|ideal\s+gas|boyle|charles|gay[-\s]?lussac|gas\s+law)\b",
    re.IGNORECASE,
)

# Detect solution chemistry: "molarity", "molality", "dilution", "M1V1"
_SOLUTION_CUE = re.compile(
    r"\b(?:molarity|molality|dilut\w*|M1V1|concentration\s+of\s+solution)\b",
    re.IGNORECASE,
)

_ELEMENT_CUE = re.compile(
    r"\b(?:atomic\s+mass|atomic\s+number|electronegativity|periodic\s+table|element)\b",
    re.IGNORECASE,
)

# Cues that indicate a chemistry question about a specific compound.
_COMPOUND_CUES = re.compile(
    r"\b(?:structure|formula|molecule|molecular|smiles|compound|chemical|"
    r"what\s+is|tell\s+me\s+about|draw|show|describe)\b",
    re.IGNORECASE,
)

# Common compound name patterns — a word or two after a cue.
# e.g. "what is aspirin", "structure of caffeine", "molecular formula of ethanol"
_COMPOUND_NAME_RE = re.compile(
    r"\b(?:(?:lewis\s+)?structure\s+of|molecular\s+formula\s+of|formula\s+of|"
    r"what\s+is|what's|tell\s+me\s+about|"
    r"draw\s+(?:the\s+)?(?:lewis\s+)?structure\s+of|"
    r"show(?:\s+me)?\s+(?:the\s+)?(?:lewis\s+)?structure\s+of|"
    r"draw\s+(?:the\s+)?(?:molecule\s+)?|show\s+me\s+(?:the\s+)?(?:molecule\s+)?|"
    r"describe(?:\s+the)?(?:\s+molecule)?\s+|"
    r"smiles\s+for|smiles\s+of|compound|chemical\s+structure\s+of)\s*"
    r"([a-zA-Z][a-zA-Z0-9\-\s]{2,40}?)"
    r"(?:\?|$|\.|,|\s+(?:and|or|with|in|at|for|to|is|are|the))",
    re.IGNORECASE,
)

# Known non-chemistry words that match the cue pattern.
_FALSE_POSITIVES = frozenset(
    {
        "the",
        "this",
        "that",
        "it",
        "a",
        "an",
        "water",
        "light",
        "energy",
        "time",
        "space",
        "code",
        "data",
        "file",
        "image",
        "text",
    }
)

_MOL_AMOUNT_RE = re.compile(
    r"(-?\d+(?:\.\d+)?)\s*mol(?:e|es)?(?:\s+of)?\s+([A-Z][A-Za-z0-9\(\)\.]*)"
)
_ATOMIC_MASS_PHRASE = re.compile(r"\batomic\s+mass\b", re.IGNORECASE)
_H_CONC_RE = re.compile(r"\[H\+?\]\s*=\s*([\d.eE+\-]+)")
_POH_EQ_RE = re.compile(r"\bpOH\s*=\s*(-?\d+(?:\.\d+)?)")
_PH_EQ_RE = re.compile(r"\bpH\s*=\s*(-?\d+(?:\.\d+)?)")
_ATM_RE = re.compile(r"(-?\d+(?:\.\d+)?)\s*atm\b", re.IGNORECASE)
_VOLUME_L_RE = re.compile(r"(-?\d+(?:\.\d+)?)\s*(?:L|liters?|litres?)\b")
_MOLES_BARE_RE = re.compile(r"(-?\d+(?:\.\d+)?)\s*mol(?:e|es)?\b", re.IGNORECASE)
_KELVIN_RE = re.compile(r"(-?\d+(?:\.\d+)?)\s*K\b")
_M1_RE = re.compile(r"\bM1\s*=\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE)
_V1_RE = re.compile(r"\bV1\s*=\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE)
_M2_RE = re.compile(r"\bM2\s*=\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE)
_V2_RE = re.compile(r"\bV2\s*=\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE)

_ELEMENT_NAMES = tuple(
    sorted(
        ((str(info["name"]).lower(), symbol) for symbol, info in PERIODIC_TABLE.items()),
        key=lambda pair: len(pair[0]),
        reverse=True,
    )
)


def is_chemistry_question(content: str) -> bool:
    """True when the user message is chemistry compute or compound lookup."""
    if not content.strip():
        return False
    eq_match = _EQUATION_RE.search(content)
    if eq_match is not None and _BALANCE_CUE.search(content):
        return True
    if _MOLAR_MASS_RE.search(content):
        return True
    if _STOICH_CUE.search(content) and eq_match is not None:
        return True
    if _DESCRIPTOR_CUE.search(content):
        return True
    if _PH_CUE.search(content):
        return True
    if _SOLUTION_CUE.search(content):
        return True
    if _GAS_LAW_CUE.search(content):
        return True
    if _ELEMENT_CUE.search(content):
        return True
    if not _COMPOUND_CUES.search(content):
        return False
    # Must also have a molecule-ish word or a compound name.
    if re.search(
        r"\b(?:molecule|smiles|compound|chemical|molecular|atom|bond|reaction)\b",
        content,
        re.IGNORECASE,
    ):
        return True
    # "what is aspirin" without explicit chemistry words — still try.
    return bool(_COMPOUND_NAME_RE.search(content))


def extract_compound_name(content: str) -> str | None:
    """Extract a candidate compound name from a chemistry question.

    Returns None when no compound name can be identified.
    """
    match = _COMPOUND_NAME_RE.search(content)
    if match is None:
        return None
    name = match.group(1).strip().lower()
    # Clean up trailing articles/prepositions.
    name = re.sub(r"\s+(?:the|a|an|of|for|with)$", "", name).strip()
    # "draw the structure of CO2" used to capture "structure of carbon dioxide".
    name = re.sub(r"^(?:the\s+)?(?:lewis\s+)?structure\s+of\s+", "", name).strip()
    if not name or name in _FALSE_POSITIVES:
        return None
    if len(name) < 3 or len(name) > 40:
        return None
    return name


def _format_balanced(balanced: Any) -> str:
    r_str = " + ".join(f"{c} {s}" for s, c in sorted(balanced.reactants.items()))
    p_str = " + ".join(f"{c} {s}" for s, c in sorted(balanced.products.items()))
    return f"{r_str} -> {p_str}"


def _mol_amounts(content: str) -> list[tuple[str, float]]:
    found: list[tuple[str, float]] = []
    for match in _MOL_AMOUNT_RE.finditer(content):
        formula = match.group(2).strip()
        if formula:
            found.append((formula, float(match.group(1))))
    return found


def _target_formula(content: str, products: dict[str, int]) -> str | None:
    lower = content.lower()
    for formula in products:
        if formula.lower() in lower:
            return formula
    return next(iter(products), None)


def _first_float(pattern: re.Pattern[str], content: str) -> float | None:
    match = pattern.search(content)
    if match is None:
        return None
    return float(match.group(1))


def _element_info(content: str) -> dict[str, float | int | str] | None:
    if _ELEMENT_CUE.search(content) is None:
        return None
    lower = f" {content.lower()} "
    for name, symbol in _ELEMENT_NAMES:
        if f" {name} " in lower or lower.strip().endswith(name):
            return chemistry_service.get_element_info(symbol)
    padded = f" {content} "
    for symbol in PERIODIC_TABLE:
        if f" {symbol} " in padded or f" {symbol}?" in padded:
            return chemistry_service.get_element_info(symbol)
        if f" {symbol.lower()} " in lower:
            return chemistry_service.get_element_info(symbol)
    return None


def _format_element_block(info: dict[str, float | int | str]) -> str:
    name = info.get("name", "element")
    lines = [f"[Verified element data for {name}]"]
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


async def build_chemistry_context(
    content: str,
    settings: Settings,
    redis: Redis | None = None,
) -> str | None:
    """Fetch chemistry context for a user message.

    Returns a context block string to inject into the prompt, or None
    when no chemistry context is needed or the fetch fails.
    """
    _ = settings
    # Check for equation balancing first (no PubChem needed).
    eq_match = _EQUATION_RE.search(content)
    if eq_match and _BALANCE_CUE.search(content):
        equation = eq_match.group(1).strip()
        try:
            balanced = chemistry_service.balance_equation(equation)
            if balanced.balanced:
                return (
                    f"[Verified balanced equation]\n"
                    f"{_format_balanced(balanced)}\n"
                    f"Use this balanced equation verbatim."
                )
        except Exception:
            logger.info("equation balancing failed for %r", equation, exc_info=True)

    # Check for molar mass questions. "atomic mass of Fe" is element lookup.
    mm_match = _MOLAR_MASS_RE.search(content)
    if mm_match and _ATOMIC_MASS_PHRASE.search(content) is None:
        formula = mm_match.group(1).strip()
        try:
            mass = chemistry_service.molar_mass(formula)
            return (
                f"[Verified molar mass]\n"
                f"Molar mass of {formula}: {mass} g/mol\n"
                f"Use this value verbatim in your answer."
            )
        except Exception:
            logger.info("molar mass failed for %r", formula, exc_info=True)

    # Stoichiometry / limiting reagent (with an equation).
    if _STOICH_CUE.search(content) and eq_match:
        equation = eq_match.group(1).strip()
        amounts = _mol_amounts(content)
        try:
            if "limiting" in content.lower() and len(amounts) >= 2:
                limit_result = chemistry_service.limiting_reagent(
                    equation,
                    {formula: amt for formula, amt in amounts},
                )
                if limit_result.error is None:
                    return (
                        f"[Verified limiting reagent]\n{limit_result.answer}\n"
                        f"Use this value verbatim."
                    )
            elif amounts:
                known, amount = amounts[0]
                balanced = chemistry_service.balance_equation(equation)
                target = _target_formula(content, balanced.products) if balanced.balanced else None
                stoich_result = chemistry_service.stoichiometry(equation, known, amount, target)
                if stoich_result.error is None:
                    return (
                        f"[Verified stoichiometry]\n{stoich_result.answer}\n"
                        f"Use this value verbatim."
                    )
            balanced = chemistry_service.balance_equation(equation)
            if balanced.balanced:
                return (
                    f"[Verified stoichiometry]\n"
                    f"Balanced equation: {_format_balanced(balanced)}\n"
                    f"Use mole ratios from the balanced coefficients for your calculation."
                )
        except Exception:
            logger.info("stoichiometry context failed", exc_info=True)

    # Check for molecular descriptor questions (with a SMILES in the message).
    if _DESCRIPTOR_CUE.search(content):
        # Try to find a SMILES-like string in the message.
        smiles_match = re.search(r"\b([A-Z][A-Za-z0-9@\[\]\(\)=#\\\\/\\\\.]{4,60})\b", content)
        if smiles_match:
            smiles = smiles_match.group(1)
            try:
                desc = chemistry_service.compute_descriptors(smiles)
                if desc.error is None:
                    return (
                        f"[Verified molecular descriptors for {desc.smiles}]\n"
                        f"MW: {desc.molecular_weight} g/mol\n"
                        f"LogP: {desc.log_p}\n"
                        f"TPSA: {desc.tpsa}\n"
                        f"H-bond donors: {desc.h_bond_donors}\n"
                        f"H-bond acceptors: {desc.h_bond_acceptors}\n"
                        f"Rotatable bonds: {desc.rotatable_bonds}\n"
                        f"Rings: {desc.ring_count}\n"
                        f"Use these values verbatim in your answer."
                    )
            except Exception:
                logger.info("descriptor context failed for %r", smiles, exc_info=True)

    # Check for pH questions.
    if _PH_CUE.search(content):
        h_match = _H_CONC_RE.search(content)
        if h_match:
            try:
                h_conc = float(h_match.group(1))
                ph_result = chemistry_service.ph_from_concentration(h_conc)
                if ph_result.error is None:
                    return (
                        f"[Verified pH calculation]\n{ph_result.answer}\nUse this value verbatim."
                    )
            except Exception:
                logger.info("pH context failed", exc_info=True)
        poh_val = _first_float(_POH_EQ_RE, content)
        if poh_val is not None:
            ph_result = chemistry_service.ph_from_poh(poh_val)
            if ph_result.error is None:
                return f"[Verified pH calculation]\n{ph_result.answer}\nUse this value verbatim."
        ph_val = _first_float(_PH_EQ_RE, content)
        if ph_val is not None and ("[H" in content or "hydrogen ion" in content.lower()):
            ph_result = chemistry_service.h_from_ph(ph_val)
            if ph_result.error is None:
                return f"[Verified pH calculation]\n{ph_result.answer}\nUse this value verbatim."

    # Gas law — only when exactly one of P,V,n,T is missing.
    if _GAS_LAW_CUE.search(content):
        pressure = _first_float(_ATM_RE, content)
        volume = _first_float(_VOLUME_L_RE, content)
        moles = _first_float(_MOLES_BARE_RE, content)
        temperature = _first_float(_KELVIN_RE, content)
        given = [pressure, volume, moles, temperature]
        if sum(1 for v in given if v is None) == 1:
            gas = chemistry_service.ideal_gas_law(
                pressure=pressure,
                volume=volume,
                moles=moles,
                temperature=temperature,
            )
            if gas.error is None:
                return f"[Verified gas law]\n{gas.answer}\nUse this value verbatim."

    # Solution chemistry — molarity / dilution when numbers are present.
    if _SOLUTION_CUE.search(content):
        m1 = _first_float(_M1_RE, content)
        v1 = _first_float(_V1_RE, content)
        m2 = _first_float(_M2_RE, content)
        v2 = _first_float(_V2_RE, content)
        if m1 is not None and v1 is not None and (m2 is None) != (v2 is None):
            dil = chemistry_service.dilution(m1, v1, v2=v2, m2=m2)
            if dil.error is None:
                return f"[Verified dilution]\n{dil.answer}\nUse this value verbatim."
        moles = _first_float(_MOLES_BARE_RE, content)
        volume = _first_float(_VOLUME_L_RE, content)
        if moles is not None and volume is not None:
            mol = chemistry_service.molarity(moles, volume)
            if mol.error is None:
                return f"[Verified molarity]\n{mol.answer}\nUse this value verbatim."

    element = _element_info(content)
    if element is not None:
        return _format_element_block(element)

    # Compound lookup via PubChem.
    if not is_chemistry_question(content):
        return None

    name = extract_compound_name(content)
    if name is None:
        return None

    lookup = await pubchem_gateway.lookup_by_name(name, redis=redis)
    if lookup.error is not None or lookup.compound is None:
        logger.info("PubChem lookup failed for %r: %s", name, lookup.error)
        return None

    compound = lookup.compound
    # Build a context block that tells the model the verified SMILES and
    # properties, so it can emit a ```smiles fence and discuss real data.
    lines = [
        f"[Chemistry context for {name}]",
        f"Canonical SMILES: {compound.smiles}",
        f"Molecular formula: {compound.molecular_formula}",
        f"Molecular weight: {compound.molecular_weight:.2f} g/mol",
        f"PubChem CID: {compound.cid}",
        "Use the SMILES above verbatim in a ```smiles fence if you show the structure.",
    ]

    return "\n".join(lines)
