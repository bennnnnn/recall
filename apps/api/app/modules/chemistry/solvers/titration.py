# ruff: noqa: RUF001 -- textbook chemistry uses multiplication and minus signs.
"""Strong and weak titration regions."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import replace

from app.models.schemas.chemistry import ChemistryIntent
from app.models.schemas.chemistry.scene import TitrationAnchor, TitrationScene
from app.modules.chemistry.solvers.acid import ph_text
from app.modules.chemistry.solvers.common_chem import inp, num, verified, weak_dissociation
from app.modules.chemistry.solvers.constants import KW, PKW
from app.modules.chemistry.solvers.params import require
from app.modules.chemistry.solvers.types import ChemistryResult
from app.services.solving import SolveServiceError

# Volumes and moles are typed decimals, so equal amounts differ only by float noise.
_TOLERANCE = 1e-9


def _titration_moles(intent: ChemistryIntent) -> tuple[float, float, float, float | None]:
    ma = require(intent, "ma", positive=True)
    va = require(intent, "va_l", positive=True)
    mb = require(intent, "mb", positive=True)
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
            (f"Ma = {inp(ma)} mol/L", f"Va = {inp(va)} L", f"Mb = {inp(mb)} mol/L"),
            "Equivalence volume",
            "Strong acid–strong base equivalence",
            "MaVa = MbVb",
            (f"Vb = ({inp(ma)})({inp(va)}) / {inp(mb)}",),
            shown,
            shown,
            region="equivalence",
            detail=f"equivalence volume {num(volume)} L",
        )
    acid_moles = ma * va
    base_moles = mb * vb
    total = va + vb
    scale = max(acid_moles, base_moles)
    # Net strong acid per litre (negative past equivalence). Solving [H+]^2 - net[H+] - Kw = 0
    # keeps water's own ions in the answer, so pH 7 at equivalence and no absurd pH 7.7
    # a hair before it.
    net = (acid_moles - base_moles) / total
    hydrogen = (net + math.sqrt(net * net + 4 * KW)) / 2
    lines = [
        f"n(H+) = MaVa = ({inp(ma)})({inp(va)}) = {num(acid_moles)} mol",
        f"n(OH-) = MbVb = ({inp(mb)})({inp(vb)}) = {num(base_moles)} mol",
        f"V = Va + Vb = {inp(va)} + {inp(vb)} = {num(total)} L",
    ]
    if abs(acid_moles - base_moles) <= _TOLERANCE * scale:
        ph = "7"
        region = "equivalence"
        detail = "equivalence: pH = 7 at 25 °C"
        lines.append("n(H+) = n(OH-), only water's own ions remain, so pH = 7 at 25 °C")
    else:
        ph = ph_text(hydrogen)
        if acid_moles > base_moles:
            region = "before equivalence"
            detail = f"before equivalence: [H+] = {num(hydrogen)}"
            lines.append(f"[H+] = (n(H+) − n(OH-)) / V = {num(net)} mol/L")
        else:
            region = "after equivalence"
            detail = f"after equivalence: [OH-] = {num(-net)}"
            lines.append(f"[OH-] = (n(OH-) − n(H+)) / V = {num(-net)} mol/L")
        lines.append(
            f"[H+] = [net + √(net^2 + 4Kw)] / 2 = {num(hydrogen)} mol/L (water's ions included)"
        )
        lines.append(f"pH = −log10({num(hydrogen)}) = {ph}")
    return _done(
        intent,
        "Verified strong titration",
        (
            f"Ma = {inp(ma)} mol/L",
            f"Va = {inp(va)} L",
            f"Mb = {inp(mb)} mol/L",
            f"Vb = {inp(vb)} L",
        ),
        "pH",
        "Strong acid–strong base titration",
        "[H+] = (n(H+) − n(OH-)) / (Va + Vb)",
        lines,
        f"pH = {ph}",
        ph,
        region=region,
        detail=detail,
    )


def solve_titration_weak(intent: ChemistryIntent) -> ChemistryResult:
    if intent.params.get("kb") is not None and intent.params.get("ka") is None:
        return _weak_titration(intent, acid=False)
    return _weak_titration(intent, acid=True)


def _weak_titration(intent: ChemistryIntent, *, acid: bool) -> ChemistryResult:
    """A weak acid titrated by strong base, or (``acid=False``) a weak base by strong acid.

    The two are mirror images: swap H+ with OH-, Ka with Kb, and pH with pOH. The weak-acid
    case reads Ma/Va as the analyte; the weak-base case reads Mb/Vb as the base and Ma/Va as
    the strong acid that is added.
    """
    ma, va, mb, vb = _titration_moles(intent)
    if acid:
        constant = require(intent, "ka", positive=True)
        symbol, weak, conj, titrant = "Ka", "HA", "A-", "OH-"
        analyte_moles, titrant_moles = ma * va, mb * vb
        analyte_name = f"n(HA) = MaVa = ({inp(ma)})({inp(va)})"
        titrant_name = f"n(OH-) = MbVb = ({inp(mb)})({inp(vb)})"
        analyte_conc = ma
    else:
        constant = require(intent, "kb", positive=True)
        symbol, weak, conj, titrant = "Kb", "B", "BH+", "H+"
        analyte_moles, titrant_moles = mb * vb, ma * va
        analyte_name = f"n(B) = MbVb = ({inp(mb)})({inp(vb)})"
        titrant_name = f"n(H+) = MaVa = ({inp(ma)})({inp(va)})"
        analyte_conc = mb
    if vb is None:
        raise SolveServiceError("weak titration needs the added volume")
    total = va + vb
    p_constant = -math.log10(constant)
    p_name = "pKa" if acid else "pKb"
    scale = max(analyte_moles, titrant_moles)

    lines = [
        f"{analyte_name} = {num(analyte_moles)} mol",
        f"{titrant_name} = {num(titrant_moles)} mol",
        f"V = {inp(va)} + {inp(vb)} = {num(total)} L",
    ]
    ph_of_p = (lambda p: p) if acid else (lambda p: PKW - p)  # pH from pKa, or from pKb via pOH
    if abs(titrant_moles - analyte_moles / 2) <= _TOLERANCE * scale:
        ph = num(ph_of_p(p_constant))
        region = "half-equivalence"
        detail = f"half-equivalence: {'pH = pKa' if acid else 'pOH = pKb'}"
        formula = "pH = pKa" if acid else "pOH = pKb"
        lines.append(f"{p_name} = −log10({inp(constant)}) = {num(p_constant)}")
        lines.append(
            f"n({titrant}) = n({weak}) / 2, so {conj} = {weak} and "
            + (
                f"pH = pKa = {ph}"
                if acid
                else f"pOH = pKb = {num(p_constant)}, pH = {PKW} − {num(p_constant)} = {ph}"
            )
        )
    elif titrant_moles == 0:
        amount = weak_dissociation(constant, analyte_conc)
        governing = "H+" if acid else "OH-"
        lines.append(f"{symbol} = x^2 / (C − x), C = {inp(analyte_conc)} mol/L")
        lines.append(f"[{governing}] = x = {num(amount)} mol/L")
        ph = num(-math.log10(amount) if acid else PKW + math.log10(amount))
        region = "start"
        detail = f"before titrant is added: [{governing}] = {num(amount)}"
        formula = f"{symbol} = x^2 / (C − x)"
    elif titrant_moles < analyte_moles - _TOLERANCE * scale:
        remaining = analyte_moles - titrant_moles
        offset = math.log10(titrant_moles / remaining)
        ph_value = p_constant + offset
        ph = num(ph_value if acid else PKW - ph_value)
        region = "buffer region"
        detail = f"buffer: [{conj}]/[{weak}] = {num(titrant_moles)} / {num(remaining)}"
        formula = (
            f"pH = pKa + log10([{conj}]/[{weak}])"
            if acid
            else (f"pOH = pKb + log10([{conj}]/[{weak}])")
        )
        lines.append(f"{p_name} = −log10({inp(constant)}) = {num(p_constant)}")
        lines.append(f"n({conj}) = n({titrant}) = {num(titrant_moles)} mol")
        lines.append(
            f"n({weak}) = {num(analyte_moles)} − {num(titrant_moles)} = {num(remaining)} mol"
        )
        ratio = f"{num(titrant_moles)} / {num(remaining)}"
        if acid:
            lines.append(f"pH = {num(p_constant)} + log10({ratio}) = {ph}")
        else:
            lines.append(f"pOH = {num(p_constant)} + log10({ratio}) = {num(ph_value)}")
            lines.append(f"pH = {PKW} − {num(ph_value)} = {ph}")
    elif abs(titrant_moles - analyte_moles) <= _TOLERANCE * scale:
        salt = analyte_moles / total
        conj_constant = KW / constant
        amount = weak_dissociation(conj_constant, salt)
        produced = "OH-" if acid else "H+"
        lines.append(f"[{conj}] = {num(analyte_moles)} / {num(total)} = {num(salt)} mol/L")
        conj_symbol = "Kb" if acid else "Ka"
        k_conj = num(conj_constant)
        lines.append(f"{conj_symbol} = Kw / {symbol} = ({num(KW)}) / ({inp(constant)}) = {k_conj}")
        lines.append(f"x^2 + ({k_conj})x − ({k_conj})({num(salt)}) = 0")
        lines.append(f"[{produced}] = x = {num(amount)} mol/L")
        ph = num(PKW + math.log10(amount) if acid else -math.log10(amount))
        region = "equivalence"
        detail = f"equivalence: [{conj}] = {num(salt)}, {conj_symbol} = Kw/{symbol}"
        formula = f"{conj_symbol} = Kw / {symbol}"
    else:
        excess = (titrant_moles - analyte_moles) / total
        ph = num(PKW + math.log10(excess) if acid else -math.log10(excess))
        region = "after equivalence"
        ion = "OH-" if acid else "H+"
        detail = f"after equivalence: [{ion}] = {num(excess)}"
        formula = f"[{ion}] = excess {'base' if acid else 'acid'} / total volume"
        lines.append(
            f"[{ion}] = ({num(titrant_moles)} − {num(analyte_moles)}) / {num(total)} = "
            f"{num(excess)} mol/L"
        )
    return _done(
        intent,
        "Verified weak titration" if acid else "Verified weak-base titration",
        (
            f"Ma = {inp(ma)} mol/L",
            f"Va = {inp(va)} L",
            f"Mb = {inp(mb)} mol/L",
            f"Vb = {inp(vb)} L",
            f"{symbol} = {inp(constant)}",
        ),
        "pH",
        "Weak acid–strong base titration" if acid else "Weak base–strong acid titration",
        formula,
        lines,
        f"pH = {ph}",
        ph,
        region=region,
        detail=detail,
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
    *,
    region: str,
    detail: str,
) -> ChemistryResult:
    return _with_scene(
        intent,
        verified(title, given, find, formula_name, formula, substitution, answer, value),
        region=region,
        detail=detail,
    )


def _with_scene(
    intent: ChemistryIntent, result: ChemistryResult, *, region: str, detail: str
) -> ChemistryResult:
    anchors = [
        anchor
        for anchor in (_start(intent), _half(intent), _equivalence(intent))
        if anchor is not None
    ]
    anchors.append(TitrationAnchor(label="solved", detail=detail, value=result.answer_value))
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
        ph = _safeph_text(lambda: weak_dissociation(ka, ma))
    elif kb is not None and kb > 0:
        ph = _safeph_text(lambda: weak_dissociation(kb, mb), basic=True)
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
            ph=num(PKW + math.log10(kb)),
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
        ph = _safeph_text(lambda: weak_dissociation(KW / kb, salt))
    else:
        titrant = ma * va / mb
        if ka is not None and ka > 0:
            salt = (ma * va) / (va + titrant)
            ph = _safeph_text(lambda: weak_dissociation(KW / ka, salt), basic=True)
        else:
            ph = "7"
    if ph is None:
        return None
    return TitrationAnchor(label="equivalence", ph=ph, volume=f"{num(titrant)} L")


def _safeph_text(root: Callable[[], float], *, basic: bool = False) -> str | None:
    try:
        amount = root()
    except SolveServiceError:
        return None
    if amount <= 0:
        return None
    value = PKW + math.log10(amount) if basic else -math.log10(amount)
    return num(value)
