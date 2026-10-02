"""Corpus rows for the thermal, fluid, modern and upper-level laws.

Worked by hand like the rest of ``corpus.py``: R = 8.314 J/(mol·K), CODATA
constants, g = 9.81 m/s², and water's c = 4186 J/(kg·K).
"""

from __future__ import annotations

from app.tests.modules.physics.corpus_case import Case, decline, q

CASES: tuple[Case, ...] = (
    q("A gas of 2 mol at 300 K occupies 0.05 m^3. Find the pressure.", (99768, "Pa")),
    q(
        "A gas occupies 2 L at 27 °C. It is heated to 127 °C at constant pressure. "
        "Find the new volume.",
        (2.6663e-3, "m^3"),
    ),
    q(
        "A sealed container of gas at 100 kPa and 300 K is heated to 450 K. Find the new pressure.",
        (150000, "Pa"),
    ),
    q(
        "Find the rms speed of oxygen molecules at 300 K. The molar mass of oxygen is 32 g/mol.",
        (483.56, "m/s"),
    ),
    q("Find the internal energy of 2 mol of a diatomic gas at 300 K.", (12471, "J")),
    q(
        "200 g of water at 80 °C is mixed with 300 g of water at 20 °C. "
        "Find the final temperature.",
        (317.15, "K"),
    ),
    q("Find the absolute pressure at a depth of 10 m in water.", (199425, "Pa")),
    q(
        "Ice of density 917 kg/m^3 floats in water of density 1000 kg/m^3. "
        "What fraction of the ice is submerged?",
        (0.917, ""),
    ),
    q("Find the momentum of a photon of wavelength 500 nm.", (1.3252e-27, "kg*m/s")),
    q(
        "Light of frequency 1.2 × 10^15 Hz falls on a metal with work function 2.3 eV. "
        "Find the stopping potential.",
        (2.6646, "V"),
    ),
    q(
        "An electron in hydrogen falls from n = 3 to n = 2. "
        "Find the wavelength of the emitted photon.",
        (6.5611e-7, "m"),
    ),
    q("A proton moves at 0.8c. Find its relativistic momentum.", (6.6871e-19, "kg*m/s")),
    q("Find the Schwarzschild radius of the Sun.", (2953.3, "m")),
    q("Find the period of a satellite orbiting 400 km above Earth.", (5544.8, "s")),
)

TRAPS: tuple[Case, ...] = (
    # "at 20 °C" is a temperature, and reading it as the change gave 167 kJ.
    decline("How much energy is needed to heat 2 kg of water at 20 °C?"),
    # No body named, so no radius to add the height to.
    decline("A satellite orbits at a height of 400 km. Find its orbital period."),
    # Nothing says the temperature is constant.
    decline(
        "A gas occupies 4 L at 2 atm. The pressure is increased to 4 atm. Find the new volume."
    ),
    # Denser than water: it sinks.
    decline(
        "A block of density 1200 kg/m^3 floats in water of density 1000 kg/m^3. "
        "What fraction is submerged?"
    ),
)
