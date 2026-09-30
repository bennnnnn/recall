"""Heavy-piston equilibrium stays with the solver, including the inverted balance."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.physics.catalog import formula_spec, select_formula
from app.modules.physics.solvers.school_matter import _heavy_piston
from app.services.solving import SolveServiceError
from app.tests.modules.physics.support import (
    build_verified_physics_block,
    extract_physics_intent,
    maybe_direct_physics_reply,
    needs_physics,
)

_SETTINGS = Settings(math_tools_enabled=True)
_ANSWER = "140000 Pa; 0.0356143 m^3; 600 K; 4986 J; 12465 J; 60000 Pa; 0.0831 m^3"

_PISTON = (
    "A cylinder contains n = 2 mol of a monatomic ideal gas with C_V = 3/2 R. "
    "A piston of mass M = 40 kg and area A = 0.01 m^2 closes it. "
    "Atmospheric pressure is P_0 = 1.0 \\times 10^5 Pa and the temperature is "
    "T_0 = 300 K. Take g = 10 m/s^2 and R = 8.31 J/(mol·K). "
    "The cylinder is held vertically with the piston above the gas. "
    "Find the pressure and the volume. "
    "The gas is heated slowly so that the volume doubles. "
    "Find the temperature, the work done by the gas, and the heat supplied. "
    "The cylinder is suddenly turned upside down and the temperature is brought "
    "back to the original temperature. Find the new pressure and volume."
)

_PISTON_UNICODE = (
    "A cylinder contains n = 2 mol of monatomic ideal gas, C_V = \\frac{3}{2} R. "
    "Piston mass M = 40 kg, area A = 0.01 m². "
    "P₀ = 1.0 × 10^5 Pa, T₀ = 300 K, g = 10 m/s², R = 8.31 J/(mol·K). "
    "Held vertically, piston above the gas. Volume doubles when heated slowly. "
    "Heat supplied. Then turned upside down at the original temperature."
)

_UPRIGHT = (
    "A vertical cylinder holds n = 2 mol of monatomic ideal gas under a piston. "
    "M = 40 kg, A = 0.01 m^2, P0 = 100000 Pa, T0 = 300 K, g = 10 m/s^2, "
    "R = 8.31 J/mol/K. Find the pressure and volume."
)

_PHRASES = (
    "A vertical cylinder of monatomic ideal gas is closed by a piston of mass 40 kg "
    "and cross-sectional area of 0.01 m^2. It holds 2 mol. "
    "Atmospheric pressure is 100000 Pa. Temperature is 300 K. "
    "Gravity is 10 m/s^2. R = 8.31 J/mol/K."
)

_BARE_POWER = (
    "A vertical cylinder holds n = 2 mol of monatomic ideal gas under a piston. "
    "M = 40 kg, A = 0.01 m^2, P0 = 10^5 Pa, T0 = 300 K, g = 10 m/s^2, "
    "R = 8.31 J/mol/K."
)

_HEAT_FROM_CP = (
    "An ideal gas under a vertical piston has n = 2 mol, M = 40 kg, "
    "A = 0.01 m^2, P0 = 100000 Pa, T0 = 300 K, g = 10 m/s^2, "
    "R = 8.31 J/mol/K, and Cp = 5/2 R. The volume doubles. Find the heat supplied."
)

_WORK_ONLY = (
    "An ideal gas under a vertical piston has n = 2 mol, M = 40 kg, "
    "A = 0.01 m^2, P0 = 100000 Pa, T0 = 300 K, g = 10 m/s^2, "
    "R = 8.31 J/mol/K. The volume doubles. Find the temperature and the work."
)

_METRIC_PREFIXES = (
    "A vertical cylinder holds n = 2 mol of monatomic ideal gas under a piston. "
    "M = 40000 g, A = 100 cm^2, P0 = 100 kPa, T0 = 300 K, g = 10 m/s^2, "
    "R = 8.31 J/mol/K."
)

_FLIP_ONLY = (
    "An ideal gas is held by a piston that is turned upside down at the original "
    "temperature. n = 2 mol, M = 40 kg, A = 0.01 m^2, P_0 = 100000 Pa, "
    "T_0 = 300 K, g = 10 m/s^2, R = 8.31 J/mol/K."
)

# The flip sentence repeats the original temperature. That restatement is one given.
_REPEATED_TEMPERATURE = (
    "A vertical cylinder is closed by a piston of mass M = 40 kg and area A = 0.01 m^2. "
    "It contains n = 2 mol of a monatomic ideal gas with C_V = 3/2 R. "
    "Atmospheric pressure is P_0 = 1.0 \\times 10^5 Pa. The gas temperature is T_0 = 300 K. "
    "Take g = 10 m/s^2 and R = 8.31 J/(mol·K). "
    "The piston rests on the gas. Find the equilibrium pressure P_1 and volume V_1. "
    "The gas is heated slowly until V_2 = 2V_1. "
    "Find the temperature, the work done by the gas, and the heat supplied. "
    "The cylinder is suddenly turned completely upside down. The piston cannot fall out. "
    "Assuming the gas temperature is momentarily maintained at T_0 = 300 K during this "
    "quick flip, find the new mechanical equilibrium pressure P_3 and volume V_3 "
    "once it stabilizes. Show the step-by-step breakdown."
)

VERIFIED = [
    (_PISTON, _ANSWER),
    (_PISTON_UNICODE, _ANSWER),
    (_UPRIGHT, "140000 Pa; 0.0356143 m^3"),
    (_PHRASES, "140000 Pa; 0.0356143 m^3"),
    (_BARE_POWER, "140000 Pa; 0.0356143 m^3"),
    (_METRIC_PREFIXES, "140000 Pa; 0.0356143 m^3"),
    (_HEAT_FROM_CP, "140000 Pa; 0.0356143 m^3; 600 K; 4986 J; 12465 J"),
    (_WORK_ONLY, "140000 Pa; 0.0356143 m^3; 600 K; 4986 J"),
    (_FLIP_ONLY, "60000 Pa; 0.0831 m^3"),
    (_REPEATED_TEMPERATURE, _ANSWER),
    (
        _UPRIGHT.replace("g = 10 m/s^2", "g = 10 m/s^2. Again, g = 10 m/s^2"),
        "140000 Pa; 0.0356143 m^3",
    ),
    (
        _UPRIGHT.replace("R = 8.31 J/mol/K.", "R = 8.31 J/mol/K. Use R = 8.31 J/mol/K."),
        "140000 Pa; 0.0356143 m^3",
    ),
]

REFUSED = [
    (
        "A monatomic ideal gas is trapped by a piston of mass M = 40 kg and area "
        "A = 0.01 m^2. P_0 = 100000 Pa, T_0 = 300 K, n = 2 mol. "
        "The cylinder is vertical."
    ),
    (
        "An isobaric expansion at a pressure of 100000 Pa changes volume "
        "from 0.01 m^3 to 0.03 m^3 in a piston. Find the work."
    ),
    (
        "A cylinder with a piston holds n = 2 mol of monatomic ideal gas. "
        "The piston mass is M = 400 kg and area A = 0.01 m^2. "
        "P_0 = 100000 Pa, T_0 = 300 K, g = 10 m/s^2, R = 8.31 J/mol/K. "
        "The cylinder is turned upside down at the original temperature."
    ),
    (
        "An ideal gas is trapped by a piston of mass M = 40 kg and area A = 0.01 m^2. "
        "P_0 = 100000 Pa, T_0 = 300 K, g = 10 m/s^2, n = 2 mol. "
        "The cylinder is vertical. The volume doubles. How much heat is supplied?"
    ),
    (
        "A horizontal piston traps n = 2 mol of monatomic ideal gas. "
        "M = 40 kg, A = 0.01 m^2, P0 = 100000 Pa, T0 = 300 K, g = 10 m/s^2."
    ),
    (
        "A vertical piston traps n = 2 mol of monatomic ideal gas. "
        "M = 40 kg, A = 0.01 m^2, P0 = 100000 Pa, T0 = 300 K, g = 10 m/s^2, "
        "R = 0.0821 atm."
    ),
    (
        "A vertical piston traps n = 2 mol of monatomic ideal gas. The cylinder is "
        "turned upside down adiabatically. M = 40 kg, A = 0.01 m^2, "
        "P0 = 100000 Pa, T0 = 300 K, g = 10 m/s^2, R = 8.31 J/mol/K."
    ),
    (
        "A vertical piston traps n = 2 mol of monatomic ideal gas. "
        "The cylinder is turned upside down. Find the new temperature. "
        "M = 40 kg, A = 0.01 m^2, P0 = 100000 Pa, T0 = 300 K, "
        "g = 10 m/s^2, R = 8.31 J/mol/K."
    ),
    (
        "A vertical cylinder holds n = 2 mol of monatomic ideal gas under a piston. "
        "M = 40 kg, A = 0.01 m^2, P0 = 100000 Pa, T_0 = 300 K, T_0 = 290 K, "
        "g = 10 m/s^2, R = 8.31 J/mol/K."
    ),
    (
        "A vertical cylinder holds n = 2 mol of monatomic ideal gas under a piston. "
        "M = 40 kg, A = 0.01 m^2, P0 = 100000 Pa, T0 = 300 K, g = 10 m/s^2, "
        "R = 8.31 J/mol/K, R = 8.314 J/mol/K."
    ),
    (
        "A vertical cylinder holds n = 2 mol of monatomic ideal gas under a piston. "
        "M = 40 kg, A = 0.01 m^2, P0 = 100000 Pa, T0 = 300 K, g = 10 m/s^2, "
        "g = 9.81 m/s^2, R = 8.31 J/mol/K."
    ),
]


def _answer(text: str) -> str | None:
    intent = extract_physics_intent(text)
    if intent is None:
        return None
    block = build_verified_physics_block(intent, _SETTINGS)
    return None if block is None else block.canonical_answer


@pytest.mark.parametrize(("text", "answer"), VERIFIED)
def test_heavy_piston_is_verified(text: str, answer: str) -> None:
    assert needs_physics(text)
    intent = extract_physics_intent(text)
    assert intent is not None
    assert intent.physics_op == "heavy_piston"
    assert _answer(text) == answer


@pytest.mark.parametrize("text", REFUSED)
def test_incomplete_or_unsupported_piston_is_not_answered(text: str) -> None:
    assert _answer(text) is None


def test_subscript_temperature_is_not_confused_with_another_kelvin() -> None:
    text = (
        "A vertical cylinder holds n = 2 mol of monatomic ideal gas under a piston. "
        "M = 40 kg, A = 0.01 m^2, P_{0} = 100000 Pa, T₀ = 300 K, the wall is at 290 K, "
        "g = 10 m/s^2, R = 8.31 J/mol/K."
    )
    intent = extract_physics_intent(text)
    assert intent is not None
    assert intent.physics_params is not None
    assert intent.physics_params["temp"] == 300
    assert _answer(text) == "140000 Pa; 0.0356143 m^3"


def test_solver_rejects_impossible_piston_inputs() -> None:
    base = {"moles": 2.0, "M": 40.0, "area": 0.01, "p_atm": 1e5, "temp": 300.0, "g": 10.0}
    with pytest.raises(SolveServiceError):
        _heavy_piston({**base, "gas_r": 0.0, "upright": 1.0})
    with pytest.raises(SolveServiceError):
        _heavy_piston({**base, "upright": 1.0, "expand_ratio": 1.0})
    with pytest.raises(SolveServiceError):
        _heavy_piston({**base, "upright": 1.0, "expand_ratio": 2.0, "cv_over_r": 0.0})
    with pytest.raises(SolveServiceError):
        _heavy_piston(base)


def test_unstated_gas_constant_uses_the_registry_value() -> None:
    text = (
        "A vertical cylinder holds n = 2 mol of monatomic ideal gas under a piston. "
        "M = 40 kg, A = 0.01 m^2, P0 = 100000 Pa, T0 = 300 K, g = 10 m/s^2. "
        "Find the pressure and volume."
    )
    intent = extract_physics_intent(text)
    assert intent is not None
    assert "gas_r" not in (intent.physics_params or {})
    answer = _answer(text)
    assert answer is not None
    assert answer.startswith("140000 Pa; ")
    assert "0.0356143" not in answer


def test_direct_reply_keeps_the_inverted_balance_and_exact_work() -> None:
    intent = extract_physics_intent(_PISTON)
    assert intent is not None
    block = build_verified_physics_block(intent, _SETTINGS)
    assert block is not None
    spec = formula_spec("heavy_piston")
    assert spec is not None
    _base, lines, _assumptions = select_formula(spec, intent.physics_params or {})
    assert lines == tuple(block.physics_formulas)
    reply = maybe_direct_physics_reply(block, _PISTON)
    assert reply is not None
    assert r"P_3 = P_0 - \frac{Mg}{A}" in reply
    assert r"P_1 = P_0 + \frac{Mg}{A}" in reply
    assert "4986 J" in reply
    assert "12465 J" in reply
    assert "60000 Pa" in reply
    assert "4980" not in reply
    assert "12459" not in reply
    stepped = _PISTON + " Show the step-by-step breakdown."
    assert maybe_direct_physics_reply(block, stepped) is not None


_WORKSHEET = (
    "A cylinder with a movable piston contains n = 2 mol of a monatomic ideal gas. "
    "The molar heat capacity at constant volume is C_V = 3/2 R. "
    "The piston has mass M = 40 kg and cross-sectional area A = 0.01 m^2. "
    "The atmospheric pressure is P_0 = 1.0 \\times 10^5 Pa. "
    "Initially the gas temperature is T_0 = 300 K. "
    "Take g = 10 m/s^2 and R = 8.31 J/(mol·K). The piston cannot fall out. "
    "(1) Initial equilibrium. The cylinder stands upright, so the piston rests on "
    "top of the gas with the atmosphere above it. Find the equilibrium pressure "
    "P_1 of the gas and the volume V_1. "
    "(2) Isobaric expansion. The gas is heated slowly until the volume doubles, "
    "V_2 = 2 V_1, while the pressure stays constant. Find the new temperature T_2, "
    "the work W done by the gas, and the heat Q supplied to the gas. "
    "(3) The cylinder is suddenly turned completely upside down. The piston cannot "
    "fall out. Assuming the gas temperature is momentarily maintained at T_0 = 300 K "
    "during this quick flip, find the new mechanical equilibrium pressure P_3 and "
    "volume V_3 once it stabilizes. Show the step-by-step breakdown."
)


def test_worksheet_longer_than_the_shared_cap_is_verified() -> None:
    assert len(_WORKSHEET) > 1000
    assert needs_physics(_WORKSHEET)
    assert _answer(_WORKSHEET) == _ANSWER
    intent = extract_physics_intent(_WORKSHEET)
    assert intent is not None
    block = build_verified_physics_block(intent, _SETTINGS)
    assert block is not None
    reply = maybe_direct_physics_reply(block, _WORKSHEET)
    assert reply is not None
    assert r"P_3 = P_0 - \frac{Mg}{A}" in reply
    assert "0.0356143 m^3" in reply
    assert "3.56" not in reply


def test_long_non_piston_stays_outside_physics() -> None:
    short = "A 5 kg block is pulled with a force of 20 N. Find the acceleration."
    assert needs_physics(short)
    padded = short + (" The surface is level." * 80)
    assert len(padded) > 1000
    assert needs_physics(padded) is False
    assert extract_physics_intent(padded) is None


def test_worksheet_past_the_piston_ceiling_is_not_physics() -> None:
    padded = _WORKSHEET + (" Restate the givens." * 400)
    assert len(padded) > 4000
    assert needs_physics(padded) is False
    assert extract_physics_intent(padded) is None


def test_incomplete_long_piston_is_not_another_operation() -> None:
    text = _WORKSHEET.replace("g = 10 m/s^2 and ", "")
    assert len(text) > 1000
    assert extract_physics_intent(text) is None


def test_repeated_temperature_stays_direct_beside_another_kelvin() -> None:
    text = _REPEATED_TEMPERATURE + " The wall is at 290 K."
    intent = extract_physics_intent(text)
    assert intent is not None
    assert intent.physics_params is not None
    assert intent.physics_params["temp"] == 300
    assert _answer(text) == _ANSWER
    block = build_verified_physics_block(intent, _SETTINGS)
    assert block is not None
    reply = maybe_direct_physics_reply(block, text)
    assert reply is not None
    assert r"P_3 = P_0 - \frac{Mg}{A}" in reply
    assert "Let's go step-by-step" not in reply
