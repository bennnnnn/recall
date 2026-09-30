"""Physical constants and reference tables the solvers share.

One home, so a solver never imports a sibling solver for a number and two files never carry two
different values of the same constant.
"""

from __future__ import annotations

GAS_R = 0.082057366080960  # L·atm/(mol·K)
GAS_R_J = 8.31446261815324  # J/(mol·K)
FARADAY = 96485.33212  # C/mol
AVOGADRO = 6.02214076e23  # 1/mol
KW = 1.0e-14  # water ion product at 25 °C
PKW = 14  # -log10(KW), so pH + pOH
PROTON_U = 1.007276466621  # proton mass in u
NEUTRON_U = 1.00866491595  # neutron mass in u
MEV_PER_U = 931.494  # energy equivalent of 1 u

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
