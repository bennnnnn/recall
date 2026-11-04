"""Verified motion on one vertical line under gravity: a throw straight up, a fall."""

from __future__ import annotations

from app.modules.physics.catalog.suvat import TWO_BODIES
from app.services.law_binding.spec import Binding, FormulaSpec, FormulaVariant, formula, var

# Motion on one vertical line under gravity alone: thrown straight up, or falling. A
# speed up a ramp, a car that speeds up or a launch at an angle is another law's.
_VERTICAL_LAUNCH = (
    "thrown up",
    "throws up",
    "tossed up",
    "launched up",
    "shot up",
    "fired up",
    "kicked up",
    "straight up",
    "upward",
    "upwards",
    "vertically",
    "into the air",
    "dropped",
    "falls",
    "falling",
)
# A drag law stated is the drag law's fall (``extractors/drag.py``); "ignore air
# resistance" says the opposite, so only a stated law of drag rules free fall out.
_STATED_DRAG = (
    "-kv",
    "kv^2",
    "kv²",
    "linear drag",
    "quadratic drag",
    "drag proportional",
    "drag force",
)
_NOT_VERTICAL = (
    "horizontal",
    "horizontally",
    "angle",
    "incline",
    "slope",
    "ramp",
    *_STATED_DRAG,
    *TWO_BODIES,
)
_FALL_G = var("g", "g", "meter / second ** 2", fallback="gravity")
_FALL_V0 = var("v0", "v_0", "meter / second")
_FALL_H0 = var("h0", "h_0", "meter")
# A throw from the hand: its top and the time to it need no height. Above a stated
# launch height, "how high" may be above the ground or above the launch point; the
# fall's extractor reads which, so those laws bind from the launch alone.
_THROWN = frozenset({"g", "v0"})
_THROWN_FROM = frozenset({"g", "v0", "h0"})

SPECS: tuple[FormulaSpec, ...] = (
    formula(
        "position",
        "kinematics",
        "Constant-acceleration equation",
        "h",
        variables=(
            var("g", "g", "meter / second ** 2"),
            var("h0", "h_0", "meter"),
            var("t", "t", "second"),
            var("v0", "v_0", "meter / second"),
        ),
    ),
    formula(
        "velocity",
        "kinematics",
        "Constant-acceleration equation",
        "v",
        variables=(
            var("g", "g", "meter / second ** 2"),
            var("h0", "h_0", "meter"),
            var("t", "t", "second"),
            var("v0", "v_0", "meter / second"),
        ),
    ),
    formula(
        "time_to_ground",
        "kinematics",
        "Constant-acceleration equation",
        "t",
        variables=(_FALL_G, _FALL_H0, _FALL_V0),
        binding=Binding(
            asks=(
                "time of flight",
                "how long",
                "total time",
                "time in the air",
                "comes back",
                "come back",
                "hit the ground",
                "hits the ground",
                "reach the ground",
                "time to land",
                "time to fall",
            ),
            result=("second",),
            inputs=(_THROWN, _THROWN_FROM, frozenset({"g", "h0"})),
            cues=_VERTICAL_LAUNCH,
            excludes=_NOT_VERTICAL,
        ),
    ),
    formula(
        "speed",
        "kinematics",
        "Constant-acceleration equation",
        "v",
        variants=(FormulaVariant(absent=frozenset({"t"}), result_symbol="v_{impact}"),),
        variables=(
            var("g", "g", "meter / second ** 2"),
            var("h0", "h_0", "meter"),
            var("t", "t", "second"),
            var("v0", "v_0", "meter / second"),
        ),
    ),
    formula(
        "acceleration",
        "kinematics",
        "Constant-acceleration equation",
        "a",
        variables=(
            var("g", "g", "meter / second ** 2"),
            var("h0", "h_0", "meter"),
            var("v0", "v_0", "meter / second"),
        ),
    ),
    formula(
        "time_to_peak",
        "kinematics",
        "Constant-acceleration equation",
        "t_{\\text{top}}",
        base_latex=r"t_{\text{top}} = \frac{v_0}{g}",
        variables=(_FALL_G, _FALL_H0, _FALL_V0),
        binding=Binding(
            asks=(
                "reach the top",
                "to the top",
                "reach its maximum height",
                "reach maximum height",
                "maximum height",
                "max height",
                "highest point",
                "time to peak",
            ),
            result=("second",),
            inputs=(_THROWN,),
            cues=_VERTICAL_LAUNCH,
            excludes=_NOT_VERTICAL,
        ),
    ),
    formula(
        "vertical_max_height",
        "kinematics",
        "Constant-acceleration equation",
        "h_{\\max}",
        base_latex=r"h_{\max} = h_0 + \frac{v_0^2}{2g}",
        variables=(_FALL_G, _FALL_H0, _FALL_V0),
        binding=Binding(
            asks=(
                "maximum height",
                "max height",
                "how high",
                "highest point",
                "greatest height",
                "peak height",
            ),
            result=("meter",),
            inputs=(_THROWN,),
            cues=_VERTICAL_LAUNCH,
            excludes=_NOT_VERTICAL,
        ),
    ),
)
