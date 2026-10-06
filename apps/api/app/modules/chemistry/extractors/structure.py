"""Structure: electron configuration, oxidation states, VSEPR, formal charge, complexes."""

from __future__ import annotations

import re
from typing import Literal

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.coordination import parse_complex_formula
from app.modules.chemistry.extractors.parsing import (
    _N,
    _element,
    _floats,
    _search,
)
from app.modules.chemistry.request import CHEMICAL_FORMULA
from app.modules.chemistry.species_facts import (
    is_formula,
)


def _extract_structure(text: str) -> ChemistryIntent | None:
    # "the oxidation state of S in H2SO4" answers with every element's state, S's among them.
    oxidation = re.search(
        rf"oxidation (?:state|number)s?(?: of (?:each element|[A-Za-z]+))? in "
        rf"({CHEMICAL_FORMULA})(?![A-Za-z0-9])",
        text,
        re.IGNORECASE,
    )
    if oxidation:
        return ChemistryIntent(
            kind="structure", chemistry_op="oxidation_state", formula=oxidation.group(1)
        )
    vsepr = re.search(
        rf"\b(?:VSEPR(?: shape)?|(?:molecular |electron )?(?:shape|geometry)) of "
        rf"({CHEMICAL_FORMULA})(?![A-Za-z0-9])",
        text,
        re.IGNORECASE,
    )
    if vsepr and is_formula(vsepr.group(1)):
        return ChemistryIntent(kind="structure", chemistry_op="vsepr", formula=vsepr.group(1))
    if re.search(r"\bformal charge\b", text, re.IGNORECASE):
        valence = _search(rf"\bvalence\s*=\s*({_N})", text)
        nonbonding = _search(rf"\bnonbonding\s*=\s*({_N})", text)
        bonding = _search(rf"\bbonding\s*=\s*({_N})", text)
        params = _floats(valence=valence, nonbonding=nonbonding, bonding=bonding)
        if params is not None:
            return ChemistryIntent(kind="structure", chemistry_op="formal_charge", params=params)
    return None


def _extract_coordination(text: str) -> ChemistryIntent | None:
    complex_match = re.search(r"coordination complex\s+(\S+)", text, re.IGNORECASE)
    if complex_match:
        return ChemistryIntent(
            kind="inorganic",
            chemistry_op="coordination_complex",
            formula=complex_match.group(1).rstrip("?.,;"),
        )
    return None


def _extract_crystal_field(text: str) -> ChemistryIntent | None:
    if not re.search(r"\b(?:crystal field|magnetic moment)\b", text, re.IGNORECASE):
        return None
    without_geometry = re.sub(
        r"\b(?:square[- ]planar|tetrahedral|octahedral)\b",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    formula = re.search(
        r"(?:crystal field|magnetic moment) of\s+(\S+)",
        without_geometry,
        re.IGNORECASE,
    )
    if formula is None:
        return None
    # "magnetic moment of 0.200 A m^2" is a magnitude. A crystal-field moment names a complex.
    token = formula.group(1).rstrip("?.!,")
    if parse_complex_formula(token) is None:
        return None
    stated = _stated_geometry(text)
    if stated == "ambiguous":
        return None
    return ChemistryIntent(
        kind="inorganic",
        chemistry_op="crystal_field",
        formula=token,
        geometry=None if stated is None else stated,
    )


def _stated_geometry(
    text: str,
) -> Literal["octahedral", "tetrahedral", "square_planar", "ambiguous"] | None:
    square = re.search(r"\bsquare[- ]planar\b", text, re.IGNORECASE) is not None
    tetrahedral = re.search(r"\btetrahedral\b", text, re.IGNORECASE) is not None
    octahedral = re.search(r"\boctahedral\b", text, re.IGNORECASE) is not None
    chosen = sum((square, tetrahedral, octahedral))
    if chosen > 1:
        return "ambiguous"
    if square:
        return "square_planar"
    if tetrahedral:
        return "tetrahedral"
    if octahedral:
        return "octahedral"
    return None


_CONFIGURATION = re.compile(
    r"\belectron(?:ic)?\s+configuration\s+(?:of|for)\s+(?:an?\s+|the\s+)?(?:neutral\s+)?"
    r"(?:element\s+|atom\s+of\s+)?(?P<element>[A-Za-z]+)(?:\s+atom)?(?![A-Za-z0-9+\-^])",
    re.IGNORECASE,
)


def _extract_electron_configuration(text: str) -> ChemistryIntent | None:
    """ "What is the electron configuration of Fe?" from the element table (neutral atom)."""
    match = _CONFIGURATION.search(text)
    if match is None:
        return None
    element = _element(match.group("element"))
    if element is None:
        return None
    return ChemistryIntent(kind="structure", chemistry_op="electron_configuration", target=element)
