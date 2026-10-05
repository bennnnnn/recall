"""Physical constants and reference tables the solvers share.

One home, so a solver never imports a sibling solver for a number and two files never carry two
different values of the same constant.
"""

from __future__ import annotations

from app.services.units import constant

# CODATA values from the shared unit registry, in the units chemistry works in. A test pins
# each, so a Pint upgrade cannot move an answer.
GAS_R = constant("molar_gas_constant", "L * atm / (mol * K)")
GAS_R_J = constant("molar_gas_constant", "J / (mol * K)")
BOLTZMANN = constant("boltzmann_constant", "J / K")
PLANCK = constant("planck_constant", "J * s")
FARADAY = constant("faraday_constant", "C / mol")
AVOGADRO = constant("avogadro_constant", "1 / mol")
PROTON_U = constant("proton_mass", "u")
NEUTRON_U = constant("neutron_mass", "u")
# The energy equivalent of 1 u.
MEV_PER_U = constant("atomic_mass_constant * speed_of_light ** 2", "MeV")
# Water's ion product at 25 °C is a tabulated value, not a constant of nature.
KW = 1.0e-14
PKW = 14  # -log10(KW), so pH + pOH

# Standard reduction potential and electrons for the common aqueous ion.
STANDARD_REDUCTION: dict[str, tuple[float, int]] = {
    "Li": (-3.04, 1),
    "K": (-2.93, 1),
    "Ba": (-2.91, 2),
    "Ca": (-2.87, 2),
    "Na": (-2.71, 1),
    "Mg": (-2.37, 2),
    "Al": (-1.66, 3),
    "Mn": (-1.18, 2),
    "Zn": (-0.76, 2),
    "Cr": (-0.74, 3),
    "Fe": (-0.44, 2),
    "Cd": (-0.40, 2),
    "Co": (-0.28, 2),
    "Ni": (-0.25, 2),
    "Sn": (-0.14, 2),
    "Pb": (-0.13, 2),
    "H": (0.0, 2),
    "Cu": (0.34, 2),
    "Ag": (0.80, 1),
    "Hg": (0.85, 2),
    "Au": (1.50, 3),
}
