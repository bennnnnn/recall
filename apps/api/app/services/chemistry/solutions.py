"""Acid-base, gas-law, and solution calculations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class pHResult:
    """Result of a pH / acid-base calculation."""

    answer: str
    ph: float | None = None
    poh: float | None = None
    error: str | None = None


def ph_from_concentration(h_concentration: float) -> pHResult:
    """Calculate pH from [H+] concentration (mol/L).

    pH = -log10([H+])
    """
    import math

    if h_concentration <= 0:
        return pHResult(answer="", error="concentration must be positive")
    ph = -math.log10(h_concentration)
    poh = 14.0 - ph
    return pHResult(
        answer=f"pH = -log10({h_concentration}) = {ph:.2f}",
        ph=round(ph, 2),
        poh=round(poh, 2),
    )


def ph_from_poh(poh: float) -> pHResult:
    """Calculate pH from pOH: pH = 14 - pOH."""
    ph = 14.0 - poh
    return pHResult(
        answer=f"pH = 14 - {poh} = {ph:.2f}",
        ph=round(ph, 2),
        poh=round(poh, 2),
    )


def h_from_ph(ph: float) -> pHResult:
    """Calculate [H+] from pH: [H+] = 10^(-pH)."""

    h_conc = 10 ** (-ph)
    return pHResult(
        answer=f"[H+] = 10^(-{ph}) = {h_conc:.2e} mol/L",
        ph=round(ph, 2),
    )


@dataclass(frozen=True)
class GasLawResult:
    """Result of a gas law calculation."""

    answer: str
    value: float | None = None
    error: str | None = None


def ideal_gas_law(
    pressure: float | None = None,
    volume: float | None = None,
    moles: float | None = None,
    temperature: float | None = None,
) -> GasLawResult:
    """Solve PV=nRT for the missing variable.

    Exactly one of P, V, n, T must be None (the unknown).
    Temperature in Kelvin, pressure in atm, volume in L.
    R = 0.0821 L·atm/(mol·K).
    """
    R = 0.0821
    given = {"P": pressure, "V": volume, "n": moles, "T": temperature}
    none_count = sum(1 for v in given.values() if v is None)
    if none_count != 1:
        return GasLawResult(answer="", error="exactly one variable must be unknown (None)")

    if pressure is None:
        # P = nRT / V
        if volume is None or moles is None or temperature is None:
            return GasLawResult(answer="", error="missing required values")
        p = (moles * R * temperature) / volume
        return GasLawResult(
            answer=f"P = nRT/V = ({moles} * {R} * {temperature}) / {volume} = {p:.4f} atm",
            value=round(p, 4),
        )
    if volume is None:
        # V = nRT / P
        if pressure is None or moles is None or temperature is None:
            return GasLawResult(answer="", error="missing required values")
        v = (moles * R * temperature) / pressure
        return GasLawResult(
            answer=f"V = nRT/P = ({moles} * {R} * {temperature}) / {pressure} = {v:.4f} L",
            value=round(v, 4),
        )
    if moles is None:
        # n = PV / RT
        if pressure is None or volume is None or temperature is None:
            return GasLawResult(answer="", error="missing required values")
        n = (pressure * volume) / (R * temperature)
        return GasLawResult(
            answer=f"n = PV/RT = ({pressure} * {volume}) / ({R} * {temperature}) = {n:.4f} mol",
            value=round(n, 4),
        )
    # temperature is None → T = PV / nR
    if pressure is None or volume is None or moles is None:
        return GasLawResult(answer="", error="missing required values")
    t = (pressure * volume) / (moles * R)
    return GasLawResult(
        answer=f"T = PV/nR = ({pressure} * {volume}) / ({moles} * {R}) = {t:.4f} K",
        value=round(t, 4),
    )


@dataclass(frozen=True)
class SolutionResult:
    """Result of a solution chemistry calculation."""

    answer: str
    value: float | None = None
    error: str | None = None


def molarity(moles: float, volume_liters: float) -> SolutionResult:
    """Calculate molarity: M = moles / volume (L)."""
    if volume_liters <= 0:
        return SolutionResult(answer="", error="volume must be positive")
    m = moles / volume_liters
    return SolutionResult(
        answer=f"M = {moles} / {volume_liters} = {m:.4f} mol/L",
        value=round(m, 4),
    )


def dilution(
    m1: float,
    v1: float,
    v2: float | None = None,
    m2: float | None = None,
) -> SolutionResult:
    """Solve M1V1 = M2V2 for the missing variable.

    Exactly one of V2 or M2 must be None.
    """
    if v2 is None and m2 is None:
        return SolutionResult(answer="", error="one of V2 or M2 must be unknown")
    if v2 is not None and m2 is not None:
        return SolutionResult(answer="", error="only one of V2 or M2 can be unknown")
    if v2 is None:
        # V2 = M1V1 / M2
        if m2 is None or m2 == 0:
            return SolutionResult(answer="", error="M2 must be non-zero")
        v = (m1 * v1) / m2
        return SolutionResult(
            answer=f"V2 = M1V1/M2 = ({m1} * {v1}) / {m2} = {v:.4f} L",
            value=round(v, 4),
        )
    # m2 is None → M2 = M1V1 / V2
    if v2 == 0:
        return SolutionResult(answer="", error="V2 must be non-zero")
    m = (m1 * v1) / v2
    return SolutionResult(
        answer=f"M2 = M1V1/V2 = ({m1} * {v1}) / {v2} = {m:.4f} mol/L",
        value=round(m, 4),
    )
