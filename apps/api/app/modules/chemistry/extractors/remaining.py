"""Extractors for the closed calculations added after the school table."""

from __future__ import annotations

import re
from typing import Literal

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.extractors.parsing import _N, _floats, _search

_NUMBERS = re.compile(rf"{_N}")
_NUCLIDE = r"(?:[A-Z][a-z]?-\d+|\d+[A-Z][a-z]?)"
_REACTIONS = {
    "hbr addition": "hbr",
    "bromine addition": "bromine",
    "acid hydration": "hydration",
    "hydroxide substitution": "hydroxide",
    "esterification": "esterification",
}


def _extract_remaining(text: str) -> ChemistryIntent | None:
    nuclear = _mass_defect(text)
    if nuclear is not None:
        return nuclear
    crystal = _crystal(text)
    if crystal is not None:
        return crystal
    stats = _statistics(text)
    if stats is not None:
        return stats
    kinetics = _extract_michaelis(text)
    if kinetics is not None:
        return kinetics
    reaction = _reaction(text)
    if reaction is not None:
        return reaction
    spectrum = _spectrum(text)
    if spectrum is not None:
        return spectrum
    return None


def _mass_defect(text: str) -> ChemistryIntent | None:
    if not re.search(r"\b(?:mass defect|binding energy)\b", text, re.IGNORECASE):
        return None
    nuclide = re.search(rf"\b({_NUCLIDE})\b", text)
    mass = _search(rf"\bnuclear mass\s*=\s*({_N})", text)
    if nuclide is None or mass is None:
        return None
    return ChemistryIntent(
        kind="nuclear",
        chemistry_op="mass_defect",
        formula=nuclide.group(1),
        params={"nuclear_mass": mass},
        units={"nuclear_mass": "u"},
    )


def _crystal(text: str) -> ChemistryIntent | None:
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
    stated = _stated_geometry(text)
    if stated == "ambiguous":
        return None
    return ChemistryIntent(
        kind="inorganic",
        chemistry_op="crystal_field",
        formula=formula.group(1).rstrip("?.!,"),
        geometry=None if stated is None else stated,
    )


def _statistics(text: str) -> ChemistryIntent | None:
    if re.search(r"\bstandard error\b", text, re.IGNORECASE):
        samples = _number_list(text)
        if len(samples) >= 2:
            return ChemistryIntent(
                kind="analytical", chemistry_op="standard_error", samples=samples
            )
    if re.search(r"\bstandard deviation\b", text, re.IGNORECASE):
        samples = _number_list(text)
        if len(samples) >= 2:
            return ChemistryIntent(
                kind="analytical", chemistry_op="standard_deviation", samples=samples
            )
    if re.search(r"\bpercent error\b", text, re.IGNORECASE):
        experimental = _search(rf"experimental\s*=\s*({_N})", text)
        accepted = _search(rf"accepted\s*=\s*({_N})", text)
        params = _floats(experimental=experimental, accepted=accepted)
        if params is not None:
            return ChemistryIntent(kind="analytical", chemistry_op="percent_error", params=params)
    if re.search(r"\brelative uncertainty\b", text, re.IGNORECASE):
        params = _floats(
            a=_search(rf"\ba\s*=\s*({_N})", text),
            da=_search(rf"\bda\s*=\s*({_N})", text),
            b=_search(rf"\bb\s*=\s*({_N})", text),
            db=_search(rf"\bdb\s*=\s*({_N})", text),
        )
        if params is not None:
            return ChemistryIntent(
                kind="analytical", chemistry_op="relative_uncertainty", params=params
            )
    if re.search(r"\b(?:retention factor|\bRf\b)\b", text, re.IGNORECASE):
        spot = _search(rf"spot\s*=\s*({_N})", text)
        front = _search(rf"(?:solvent front|front)\s*=\s*({_N})", text)
        if spot is not None and front is not None:
            return ChemistryIntent(
                kind="analytical",
                chemistry_op="chromatography_rf",
                params={"spot": spot, "front": front},
            )
    return None


# Concentrations a Km and an [S] are written in, in mol/L.
_CONCENTRATION = {
    "M": 1.0,
    "mol/L": 1.0,
    "mM": 1e-3,
    "mmol/L": 1e-3,
    "µM": 1e-6,
    "μM": 1e-6,
    "uM": 1e-6,
    "nM": 1e-9,
}
_CONCENTRATION_UNIT = "|".join(re.escape(unit) for unit in sorted(_CONCENTRATION, key=len)[::-1])
# A rate: an amount or a concentration per unit time ("10 μmol/min", "0.5 mM/s").
_RATE_UNIT = r"(?:[µμun]?mol|[mµμun]?M)\s*/\s*(?:s|min|h)\b"


def _michaelis_value(label: str, text: str, unit: str) -> tuple[float, str | None] | None:
    """``Km = 2 mM`` as (2.0, "mM"); a bare ``Km = 2`` as (2.0, None)."""
    match = re.search(rf"{label}\s*=\s*({_N})(?:\s*({unit})(?![A-Za-z]))?", text)
    if match is None:
        return None
    return float(match.group(1)), match.group(2)


