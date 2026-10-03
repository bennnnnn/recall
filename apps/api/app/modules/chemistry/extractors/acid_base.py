"""pH, pOH and acid strength: a solution's acidity from its concentration or its constant."""

from __future__ import annotations

import re

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.extractors.parsing import (
    _N,
    _search,
)
from app.modules.chemistry.request import CHEMICAL_FORMULA


def _extract_ph(text: str) -> ChemistryIntent | None:
    h = _search(rf"\[H\+?\]\s*=\s*({_N})", text, flags=0)
    if h is not None and re.search(r"\bpH\b", text):
        return ChemistryIntent(kind="acid_base", chemistry_op="ph_from_h", params={"h": h})
    oh = _search(rf"\[OH-?\]\s*=\s*({_N})", text, flags=0)
    if oh is not None and re.search(r"\bpOH\b", text):
        return ChemistryIntent(kind="acid_base", chemistry_op="poh_from_oh", params={"oh": oh})
    poh = _search(rf"\bpOH\s*=\s*({_N})", text)
    if poh is not None and re.search(r"\bpH\b", text):
        return ChemistryIntent(kind="acid_base", chemistry_op="ph_from_poh", params={"poh": poh})
    ph = _search(rf"\bpH\s*=\s*({_N})", text)
    if ph is not None and re.search(r"\[H\+?\]|hydrogen ion", text, re.IGNORECASE):
        return ChemistryIntent(kind="acid_base", chemistry_op="h_from_ph", params={"ph": ph})
    if re.search(r"\b(?:buffer|Henderson)\b", text, re.IGNORECASE):
        pka = _search(rf"\bpK(?:a|ₐ)\s*=\s*({_N})", text)
        base = _search(rf"\[(?:A-|A⁻|base)\]\s*=\s*({_N})", text)
        acid = _search(rf"\[(?:HA|acid)\]\s*=\s*({_N})", text)
        if pka is not None and base is not None and acid is not None:
            return ChemistryIntent(
                kind="acid_base",
                chemistry_op="buffer_ph",
                params={"pka": pka, "base": base, "acid": acid},
            )
    return None


def _extract_acid_solution(text: str) -> ChemistryIntent | None:
    if re.search(r"\bweak acid\b", text, re.IGNORECASE):
        pair = _molar_formula(text)
        ka = _search(rf"\bKa\s*=\s*({_N})", text, flags=0)
        if pair and ka is not None:
            return ChemistryIntent(
                kind="acid_base",
                chemistry_op="weak_acid_ph",
                formula=pair[1],
                params={"concentration": pair[0], "ka": ka},
            )
    if re.search(r"\bweak base\b", text, re.IGNORECASE):
        pair = _molar_formula(text)
        kb = _search(rf"\bKb\s*=\s*({_N})", text, flags=0)
        if pair and kb is not None:
            return ChemistryIntent(
                kind="acid_base",
                chemistry_op="weak_base_ph",
                formula=pair[1],
                params={"concentration": pair[0], "kb": kb},
            )
    if re.search(r"\bpolyprotic\b", text, re.IGNORECASE):
        pair = _molar_formula(text)
        ka1 = _search(rf"\bKa1\s*=\s*({_N})", text, flags=0)
        if pair and ka1 is not None:
            return ChemistryIntent(
                kind="acid_base",
                chemistry_op="polyprotic_ph",
                formula=pair[1],
                params={"concentration": pair[0], "ka1": ka1},
            )
    if re.search(r"\bstrong acid\b", text, re.IGNORECASE):
        pair = _molar_formula(text)
        if pair:
            return ChemistryIntent(
                kind="acid_base",
                chemistry_op="strong_acid_ph",
                formula=pair[1],
                params={"concentration": pair[0]},
            )
    if re.search(r"\bstrong base\b", text, re.IGNORECASE):
        pair = _molar_formula(text)
        if pair:
            return ChemistryIntent(
                kind="acid_base",
                chemistry_op="strong_base_ph",
                formula=pair[1],
                params={"concentration": pair[0]},
            )
    ka = _search(rf"\bKa\s*=\s*({_N})", text, flags=0)
    kb = _search(rf"\bKb\s*=\s*({_N})", text, flags=0)
    if ka is not None and re.search(r"\bpKa\b", text):
        return ChemistryIntent(
            kind="acid_base", chemistry_op="ka_kb", target="pKa", params={"ka": ka}
        )
    if kb is not None and re.search(r"\bpKb\b", text):
        return ChemistryIntent(
            kind="acid_base", chemistry_op="ka_kb", target="pKb", params={"kb": kb}
        )
    if ka is not None and re.search(r"\bKb\b", text, flags=0):
        return ChemistryIntent(
            kind="acid_base", chemistry_op="ka_kb", target="Kb", params={"ka": ka}
        )
    if kb is not None and re.search(r"\bKa\b", text, flags=0):
        return ChemistryIntent(
            kind="acid_base", chemistry_op="ka_kb", target="Ka", params={"kb": kb}
        )
    return None


def _molar_formula(text: str) -> tuple[float, str] | None:
    match = re.search(rf"({_N})\s*M\s+({CHEMICAL_FORMULA})(?![A-Za-z0-9])", text)
    if match is None:
        return None
    return float(match.group(1)), match.group(2)
