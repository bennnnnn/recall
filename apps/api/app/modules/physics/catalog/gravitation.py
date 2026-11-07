"""Verified gravitation operations."""

from __future__ import annotations

from app.modules.physics.bodies import CENTRAL_BODY_WORDS, ORBITING_BODY_WORDS
from app.services.law_binding.spec import Binding, FormulaSpec, formula, var

# What stands on the planet: the stated mass is this, never the planet's own.
_SMALL_BODY = (
    "mass",
    "object",
    "body",
    "person",
    "man",
    "woman",
    "student",
    "ball",
    "rock",
    "box",
    "block",
    "astronaut",
    "apple",
)

# The mass of the body orbited or stood on: stated with the body's name ("a planet of
# mass 6e24 kg"), or the named body's own. It is never the mass of what orbits it.
_CENTRAL_MASS = var("M", "M", "kilogram", words=CENTRAL_BODY_WORDS, fallback="body_mass")
# The orbiting or standing body's mass, which none of these results depends on: "a 500 kg
# satellite" fills it, so the 500 kg is never read as the central mass.
_ORBITING_MASS = var("m_body", "m", "kilogram", words=ORBITING_BODY_WORDS, needs_words=True)


def _with_body(*inputs: str) -> tuple[frozenset[str], ...]:
    """The law's inputs, with and without the orbiting body's mass stated."""
    return (frozenset(inputs), frozenset({*inputs, "m_body"}))


_GRAVITY_ASKS = (
    "acceleration due to gravity",
    "gravitational acceleration",
    "surface gravity",
    "gravitational field strength",
    "value of g",
    # "what's g at an altitude of 300 km?"
    "g at",
    "g on",
)