def _extract_michaelis(text: str) -> ChemistryIntent | None:
    """Michaelis-Menten, named or recognized by its Vmax and Km, in the units it is written in.

    Km and [S] share one concentration unit (or are both bare); a mixed pair is converted to
    mol/L. The rate keeps the unit of the Vmax or v it is written with.
    """
    named = re.search(r"\bMichaelis[- ]Menten\b", text, re.IGNORECASE)
    if not named and not (re.search(r"\bVmax\b", text) and re.search(r"\bKm\b", text)):
        return None
    read = {
        "v": _michaelis_value(r"\bv(?!\s*=\s*[\d.]+\s*m?L\b)", text, _RATE_UNIT),
        "vmax": _michaelis_value(r"\bVmax", text, _RATE_UNIT),
        "km": _michaelis_value(r"\bKm", text, _CONCENTRATION_UNIT),
        "substrate": _michaelis_value(r"(?:\bS|\[S\])", text, _CONCENTRATION_UNIT),
    }
    present = {key: value for key, value in read.items() if value is not None}
    if len(present) != 3:
        return None
    rate_units = {present[key][1] for key in ("v", "vmax") if key in present}
    concentration_units = {present[key][1] for key in ("km", "substrate") if key in present}
    if len(rate_units) != 1 or (None in concentration_units and len(concentration_units) > 1):
        return None
    params = {key: value for key, (value, _unit) in present.items()}
    concentration = next(iter(concentration_units))
    if len(concentration_units) > 1:
        for key in ("km", "substrate"):
            if key in present:
                params[key] = present[key][0] * _CONCENTRATION[present[key][1] or "M"]
        concentration = "mol/L"
    units = {
        name: unit
        for name, unit in (("rate", next(iter(rate_units))), ("concentration", concentration))
        if unit is not None
    }
    return ChemistryIntent(
        kind="biochemistry", chemistry_op="michaelis_menten", params=params, units=units
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


def _reaction(text: str) -> ChemistryIntent | None:
    lowered = text.lower()
    key = next((name for name in _REACTIONS if name in lowered), None)
    if key is None:
        return None
    # Peroxide/radical HBr is anti-Markovnikov. This path only verifies the ionic rule.
    if _REACTIONS[key] == "hbr" and re.search(r"\b(?:peroxides?|radicals?|roor)\b", lowered):
        return None
    smiles = re.findall(r"\bSMILES\s+(\S+)", text, re.IGNORECASE)
    if not smiles:
        return None
    partner = smiles[1].rstrip("?.!,") if len(smiles) > 1 else None
    return ChemistryIntent(
        kind="organic",
        chemistry_op="named_reaction",
        formula=smiles[0].rstrip("?.!,"),
        target=_REACTIONS[key],
        equation=partner,
    )


def _spectrum(text: str) -> ChemistryIntent | None:
    smiles = re.search(r"\bSMILES\s+(\S+)", text, re.IGNORECASE)
    formula = smiles.group(1).rstrip("?.!,") if smiles else None
    if re.search(r"\bIR ranges\b", text, re.IGNORECASE) and formula:
        return ChemistryIntent(kind="spectroscopy", chemistry_op="ir_ranges", formula=formula)
    if re.search(r"\bNMR ranges\b", text, re.IGNORECASE) and formula:
        return ChemistryIntent(kind="spectroscopy", chemistry_op="nmr_ranges", formula=formula)
    ir_peak = _search(rf"\bIR peak\s*(?:=|at)?\s*({_N})", text)
    if ir_peak is not None:
        return ChemistryIntent(
            kind="spectroscopy", chemistry_op="ir_peak", params={"peak": ir_peak}
        )
    nmr_peak = _search(rf"\bNMR peak\s*(?:=|at)?\s*({_N})", text)
    if nmr_peak is not None:
        return ChemistryIntent(
            kind="spectroscopy", chemistry_op="nmr_peak", params={"peak": nmr_peak}
        )
    if re.search(r"\bNMR splitting\b", text, re.IGNORECASE):
        neighbors = _search(rf"neighbors\s*=\s*({_N})", text)
        if neighbors is not None:
            return ChemistryIntent(
                kind="spectroscopy", chemistry_op="nmr_splitting", params={"neighbors": neighbors}
            )
    if re.search(r"\bmolecular ion\b", text, re.IGNORECASE):
        target = formula
        if target is None:
            plain = re.search(
                rf"molecular ion of\s+({_NUCLIDE}|[A-Z][A-Za-z0-9]+)", text, re.IGNORECASE
            )
            target = plain.group(1) if plain else None
        if target:
            return ChemistryIntent(
                kind="spectroscopy", chemistry_op="molecular_ion", formula=target
            )
    return None


def _number_list(text: str) -> list[float]:
    """The delimited list of plain numbers after ``:`` or ``of``; empty if anything else is in it.

    Counts and charges elsewhere in the sentence ("5 measurements", ``Cu2+``) are not data.
    """
    colon = text.find(":")
    if colon >= 0:
        tail = text[colon + 1 :]
    else:
        marker = re.search(r"\bof\b", text, re.IGNORECASE)
        tail = text[marker.end() :] if marker else text
    tokens = [
        token
        for token in re.split(r"[,;\s]+", tail.strip(" .?!"))
        if token and token.lower() not in {"and", "&"}
    ]
    if not tokens or not all(re.fullmatch(_N, token) for token in tokens):
        return []
    return [float(token) for token in tokens]
