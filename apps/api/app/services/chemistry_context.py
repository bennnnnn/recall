"""Chemistry context — detect chemistry questions and fetch PubChem data.

When a user asks about a compound by name (e.g. "what is aspirin?"),
this fetches the compound from PubChem and injects the SMILES + properties
into the prompt context so the model can render a verified ```smiles fence
and discuss real properties.
"""

from __future__ import annotations

import logging
import re

from app.core.config import Settings
from app.gateways import pubchem_gateway
from app.services import chemistry_service

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

# Cues that indicate a chemistry question about a specific compound.
_COMPOUND_CUES = re.compile(
    r"\b(?:structure|formula|molecule|molecular|smiles|compound|chemical|"
    r"what\s+is|tell\s+me\s+about|draw|show|describe)\b",
    re.IGNORECASE,
)

# Common compound name patterns — a word or two after a cue.
# e.g. "what is aspirin", "structure of caffeine", "molecular formula of ethanol"
_COMPOUND_NAME_RE = re.compile(
    r"\b(?:structure\s+of|molecular\s+formula\s+of|formula\s+of|"
    r"what\s+is|what's|tell\s+me\s+about|draw\s+(?:the\s+)?(?:molecule\s+)?|show\s+me\s+(?:the\s+)?(?:molecule\s+)?|describe(?:\s+the)?(?:\s+molecule)?\s+|"
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


def is_chemistry_question(content: str) -> bool:
    """True when the user message looks like a chemistry question."""
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
    if not name or name in _FALSE_POSITIVES:
        return None
    if len(name) < 3 or len(name) > 40:
        return None
    return name


async def build_chemistry_context(
    content: str,
    settings: Settings,
) -> str | None:
    """Fetch chemistry context for a user message.

    Returns a context block string to inject into the prompt, or None
    when no chemistry context is needed or the fetch fails.
    """
    # Check for equation balancing first (no PubChem needed).
    eq_match = _EQUATION_RE.search(content)
    if eq_match and _BALANCE_CUE.search(content):
        equation = eq_match.group(1).strip()
        try:
            balanced = chemistry_service.balance_equation(equation)
            if balanced.balanced:
                r_str = " + ".join(f"{c} {s}" for s, c in sorted(balanced.reactants.items()))
                p_str = " + ".join(f"{c} {s}" for s, c in sorted(balanced.products.items()))
                return (
                    f"[Verified balanced equation]\n"
                    f"{r_str} -> {p_str}\n"
                    f"Use this balanced equation verbatim."
                )
        except Exception:
            logger.info("equation balancing failed for %r", equation, exc_info=True)

    # Check for molar mass questions.
    mm_match = _MOLAR_MASS_RE.search(content)
    if mm_match:
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

    # Compound lookup via PubChem.
    if not is_chemistry_question(content):
        return None

    name = extract_compound_name(content)
    if name is None:
        return None

    result = await pubchem_gateway.lookup_by_name(name)
    if result.error is not None or result.compound is None:
        logger.info("PubChem lookup failed for %r: %s", name, result.error)
        return None

    compound = result.compound
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
