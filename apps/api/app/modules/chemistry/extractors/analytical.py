"""Analytical chemistry: calibration, gravimetric analysis, standard addition, statistics."""

from __future__ import annotations

import re

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.extractors.parsing import (
    _N,
    _floats,
    _search,
)


def _extract_analytical(text: str) -> ChemistryIntent | None:
    if re.search(r"\bcalibration curve\b", text, re.IGNORECASE):
        slope = _search(rf"\bslope\s*=\s*({_N})", text)
        intercept = _search(rf"\bintercept\s*=\s*({_N})", text)
        signal = _search(rf"\bsignal\s*=\s*({_N})", text)
        params = _floats(slope=slope, intercept=intercept, signal=signal)
        if params is not None:
            return ChemistryIntent(kind="analytical", chemistry_op="calibration", params=params)
    if re.search(r"\bGravimetric\b", text, re.IGNORECASE):
        mass = _search(rf"precipitate mass\s*=\s*({_N})", text)
        factor = _search(rf"\bfactor\s*=\s*({_N})", text)
        if mass is not None and factor is not None:
            return ChemistryIntent(
                kind="analytical",
                chemistry_op="gravimetric",
                params={"precipitate_mass": mass, "factor": factor},
            )
    if re.search(r"\bStandard addition\b", text, re.IGNORECASE):
        params = _floats(
            sample_signal=_search(rf"sample signal\s*=\s*({_N})", text),
            spiked_signal=_search(rf"spiked signal\s*=\s*({_N})", text),
            standard_concentration=_search(rf"standard concentration\s*=\s*({_N})", text),
            standard_volume=_search(rf"standard volume\s*=\s*({_N})", text),
            sample_volume=_search(rf"sample volume\s*=\s*({_N})", text),
        )
        if params is not None:
            return ChemistryIntent(
                kind="analytical", chemistry_op="standard_addition", params=params
            )
    return None


def _extract_statistics(text: str) -> ChemistryIntent | None:
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
