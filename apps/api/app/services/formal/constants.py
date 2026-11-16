"""The standard constants a school question may rely on without stating them.

A constant the model adds must be one of these, within ``TOLERANCE`` of its value in the same
kind of unit: g as 9.8 or 9.81 m/s², c, the speed of sound in air, water's density and
specific heat, and so on. Anything else a question does not state is a number the model
made up, and the setup is refused.
"""

from __future__ import annotations

from typing import Any

TOLERANCE = 0.03

# (value, unit) in units pint reads.
CONSTANTS: tuple[tuple[float, str], ...] = (
    (9.81, "m/s**2"),  # g; 9.8 and 10 are within or noted below
    (10.0, "m/s**2"),  # g as many school books round it
    (6.674e-11, "N*m**2/kg**2"),  # G
    (2.998e8, "m/s"),  # c
    (343.0, "m/s"),  # sound in air (340 within tolerance)
    (1.602e-19, "C"),  # e
    (9.109e-31, "kg"),  # electron mass
    (1.673e-27, "kg"),  # proton mass
    (6.626e-34, "J*s"),  # h
    (8.988e9, "N*m**2/C**2"),  # Coulomb's k
    (8.854e-12, "F/m"),  # epsilon_0
    (1.257e-6, "H/m"),  # mu_0
    (6.022e23, "1/mol"),  # Avogadro
    (8.314, "J/(mol*K)"),  # R
    (0.08206, "L*atm/(mol*K)"),  # R in L atm
    (1.381e-23, "J/K"),  # Boltzmann
    (5.670e-8, "W/(m**2*K**4)"),  # Stefan-Boltzmann
    (101325.0, "Pa"),  # one atmosphere
    (1000.0, "kg/m**3"),  # water's density
    (1.225, "kg/m**3"),  # air's density
    (4186.0, "J/(kg*K)"),  # water's specific heat (4180, 4184, 4200 within)
    (3.34e5, "J/kg"),  # water's latent heat of fusion
    (2.26e6, "J/kg"),  # water's latent heat of vaporisation
    (5.972e24, "kg"),  # Earth's mass
    (6.371e6, "m"),  # Earth's radius
    (1.989e30, "kg"),  # the Sun's mass
    (7.35e22, "kg"),  # the Moon's mass
    (1.496e11, "m"),  # one astronomical unit
)


def is_standard(magnitude: float, units: Any, registry: Any) -> bool:
    """``magnitude`` in ``units`` (both in base SI) is one of the standard constants."""
    for value, unit in CONSTANTS:
        known = registry.Quantity(value, unit).to_base_units()
        if known.dimensionality != units.dimensionality:
            continue
        if magnitude and abs(magnitude - known.magnitude) <= TOLERANCE * abs(known.magnitude):
            return True
    return False
