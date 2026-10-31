"""Verified wave optics: interference, diffraction, polarization and Bragg reflection."""

from __future__ import annotations

from app.services.law_binding.spec import Binding, FormulaSpec, FormulaVariant, formula, var

SPECS: tuple[FormulaSpec, ...] = (
    formula(
        "double_slit_fringe_spacing",
        "optics",
        "Double-slit interference",
        "\\Delta y",
        base_latex="\\Delta y = \\frac{\\lambda L}{d}",
        assumptions=("the screen is far from the slits compared with their separation",),
        # Three lengths, each named: the slits' separation, the screen's
        # distance, and the light's wavelength.
        variables=(
            var(
                "L",
                "L",
                "meter",
                words=("screen", "to the screen", "away"),
                needs_words=True,
            ),
            var(
                "d",
                "d",
                "meter",
                words=("slits", "slit separation", "apart", "separated by"),
                needs_words=True,
            ),
            var("wavelength", r"\lambda", "meter", words=("wavelength", "light"), needs_words=True),
        ),
        binding=Binding(
            asks=(
                "fringe spacing",
                "fringe separation",
                "fringe width",
                "spacing between the fringes",
                "spacing between fringes",
                "distance between the fringes",
                "distance between adjacent",
                "separation of the fringes",
                "spacing of the fringes",
            ),
            result=("meter",),
            inputs=(frozenset({"L", "d", "wavelength"}),),
            cues=("double slit", "double-slit", "two slits", "young"),
            nonnegative=True,
        ),
    ),
    formula(
        "diffraction_central_width",
        "optics",
        "Single-slit diffraction",
        "w",
        base_latex="w = \\frac{2\\lambda L}{a}",
        variables=(
            var("L", "L", "meter"),
            var("d", "a", "meter"),
            var("wavelength", r"\lambda", "meter"),
        ),
    ),
    formula(
        "malus_intensity",
        "optics",
        "Malus's law",
        "I",
        base_latex="I = I_0\\cos^2\\theta",
        variables=(
            var("angle", r"\theta", dimensionless=True),
            var("intensity0", "I_0", "watt / meter ** 2"),
        ),
    ),
    formula(
        "brewster_angle",
        "optics",
        "Brewster's law",
        "\\theta_B",
        base_latex="\\tan\\theta_B = \\frac{n_2}{n_1}",
        variables=(
            var("n1", "n_1", dimensionless=True),
            var("n2", "n_2", dimensionless=True),
        ),
    ),
    formula(
        "grating_angle",
        "optics",
        "Diffraction-grating equation",
        r"\theta",
        base_latex=r"d\sin\theta = n\lambda",
        expression="asin(order*wavelength*line_density)*180/pi",
        variants=(
            FormulaVariant(
                present=frozenset({"d"}),
                expression="asin(order*wavelength/d)*180/pi",
            ),
        ),
        variables=(
            var("d", "d", "meter", words=("spacing", "separation", "lines are")),
            var("line_density", "N", "1 / meter"),
            var(
                "order",
                "n",
                dimensionless=True,
                words=("order",),
                implied=(
                    ("first order", 1.0),
                    ("first-order", 1.0),
                    ("second order", 2.0),
                    ("second-order", 2.0),
                    ("third order", 3.0),
                    ("third-order", 3.0),
                ),
            ),
            var("wavelength", r"\lambda", "meter", words=("wavelength", "light")),
        ),
        binding=Binding(
            asks=("angle",),
            result=("degree",),
            inputs=(
                frozenset({"line_density", "order", "wavelength"}),
                frozenset({"d", "order", "wavelength"}),
            ),
            cues=("grating",),
            nonnegative=True,
        ),
    ),
    formula(
        "bragg_wavelength",
        "optics",
        "Bragg's law",
        r"\lambda",
        base_latex=r"n\lambda = 2d\sin\theta",
        expression="2*d*sin(angle_bragg)/order",
        variables=(
            var("angle_bragg", r"\theta", dimensionless=True),
            var("d", "d", "meter", words=("spacing", "separation", "apart", "planes")),
            var(
                "order",
                "n",
                dimensionless=True,
                words=("order",),
                needs_words=True,
                implied=(
                    ("first order", 1.0),
                    ("first-order", 1.0),
                    ("second order", 2.0),
                    ("second-order", 2.0),
                    ("third order", 3.0),
                    ("third-order", 3.0),
                ),
            ),
        ),
        binding=Binding(
            asks=("wavelength",),
            result=("meter",),
            inputs=(frozenset({"angle_bragg", "d", "order"}),),
            cues=("bragg",),
            nonnegative=True,
        ),
    ),
    formula(
        "bragg_spacing",
        "optics",
        "Bragg's law",
        "d",
        base_latex=r"n\lambda = 2d\sin\theta",
        expression="order*wavelength/(2*sin(angle_bragg))",
        variables=(
            var("angle_bragg", r"\theta", dimensionless=True),
            var(
                "order",
                "n",
                dimensionless=True,
                words=("order",),
                needs_words=True,
                implied=(
                    ("first order", 1.0),
                    ("first-order", 1.0),
                    ("second order", 2.0),
                    ("second-order", 2.0),
                    ("third order", 3.0),
                    ("third-order", 3.0),
                ),
            ),
            var("wavelength", r"\lambda", "meter", words=("wavelength",), needs_words=True),
        ),
        binding=Binding(
            asks=("spacing", "separation", "plane spacing", "interplanar spacing"),
            result=("meter",),
            inputs=(frozenset({"angle_bragg", "order", "wavelength"}),),
            cues=("bragg",),
            nonnegative=True,
        ),
    ),
)
