"""Verified capacitor operations: storage, networks, charging and discharging."""

from __future__ import annotations

from app.services.law_binding.spec import Binding, FormulaSpec, bind, formula, var

_CHARGE = var("Q", "Q", "coulomb")
_CAPACITANCE = var("capacitance", "C", "farad")

SPECS: tuple[FormulaSpec, ...] = (
    formula(
        "capacitance",
        "circuit",
        "Capacitance formula",
        "C",
        variables=(
            var("Q", "Q", "coulomb"),
            var("V", "V", "volt"),
        ),
        binding=bind(("capacitance",), "farad", "Q", "V"),
    ),
    formula(
        "parallel_plate_capacitance",
        "circuit",
        "Parallel-plate capacitance",
        "C",
        base_latex="C = \\frac{\\epsilon_0A}{d}",
        variables=(
            var("area", "A", "meter ** 2"),
            var("d", "d", "meter"),
        ),
    ),
    formula(
        "capacitor_energy",
        "circuit",
        "Capacitor energy",
        "U",
        base_latex="U = \\frac{1}{2}CV^2",
        variables=(
            var("V", "V", "volt"),
            var("capacitance", "C", "farad"),
        ),
    ),
    formula(
        "rc_time_constant",
        "circuit",
        "RC time constant",
        "\\tau",
        base_latex="\\tau = RC",
        variables=(
            var("R", "R", "ohm"),
            var("capacitance", "C", "farad"),
        ),
        binding=bind(("time constant",), "second", "R", "capacitance"),
    ),
    formula(
        "capacitor_charge",
        "circuit",
        "Capacitance formula",
        "Q",
        base_latex="Q = CV",
        expression="capacitance*V",
        variables=(_CAPACITANCE, var("V", "V", "volt")),
        binding=bind(
            ("charge stored", "charge"), "coulomb", "capacitance", "V", cues=("capacitor",)
        ),
    ),
    formula(
        "capacitor_voltage",
        "circuit",
        "Capacitance formula",
        "V",
        base_latex="Q = CV",
        expression="Q/capacitance",
        variables=(_CAPACITANCE, _CHARGE),
        binding=bind(
            ("potential difference", "voltage"), "volt", "Q", "capacitance", cues=("capacitor",)
        ),
    ),
    formula(
        "capacitors_series",
        "circuit",
        "Capacitors in series",
        "C",
        base_latex=r"\frac{1}{C} = \frac{1}{C_1} + \frac{1}{C_2}",
        expression="c1*c2/(c1 + c2)",
        variables=(var("c1", "C_1", "farad"), var("c2", "C_2", "farad")),
        binding=Binding(
            asks=(
                "total capacitance",
                "combined capacitance",
                "equivalent capacitance",
                "capacitance",
            ),
            result=("farad",),
            inputs=(frozenset({"c1", "c2"}),),
            cues=("series",),
            interchangeable=("c1", "c2"),
            nonnegative=True,
        ),
    ),
    formula(
        "capacitors_parallel",
        "circuit",
        "Capacitors in parallel",
        "C",
        base_latex="C = C_1 + C_2",
        expression="c1 + c2",
        variables=(var("c1", "C_1", "farad"), var("c2", "C_2", "farad")),
        binding=Binding(
            asks=(
                "total capacitance",
                "combined capacitance",
                "equivalent capacitance",
                "capacitance",
            ),
            result=("farad",),
            inputs=(frozenset({"c1", "c2"}),),
            cues=("parallel",),
            interchangeable=("c1", "c2"),
            nonnegative=True,
        ),
    ),
    # A capacitor charging or discharging through a resistor, after a time.
    formula(
        "capacitor_charging_voltage",
        "circuit",
        "RC charging equation",
        "V",
        base_latex=r"V = V_0\left(1 - e^{-t/RC}\right)",
        assumptions=("the capacitor starts uncharged",),
        expression="v_supply*(1 - exp(-t/(R*capacitance)))",
        variables=(
            var("R", "R", "ohm"),
            _CAPACITANCE,
            var("t", "t", "second"),
            var("v_supply", "V_0", "volt"),
        ),
        binding=bind(
            ("potential difference", "voltage"),
            "volt",
            "R",
            "capacitance",
            "t",
            "v_supply",
            cues=("charging", "charges", "being charged", "is charged"),
            excludes=("discharg",),
        ),
    ),
    formula(
        "capacitor_discharge_voltage",
        "circuit",
        "RC discharge equation",
        "V",
        base_latex=r"V = V_0 e^{-t/RC}",
        expression="v_supply*exp(-t/(R*capacitance))",
        variables=(
            var("R", "R", "ohm"),
            _CAPACITANCE,
            var("t", "t", "second"),
            var("v_supply", "V_0", "volt"),
        ),
        binding=bind(
            ("potential difference", "voltage"),
            "volt",
            "R",
            "capacitance",
            "t",
            "v_supply",
            cues=("discharg",),
        ),
    ),
)
