"""Verified fluids operations."""

from __future__ import annotations

from app.services.law_binding.spec import FormulaSpec, FormulaVariant, formula, var

SPECS: tuple[FormulaSpec, ...] = (
    formula(
        "pressure_from_force",
        "fluids",
        "Pressure formula",
        "P",
        base_latex="P = \\frac{F}{A}",
        variables=(
            var("F", "F", "newton"),
            var("area", "A", "meter ** 2"),
        ),
    ),
    formula(
        "pressure_at_depth",
        "fluids",
        "Hydrostatic-pressure equation",
        "P",
        assumptions=("gauge pressure, not absolute",),
        variables=(
            var("depth", "h", "meter"),
            var("g", "g", "meter / second ** 2"),
            var("rho", r"\rho", "kilogram / meter ** 3"),
        ),
    ),
    formula(
        "upthrust",
        "fluids",
        "Archimedes' principle",
        "F_b",
        variables=(
            var("g", "g", "meter / second ** 2"),
            var("rho", r"\rho", "kilogram / meter ** 3"),
            var("volume", "V", "meter ** 3"),
        ),
    ),
    formula(
        "density",
        "fluids",
        "Density formula",
        "\\rho",
        base_latex="\\rho = \\frac{m}{V}",
        variables=(
            var("m", "m", "kilogram"),
            var("volume", "V", "meter ** 3"),
        ),
    ),
    formula(
        "continuity_velocity",
        "fluids",
        "Continuity equation",
        "v_2",
        base_latex="A_1v_1 = A_2v_2",
        variables=(
            var("A1", "A_1", "meter ** 2"),
            var("A2", "A_2", "meter ** 2"),
            var("v", "v", "meter / second"),
        ),
    ),
    formula(
        "flow_rate",
        "fluids",
        "Volume-flow-rate formula",
        "Q",
        variables=(
            var("area", "A", "meter ** 2"),
            var("v", "v", "meter / second"),
        ),
    ),
    formula(
        "hydraulic_force",
        "fluids",
        "Pascal's principle",
        "F_2",
        base_latex="\\frac{F_1}{A_1} = \\frac{F_2}{A_2}",
        variables=(
            var("A1", "A_1", "meter ** 2"),
            var("A2", "A_2", "meter ** 2"),
            var("F1", "F_1", "newton"),
        ),
    ),
    formula(
        "bernoulli_pressure",
        "fluids",
        "Bernoulli's equation",
        "P_2",
        base_latex="P_1 + \\frac{1}{2}\\rho v_1^2 = P_2 + \\frac{1}{2}\\rho v_2^2",
        assumptions=("horizontal flow, so the height terms cancel",),
        variants=(
            FormulaVariant(
                present=frozenset({"h1", "h2"}),
                latex=(
                    r"P_1 + \frac{1}{2}\rho v_1^2 + \rho gh_1 = "
                    r"P_2 + \frac{1}{2}\rho v_2^2 + \rho gh_2"
                ),
                assumptions=("steady incompressible flow with no viscosity",),
            ),
        ),
        variables=(
            var("g", "g", "meter / second ** 2"),
            var("h1", "h_1", "meter"),
            var("h2", "h_2", "meter"),
            var("pres1", "P_1", "pascal"),
            var("rho", r"\rho", "kilogram / meter ** 3"),
            var("v1", "v_1", "meter / second"),
            var("v2", "v_2", "meter / second"),
        ),
    ),
    formula(
        "poiseuille_flow",
        "fluids",
        "Poiseuille's law",
        "Q",
        base_latex=r"Q = \frac{\pi r^4\Delta P}{8\eta L}",
        assumptions=("steady laminar flow in a straight pipe",),
        variables=(
            var("L", "L", "meter"),
            var("delta_pressure", r"\Delta P", "pascal"),
            var("r", "r", "meter"),
            var("viscosity", r"\eta", "pascal * second"),
        ),
    ),
    formula(
        "mass_flow_rate",
        "fluids",
        "Mass-flow-rate equation",
        "\\dot{m}",
        base_latex="\\dot{m} = \\rho Av",
        variables=(
            var("area", "A", "meter ** 2"),
            var("rho", r"\rho", "kilogram / meter ** 3"),
            var("v", "v", "meter / second"),
        ),
    ),
    formula(
        "torricelli_speed",
        "fluids",
        "Torricelli's law",
        "v",
        base_latex="v = \\sqrt{2gh}",
        variables=(
            var("depth", "h", "meter"),
            var("g", "g", "meter / second ** 2"),
        ),
    ),
    formula(
        "stokes_drag",
        "fluids",
        "Stokes' drag law",
        "F_d",
        base_latex="F_d = 6\\pi\\eta rv",
        variables=(
            var("r", "r", "meter"),
            var("v", "v", "meter / second"),
            var("viscosity", r"\eta", "pascal * second"),
        ),
    ),
    formula(
        "reynolds_number",
        "fluids",
        "Reynolds-number equation",
        "Re",
        base_latex="Re = \\frac{\\rho vL}{\\eta}",
        variables=(
            var("L", "L", "meter"),
            var("rho", r"\rho", "kilogram / meter ** 3"),
            var("v", "v", "meter / second"),
            var("viscosity", r"\eta", "pascal * second"),
        ),
    ),
    formula(
        "surface_tension",
        "fluids",
        "Surface-tension definition",
        "\\gamma",
        base_latex="\\gamma = \\frac{F}{L}",
        variables=(
            var("F", "F", "newton"),
            var("L", "L", "meter"),
        ),
    ),
    formula(
        "laplace_pressure",
        "fluids",
        "Young-Laplace equation",
        "\\Delta P",
        base_latex=r"\Delta P = \frac{2\gamma}{r}",
        variants=(
            FormulaVariant(
                equals=(("mode_factor", 4.0),),
                latex=r"\Delta P = \frac{4\gamma}{r}",
            ),
        ),
        variables=(
            var("mode_factor", "mode_factor", dimensionless=True, visible=False),
            var("r", "r", "meter"),
            var("surface_tension", r"\gamma", "newton / meter"),
        ),
    ),
    # ``k`` is the spring constant elsewhere, so the drag coefficient is ``drag_k``.
    formula(
        "linear_drag_fall",
        "fluids",
        "Linear drag under constant gravity",
        "v(t)",
        base_latex=r"v(t)=\frac{mg}{k}\left(1-e^{-(k/m)t}\right)",
        assumptions=(
            "Downward is positive",
            "Drag is -kv with k positive",
            "Released from rest unless a downward initial speed is given",
        ),
        variables=(
            var("drag_k", "k", "kilogram / second"),
            var("g", "g", "meter / second ** 2"),
            var("m", "m", "kilogram"),
            var("show_motion", "show_motion", dimensionless=True, visible=False),
            var("t", "t", "second"),
            var("v0", "v_0", "meter / second"),
        ),
    ),
    formula(
        "linear_drag_upward",
        "fluids",
        "Linear drag on an upward throw",
        "v(t)",
        base_latex=r"v(t)=-\frac{mg}{k}+\left(v_0+\frac{mg}{k}\right)e^{-(k/m)t}",
        assumptions=("Upward is positive", "Drag is -kv on the signed velocity"),
        variables=(
            var("drag_k", "k", "kilogram / second"),
            var("g", "g", "meter / second ** 2"),
            var("m", "m", "kilogram"),
            var("t", "t", "second"),
            var("v0", "v_0", "meter / second"),
        ),
    ),
    formula(
        "quadratic_drag_fall",
        "fluids",
        "Quadratic drag under constant gravity",
        "v(t)",
        base_latex=r"v(t)=v_T\tanh\left(\frac{gt}{v_T}\right),\quad v_T=\sqrt{\frac{mg}{b}}",
        assumptions=(
            "Downward is positive",
            "Drag is -bv^2 with b positive",
            "Released from rest",
        ),
        variables=(
            var("drag_b", "b", "kilogram / meter"),
            var("g", "g", "meter / second ** 2"),
            var("m", "m", "kilogram"),
            var("show_motion", "show_motion", dimensionless=True, visible=False),
            var("t", "t", "second"),
        ),
    ),
    formula(
        "stokes_terminal_velocity",
        "fluids",
        "Stokes terminal velocity",
        "v_T",
        base_latex=r"v_T=\frac{2r^{2}(\rho_{s}-\rho_{f})g}{9\eta}",
        assumptions=("Laminar flow around a sphere", "The sphere is denser than the fluid"),
        variables=(
            var("g", "g", "meter / second ** 2"),
            var("r", "r", "meter"),
            var("rho", r"\rho_f", "kilogram / meter ** 3"),
            var("rho_body", r"\rho_s", "kilogram / meter ** 3"),
            var("viscosity", r"\eta", "pascal * second"),
        ),
    ),
)
