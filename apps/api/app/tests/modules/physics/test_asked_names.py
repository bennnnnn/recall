"""The quantity a worked reply finds is named as its law means it, never by its letter alone."""

from __future__ import annotations

import re

import pytest

from app.modules.physics.asked_names import asked_meaning
from app.modules.physics.catalog import CATALOG
from app.modules.physics.glossary import given_meaning
from app.modules.physics.law_nouns import named_laws, result_name
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
        # The law's own name for its result ("power" of a lens, in dioptres) is its name.
        if meaning == result_name(spec):
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


@pytest.mark.parametrize(
    ("operation", "symbol", "answer_unit"),
    [
        # Two results on one line: the law's one name fitted only the first (review of
        # PR #2420: "a, T (acceleration)").
        ("atwood", r"a,\ T", "m/s²"),
        ("table_pulley", r"a,\ T", "m/s²"),
    ],
)
def test_a_result_of_several_symbols_names_each(
    operation: str, symbol: str, answer_unit: str
) -> None:
    assert asked_meaning(operation, symbol, answer_unit) == "acceleration, tension"


def test_a_result_of_several_symbols_one_has_no_name_for_is_unnamed() -> None:
    # F_x and F_y have no name in newtons: no name is better than half of one.
    assert asked_meaning("resolve_force", r"F_x,\ F_y", "N") is None


@pytest.mark.parametrize(
    ("operation", "symbol", "unit", "meaning"),
    [
        # A proper noun keeps its capital: the asks a question is matched by are lowercase.
        ("de_broglie_from_voltage", r"\lambda", "m", "de Broglie wavelength"),
        ("fermi_energy", "E_F", "J", "Fermi energy"),
        ("schwarzschild_radius", "r_s", "m", "Schwarzschild radius"),
        ("hall_voltage", "V_H", "V", "Hall voltage"),
        ("hall_coefficient", "R_H", "m^3/C", "Hall coefficient"),
        ("debye_length", r"\lambda_D", "m", "Debye length"),
        ("friedmann_hubble", "H", "1/s", "Hubble parameter"),
        ("zeeman_shift", r"\Delta E", "J", "Zeeman shift"),
        ("poisson_ratio", r"\nu", None, "Poisson's ratio"),
        ("alfven_speed", "v_A", "m/s", "Alfvén speed"),
        ("hawking_temperature", "T_H", "K", "Hawking temperature"),
        ("higgs_mass", "m_H", "kg", "Higgs mass"),
        # A name says what the quantity is: a rate is no count, a part no bare "component".
        ("photon_emission_rate", r"\frac{N}{t}", "1/s", "photons emitted per second"),
        (
            "weight_along_slope",
            r"F_{\parallel}",
            "N",
            "component of the weight along the slope",
        ),
        ("sound_level_from_ratio", "L_2", "dB", "sound level"),
        ("half_life_fraction", r"\frac{N}{N_0}", None, "fraction remaining"),
        ("percent_after_half_lives", r"\frac{N}{N_0}", "%", "percentage remaining"),
        ("floating_fraction", r"\frac{V_{sub}}{V}", None, "fraction submerged"),
        ("boltzmann_population_ratio", r"\frac{N_2}{N_1}", None, "population ratio"),
        ("time_to_peak", r"t_{\text{top}}", "s", "time to the top"),
        ("wavelength_in_medium", r"\lambda_n", "m", "wavelength in the medium"),
    ],
)
def test_a_result_is_named_for_a_reader(
    operation: str, symbol: str, unit: str | None, meaning: str
) -> None:
    assert asked_meaning(operation, symbol, unit) == meaning


_PROPER = re.compile(r"(?<=\s)[A-Z][a-zé]+")
_LOOSE_END = re.compile(r"^(?:to|in|of|at|on|for|from|by)\b|\b(?:to|in|of|at|on|for|from|by)$")


@pytest.mark.parametrize("operation", sorted(named_laws()))
def test_every_result_name_is_written_for_a_reader(operation: str) -> None:
    spec = CATALOG[operation]
    name = result_name(spec)
    assert name and spec.binding is not None
    # Not a phrase cut from a question ("to the top", "wavelength in").
    assert not _LOOSE_END.search(name)
    # A name its law's name capitalises past the first word (Zeeman in "Normal Zeeman
    # shift") keeps that capital.
    for proper in _PROPER.findall(spec.law_name):
        assert proper.lower() not in name.split() or proper in name, (operation, name)
