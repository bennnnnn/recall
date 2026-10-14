"""Verified kinematics operations."""

from __future__ import annotations

from app.services.law_binding.spec import Binding, FormulaSpec, FormulaVariant, formula, var

# A drop from a height and a sound's trip to a wall and back are not one
# distance covered at one speed: d = vt read "rolls off a 1.2 m high table at
# 3 m/s" as 0.4 s, and an echo heard after 0.6 s as a wall 204 m away.
_NOT_CONSTANT_SPEED = (
    "high",
    "tall",
    "height",
    "fall",
    "falls",
    "falling",
    "dropped",
    "rolls off",
    "thrown",
    "echo",
    "echoes",
    "sonar",
)

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
        variables=(
            var("g", "g", "meter / second ** 2"),
            var("h0", "h_0", "meter"),
            var("v0", "v_0", "meter / second"),
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
        variables=(
            var("g", "g", "meter / second ** 2"),
            var("h0", "h_0", "meter"),
            var("v0", "v_0", "meter / second"),
        ),
    ),
    formula(
        "vertical_max_height",
        "kinematics",
        "Constant-acceleration equation",
        "h_{\\max}",
        base_latex=r"h_{\max} = h_0 + \frac{v_0^2}{2g}",
        variables=(
            var("g", "g", "meter / second ** 2"),
            var("h0", "h_0", "meter"),
            var("v0", "v_0", "meter / second"),
        ),
    ),
    formula(
        "average_speed",
        "kinematics",
        "Average speed formula",
        "v",
        base_latex="v = \\frac{d}{t}",
        variables=(
            var("d", "d", "meter"),
            var("t", "t", "second"),
        ),
    ),
    formula(
        "rate_speed",
        "kinematics",
        "Speed formula",
        "v",
        base_latex="v = \\frac{d}{t}",
        variables=(
            var("d", "d", "meter"),
            var("t", "t", "second"),
        ),
        binding=Binding(
            asks=("average speed", "average velocity", "speed", "how fast"),
            excludes=_NOT_CONSTANT_SPEED,
            result=("meter / second",),
            inputs=(frozenset({"d", "t"}),),
            nonnegative=True,
        ),
    ),
    # Two legs at two speeds: the average is the whole distance over the whole
    # time, never the mean of the speeds. 100 km at 50 km/h then 100 km at
    # 100 km/h is 66.7 km/h over the trip, not 75. The legs pair in the order
    # they are written: the first distance goes with the first speed.
    formula(
        "average_speed_two_legs",
        "kinematics",
        "Average speed",
        r"\bar{v}",
        base_latex=r"\bar{v} = \frac{d_1 + d_2}{t_1 + t_2}",
        variables=(
            var("d1", "d_1", "meter"),
            var("d2", "d_2", "meter"),
            var("v1", "v_1", "meter / second"),
            var("v2", "v_2", "meter / second"),
            # "for the 200 km trip": the total, stated beside the legs.
            var(
                "d_total",
                "d",
                "meter",
                words=("trip", "journey", "total", "whole", "entire", "altogether", "in all"),
                needs_words=True,
            ),
        ),
        binding=Binding(
            asks=("average speed",),
            result=("meter / second",),
            inputs=(
                frozenset({"d1", "d2", "v1", "v2"}),
                frozenset({"d1", "d2", "v1", "v2", "d_total"}),
            ),
            interchangeable=("d1", "d2", "v1", "v2", "d_total"),
            nonnegative=True,
        ),
    ),
    # The same distance at each speed (a round trip, or two halves of the way):
    # the harmonic mean. 60 km/h there and 40 km/h back is 48 km/h, not 50.
    formula(
        "average_speed_equal_distances",
        "kinematics",
        "Average speed",
        r"\bar{v}",
        base_latex=r"\bar{v} = \frac{2 v_1 v_2}{v_1 + v_2}",
        variables=(
            var("v1", "v_1", "meter / second"),
            var("v2", "v_2", "meter / second"),
        ),
        binding=Binding(
            asks=("average speed",),
            result=("meter / second",),
            inputs=(frozenset({"v1", "v2"}),),
            cues=(
                "half the distance",
                "half of the distance",
                "half the way",
                "halfway",
                "returns",
                "return trip",
                "way back",
                "comes back",
                "drives back",
                "round trip",
            ),
            excludes=("half the time", "half of the time", "for equal times"),
            interchangeable=("v1", "v2"),
            nonnegative=True,
        ),
    ),
    # The same time at each speed: the plain mean. 40 km/h for half the time
    # and 60 km/h for the other half is 50 km/h.
    formula(
        "average_speed_equal_times",
        "kinematics",
        "Average speed",
        r"\bar{v}",
        base_latex=r"\bar{v} = \frac{v_1 + v_2}{2}",
        variables=(
            var("v1", "v_1", "meter / second"),
            var("v2", "v_2", "meter / second"),
        ),
        binding=Binding(
            asks=("average speed",),
            result=("meter / second",),
            inputs=(frozenset({"v1", "v2"}),),
            cues=("half the time", "half of the time", "for equal times"),
            interchangeable=("v1", "v2"),
            nonnegative=True,
        ),
    ),
    formula(
        "rate_distance",
        "kinematics",
        "Speed formula",
        "d",
        base_latex="v = \\frac{d}{t}",
        variables=(
            var("t", "t", "second"),
            var("v", "v", "meter / second"),
        ),
        binding=Binding(
            asks=("how far", "distance", "how many metres", "how many meters", "how much distance"),
            excludes=_NOT_CONSTANT_SPEED,
            result=("meter",),
            inputs=(frozenset({"t", "v"}),),
            nonnegative=True,
        ),
    ),
    formula(
        "rate_time",
        "kinematics",
        "Speed formula",
        "t",
        base_latex="v = \\frac{d}{t}",
        variables=(
            var("d", "d", "meter"),
            var("v", "v", "meter / second"),
        ),
        binding=Binding(
            asks=("how long", "time taken", "time"),
            excludes=_NOT_CONSTANT_SPEED,
            result=("second",),
            inputs=(frozenset({"d", "v"}),),
            nonnegative=True,
        ),
    ),
    formula(
        "stopping_distance",
        "kinematics",
        "Stopping distance",
        "d",
        variants=(
            FormulaVariant(
                lines=(
                    r"d_r = v t_r",
                    r"d_b = \frac{v t_b}{2}",
                    r"d = d_r + d_b",
                    r"a = -\frac{v}{t_b}",
                ),
                assumptions=(
                    "Constant speed while reacting",
                    "Constant deceleration while braking",
                    "Final speed is zero",
                ),
            ),
        ),
        variables=(
            var("t_brake", "t_b", "second"),
            var("t_react", "t_r", "second"),
            var("v", "v", "meter / second"),
        ),
    ),
    # How far a dropped body falls in a time: h = ½gt² from rest.
    formula(
        "drop_height",
        "kinematics",
        "Free-fall equation",
        "h",
        base_latex=r"h = \tfrac{1}{2}gt^2",
        assumptions=("released from rest", "no air resistance"),
        expression="g*t**2/2",
        variables=(
            var("g", "g", "meter / second ** 2", fallback="gravity"),
            var("t", "t", "second"),
        ),
        binding=Binding(
            asks=("how high", "how deep", "how far", "height", "depth", "distance"),
            result=("meter",),
            inputs=(frozenset({"g", "t"}),),
            cues=("dropped", "drops", "falls", "free fall", "released", "freely"),
            nonnegative=True,
        ),
    ),
    # t = d/c: light covers any stated distance at c.
    formula(
        "light_travel_time",
        "kinematics",
        "Speed of light",
        "t",
        base_latex=r"t = \frac{d}{c}",
        assumptions=("light in a vacuum (or air)",),
        expression="d/c_light",
        variables=(var("d", "d", "meter"),),
        binding=Binding(
            asks=("how long", "time", "how much time"),
            result=("second",),
            inputs=(frozenset({"d"}),),
            cues=("light", "laser", "radio signal", "radio wave"),
            excludes=("light year", "light-year", "lightning", "sound", "car", "train", "runner"),
            nonnegative=True,
        ),
    ),
)
