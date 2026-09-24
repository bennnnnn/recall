"""Every physics param must declare its dimension.

`_PARAM_SI_DIMENSIONS` reads like documentation and is not: it is the only
thing standing between a user's unit spelling and Pint's interpretation of it,
and Pint's lowercase spellings are actively hostile. Measured:

    "pa"  -> petayear      [time]
    "t"   -> tonne         [mass]
    "c"   -> speed of light
    "k"   -> Boltzmann constant

Every extractor regex in this package is IGNORECASE, so those spellings do
arrive. With a dimension entry, "100 pa" for a pressure is refused. Without
one, it converts to 0.0032 *seconds* and the solve proceeds to a confident
wrong answer.

So this walks every phrasing the physics suites claim to verify, collects the
param keys those intents actually carry, and requires each to be declared.
Adding a kind without touching the table fails here rather than in production.
"""

from __future__ import annotations

import pytest

from app.models.schemas.physics import PhysicsIntent
from app.modules.physics.solver import _PARAM_SI_DIMENSIONS
from app.services.math.tools import extract_math_intent

# Genuinely dimensionless, or converted before `_to_si` ever sees them.
# `angle`/`angle2` are turned from degrees into radians by `_params_in_si`.
_DIMENSIONLESS = frozenset(
    {
        "mu",
        "angle",
        "angle2",
        "elastic",
        "n1",
        "n2",
    }
)


def _verified_questions() -> list[str]:
    """Every question the physics suites pin an answer for."""
    from app.tests.modules.physics import (
        test_physics_circuits,
        test_physics_projectile,
        test_physics_round3_gaps,
        test_physics_waves_optics_thermal,
    )

    questions: list[str] = []
    for module in (
        test_physics_projectile,
        test_physics_round3_gaps,
        test_physics_waves_optics_thermal,
        test_physics_circuits,
    ):
        for name in ("VERIFIED", "NEW_OPS", "NETWORKS", "UNIT_ONLY"):
            for row in getattr(module, name, []):
                questions.append(row[0])
    return questions


def test_the_corpus_is_not_empty() -> None:
    """A silent import failure would make every assertion below vacuous."""
    assert len(_verified_questions()) > 80


@pytest.mark.parametrize("text", _verified_questions(), ids=lambda t: t[:44])
def test_every_emitted_param_declares_a_dimension(text: str) -> None:
    intent = extract_math_intent(text)
    assert isinstance(intent, PhysicsIntent), f"no intent for {text!r}"
    undeclared = [
        key
        for key in (intent.physics_params or {})
        if key not in _PARAM_SI_DIMENSIONS and key not in _DIMENSIONLESS
    ]
    assert not undeclared, (
        f"{undeclared} carry units but have no _PARAM_SI_DIMENSIONS entry, so a "
        f"lowercase unit spelling can convert them into the wrong dimension."
    )


def test_every_declared_dimension_is_a_real_unit() -> None:
    """A typo in the table disables the check it exists to perform."""
    from app.services.math.school import get_unit_registry

    ureg = get_unit_registry()
    broken = []
    for key, spec in _PARAM_SI_DIMENSIONS.items():
        try:
            ureg(spec)
        except Exception:  # any parse failure is the bug
            broken.append((key, spec))
    assert not broken, f"unparseable dimension specs: {broken}"
