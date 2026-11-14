"""Verified projectile operations."""

from __future__ import annotations

from app.services.law_binding.spec import Binding, FormulaSpec, FormulaVariant, formula, var

# A launch "horizontally" from a height states the angle (0°) without a number,
# and so does anything that rolls, slides or drives off an edge.
_LEVEL_LAUNCH = (
    "horizontally",
    "rolls off",
    "rolled off",
    "rolling off",
    "slides off",
    "slid off",
    "sliding off",
    "runs off",
    "ran off",
    "drives off",
    "drove off",
)
# The binder adds this cue when the question states an angle (``binding.named_laws``): a
# launch at 30° is a projectile's, wherever it starts from.
AT_AN_ANGLE = "at an angle"
# Where a launch height is: said with no height stated ("from the top of a hill"), the
# landing is below the launch by an unknown height, so a ground launch's laws decline.
# A ramp or a hill named this way is a launch site, not a surface it moves along.
_LAUNCH_SITES = (
    *("cliff", "hill", "building", "tower", "roof", "balcony", "bridge", "ledge"),
    *("table", "bench", "top of"),
)
# A length is the launch height only when the words name it so: "kicked toward a wall
# 30 m away" states no height, and read as one it would be launched from 30 m up.
_HEIGHT_WORDS = (
    "high",
    "height",
    "tall",
    "above",
    "cliff",
    "table",
    "bench",
    "roof",
    "building",
    "tower",
    "balcony",
    "ledge",
    "platform",
    "bridge",
    "off a",
    "off the",
    "top of",
    "from",
)
_LAUNCH = (
    var(
        "angle",
        r"\theta",
        dimensionless=True,
        implied=tuple((phrase, 0.0) for phrase in _LEVEL_LAUNCH),
    ),
    var("g", "g", "meter / second ** 2", fallback="gravity"),
    var("h0", "h_0", "meter", words=_HEIGHT_WORDS, needs_words=True, named_by=_LAUNCH_SITES),
    var("v0", "v_0", "meter / second"),
)
_FROM_A_HEIGHT = frozenset({"angle", "g", "h0", "v0"})
# It flies: from above the ground, or launched upward (a missing height is the ground).
# Rolled off "horizontally" with no height stated, it would land where it started. Each
# side is tested on its own sign, never a sum: an angle in radians plus a height in metres
# made a 60° downward throw from a 0.5 m table land nowhere.
_FLIES = ("h0 if h0 > 0 else sin(angle)",)
# Launched and landing on level ground: no height stated.
_FROM_THE_GROUND = frozenset({"angle", "g", "v0"})
# Another situation than a free flight from a launch: a slope's motion, a pull, a swing,
# or a flight toward a wall or a target, whose question is another one.
_NOT_A_FREE_FLIGHT = (
    *("incline", "inclined", "slope"),
    *("rope", "string", "pendulum", "tension"),
    *("wall", "fence"),
    # A flight lands; a body that comes to a stop moved along a surface ("a cart rolls
    # up a 10° ramp at 6 m/s: how far before stopping").
    *("before stopping", "before it stops", "comes to rest", "comes to a stop"),
)
# A speed asked somewhere on the way up or down, not where it lands.
_ON_THE_WAY = (
    "at the top",
    "at its highest",
    "at the highest point",
    "at the peak",
    "at its peak",
    "at maximum height",
    "at its maximum height",
    "at max height",
    "halfway",
    "seconds after",
)


