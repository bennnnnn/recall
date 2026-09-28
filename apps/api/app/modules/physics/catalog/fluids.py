"""Verified fluids operations."""

from __future__ import annotations

from app.modules.physics.catalog.spec import FormulaSpec, formula

SPECS: tuple[FormulaSpec, ...] = (
    formula(
        "pressure_from_force", "fluids", "Pressure formula", "P", base_latex="P = \\frac{F}{A}"
    ),
    formula(
        "pressure_at_depth",
        "fluids",
        "Hydrostatic-pressure equation",
        "P",
        assumptions=("gauge pressure, not absolute",),
    ),
    formula("upthrust", "fluids", "Archimedes' principle", "F_b"),
    formula("density", "fluids", "Density formula", "\\rho", base_latex="\\rho = \\frac{m}{V}"),
    formula(
        "continuity_velocity", "fluids", "Continuity equation", "v_2", base_latex="A_1v_1 = A_2v_2"
    ),
    formula("flow_rate", "fluids", "Volume-flow-rate formula", "Q"),
    formula(
        "hydraulic_force",
        "fluids",
        "Pascal's principle",
        "F_2",
        base_latex="\\frac{F_1}{A_1} = \\frac{F_2}{A_2}",
    ),
    formula(
        "bernoulli_pressure",
        "fluids",
        "Bernoulli's equation",
        "P_2",
        base_latex="P_1 + \\frac{1}{2}\\rho v_1^2 = P_2 + \\frac{1}{2}\\rho v_2^2",
        assumptions=("horizontal flow, so the height terms cancel",),
    ),
    formula(
        "poiseuille_flow",
        "fluids",
        "Poiseuille's law",
        "Q",
        base_latex=r"Q = \frac{\pi r^4\Delta P}{8\eta L}",
        assumptions=("steady laminar flow in a straight pipe",),
    ),
    formula(
        "mass_flow_rate",
        "fluids",
        "Mass-flow-rate equation",
        "\\dot{m}",
        base_latex="\\dot{m} = \\rho Av",
    ),
    formula("torricelli_speed", "fluids", "Torricelli's law", "v", base_latex="v = \\sqrt{2gh}"),
    formula("stokes_drag", "fluids", "Stokes' drag law", "F_d", base_latex="F_d = 6\\pi\\eta rv"),
    formula(
        "reynolds_number",
        "fluids",
        "Reynolds-number equation",
        "Re",
        base_latex="Re = \\frac{\\rho vL}{\\eta}",
    ),
    formula(
        "surface_tension",
        "fluids",
        "Surface-tension definition",
        "\\gamma",
        base_latex="\\gamma = \\frac{F}{L}",
    ),
    formula(
        "laplace_pressure",
        "fluids",
        "Young-Laplace equation",
        "\\Delta P",
        base_latex="\\Delta P = \\frac{k\\gamma}{r}",
    ),
)
