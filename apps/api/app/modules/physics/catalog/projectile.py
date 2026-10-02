"""Verified projectile operations."""

from __future__ import annotations

from app.modules.physics.catalog.spec import Binding, FormulaSpec, FormulaVariant, formula, var

# A launch "horizontally" from a height states the angle (0°) without a number.
_LAUNCH = (
    var("angle", r"\theta", dimensionless=True, implied=(("horizontally", 0.0),)),
    var("g", "g", "meter / second ** 2", fallback="gravity"),
    var("h0", "h_0", "meter"),
    var("v0", "v_0", "meter / second"),
)
_FROM_A_HEIGHT = (frozenset({"angle", "g", "h0", "v0"}),)


def _horizontal(asks: tuple[str, ...], result: str) -> Binding:
    return Binding(
        asks=asks,
        result=(result,),
        inputs=_FROM_A_HEIGHT,
        cues=("horizontally",),
        nonnegative=True,
    )


SPECS: tuple[FormulaSpec, ...] = (
    formula(
        "range",
        "projectile",
        "Projectile-motion equation",
        "R",
        assumptions=("constant g, no air resistance, and the same launch and landing height",),
        variants=(FormulaVariant(positive=frozenset({"h0"}), assumptions=()),),
        variables=_LAUNCH,
        binding=_horizontal(("how far", "range", "horizontal distance", "distance"), "meter"),
    ),
    formula(
        "max_height",
        "projectile",
        "Projectile-motion equation",
        "H_{max}",
        variables=(
            var("angle", r"\theta", dimensionless=True),
            var("g", "g", "meter / second ** 2"),
            var("h0", "h_0", "meter"),
            var("v0", "v_0", "meter / second"),
        ),
    ),
    formula(
        "time_of_flight",
        "projectile",
        "Projectile-motion equation",
        "t_{flight}",
        variables=_LAUNCH,
        binding=_horizontal(("time of flight", "how long", "time"), "second"),
    ),
    formula(
        "impact_speed",
        "projectile",
        "Projectile-motion equation",
        "v_{impact}",
        variables=_LAUNCH,
        binding=_horizontal(("impact speed", "speed", "how fast", "velocity"), "meter / second"),
    ),
    formula(
        "launch_angle",
        "projectile",
        "Projectile-motion equation",
        "\\theta",
        variables=(
            var("d", "d", "meter"),
            var("g", "g", "meter / second ** 2"),
            var("v0", "v_0", "meter / second"),
        ),
    ),
)
