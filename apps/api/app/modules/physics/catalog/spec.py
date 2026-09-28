"""One verified physics operation: the law, its base equation, and its assumptions.

Solvers still own word-problem procedure. This record owns the identity those
procedures used to repeat in the direct-reply dictionaries.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FormulaSpec:
    """Identity of one ``physics_op``."""

    id: str
    kind: str
    law_name: str
    result_symbol: str
    base_latex: str | None = None
    assumptions: tuple[str, ...] = ()


def formula(
    operation: str,
    kind: str,
    law_name: str,
    result_symbol: str,
    base_latex: str | None = None,
    assumptions: tuple[str, ...] = (),
) -> FormulaSpec:
    return FormulaSpec(
        id=operation,
        kind=kind,
        law_name=law_name,
        result_symbol=result_symbol,
        base_latex=base_latex,
        assumptions=assumptions,
    )


def visible_assumptions(spec: FormulaSpec, params: dict[str, float]) -> tuple[str, ...]:
    """Assumptions that are true for this solve, not merely printed on the law.

    A level-ground range states the equal-height condition. An elevated launch
    uses a different equation, so that sentence would be false. Work and power
    state the parallel-force condition only when the angle was left out.
    """
    if spec.id == "range" and params.get("h0", 0.0) > 0:
        return ()
    if spec.id == "work" and "angle" in params:
        return ()
    if spec.id == "power" and ("angle" in params or "F" not in params or "v" not in params):
        return ()
    if spec.id in {"magnetic_force_charge", "magnetic_force_wire", "magnetic_flux"}:
        if "angle" in params:
            return ()
    if spec.id == "doppler_frequency" and "v_obs" in params:
        return ("motion is along the line joining the source and the observer",)
    if spec.id == "bernoulli_pressure" and "h1" in params:
        return ("steady incompressible flow with no viscosity",)
    return spec.assumptions
