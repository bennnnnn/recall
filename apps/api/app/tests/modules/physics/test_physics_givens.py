"""What a question states, what it asks, and what a solve may leave out."""

from __future__ import annotations

import pytest

from app.models.schemas.physics import PhysicsIntent
from app.modules.physics.accounting import competing_given
from app.modules.physics.ask import asked_dimensions, asked_phrases, result_dimension
from app.modules.physics.givens import ANGLE, scan_givens, unit_dimension

_VELOCITY = unit_dimension("meter / second")[0]  # type: ignore[index]
_TIME = unit_dimension("second")[0]  # type: ignore[index]
_LENGTH = unit_dimension("meter")[0]  # type: ignore[index]
_FORCE = unit_dimension("newton")[0]  # type: ignore[index]
_ACCELERATION = unit_dimension("meter / second ** 2")[0]  # type: ignore[index]


def test_scan_givens_reads_value_unit_and_si() -> None:
    givens = scan_givens("heat 2 kg of water from 20 °C to 80 °C, c = 4200 J/kg°C, 100 µF.")
    assert [(given.value, given.unit) for given in givens] == [
        (2.0, "kg"),
        (20.0, "°C"),
        (80.0, "°C"),
        (4200.0, "J/kg°C"),
        (100.0, "µF"),
    ]
    assert givens[1].si == pytest.approx(293.15)
    assert givens[4].si == pytest.approx(1e-4)


@pytest.mark.parametrize(
    ("text", "values"),
    [
        ("Q1. A question with a label", []),
        ("give the answer to 3 s.f.", []),
        ("the 2nd ball", []),
        ("a = 9.8 m/s^2", [9.8]),
    ],
)
def test_scan_givens_skips_what_is_not_a_quantity(text: str, values: list[float]) -> None:
    assert [given.value for given in scan_givens(text)] == values


def test_scan_givens_never_reads_prose_as_units() -> None:
    givens = scan_givens("walk 3 at a time, 4 in a row, 5 a day")
    assert [given.dimension for given in givens] == [None, None, None]


def test_angles_are_their_own_dimension() -> None:
    (angle,) = scan_givens("at 30 degrees")
    assert angle.dimension == ANGLE


@pytest.mark.parametrize(
    ("text", "dimensions"),
    [
        (
            "A ball is dropped from 80 m. What is its speed just before it hits the ground?",
            (_VELOCITY,),
        ),
        ("How long does it take a car to accelerate from 0 to 27 m/s?", (_TIME,)),
        ("How far does a plane travel in 3 hours at 800 km/h?", (_LENGTH,)),
        ("Find the time of flight, the maximum height and the range.", (_TIME, _LENGTH)),
        (
            "Two masses hang over a pulley. Find the acceleration and the tension.",
            (_ACCELERATION, _FORCE),
        ),
        ("what is g on a planet of mass 6e24 kg and radius 6.4e6 m", ()),
        ("Find the energy equivalent of 2 kg of mass.", (unit_dimension("joule")[0],)),  # type: ignore[index]
        ("A lens has focal length 0.25 m. Find its power.", ()),
        ("Find its horizontal and vertical components.", ()),
        ("hello there", ()),
    ],
)
def test_asked_dimensions(text: str, dimensions: tuple[str, ...]) -> None:
    assert asked_dimensions(text) == dimensions


def test_asked_phrases_name_the_quantity() -> None:
    assert asked_phrases("A stone falls 45 m. Find its velocity when it lands.") == ("velocity",)
    assert asked_phrases("What fraction remains after 20 days?") == ("fraction",)


@pytest.mark.parametrize(
    ("unit", "dimension"),
    [
        ("m/s^2", _ACCELERATION),
        ("N*s", unit_dimension("kilogram * meter / second")[0]),  # type: ignore[index]
        ("deg", ANGLE),
        ("", "dimensionless"),
        ("D", unit_dimension("1 / meter")[0]),  # type: ignore[index]
    ],
)
def test_result_dimension(unit: str, dimension: str) -> None:
    assert result_dimension(unit) == dimension


def _intent(op: str, kind: str, params: dict[str, float], units: dict[str, str]) -> PhysicsIntent:
    return PhysicsIntent(kind=kind, physics_op=op, physics_params=params, physics_units=units)  # type: ignore[arg-type]


def test_a_second_speed_competes_with_the_first() -> None:
    intent = _intent("kinetic_energy", "energy", {"m": 2, "v": 3}, {"m": "kg", "v": "m/s"})
    given = competing_given(intent, "the kinetic energy of 2 kg at 3 m/s and at 4 m/s")
    assert given is not None and given.value == 4


def test_a_distractor_of_another_kind_is_allowed() -> None:
    intent = _intent(
        "time_to_ground", "kinematics", {"g": 9.81, "h0": 20, "v0": 0}, {"h0": "m", "v0": "m/s"}
    )
    assert competing_given(intent, "A 5 kg ball is dropped from 20 m.") is None


@pytest.mark.parametrize(
    ("op", "kind", "params", "units", "text"),
    [
        (
            "kirchhoff_junction",
            "circuit",
            {"i_enter": 5, "i_leave": 1},
            {"i_enter": "A", "i_leave": "A"},
            "currents of 2 A and 3 A enter and 1 A leaves",
        ),
        (
            "heat_energy",
            "thermal",
            {"m": 2, "c_heat": 4200, "delta_temp": 60},
            {"m": "kg", "c_heat": "J/kg/K", "delta_temp": "K"},
            "heat 2 kg from 20 °C to 80 °C with c = 4200 J/kg/K",
        ),
    ],
)
def test_a_value_derived_from_givens_accounts_for_them(
    op: str, kind: str, params: dict[str, float], units: dict[str, str], text: str
) -> None:
    assert competing_given(_intent(op, kind, params, units), text) is None


def test_a_direction_sign_is_not_a_different_value() -> None:
    intent = _intent(
        "impulse", "momentum", {"m": 0.2, "v1": 10, "v2": -8}, {"m": "kg", "v1": "m/s", "v2": "m/s"}
    )
    assert competing_given(intent, "0.2 kg at 10 m/s rebounds at 8 m/s") is None


def test_a_stated_gravity_is_a_setting_not_a_given() -> None:
    intent = _intent("net_force", "force", {"m": 5, "a": 2}, {"m": "kg", "a": "m/s^2"})
    assert competing_given(intent, "5 kg at 2 m/s^2, with g = 9.8 m/s^2") is None
