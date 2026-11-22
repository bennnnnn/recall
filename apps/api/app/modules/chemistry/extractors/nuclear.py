"""Nuclear chemistry: a nuclear equation's missing particle and a nuclide's mass defect."""

from __future__ import annotations

import re

from app.modules.chemistry.extractors.parsing import (
    _N,
    _NUCLIDE,
    _search,
)
from app.modules.chemistry.schemas import ChemistryIntent


def _extract_nuclear_equation(text: str) -> ChemistryIntent | None:
    # Half-lives, decay constants and activities are physics' laws (physics/catalog/nuclear.py).
    match = re.search(r"nuclear equation\s*:?\s+(.+)$", text, re.IGNORECASE)
    if match:
        return ChemistryIntent(
            kind="nuclear", chemistry_op="nuclear_equation", equation=match.group(1).strip()
        )
    return None


# "helium-4", "uranium 235": an element by name and its mass number.
_NAMED_NUCLIDE = re.compile(r"\b(?P<name>[A-Za-z]{3,})[- ](?P<mass>\d{1,3})\b")
# The nucleus's mass, as a question states it: "nuclear mass = 4.0015 u", "A helium-4 nucleus
# has a mass of 4.001506 u", "the mass of the nucleus is 4.0015 u". An atom's mass is no
# nucleus's (its electrons are in it), so only a nucleus named in the sentence is read.
_NUCLEAR_MASS = (
    rf"\bnuclear mass\s*=\s*({_N})",
    rf"\bnucle(?:us|ar)\b[^.?!]{{0,40}}?\bmass\s+(?:of|is|=)\s*({_N})\s*u\b",
    rf"\bmass\s+of\s+(?:the|a|an)\s+(?:[\w-]+\s+){{0,2}}?nucleus\s+(?:is|=)\s*({_N})\s*u\b",
)
# The constants a question states, which its answer uses: "The proton mass is 1.007276 u",
# "mass of a neutron = 1.008665 u", "(1 u = 931.5 MeV)".
_PARTICLE_MASS = (
    r"\b{particle}\s+mass\s+(?:is|=|of)\s*({number})\s*u\b",
    r"\bmass\s+of\s+(?:a|an|the|one)\s+{particle}\s+(?:is|=)\s*({number})\s*u\b",
)
_MEV_PER_U = rf"\b1\s*u\s*(?:=|is|equals)\s*({_N})\s*MeV\b"


# A particle's mass is no nucleus's: "a proton has a mass of 1.007276 u" sits beside it.
# An atom's mass is no nucleus's either: it holds the electrons' (4.002603 u for He-4's atom,
# 4.001506 u for its nucleus), about 1 MeV of binding energy (review, #2525).
_PARTICLE = re.compile(
    r"\b(?:protons?|neutrons?|electrons?|atomic|isotopic|atoms?)\b", re.IGNORECASE
)
# A nucleus's mass in u is within one of its mass number (He-4 4.0015, U-238 238.0003).
_MASS_NUMBER_SLACK = 1.0


def _named_nuclides(text: str) -> list[str]:
    """Each nuclide a question names, as ``He-4``, once: written as one, or by name and
    number."""
    from app.modules.chemistry.species_facts import ELEMENT_NAMES

    found = [match.group(1) for match in re.finditer(rf"\b({_NUCLIDE})\b", text)]
    for named in _NAMED_NUCLIDE.finditer(text):
        symbol = ELEMENT_NAMES.get(named.group("name").lower())
        if symbol is not None:
            found.append(f"{symbol}-{named.group('mass')}")
    return list(dict.fromkeys(_as_symbol_first(nuclide) for nuclide in found))


def _as_symbol_first(nuclide: str) -> str:
    """``4He`` as ``He-4``, so one nuclide written two ways counts once."""
    written = re.fullmatch(r"(\d+)([A-Z][a-z]?)", nuclide)
    return f"{written.group(2)}-{written.group(1)}" if written else nuclide


def _nuclear_mass(text: str) -> float | None:
    """The nucleus's mass the question states, never a proton's or a neutron's that a
    pattern reaches across to (review, #2525)."""
    for pattern in _NUCLEAR_MASS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            if _PARTICLE.search(match.group(0)) is None:
                return float(match.group(1))
    return None


def _extract_mass_defect(text: str) -> ChemistryIntent | None:
    if not re.search(r"\b(?:mass defect|binding energy)\b", text, re.IGNORECASE):
        return None
    # Two nuclides is a reaction, whose mass defect is no one nucleus's (review, #2525).
    nuclides = _named_nuclides(text)
    mass = _nuclear_mass(text)
    if len(nuclides) != 1 or mass is None:
        return None
    nuclide = nuclides[0]
    if abs(mass - int(nuclide.rsplit("-", 1)[1])) >= _MASS_NUMBER_SLACK:
        return None
    params = {"nuclear_mass": mass}
    units = {"nuclear_mass": "u"}
    for name in ("proton", "neutron"):
        for pattern in _PARTICLE_MASS:
            value = _search(pattern.format(particle=name, number=_N), text)
            if value is not None:
                params[f"{name}_mass"], units[f"{name}_mass"] = value, "u"
                break
    per_u = _search(_MEV_PER_U, text)
    if per_u is not None:
        params["mev_per_u"], units["mev_per_u"] = per_u, "MeV"
    return ChemistryIntent(
        kind="nuclear",
        chemistry_op="mass_defect",
        formula=nuclide,
        params=params,
        units=units,
    )
