"""Verified lift operations: what a lift's floor or scale pushes with as it accelerates.

The laws a lift's reading is not set it aside: the weight's by ``IN_A_LIFT_MARKER``, m = F/a
by the other forces it shares the push with (``net_force``).
"""

from __future__ import annotations

from app.modules.physics.net_force import LIFT
from app.services.law_binding.spec import Binding, FormulaSpec, FormulaVariant, formula, var

# The direction a lift accelerates in, said outright. Unsaid ("accelerates at 2 m/s²",
# "moving up, it slows at 2 m/s²"), the law has no form: up was its default, and
# "accelerating at 2 m/s² downward" read 708.6 N for 468.6 N.
_UPWARD = (
    "accelerating upward",
    "accelerates upward",
    "accelerated upward",
    "accelerating up at",
    "accelerates up at",
    "upward acceleration",
    "upwards acceleration",
    "upward with an acceleration",
    "upwards with an acceleration",
    "up with an acceleration",
)
_DOWNWARD = (
    "accelerating downward",
    "accelerates downward",
    "accelerated downward",
    "accelerating down at",
    "accelerates down at",
    "downward acceleration",
    "downwards acceleration",
    "downward with an acceleration",
    "downwards with an acceleration",
    "down with an acceleration",
)

SPECS: tuple[FormulaSpec, ...] = (
    formula(
        "lift_normal_force",
        "force",
        "Newton's second law in a lift",
        "N",
        base_latex="N = m(g + a)",
        expression="m*(g + accel)",
        variants=(
            FormulaVariant(
                latex="N = m(g - a)",
                present=frozenset({"downward"}),
                expression="m*(g - accel)",
            ),
        ),
        variables=(
            var("g", "g", "meter / second ** 2", fallback="gravity"),
            var("m", "m", "kilogram"),
            var("accel", "a", "meter / second ** 2", words=("accelerat",)),
            var(
                "upward",
                "",
                dimensionless=True,
                visible=False,
                implied=tuple((phrase, 1.0) for phrase in _UPWARD),
            ),
            var(
                "downward",
                "",
                dimensionless=True,
                visible=False,
                implied=tuple((phrase, 1.0) for phrase in _DOWNWARD),
            ),
        ),
        binding=Binding(
            asks=(
                "normal force",
                "apparent weight",
                "scale reading",
                "reading on the scale",
                "scales read",
                "scale read",
                "scales show",
                "scale show",
            ),
            result=("newton",),
            inputs=(
                frozenset({"g", "m", "accel", "upward"}),
                frozenset({"g", "m", "accel", "downward"}),
            ),
            cues=LIFT,
            nonnegative=True,
        ),
    ),
)
