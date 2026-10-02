"""Verified heat operations: Q = mcΔT for each unknown, mixtures and latent heat."""

from __future__ import annotations

from app.modules.physics.catalog.spec import Binding, FormulaSpec, formula, var

_LAW = "Specific-heat equation"
_RISE = ("by", "rise", "change", "increase", "raised", "heated", "cooled", "difference")
_HEAT = var("heat", "Q", "joule")
_MASS = var("m", "m", "kilogram")
_C = var("c_heat", "c", "joule / kilogram / kelvin", fallback="water_specific_heat")
_DELTA_TEMP = var("delta_temp", r"\Delta T", "kelvin", words=_RISE, needs_words=True)
_LATENT = var("latent_heat", "L", "joule / kilogram")
_PHASE_CHANGE = ("melt", "boil", "freez", "evaporat", "vapori", "condens", "latent", "solidif")


def _heat_law(
    operation: str,
    symbol: str,
    expression: str,
    asks: tuple[str, ...],
    result: str,
    *variables: str,
) -> FormulaSpec:
    known = {spec.name: spec for spec in (_HEAT, _MASS, _C, _DELTA_TEMP)}
    return formula(
        operation,
        "thermal",
        _LAW,
        symbol,
        base_latex=r"Q = mc\Delta T",
        expression=expression,
        variables=tuple(known[name] for name in variables),
        binding=Binding(
            asks=asks,
            result=(result,),
            inputs=(frozenset(variables),),
            excludes=_PHASE_CHANGE,
            nonnegative=True,
        ),
    )


SPECS: tuple[FormulaSpec, ...] = (
    _heat_law(
        "specific_heat_from_energy",
        "c",
        "heat/(m*delta_temp)",
        ("specific heat capacity", "specific heat"),
        "joule / kilogram / kelvin",
        "heat",
        "m",
        "delta_temp",
    ),
    _heat_law(
        "temperature_change_from_heat",
        r"\Delta T",
        "heat/(m*c_heat)",
        (
            "temperature rise",
            "temperature change",
            "temperature increase",
            "change in temperature",
            "rise in temperature",
            "increase in temperature",
        ),
        "kelvin",
        "heat",
        "m",
        "c_heat",
    ),
    _heat_law(
        "mass_from_heat",
        "m",
        "heat/(c_heat*delta_temp)",
        ("mass",),
        "kilogram",
        "heat",
        "c_heat",
        "delta_temp",
    ),
    # Two amounts of water mixed: the heat one loses the other gains. Both
    # are water, so c cancels; any other substance named rules this out.
    formula(
        "water_mixture_temperature",
        "thermal",
        "Conservation of energy in mixing",
        "T",
        base_latex=r"m_1 c (T_1 - T) = m_2 c (T - T_2)",
        assumptions=("both are water and no heat is lost to the surroundings",),
        expression="(m1*temp_a + m2*temp_b)/(m1 + m2)",
        variables=(
            var("m1", "m_1", "kilogram"),
            var("m2", "m_2", "kilogram"),
            var("temp_a", "T_1", "kelvin"),
            var("temp_b", "T_2", "kelvin"),
        ),
        binding=Binding(
            asks=(
                "final temperature",
                "temperature of the mixture",
                "equilibrium temperature",
                "common temperature",
                "resulting temperature",
                "temperature",
            ),
            result=("kelvin",),
            inputs=(frozenset({"m1", "m2", "temp_a", "temp_b"}),),
            cues=("water",),
            excludes=(
                "ice",
                "steam",
                "oil",
                "copper",
                "iron",
                "aluminium",
                "aluminum",
                "steel",
                "lead",
                "brass",
                "glass",
                "metal",
                "block",
                "specific heat",
            ),
            interchangeable=("m1", "m2", "temp_a", "temp_b"),
            nonnegative=True,
        ),
    ),
    formula(
        "latent_heat_from_energy",
        "thermal",
        "Latent-heat equation",
        "L",
        base_latex="Q = mL",
        expression="heat/m",
        variables=(_HEAT, _MASS),
        binding=Binding(
            asks=(
                "specific latent heat",
                "latent heat of fusion",
                "latent heat of vaporisation",
                "latent heat of vaporization",
                "latent heat",
            ),
            result=("joule / kilogram",),
            inputs=(frozenset({"heat", "m"}),),
            nonnegative=True,
        ),
    ),
    formula(
        "mass_from_latent_heat",
        "thermal",
        "Latent-heat equation",
        "m",
        base_latex="Q = mL",
        expression="heat/latent_heat",
        variables=(_HEAT, _LATENT),
        binding=Binding(
            asks=("mass",),
            result=("kilogram",),
            inputs=(frozenset({"heat", "latent_heat"}),),
            cues=_PHASE_CHANGE,
            nonnegative=True,
        ),
    ),
)
