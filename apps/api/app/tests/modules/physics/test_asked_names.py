"""The quantity a worked reply finds is named as its law means it, never by its letter alone."""

from __future__ import annotations

import pytest

from app.modules.physics.asked_names import asked_meaning
from app.modules.physics.catalog import CATALOG
from app.modules.physics.glossary import given_meaning
from app.modules.physics.solvers.si import PARAM_SI_DIMENSIONS
from app.services.law_binding.units import unit_dimension


@pytest.mark.parametrize(
    ("operation", "symbol", "meaning"),
    [
        # A letter that names another quantity elsewhere: Q is a charge in circuits.
        ("heat_energy", "Q", "heat energy"),
        ("latent_heat", "Q", "heat energy"),
        ("range", "R", "range"),
        ("weight", "W", "weight"),
        ("ideal_gas_volume", "V", "volume"),
        ("ideal_gas_pressure", "P", "pressure"),
        ("rod_center_inertia", "I", "moment of inertia"),
        ("point_source_intensity", "I", "intensity"),
        ("telescope_magnification", "M", "magnification"),
        ("angular_momentum", "L", "angular momentum"),
        ("recoil_speed", "V", "recoil speed"),
        # The same letters where they do mean the glossary's word.
        ("current", "I", "current"),
        ("resistance", "R", "resistance"),
        ("voltage", "V", "voltage"),
        ("work", "W", "work"),
        ("power", "P", "power"),
        ("charge", "Q", "charge"),
        # A law solved for one of its inputs: the work-energy theorem asked for the mass.
        ("work_energy", "m", "mass"),
    ],
)
def test_asked_meaning_names_the_quantity_its_law_finds(
    operation: str, symbol: str, meaning: str
) -> None:
    assert asked_meaning(operation, symbol) == meaning


@pytest.mark.parametrize(
    ("operation", "symbol", "answer_unit", "meaning"),
    [
        # A law with no binding: the verified answer's unit says R is not a resistance,
        # and names it by that unit's word for R.
        ("resultant_force", "R", "N", "resultant force"),
        ("resultant_force", "R", None, "resistance"),
        ("net_force", "F", "N", "force"),
    ],
)
def test_asked_meaning_reads_the_answers_unit_when_the_law_has_no_binding(
    operation: str, symbol: str, answer_unit: str | None, meaning: str | None
) -> None:
    assert asked_meaning(operation, symbol, answer_unit) == meaning


def test_no_law_names_its_result_with_another_quantitys_word() -> None:
    # Every law whose binding says the result's unit: the word on the Required line is
    # never the glossary's word for a letter of another dimension.
    wrong = []
    for spec in CATALOG.values():
        if spec.binding is None or not spec.binding.result:
            continue
        symbol = spec.result_symbol
        meaning = asked_meaning(spec.id, symbol)
        if meaning is None or meaning != given_meaning(spec.id, spec.kind, symbol):
            continue
        # The law's own word for its result ("power" of a lens, in dioptres) is its name.
        if meaning in spec.binding.asks:
            continue
        letter = _dimension(PARAM_SI_DIMENSIONS.get(symbol))
        result = _dimension(spec.binding.result[0])
        if letter is not None and result is not None and letter != result:
            wrong.append(f"{spec.id}: {symbol} = {meaning}")
    assert wrong == []


def _dimension(unit: str | None) -> str | None:
    reading = unit_dimension(unit) if unit else None
    return None if reading is None else reading[0]


@pytest.mark.parametrize(
    ("operation", "symbol", "answer_unit", "meaning"),
    [
        # A law's own result its glossary has no word for: the word for its dimension.
        ("max_height", "H_{max}", "m", "maximum height"),
        ("shm_period", "T", "s", "period"),
        ("tension", "T", "N", "tension"),
        ("pressure_at_depth", "P", "Pa", "pressure"),
        ("torque", r"\tau", "N·m", "torque"),
        ("electric_force", "F_e", "N", "electric force"),
        # The law's own ask, when it has one.
        ("half_life_remaining", "N", "g", "mass remaining"),
    ],
)
def test_a_result_the_glossary_does_not_know_is_named_by_its_dimension(
    operation: str, symbol: str, answer_unit: str, meaning: str
) -> None:
    assert asked_meaning(operation, symbol, answer_unit) == meaning


def test_a_symbol_in_another_dimension_stays_unnamed() -> None:
    # T in metres is no period and no tension: no name is better than a wrong one.
    assert asked_meaning("shm_period", "T", "m") is None