SPECS: tuple[FormulaSpec, ...] = (
    formula(
        "orbital_speed_radius",
        "gravitation",
        "Circular-orbit speed",
        "v",
        base_latex=r"v = \sqrt{\frac{GM}{r}}",
        expression="sqrt(G_grav*M/orbit_radius)",
        variables=(
            _CENTRAL_MASS,
            _ORBITING_MASS,
            var(
                "orbit_radius",
                "r",
                "meter",
                words=("radius", "distance", "orbit"),
                needs_words=True,
            ),
        ),
        binding=Binding(
            asks=("orbital speed", "orbital velocity", "speed", "velocity"),
            result=("meter / second",),
            inputs=_with_body("M", "orbit_radius"),
            cues=("orbit", "satellite"),
            # An altitude needs the planet's radius added; a semi-major axis is vis-viva.
            # "400 km above the Earth" is a height too.
            excludes=("altitude", "above", "height", "semi-major", "vis-viva"),
            nonnegative=True,
        ),
    ),
    formula(
        "gravitational_force",
        "gravitation",
        "Newton's law of gravitation",
        "F",
        variables=(
            var("m1", "m_1", "kilogram"),
            var("m2", "m_2", "kilogram"),
            var("r", "r", "meter"),
        ),
    ),
    formula(
        "orbital_velocity",
        "gravitation",
        "Orbital-motion equation",
        "v",
        variables=(
            var("M", "M", "kilogram"),
            var("altitude", "h", "meter"),
            var("radius_body", "R", "meter"),
        ),
    ),
    formula(
        "escape_velocity",
        "gravitation",
        "Escape-velocity equation",
        "v_e",
        variables=(
            var("M", "M", "kilogram"),
            var("radius_body", "R", "meter"),
        ),
    ),
    formula(
        "surface_gravity",
        "gravitation",
        "Surface-gravity equation",
        "g",
        variables=(
            var("M", "M", "kilogram"),
            var("radius_body", "R", "meter"),
        ),
    ),
    formula(
        "gravitational_potential",
        "gravitation",
        "Gravitational potential",
        "V",
        base_latex=r"V = -\frac{GM}{r}",
        assumptions=("zero at infinity",),
        variables=(
            var("M", "M", "kilogram"),
            var("r", "r", "meter"),
        ),
    ),
    formula(
        "gravitational_potential_energy",
        "gravitation",
        "Gravitational potential energy",
        "U",
        base_latex=r"U = -\frac{GMm}{r}",
        assumptions=("zero at infinity",),
        variables=(
            var("M", "M", "kilogram"),
            var("m", "m", "kilogram"),
            var("r", "r", "meter"),
        ),
    ),
    formula(
        "orbital_energy",
        "gravitation",
        "Orbital energy",
        "E",
        base_latex=r"E = -\frac{GMm}{2r}",
        assumptions=("circular orbit",),
        variables=(
            var("M", "M", "kilogram"),
            var("m", "m", "kilogram"),
            var("r", "r", "meter"),
        ),
    ),
    formula(
        "kepler_period",
        "gravitation",
        "Kepler's third law",
        "T",
        base_latex=r"T = 2\pi\sqrt{\frac{r^3}{GM}}",
        assumptions=("circular orbit around a fixed central mass",),
        variables=(_CENTRAL_MASS, _ORBITING_MASS, var("r", "r", "meter")),
        # Kepler's r is measured from the centre: "400 km above Earth" is a
        # height, and reading it as r would answer an orbit inside the planet.
        binding=Binding(
            asks=("orbital period", "period"),
            result=("second",),
            inputs=_with_body("M", "r"),
            cues=("radius", "from the centre", "from the center"),
            excludes=("above", "altitude", "height"),
            nonnegative=True,
        ),
    ),
    # Kepler's third law for the radius: an orbit of a stated period. 24 h
    # round Earth is 4.22e7 m from its centre.
    formula(
        "orbit_radius_from_period",
        "gravitation",
        "Kepler's third law",
        "r",
        base_latex=r"T = 2\pi\sqrt{\frac{r^3}{GM}}",
        assumptions=("circular orbit around a fixed central mass",),
        expression="(G_grav*M*period**2/(4*pi**2))**(1/3)",
        variables=(
            _CENTRAL_MASS,
            _ORBITING_MASS,
            var("period", "T", "second", words=("period", "every", "once"), needs_words=True),
        ),
        binding=Binding(
            # The radius from the centre; a height above the surface is less R.
            asks=("radius of its orbit", "radius of the orbit", "orbital radius", "orbit radius"),
            result=("meter",),
            inputs=_with_body("M", "period"),
            cues=("orbit",),
            excludes=("above", "altitude", "height"),
            nonnegative=True,
        ),
    ),
    # "400 km above Earth": the orbit's radius is the planet's plus that height.
    formula(
        "kepler_period_altitude",
        "gravitation",
        "Kepler's third law",
        "T",
        base_latex=r"T = 2\pi\sqrt{\frac{(R + h)^3}{GM}}",
        assumptions=("circular orbit around a fixed central mass",),
        expression="2*pi*sqrt((radius_body + altitude)**3/(G_grav*M))",
        variables=(
            _CENTRAL_MASS,
            _ORBITING_MASS,
            var(
                "altitude",
                "h",
                "meter",
                words=("above", "altitude", "height"),
                needs_words=True,
            ),
            var("radius_body", "R", "meter", fallback="body_radius"),
        ),
        binding=Binding(
            asks=("orbital period", "period", "how long"),
            result=("second",),
            inputs=_with_body("M", "altitude", "radius_body"),
            cues=("orbit",),
            nonnegative=True,
        ),
    ),
    formula(
        "vis_viva",
        "gravitation",
        "Vis-viva equation",
        "v",
        base_latex=r"v = \sqrt{GM\left(\frac{2}{r}-\frac{1}{a}\right)}",
        assumptions=("a Kepler orbit about a fixed central mass",),
        expression="sqrt(G_grav*M*(2/orbit_radius-1/semi_major))",
        variables=(
            _CENTRAL_MASS,
            _ORBITING_MASS,
            var(
                "orbit_radius",
                "r",
                "meter",
                words=("distance", "radius"),
                needs_words=True,
            ),
            var(
                "semi_major",
                "a",
                "meter",
                words=("semi-major", "semimajor"),
                needs_words=True,
            ),
        ),
        binding=Binding(
            asks=("orbital speed", "speed"),
            result=("meter / second",),
            inputs=_with_body("M", "orbit_radius", "semi_major"),
            cues=("vis-viva", "vis viva", "semi-major", "semimajor"),
            nonnegative=True,
        ),
    ),
    # g on a named planet or moon, from its mass and radius. A stated length is
    # the radius only when it is called one: "a height of 300 km above Earth's
    # surface" read as R gave 4430 m/s² for 8.96.
    formula(
        "surface_gravity_named",
        "gravitation",
        "Newton's law of gravitation",
        "g",
        base_latex=r"g = \frac{G M}{R^2}",
        expression="G_grav*M/radius_body**2",
        variables=(
            _CENTRAL_MASS,
            _ORBITING_MASS,
            var(
                "radius_body",
                "R",
                "meter",
                words=("radius",),
                fallback="body_radius",
                needs_words=True,
            ),
        ),
        binding=Binding(
            asks=_GRAVITY_ASKS,
            result=("meter / second ** 2",),
            inputs=_with_body("M", "radius_body"),
            nonnegative=True,
        ),
    ),
    # g a height above a named body's surface: the distance to its centre is R + h.
    formula(
        "gravity_at_height",
        "gravitation",
        "Newton's law of gravitation",
        "g",
        base_latex=r"g = \frac{G M}{(R + h)^2}",
        expression="G_grav*M/(radius_body + altitude)**2",
        variables=(
            _CENTRAL_MASS,
            _ORBITING_MASS,
            var(
                "altitude",
                "h",
                "meter",
                words=("above", "altitude", "height"),
                needs_words=True,
            ),
            var(
                "radius_body",
                "R",
                "meter",
                words=("radius",),
                fallback="body_radius",
                needs_words=True,
            ),
        ),
        binding=Binding(
            asks=_GRAVITY_ASKS,
            result=("meter / second ** 2",),
            inputs=_with_body("M", "altitude", "radius_body"),
            cues=("above", "altitude", "height"),
            nonnegative=True,
        ),
    ),
    # A body's weight a height above a named planet: GMm/(R + h)². A 70 kg
    # astronaut 400 km above Earth weighs 609 N, not the 687 N of the surface.
    formula(
        "weight_at_height",
        "gravitation",
        "Newton's law of gravitation",
        "W",
        base_latex=r"W = \frac{G M m}{(R + h)^2}",
        expression="G_grav*M*m/(radius_body + altitude)**2",
        variables=(
            var("M", "M", "kilogram", fallback="body_mass"),
            var("m", "m", "kilogram", words=_SMALL_BODY),
            var(
                "altitude",
                "h",
                "meter",
                words=("above", "altitude", "height"),
                needs_words=True,
            ),
            var(
                "radius_body",
                "R",
                "meter",
                words=("radius",),
                fallback="body_radius",
                needs_words=True,
            ),
        ),
        binding=Binding(
            asks=("weigh", "weight", "gravitational force", "force of gravity"),
            result=("newton",),
            inputs=(frozenset({"M", "altitude", "m", "radius_body"}),),
            cues=("above", "altitude"),
            excludes=("apparent weight", "scale", "lift", "elevator"),
            nonnegative=True,
        ),
    ),
    # F = GMm/R^2 at a named body's surface: the weight, from the law itself.
    formula(
        "gravitational_force_at_surface",
        "gravitation",
        "Newton's law of gravitation",
        "F",
        base_latex=r"F = \frac{G M m}{R^2}",
        expression="G_grav*M*m/radius_body**2",
        variables=(
            var("M", "M", "kilogram", fallback="body_mass"),
            var("radius_body", "R", "meter", fallback="body_radius"),
            var("m", "m", "kilogram", words=_SMALL_BODY),
        ),
        binding=Binding(
            asks=(
                "gravitational force",
                "force of gravity",
                "gravitational pull",
                "gravitational attraction",
            ),
            result=("newton",),
            inputs=(frozenset({"M", "radius_body", "m"}),),
            cues=("surface",),
            excludes=("orbit", "above", "altitude", "height of"),
            nonnegative=True,
        ),
    ),
)