def _horizontal(
    asks: tuple[str, ...],
    result: str,
    inputs: tuple[frozenset[str], ...] = (_FROM_A_HEIGHT, _FROM_THE_GROUND),
) -> Binding:
    return Binding(
        asks=asks,
        result=(result,),
        inputs=inputs,
        cues=(*_LEVEL_LAUNCH, AT_AN_ANGLE),
        excludes=_NOT_A_FREE_FLIGHT,
        nonnegative=True,
        requires=_FLIES,
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
    # Its top above level ground. Above a stated launch height "how high" may be above the
    # ground or above the launch, so a height stated leaves this law to the extractor.
    formula(
        "max_height",
        "projectile",
        "Projectile-motion equation",
        "H_{max}",
        variables=_LAUNCH,
        binding=Binding(
            asks=("maximum height", "max height", "how high", "peak height", "highest point"),
            result=("meter",),
            inputs=(_FROM_THE_GROUND,),
            cues=(AT_AN_ANGLE,),
            excludes=_NOT_A_FREE_FLIGHT,
            nonnegative=True,
            requires=_FLIES,
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
    # The time to the top, which "how long" alone would read as the whole flight: "how
    # long does it take to reach the top" of a kick at 20 m/s and 30° is 1.02 s, not the
    # 2.04 s in the air. It binds wherever the time of flight does, so the more specific
    # ask always has its law.
    formula(
        "projectile_time_to_peak",
        "projectile",
        "Projectile-motion equation",
        "t_{\\text{top}}",
        base_latex=r"t_{\text{top}} = \frac{v_0 \sin\theta}{g}",
        assumptions=("constant g and no air resistance",),
        expression="v0*sin(angle)/g",
        variables=_LAUNCH,
        binding=Binding(
            asks=(
                "reach the top",
                "to the top",
                "reach its maximum height",
                "reach maximum height",
                "reach the highest point",
                "reach its highest point",
                "time to peak",
            ),
            result=("second",),
            inputs=(_FROM_A_HEIGHT, _FROM_THE_GROUND),
            cues=(AT_AN_ANGLE,),
            excludes=_NOT_A_FREE_FLIGHT,
            nonnegative=True,
            requires=("angle",),
        ),
    ),
    formula(
        "impact_speed",
        "projectile",
        "Projectile-motion equation",
        "v_{impact}",
        variables=_LAUNCH,
        # From level ground it lands at its launch speed: only a fall from a height asks.
        # The speed somewhere on the way is another speed ("how fast at the top").
        binding=Binding(
            asks=("impact speed", "speed", "how fast", "velocity"),
            result=("meter / second",),
            inputs=(_FROM_A_HEIGHT,),
            cues=(*_LEVEL_LAUNCH, AT_AN_ANGLE),
            excludes=(*_NOT_A_FREE_FLIGHT, *_ON_THE_WAY),
            nonnegative=True,
            requires=_FLIES,
        ),
    ),
    # The speed it left the edge at, from the height and where it landed:
    # the fall sets the time, √(2h/g), and the range over that time is v₀.
    # A marble off a 90 cm bench that lands 1.2 m out left at 2.80 m/s.
    formula(
        "level_launch_speed",
        "projectile",
        "Projectile-motion equation",
        "v_0",
        base_latex=r"v_0 = R\sqrt{\frac{g}{2h}}",
        assumptions=("launched horizontally; no air resistance",),
        expression="d*sqrt(g/(2*h0))",
        variables=(
            var("g", "g", "meter / second ** 2", fallback="gravity"),
            var(
                "h0",
                "h",
                "meter",
                words=("high", "height", "tall", "cliff", "table", "bench", "roof", "off a"),
                needs_words=True,
            ),
            # Where it lands is its range, R, as the launch-angle law writes it.
            var(
                "d",
                "R",
                "meter",
                words=("lands", "away", "from the", "horizontal", "out"),
                needs_words=True,
            ),
        ),
        binding=Binding(
            asks=(
                "how fast was it rolling",
                "how fast was it moving",
                "how fast was it going",
                "how fast was it travelling",
                "how fast was it traveling",
                "how fast was the",
                "launch speed",
                "initial speed",
                "speed when it left",
                "speed as it left",
                "speed at which it left",
                "speed off the",
                "speed at the edge",
            ),
            result=("meter / second",),
            inputs=(frozenset({"d", "g", "h0"}),),
            cues=_LEVEL_LAUNCH,
            # The speed at the ground is another speed.
            excludes=("hit", "impact", "just before", "when it lands", "strikes"),
            nonnegative=True,
        ),
    ),
    formula(
        "launch_angle",
        "projectile",
        "Projectile-motion equation",
        "\\theta",
        variables=(
            var("d", "R", "meter"),
            var("g", "g", "meter / second ** 2"),
            var("v0", "v_0", "meter / second"),
        ),
    ),
)
