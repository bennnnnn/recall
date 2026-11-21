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


def _named_nuclide(text: str) -> str | None:
    """The nuclide a question names, as ``He-4``: written as one, or by name and number."""
    nuclide = re.search(rf"\b({_NUCLIDE})\b", text)
    if nuclide is not None:
        return nuclide.group(1)
    from app.modules.chemistry.species_facts import ELEMENT_NAMES

    for named in _NAMED_NUCLIDE.finditer(text):
        symbol = ELEMENT_NAMES.get(named.group("name").lower())
        if symbol is not None:
            return f"{symbol}-{named.group('mass')}"
    return None


def _extract_mass_defect(text: str) -> ChemistryIntent | None:
    if not re.search(r"\b(?:mass defect|binding energy)\b", text, re.IGNORECASE):
        return None
    nuclide = _named_nuclide(text)
    mass = next(
        (found for pattern in _NUCLEAR_MASS if (found := _search(pattern, text)) is not None),
        None,
    )
    if nuclide is None or mass is None:
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
