# ruff: noqa: RUF001 -- textbook chemistry uses multiplication and minus signs.
"""Strong and weak titration regions."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import replace

from app.models.schemas.chemistry import ChemistryIntent
from app.models.schemas.chemistry.scene import TitrationAnchor, TitrationScene
from app.modules.chemistry.solvers.acid import _ph, _require_positive
from app.modules.chemistry.solvers.common_chem import KW, num, verified, weak_dissociation
from app.modules.chemistry.solvers.types import ChemistryResult
from app.services.solving import SolveServiceError


def _titration_moles(intent: ChemistryIntent) -> tuple[float, float, float, float | None]:
    ma = _require_positive(intent.params.get("ma"), "Ma")
    va = _require_positive(intent.params.get("va_l"), "Va")
    mb = _require_positive(intent.params.get("mb"), "Mb")
    vb = intent.params.get("vb_l")
    if vb is not None and vb < 0:
        raise SolveServiceError("Vb cannot be negative")
    return ma, va, mb, vb


def solve_titration_strong(intent: ChemistryIntent) -> ChemistryResult:
    ma, va, mb, vb = _titration_moles(intent)
    if vb is None:
        volume = ma * va / mb
        shown = f"Vb = {num(volume)} L"
        return _done(
            intent,
            "Verified strong titration",
            (f"Ma = {num(ma)} M", f"Va = {num(va)} L", f"Mb = {num(mb)} M"),
            "Equivalence volume",
            "Strong acid–strong base equivalence",
            "MaVa = MbVb",
            (f"Vb = ({num(ma)})({num(va)}) / {num(mb)}",),
            shown,
            shown,
        )
    acid_moles = ma * va
    base_moles = mb * vb
    total = va + vb
    if abs(acid_moles - base_moles) <= 1e-9 * max(acid_moles, 1.0):
        ph = "7"
        detail = "equivalence: pH = 7 at 25 °C"
    elif acid_moles > base_moles:
        hydrogen = (acid_moles - base_moles) / total
        ph = _ph(hydrogen)
        detail = f"before equivalence: [H+] = {num(hydrogen)}"
    else:
        hydroxide = (base_moles - acid_moles) / total
        ph = num(14 + math.log10(hydroxide))
        detail = f"after equivalence: [OH−] = {num(hydroxide)}"
    return _done(
        intent,
        "Verified strong titration",
        (
            f"Ma = {num(ma)} M",
            f"Va = {num(va)} L",
            f"Mb = {num(mb)} M",
            f"Vb = {num(vb)} L",
        ),
        "pH",
        "Strong acid–strong base titration",
        "n(H+) and n(OH−) compared at the mixture volume",
        (detail,),
        f"pH = {ph}",
        ph,
    )


def solve_titration_weak(intent: ChemistryIntent) -> ChemistryResult:
    if intent.params.get("kb") is not None and intent.params.get("ka") is None:
        return _titration_weak_base(intent)
    ma, va, mb, vb = _titration_moles(intent)
    ka = _require_positive(intent.params.get("ka"), "Ka")
    if vb is None:
        raise SolveServiceError("weak titration needs the added base volume")
    acid_moles = ma * va
    base_moles = mb * vb
    total = va + vb
    pka = -math.log10(ka)
    scale = max(acid_moles, 1.0)
    if abs(base_moles - acid_moles / 2) <= 1e-6 * scale:
        ph = num(pka)
        detail = "half-equivalence: pH = pKa"
        formula = "pH = pKa"
    elif base_moles <= 1e-12:
        amount = weak_dissociation(ka, ma)
        ph = num(-math.log10(amount))
        detail = f"before base is added: [H+] = {num(amount)}"
        formula = "Ka = x² / (C − x)"
    elif base_moles < acid_moles - 1e-9 * scale:
        remaining = acid_moles - base_moles
        ph = num(pka + math.log10(base_moles / remaining))
        detail = f"buffer region: [A−]/[HA] = {num(base_moles)} / {num(remaining)}"
        formula = "pH = pKa + log([A−]/[HA])"
    elif abs(base_moles - acid_moles) <= 1e-6 * scale:
        salt = acid_moles / total
        kb = KW / ka
        hydroxide = weak_dissociation(kb, salt)
        ph = num(14 + math.log10(hydroxide))
        detail = f"equivalence: [A−] = {num(salt)}, Kb = Kw/Ka"
        formula = "Kb = Kw / Ka"
    else:
        hydroxide = (base_moles - acid_moles) / total
        ph = num(14 + math.log10(hydroxide))
        detail = f"after equivalence: [OH−] = {num(hydroxide)}"
        formula = "[OH−] = excess base / total volume"
    return _done(
        intent,
        "Verified weak titration",
        (
            f"Ma = {num(ma)} M",
            f"Va = {num(va)} L",
            f"Mb = {num(mb)} M",
            f"Vb = {num(vb)} L",
            f"Ka = {num(ka)}",
        ),
        "pH",
        "Weak acid–strong base titration",
        formula,
        (detail,),
        f"pH = {ph}",
        ph,
    )


def _titration_weak_base(intent: ChemistryIntent) -> ChemistryResult:
    """Strong acid titrant into a weak base. Ma/Va is the acid, Mb/Vb the base."""
    ma, va, mb, vb = _titration_moles(intent)
    kb = _require_positive(intent.params.get("kb"), "Kb")
    if vb is None:
        raise SolveServiceError("weak-base titration needs the base volume")
    acid_moles = ma * va
    base_moles = mb * vb
    total = va + vb
    pkb = -math.log10(kb)
    scale = max(base_moles, 1.0)
    if abs(acid_moles - base_moles / 2) <= 1e-6 * scale:
        ph = num(14 - pkb)
        detail = "half-equivalence: pOH = pKb"
        formula = "pOH = pKb"
    elif acid_moles <= 1e-12:
        hydroxide = weak_dissociation(kb, mb)
        ph = num(14 + math.log10(hydroxide))
        detail = f"before acid is added: [OH−] = {num(hydroxide)}"
        formula = "Kb = x² / (C − x)"
    elif acid_moles < base_moles - 1e-9 * scale:
        remaining = base_moles - acid_moles
        poh = pkb + math.log10(acid_moles / remaining)
        ph = num(14 - poh)
        detail = f"buffer region: [BH+]/[B] = {num(acid_moles)} / {num(remaining)}"
        formula = "pOH = pKb + log([BH+]/[B])"
    elif abs(acid_moles - base_moles) <= 1e-6 * scale:
        salt = base_moles / total
        hydrogen = weak_dissociation(KW / kb, salt)
        ph = num(-math.log10(hydrogen))
        detail = f"equivalence: [BH+] = {num(salt)}, Ka = Kw/Kb"
        formula = "Ka = Kw / Kb"
    else:
        hydrogen = (acid_moles - base_moles) / total
        ph = num(-math.log10(hydrogen))
        detail = f"after equivalence: [H+] = {num(hydrogen)}"
        formula = "[H+] = excess acid / total volume"
    return _done(
        intent,
        "Verified weak-base titration",
        (
            f"Ma = {num(ma)} M",
            f"Va = {num(va)} L",
            f"Mb = {num(mb)} M",
            f"Vb = {num(vb)} L",
            f"Kb = {num(kb)}",
        ),
        "pH",
        "Weak base–strong acid titration",
        formula,
        (detail,),
        f"pH = {ph}",
        ph,
    )


def _done(
    intent: ChemistryIntent,
    title: str,
    given: tuple[str, ...] | list[str],
    find: str,
    formula_name: str,
    formula: str,
    substitution: tuple[str, ...] | list[str],
    answer: str,
    value: str,
) -> ChemistryResult:
    return _with_scene(
        intent,
        verified(title, given, find, formula_name, formula, substitution, answer, value),
    )


def _with_scene(intent: ChemistryIntent, result: ChemistryResult) -> ChemistryResult:
    region = result.substitution[0] if result.substitution else "solved"
    anchors = [
        anchor
        for anchor in (_start(intent), _half(intent), _equivalence(intent))
        if anchor is not None
    ]
    anchors.append(TitrationAnchor(label="solved", detail=region, value=result.answer_value))
    return replace(
        result,
        scene=TitrationScene(title="Titration", region=region, anchors=anchors),
    )


def _amounts(intent: ChemistryIntent) -> tuple[float, float, float] | None:
    ma = intent.params.get("ma")
    va = intent.params.get("va_l")
    mb = intent.params.get("mb")
    if ma is None or va is None or mb is None or min(ma, va, mb) <= 0:
        return None
    return ma, va, mb


def _start(intent: ChemistryIntent) -> TitrationAnchor | None:
    amounts = _amounts(intent)
    ka = intent.params.get("ka")
    kb = intent.params.get("kb")
    if amounts is None:
        return None
    ma, _, mb = amounts
    if ka is not None and ka > 0:
        ph = _safe_ph(lambda: weak_dissociation(ka, ma))
    elif kb is not None and kb > 0:
        ph = _safe_ph(lambda: weak_dissociation(kb, mb), basic=True)
    else:
        ph = num(-math.log10(ma))
    return TitrationAnchor(label="start", ph=ph, volume="0 L") if ph else None


def _half(intent: ChemistryIntent) -> TitrationAnchor | None:
    amounts = _amounts(intent)
    ka = intent.params.get("ka")
    kb = intent.params.get("kb")
    if amounts is None:
        return None
    ma, va, mb = amounts
    if ka is not None and ka > 0:
        return TitrationAnchor(
            label="half-equivalence",
            ph=num(-math.log10(ka)),
            volume=f"{num(ma * va / (2 * mb))} L",
        )
    base_volume = intent.params.get("vb_l")
    if kb is not None and kb > 0 and base_volume is not None and base_volume > 0:
        return TitrationAnchor(
            label="half-equivalence",
            ph=num(14 + math.log10(kb)),
            volume=f"{num(mb * base_volume / (2 * ma))} L",
        )
    return None


def _equivalence(intent: ChemistryIntent) -> TitrationAnchor | None:
    amounts = _amounts(intent)
    if amounts is None:
        return None
    ma, va, mb = amounts
    ka = intent.params.get("ka")
    kb = intent.params.get("kb")
    if kb is not None and ka is None:
        base_volume = intent.params.get("vb_l")
        if base_volume is None or base_volume <= 0:
            return None
        titrant = mb * base_volume / ma
        salt = (mb * base_volume) / (titrant + base_volume)
        ph = _safe_ph(lambda: weak_dissociation(KW / kb, salt))
    else:
        titrant = ma * va / mb
        if ka is not None and ka > 0:
            salt = (ma * va) / (va + titrant)
            ph = _safe_ph(lambda: weak_dissociation(KW / ka, salt), basic=True)
        else:
            ph = "7"
    if ph is None:
        return None
    return TitrationAnchor(label="equivalence", ph=ph, volume=f"{num(titrant)} L")


def _safe_ph(root: Callable[[], float], *, basic: bool = False) -> str | None:
    try:
        amount = root()
    except SolveServiceError:
        return None
    if amount <= 0:
        return None
    value = 14 + math.log10(amount) if basic else -math.log10(amount)
    return num(value)
