"""Verified torque operations."""

from __future__ import annotations

from app.modules.physics.catalog.spec import FormulaSpec, formula

SPECS: tuple[FormulaSpec, ...] = (
    formula("torque", "torque", "Torque formula", "\\tau", base_latex="\\tau = Fd\\sin(\\theta)"),
    formula(
        "moment_balance", "torque", "Principle of moments", "d_2", base_latex="F_1d_1 = F_2d_2"
    ),
    formula("lever_arm", "torque", "Torque formula", "d", base_latex="\\tau = Fd\\sin(\\theta)"),
    formula("net_torque", "torque", "Net-torque equation", "\\tau_{net}"),
)
