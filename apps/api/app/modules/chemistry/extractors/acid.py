"""Acid, base, titration, and buffer-addition extractors."""

from __future__ import annotations

import re

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.extractors.parsing import (
    _N,
    _floats,
    _molar_formula,
    _search,
)


def _extract_acid(text: str) -> ChemistryIntent | None:
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


def _extract_titration(text: str) -> ChemistryIntent | None:
    if not re.search(r"\btitration\b", text, re.IGNORECASE):
        return None
    ma = _search(rf"\bMa\s*=\s*({_N})", text)
    va = _search(rf"\bVa\s*=\s*({_N})\s*L", text)
    mb = _search(rf"\bMb\s*=\s*({_N})", text)
    vb = _search(rf"\bVb\s*=\s*({_N})\s*L", text)
    if ma is None or va is None or mb is None:
        return None
    params = {"ma": ma, "va_l": va, "mb": mb}
    if vb is not None:
        params["vb_l"] = vb
    ka = _search(rf"\bKa\s*=\s*({_N})", text, flags=0)
    if ka is not None or re.search(r"\bweak\b", text, re.IGNORECASE):
        if ka is None:
            return None
        params["ka"] = ka
        return ChemistryIntent(kind="acid_base", chemistry_op="titration_weak", params=params)
    return ChemistryIntent(kind="acid_base", chemistry_op="titration_strong", params=params)


def _extract_buffer_addition(text: str) -> ChemistryIntent | None:
    if not re.search(r"\bbuffer after adding\b", text, re.IGNORECASE):
        return None
    pka = _search(rf"\bpKa\s*=\s*({_N})", text)
    ha = _search(rf"\bHA\s*=\s*({_N})\s*mol", text)
    base = _search(rf"\bA-\s*=\s*({_N})\s*mol", text, flags=0)
    added = _search(rf"\badded\s*=\s*({_N})\s*mol", text)
    params = _floats(pka=pka, ha_moles=ha, a_moles=base, added_moles=added)
    if params is None:
        return None
    target = "base" if re.search(r"\bbase\b", text, re.IGNORECASE) else "acid"
    return ChemistryIntent(
        kind="acid_base",
        chemistry_op="buffer_addition",
        target=target,
        params=params,
    )
