"""The effort a simple machine needs to lift a load, with its efficiency when one is stated.

"A screw jack has a pitch of 5 mm and a handle 35 cm long. Its efficiency is 40%. What effort
at the end of the handle is needed to lift a car weighing 9000 N?" had no law: the turn went
to the model unchecked, and a money card read the car and the 40% as a car loan (2026-11-18).
The ideal advantage is the machine's geometry (``machines``); a real machine's is that times
its efficiency, MA = eta x VR, and the effort is the load over it. Each machine's efficiency
from its load and effort is its own law, eta = W / (F x VR), answered as a percentage of at
most 100: solved backwards from the effort law, "what is its efficiency?" came out a bare
0.409, and an effort too small for its load an efficiency above one.
"""

from __future__ import annotations

from app.services.law_binding.spec import (
    Binding,
    FormulaSpec,
    FormulaVariant,
    VariableSpec,
    formula,
    var,
)

# The load: "a load of 800 N", or the weight of what is lifted ("a car weighing 9000 N").
_LOAD = ("load", "weight", "weighs", "weighing", "lift", "lifts", "raise", "raises")
_ASKS = ("effort", "effort force", "force needed", "force required", "input force")
_EFFORT = ("effort", "input force", "applied")
_IDEAL = ("friction is neglected",)


def _load() -> VariableSpec:
    # The load is the machine's output force, as ``machines`` names it.
    return var("F_out", "W", "newton", words=_LOAD, needs_words=True)


def _efficiency() -> VariableSpec:
    # A share, read as the fraction it is: "40%" is 0.4.
    return var("efficiency", r"\eta", dimensionless=True, words=("efficiency", "efficient"))


def _effort_force() -> VariableSpec:
    # The effort a question states, when it asks the efficiency.
    return var("F_in", "F", "newton", words=_EFFORT, needs_words=True)


def _laws(
    op: str,
    title: str,
    advantage: str,
    advantage_latex: str,
    geometry: tuple[VariableSpec, ...],
    cues: tuple[str, ...],
) -> tuple[FormulaSpec, FormulaSpec]:
    """One machine's effort law and its efficiency law."""
    return (
        _effort(
            f"machine_effort_{op}", f"Effort on {title}", advantage, advantage_latex, geometry, cues
        ),
        _efficiency_law(
            f"machine_efficiency_{op}",
            f"Efficiency of {title}",
            advantage,
            advantage_latex,
            geometry,
            cues,
        ),
    )


def _efficiency_law(
    op: str,
    title: str,
    advantage: str,
    advantage_latex: str,
    geometry: tuple[VariableSpec, ...],
    cues: tuple[str, ...],
) -> FormulaSpec:
    """The efficiency ``eta = W / (F x VR) x 100%`` of one machine from its load and effort."""
    names = frozenset({"F_out", "F_in", *(variable.name for variable in geometry)})
    return formula(
        op,
        "energy",
        title,
        r"\eta",
        base_latex=rf"\eta = \frac{{W}}{{F \, {advantage_latex}}} \times 100\%",
        expression=f"100*F_out/(F_in*({advantage}))",
        variables=(_load(), _effort_force(), *geometry),
        binding=Binding(
            asks=("efficiency",),
            result=("percent",),
            inputs=(names,),
            cues=cues,
            nonnegative=True,
            at_most=100.0,
        ),
    )


def _effort(
    op: str,
    title: str,
    advantage: str,
    advantage_latex: str,
    geometry: tuple[VariableSpec, ...],
    cues: tuple[str, ...],
) -> FormulaSpec:
    """The effort ``F = W / (eta x VR)`` of one machine, ``VR`` its geometry's ratio; with
    no efficiency stated, the ideal machine's ``F = W / VR``."""
    names = frozenset({"F_out", *(variable.name for variable in geometry)})
    return formula(
        op,
        "energy",
        title,
        "F",
        base_latex=rf"F = \frac{{W}}{{{advantage_latex}}}",
        assumptions=_IDEAL,
        expression=f"F_out/({advantage})",
        variants=(
            FormulaVariant(
                latex=rf"F = \frac{{W}}{{\eta \, {advantage_latex}}}",
                assumptions=(),
                present=frozenset({"efficiency"}),
                expression=f"F_out/(efficiency*({advantage}))",
            ),
        ),
        variables=(_load(), *geometry, _efficiency()),
        binding=Binding(
            asks=_ASKS,
            result=("newton",),
            inputs=(names, names | {"efficiency"}),
            cues=cues,
            nonnegative=True,
            # A real machine's efficiency is a share of one: "efficiency of 40" or "140%"
            # draws nothing, and an effort too small for its load solves to no efficiency.
            requires=("efficiency", "1.000001 - efficiency"),
        ),
    )


SPECS: tuple[FormulaSpec, ...] = (
    *_laws(
        "screw",
        "a screw jack",
        "2*pi*screw_handle_length/thread_pitch",
        r"\frac{2\pi L}{p}",
        (
            var("screw_handle_length", "L", "meter", words=("handle",), needs_words=True),
            var("thread_pitch", "p", "meter", words=("pitch",), needs_words=True),
        ),
        ("screw",),
    ),
    *_laws(
        "wheel_axle",
        "a wheel and axle",
        "wheel_radius/axle_radius",
        r"\frac{R}{r}",
        (
            var("wheel_radius", "R", "meter", words=("wheel",), needs_words=True),
            var("axle_radius", "r", "meter", words=("axle",), needs_words=True),
        ),
        ("wheel and axle",),
    ),
    *_laws(
        "pulley",
        "a pulley system",
        "supporting_strands",
        "n",
        (
            var(
                "supporting_strands",
                "n",
                dimensionless=True,
                words=("supporting strands", "supporting rope", "strands", "ropes"),
                needs_words=True,
            ),
        ),
        ("pulley",),
    ),
)
