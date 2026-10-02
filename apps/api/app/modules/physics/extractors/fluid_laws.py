"""Fluid laws a question names: Stokes, Reynolds, Laplace, Torricelli, Bernoulli."""

from __future__ import annotations

from collections.abc import Callable

from app.models.schemas.physics import PhysicsIntent
from app.modules.physics.extractors.common import (
    _LENGTH_UNIT_PATTERN,
    _detect_gravity,
    _find_value_with_specific_unit,
)
from app.modules.physics.extractors.fluid_readings import (
    _PRESSURE_PATTERN,
    FluidReading,
)


def _stokes(f: FluidReading) -> PhysicsIntent | None:
    if f.viscosity is None or f.radius is None or len(f.speed) != 1:
        return None
    return PhysicsIntent(
        kind="fluids",
        physics_op="stokes_drag",
        physics_params={
            "viscosity": f.viscosity[0],
            "r": f.radius[0],
            "v": f.speed[0][0],
        },
        physics_units={
            "viscosity": f.viscosity[1] or "Pa*s",
            "r": f.radius[1] or "m",
            "v": f.speed[0][1] or "m/s",
        },
        operation="solve",
    )


def _reynolds(f: FluidReading) -> PhysicsIntent | None:
    rho = f.fluid_density()
    if rho is None or f.viscosity is None or f.characteristic_length is None or len(f.speed) != 1:
        return None
    return PhysicsIntent(
        kind="fluids",
        physics_op="reynolds_number",
        physics_params={
            "rho": rho,
            "v": f.speed[0][0],
            "L": f.characteristic_length[0],
            "viscosity": f.viscosity[0],
        },
        physics_units={
            "rho": f.density[1] if f.density is not None else "kg/m^3",
            "v": f.speed[0][1] or "m/s",
            "L": f.characteristic_length[1] or "m",
            "viscosity": f.viscosity[1] or "Pa*s",
        },
        operation="solve",
    )


def _laplace(f: FluidReading) -> PhysicsIntent | None:
    if f.surface_tension is None or f.radius is None:
        return None
    factor = 4.0 if "soap bubble" in f.lower else 2.0
    return PhysicsIntent(
        kind="fluids",
        physics_op="laplace_pressure",
        physics_params={
            "surface_tension": f.surface_tension[0],
            "r": f.radius[0],
            "mode_factor": factor,
        },
        physics_units={
            "surface_tension": f.surface_tension[1] or "N/m",
            "r": f.radius[1] or "m",
            "mode_factor": "",
        },
        operation="solve",
    )


def _surface_tension(f: FluidReading) -> PhysicsIntent | None:
    length = _find_value_with_specific_unit(
        f.cleaned, _LENGTH_UNIT_PATTERN, ("length", "edge", "contact")
    )
    if f.force is None or length is None:
        return None
    return PhysicsIntent(
        kind="fluids",
        physics_op="surface_tension",
        physics_params={"F": f.force[0], "L": length[0]},
        physics_units={"F": f.force[1] or "N", "L": length[1] or "m"},
        operation="solve",
    )


def _torricelli(f: FluidReading) -> PhysicsIntent | None:
    if f.depth is None:
        return None
    return PhysicsIntent(
        kind="fluids",
        physics_op="torricelli_speed",
        physics_params={"depth": f.depth[0], "g": _detect_gravity(f.cleaned)},
        physics_units={"depth": f.depth[1] or "m", "g": "m/s^2"},
        operation="solve",
    )


def _mass_flow(f: FluidReading) -> PhysicsIntent | None:
    rho = f.fluid_density()
    if rho is None or f.area is None or len(f.speed) != 1:
        return None
    return PhysicsIntent(
        kind="fluids",
        physics_op="mass_flow_rate",
        physics_params={"rho": rho, "area": f.area[0], "v": f.speed[0][0]},
        physics_units={
            "rho": f.density[1] if f.density is not None else "kg/m^3",
            "area": f.area[1] or "m^2",
            "v": f.speed[0][1] or "m/s",
        },
        operation="solve",
    )


def _hydraulic(f: FluidReading) -> PhysicsIntent | None:
    """Pascal's principle: F1/A1 = F2/A2."""
    if f.force is None or len(f.areas) != 2:
        return None
    return PhysicsIntent(
        kind="fluids",
        physics_op="hydraulic_force",
        physics_params={"F1": f.force[0], "A1": f.areas[0][0], "A2": f.areas[1][0]},
        physics_units={
            "F1": f.force[1] or "N",
            "A1": f.areas[0][1] or "m^2",
            "A2": f.areas[1][1] or "m^2",
        },
        operation="solve",
    )


def _bernoulli(f: FluidReading) -> PhysicsIntent | None:
    """Bernoulli. Heights only when both are stated; otherwise horizontal."""
    # Height terms are not guessed. Both heights, or the word horizontal.
    initial_height = _find_value_with_specific_unit(
        f.cleaned,
        _LENGTH_UNIT_PATTERN,
        ("initial height", "starting height"),
        require_keyword=True,
    )
    final_height = _find_value_with_specific_unit(
        f.cleaned,
        _LENGTH_UNIT_PATTERN,
        ("final height", "ending height"),
        require_keyword=True,
    )
    pressure = _find_value_with_specific_unit(f.cleaned, _PRESSURE_PATTERN)
    rho = f.fluid_density()
    if (
        initial_height is not None
        and final_height is not None
        and pressure is not None
        and rho is not None
        and len(f.speed) == 2
    ):
        return PhysicsIntent(
            kind="fluids",
            physics_op="bernoulli_pressure",
            physics_params={
                "pres1": pressure[0],
                "rho": rho,
                "v1": f.speed[0][0],
                "v2": f.speed[1][0],
                "h1": initial_height[0],
                "h2": final_height[0],
                "g": _detect_gravity(f.cleaned),
            },
            physics_units={
                "pres1": pressure[1] or "Pa",
                "rho": f.density[1] if f.density is not None else "kg/m^3",
                "v1": f.speed[0][1] or "m/s",
                "v2": f.speed[1][1] or "m/s",
                "h1": initial_height[1] or "m",
                "h2": final_height[1] or "m",
                "g": "m/s^2",
            },
            operation="solve",
        )
    if "horizontal" not in f.lower:
        return None
    if pressure is None or rho is None or len(f.speed) != 2:
        return None
    return PhysicsIntent(
        kind="fluids",
        physics_op="bernoulli_pressure",
        physics_params={
            "pres1": pressure[0],
            "rho": rho,
            "v1": f.speed[0][0],
            "v2": f.speed[1][0],
        },
        physics_units={
            "pres1": pressure[1] or "Pa",
            "rho": f.density[1] if f.density is not None else "kg/m^3",
            "v1": f.speed[0][1] or "m/s",
            "v2": f.speed[1][1] or "m/s",
        },
        operation="solve",
    )


# Each named law and the phrases that name it, tried in this order. A question
# that names one is answered or declined by that law alone.
NAMED_FLUID_LAWS: tuple[
    tuple[tuple[str, ...], Callable[[FluidReading], PhysicsIntent | None]], ...
] = (
    (("stokes",), _stokes),
    (("reynolds",), _reynolds),
    (("laplace pressure", "soap bubble", "droplet"), _laplace),
    (("surface tension",), _surface_tension),
    (("torricelli",), _torricelli),
    (("mass flow rate",), _mass_flow),
    (("hydraulic", "pascal's principle"), _hydraulic),
    (("bernoulli",), _bernoulli),
)
