"""Chemistry's constants are CODATA values from the shared unit registry, pinned.

A Pint upgrade that moved one would move answers, so each magnitude is held here.
"""

from __future__ import annotations

import pytest

from app.modules.chemistry.solvers import constants
from app.services.units import constant


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("GAS_R", 0.08205736608095969),
        ("GAS_R_J", 8.314462618153241),
        ("FARADAY", 96485.33212331001),
        ("AVOGADRO", 6.02214076e23),
        ("PROTON_U", 1.007276466620409),
        ("NEUTRON_U", 1.0086649159477235),
        ("MEV_PER_U", 931.4941024171442),
    ],
)
def test_a_chemistry_constant_is_the_registrys_codata_value(name: str, value: float) -> None:
    assert getattr(constants, name) == pytest.approx(value, rel=1e-15)


def test_a_registry_constant_reads_in_the_unit_asked_or_in_si() -> None:
    assert constant("molar_gas_constant", "L * atm / (mol * K)") == pytest.approx(0.0820573661)
    assert constant("molar_gas_constant") == pytest.approx(8.314462618)
