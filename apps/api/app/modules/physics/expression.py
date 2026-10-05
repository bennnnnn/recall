"""Physics' notation for the shared expression evaluator: its constants and its numbers.

The evaluator is ``services.law_binding.expression``; a physics expression may name the
constants below, and its substitution prints a value with the figures the user wrote.
"""

from __future__ import annotations

from collections.abc import Mapping

from app.modules.physics.display import latex_given
from app.modules.physics.solvers.common import (
    _BIG_G,
    _BOHR_RADIUS,
    _BOLTZMANN,
    _COULOMB_K,
    _ELEMENTARY_CHARGE,
    _EPSILON_0,
    _GAS_CONSTANT,
    _HBAR,
    _MU_0,
    _PLANCK_H,
    _RYDBERG,
    _SPEED_OF_LIGHT,
    _STEFAN_BOLTZMANN,
)
from app.services.law_binding import expression as _shared
from app.services.law_binding.expression import ExpressionError, Notation, parse

__all__ = ["PHYSICS_NOTATION", "ExpressionError", "evaluate", "names", "parse", "to_latex"]

# Physical constants by the name an expression uses, with the symbol the
# formula shows. The values are the solvers' own (CODATA via Pint).
PHYSICS_NOTATION = Notation(
    constants={
        "mu_0": (_MU_0, r"\mu_0"),
        "epsilon_0": (_EPSILON_0, r"\varepsilon_0"),
        "k_e": (_COULOMB_K, "k_e"),
        "G_grav": (_BIG_G, "G"),
        "h_planck": (_PLANCK_H, "h"),
        "c_light": (_SPEED_OF_LIGHT, "c"),
        "e_charge": (_ELEMENTARY_CHARGE, "e"),
        "R_gas": (_GAS_CONSTANT, "R"),
        "k_B": (_BOLTZMANN, "k_B"),
        "hbar": (_HBAR, r"\hbar"),
        "R_inf": (_RYDBERG, r"R_\infty"),
        "a_0": (_BOHR_RADIUS, "a_0"),
        "sigma": (_STEFAN_BOLTZMANN, r"\sigma"),
    },
    number=latex_given,
)


def names(expression: str) -> frozenset[str]:
    """The variable names a physics expression reads; functions and constants excluded."""
    return _shared.names(expression, PHYSICS_NOTATION)


def evaluate(expression: str, values: Mapping[str, float]) -> float:
    """The number a physics expression gives. A domain error is a ValueError."""
    return _shared.evaluate(expression, values, PHYSICS_NOTATION)


def to_latex(
    expression: str,
    symbols: Mapping[str, str],
    values: Mapping[str, float] | None = None,
) -> str:
    """A physics expression typeset: with the law's symbols, or with ``values`` plugged in."""
    return _shared.to_latex(expression, symbols, values, notation=PHYSICS_NOTATION)
