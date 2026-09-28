"""Chemistry request gating and compound-name extraction.

This module contains words only. Numeric/formula extraction belongs in
``extract.py`` so the inexpensive turn-prep gate cannot accidentally solve.
"""

from __future__ import annotations

import re

# Charge and phase are part of the species, not a second formula. The charge
# suffix is not nested, so it does not add another ambiguous quantifier.
CHEMICAL_FORMULA = (
    r"(?:e-|[A-Z][a-z]?[0-9]*(?:\([A-Za-z0-9]+\)[0-9]*)*"
    r"(?:[A-Z][a-z]?[0-9]*(?:\([A-Za-z0-9]+\)[0-9]*)?)*)"
    r"(?:\^(?:\{\d*[+-]\}|\d*[+-])|\d*[+-])?"
    r"(?:\((?:aq|s|l|g)\))?"
)
EQUATION_RE = re.compile(
    rf"((?:{CHEMICAL_FORMULA}\s*\+\s*)*{CHEMICAL_FORMULA}\s*(?:->|→)\s*"
    rf"(?:{CHEMICAL_FORMULA}\s*\+\s*)*{CHEMICAL_FORMULA})"
)

_CHEMISTRY_CUE = re.compile(
    r"\b(?:chemistry|stoichiometr\w*|molar|mol(?:e|es)?|molecules?|formula units?|molality|"
    r"molarity|dilut\w*|M1V1|mass percent|pH|pOH|"
    r"buffer|acid|base|equilibrium|reaction quotient|thermochem|enthalpy|entropy|"
    r"gibbs|specific heat|calorimetr|kinetic|rate constant|first[- ]order|arrhenius|half[- ]life|"
    r"electrochem|nernst|electrolysis|cell potential|faraday|radioactive|nuclear|"
    r"beer[- ]lambert|absorbance|percent yield|percent composition|avogadro|pv\s*=\s*nrt|"
    r"ideal gas|gas law|molecular descriptor|logp|tpsa|periodic table|atomic mass|"
    r"empirical|molecular formula|titration|ksp|hess|vsepr|lewis|oxidation|formal charge|"
    r"boyle|charles|dalton|partial pressure|functional group|isomer|coordination|"
    r"zero[- ]order|second[- ]order|rate law|galvanic|decay constant|"
    r"nuclear equation|calibration|gravimetric|standard addition|polyprotic|"
    r"common[- ]ion|bond enthalpy|formation enthalpy|ice table|ice equilibrium|"
    r"weak acid|weak base|"
    r"strong acid|strong base|electron capture|boiling|freezing|osmotic|raoult|"
    r"combined gas|over water|precipitation|stereochemistry|kp|"
    r"\bKa\b|\bKb\b|calorimeter constant)\b",
    re.IGNORECASE,
)
_BALANCE_CUE = re.compile(r"\b(?:balance|balanced|coefficient)\b", re.IGNORECASE)
_COMPOUND_CUES = re.compile(
    r"\b(?:structure|formula|molecule|molecular|smiles|compound|chemical|"
    r"what\s+is|tell\s+me\s+about|draw|show|describe)\b",
    re.IGNORECASE,
)
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
_NAME_STOPWORDS = frozenset(
    {
        "the",
        "of",
        "a",
        "an",
        "and",
        "for",
        "to",
        "in",
        "on",
        "at",
        "with",
        "from",
        "about",
        "this",
        "that",
    }
)
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
    """True for supported calculations or plausible compound lookup requests."""
    cleaned = content.strip()
    if not cleaned:
        return False
    if _CHEMISTRY_CUE.search(cleaned):
        return True
    if EQUATION_RE.search(cleaned) and (
        _BALANCE_CUE.search(cleaned)
        or re.search(r"\b(?:moles?|grams?|limiting|yield|Kc|Qc)\b", cleaned, re.IGNORECASE)
    ):
        return True
    if not _COMPOUND_CUES.search(cleaned):
        return False
    if re.search(
        r"\b(?:molecule|smiles|compound|chemical|molecular|atom|bond|reaction)\b",
        cleaned,
        re.IGNORECASE,
    ):
        return True
    return extract_compound_name(cleaned) is not None


def extract_compound_name(content: str) -> str | None:
    """Return a conservative PubChem lookup candidate."""
    match = _COMPOUND_NAME_RE.search(content)
    if match is None:
        return None
    name = match.group(1).strip().lower()
    name = re.sub(r"\s+(?:the|a|an|of|for|with)$", "", name).strip()
    name = re.sub(r"^(?:the\s+)?(?:lewis\s+)?structure\s+of\s+", "", name).strip()
    if not name or name in _FALSE_POSITIVES or not 3 <= len(name) <= 40:
        return None
    words = name.split()
    # "what is the capital of France" matches the same lead as "what is aspirin".
    # A real compound name has no function words.
    if len(words) > 3 or any(word in _NAME_STOPWORDS for word in words):
        return None
    return name
