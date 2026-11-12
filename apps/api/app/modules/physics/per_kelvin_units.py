"""A unit per kelvin as a class writes it: a specific heat, a molar heat, a conductivity.

One quantity has many spellings ("J/kg/K", "J/(kg·K)", "J kg^-1 K^-1", "J/kg°C"), each read
without case by the physics unit table (``given_units``), whose words they join.
"""

from __future__ import annotations

PER_KELVIN_WORDS: dict[str, str] = {
    "j/kg/k": "joule / kilogram / kelvin",
    "kj/kg/k": "kilojoule / kilogram / kelvin",
    "j/mol/k": "joule / mole / kelvin",
    "j/(kg k)": "joule / kilogram / kelvin",
    "j/(kg·k)": "joule / kilogram / kelvin",
    "j/kgk": "joule / kilogram / kelvin",
    "j/kg·k": "joule / kilogram / kelvin",
    "j/kg k": "joule / kilogram / kelvin",
    "j/kg.k": "joule / kilogram / kelvin",
    "kj/kg·k": "kilojoule / kilogram / kelvin",
    "j/kg·°c": "joule / kilogram / kelvin",
    "j/kg °c": "joule / kilogram / kelvin",
    "j/(kg·°c)": "joule / kilogram / kelvin",
    "j/kg°c": "joule / kilogram / kelvin",
    "j/kg/°c": "joule / kilogram / kelvin",
    "j/(kg °c)": "joule / kilogram / kelvin",
    "j kg^-1 k^-1": "joule / kilogram / kelvin",
    "j/g/k": "joule / gram / kelvin",
    "j/(g k)": "joule / gram / kelvin",
    "j/(g·k)": "joule / gram / kelvin",
    "j/gk": "joule / gram / kelvin",
    "j/g·k": "joule / gram / kelvin",
    "j/g k": "joule / gram / kelvin",
    "j/g·°c": "joule / gram / kelvin",
    "j/g °c": "joule / gram / kelvin",
    "j/g°c": "joule / gram / kelvin",
    "j/g/°c": "joule / gram / kelvin",
    "j/(g °c)": "joule / gram / kelvin",
    "j/(g·°c)": "joule / gram / kelvin",
    "j g^-1 k^-1": "joule / gram / kelvin",
    "w/m/k": "watt / meter / kelvin",
    "w/m k": "watt / meter / kelvin",
    "w/m·k": "watt / meter / kelvin",
    "w/(m k)": "watt / meter / kelvin",
    "w/(m·k)": "watt / meter / kelvin",
    "w/(m*k)": "watt / meter / kelvin",
    "w m^-1 k^-1": "watt / meter / kelvin",
}
