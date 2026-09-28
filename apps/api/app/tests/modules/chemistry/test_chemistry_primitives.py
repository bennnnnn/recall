"""Foundations shared by the verified chemistry operations."""

from __future__ import annotations

import pytest

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.block import build_verified_chemistry
from app.modules.chemistry.coordination import parse_coordination
from app.modules.chemistry.elements import BY_NUMBER, BY_SYMBOL, ELEMENTS, get_element_info
from app.modules.chemistry.equations import balance_equation
from app.modules.chemistry.extract import extract_chemistry_intent
from app.modules.chemistry.nuclear import balance_nuclear, decay_product, format_nuclear
from app.modules.chemistry.organic import isomer_relationship, organic_facts
from app.modules.chemistry.quantity import to_atm, to_kelvin, to_liters
from app.modules.chemistry.solvers import solve_chemistry
from app.modules.chemistry.structure import lewis_structure, oxidation_states
from app.services.solving import MathServiceError


def test_periodic_table_has_every_element() -> None:
    assert len(ELEMENTS) == 118
    assert [element.number for element in ELEMENTS] == list(range(1, 119))
    assert set(BY_SYMBOL) == {element.symbol for element in ELEMENTS}
    assert set(BY_NUMBER) == set(range(1, 119))


def test_legacy_masses_and_names_stay_exact() -> None:
    carbon = get_element_info("C")
    assert carbon is not None
    assert carbon["mass"] == 12.011
    assert carbon["name"] == "Carbon"
    assert carbon["electronegativity"] == 2.55
    iron = get_element_info("Fe")
    helium = get_element_info("He")
    aluminum = get_element_info("Al")
    cesium = get_element_info("Cs")
    assert iron is not None and iron["mass"] == 55.845
    assert helium is not None and helium["mass"] == 4.003
    assert aluminum is not None and aluminum["name"] == "Aluminum"
    assert cesium is not None and cesium["name"] == "Cesium"


def test_helium_omits_electronegativity_and_f_block_omits_group() -> None:
    helium = get_element_info("He")
    assert helium is not None
    assert "electronegativity" not in helium
    uranium = get_element_info("U")
    lanthanum = get_element_info("La")
    actinium = get_element_info("Ac")
    assert uranium is not None and "group" not in uranium
    assert lanthanum is not None and lanthanum["group"] == 3
    assert actinium is not None and actinium["group"] == 3
    oganesson = get_element_info("Og")
    assert oganesson is not None
    assert oganesson["mass"] == 294.0
    assert oganesson["mass_note"] == "mass number of a long-lived isotope"
    assert "configuration" in helium
    assert helium["number"] == 2


def test_redox_balance_checks_atoms_and_charge() -> None:
    half = balance_equation("Fe2+ -> Fe3+ + e-")
    assert half.balanced
    assert half.reactants == {"Fe2+": 1}
    assert half.products == {"Fe3+": 1, "e-": 1}
    redox = extract_chemistry_intent("Balance Fe2+ -> Fe3+ + e-")
    assert redox is not None
    assert solve_chemistry(redox).answer == "Fe2+ → Fe3+ + e-"

    permanganate = balance_equation("MnO4- + Fe2+ + H+ -> Mn2+ + Fe3+ + H2O")
    assert permanganate.balanced
    assert permanganate.reactants == {"MnO4-": 1, "Fe2+": 5, "H+": 8}
    assert permanganate.products == {"Mn2+": 1, "Fe3+": 5, "H2O": 4}

    water = balance_equation("H2 + O2 -> H2O")
    assert water.reactants == {"H2": 2, "O2": 1}
    assert water.products == {"H2O": 2}


def test_explicit_phases_drop_out_of_the_equilibrium_expression() -> None:
    question = "Find Kc for CaCO3(s) -> CaO(s) + CO2(g) when [CO2]=0.2 M"
    intent = extract_chemistry_intent(question)
    assert intent is not None
    assert intent.chemistry_op == "equilibrium_constant"
    assert intent.species == {"CO2(g)": 0.2}
    assert solve_chemistry(intent).answer == "Kc = 0.2"


def test_ideal_gas_extractor_normalizes_school_units() -> None:
    assert to_kelvin(25, "C") == 298.15
    assert to_liters(500, "mL") == 0.5
    assert to_atm(101.3, "kPa") == pytest.approx(1, rel=1e-3)
    assert to_atm(750, "mmHg") == pytest.approx(750 / 760)

    celsius = extract_chemistry_intent(
        "Use ideal gas law PV=nRT: P=101.3 kPa, n=1 mol, T=25 C, find volume"
    )
    assert celsius is not None
    assert celsius.chemistry_op == "ideal_gas"
    assert celsius.params["temperature"] == pytest.approx(298.15)
    assert celsius.params["pressure"] == pytest.approx(1, rel=1e-3)
    assert "volume" not in celsius.params

    mixed = extract_chemistry_intent(
        "Use ideal gas law PV=nRT: P=750 mmHg, V=500 mL, n=1 mol, find temperature"
    )
    assert mixed is not None
    assert mixed.params["pressure"] == pytest.approx(750 / 760)
    assert mixed.params["volume"] == 0.5


def test_beer_lambert_solves_absorptivity_and_path() -> None:
    epsilon = extract_chemistry_intent(
        "Use Beer-Lambert law: absorbance=2, path length=1 cm, concentration=0.02 M, find epsilon"
    )
    path = extract_chemistry_intent(
        "Use Beer-Lambert law: absorbance=2, epsilon=100, concentration=0.02 M, find path length"
    )
    assert epsilon is not None and path is not None
    assert solve_chemistry(epsilon).answer == "ε = 100 L/(mol·cm)"
    assert solve_chemistry(path).answer == "b = 1 cm"


def test_ambiguous_oxidation_and_diprotic_strong_acid_are_refused() -> None:
    assert oxidation_states("FeSO4") == {"Fe": 2, "S": 6, "O": -2}
    assert oxidation_states("FeS") is None
    with pytest.raises(MathServiceError, match="ambiguous"):
        solve_chemistry(
            ChemistryIntent(kind="structure", chemistry_op="oxidation_state", formula="FeS")
        )
    sulfuric = extract_chemistry_intent("Find the strong acid pH of 0.010 M H2SO4")
    assert sulfuric is not None
    assert build_verified_chemistry(sulfuric) is None


@pytest.mark.parametrize(
    ("formula", "geometry", "polar", "hybrid", "bonds", "lone_pairs"),
    [
        ("CO2", "linear", False, "sp", (2, 2), 0),
        ("H2O", "bent", True, "sp3", (1, 1), 2),
        ("NH3", "trigonal pyramidal", True, "sp3", (1, 1, 1), 1),
        ("CH4", "tetrahedral", False, "sp3", (1, 1, 1, 1), 0),
        ("BF3", "trigonal planar", False, "sp2", (1, 1, 1), 0),
        ("PCl5", "trigonal bipyramidal", False, "sp3d", (1, 1, 1, 1, 1), 0),
        ("SF6", "octahedral", False, "sp3d2", (1, 1, 1, 1, 1, 1), 0),
        ("SO2", "bent", True, "sp2", (2, 2), 1),
    ],
)
def test_vsepr_for_a_unique_central_atom(
    formula: str,
    geometry: str,
    polar: bool,
    hybrid: str,
    bonds: tuple[int, ...],
    lone_pairs: int,
) -> None:
    structure = lewis_structure(formula)
    assert structure is not None
    assert structure.geometry == geometry
    assert structure.polar is polar
    assert structure.hybridization == hybrid
    assert structure.bond_orders == bonds
    assert structure.central_lone_pairs == lone_pairs
    assert structure.central_formal_charge == 0


def test_two_central_atoms_are_not_a_verified_lewis_structure() -> None:
    assert lewis_structure("HCN") is None


def test_organic_facts_and_coordination_names() -> None:
    ethanol = organic_facts("CCO")
    acid = organic_facts("CC(=O)O")
    alanine = organic_facts("C[C@H](N)C(=O)O")
    assert ethanol is not None and ethanol.groups == ("alcohol",)
    assert acid is not None and acid.groups == ("carboxylic acid",)
    assert alanine is not None and alanine.chirality == ("C1=S",)
    assert isomer_relationship("CCO", "COC") == "constitutional isomers"

    cobalt = parse_coordination("[Co(NH3)6]Cl3")
    iron = parse_coordination("K4[Fe(CN)6]")
    assert cobalt is not None
    assert cobalt.oxidation_state == 3
    assert cobalt.coordination_number == 6
    assert cobalt.name == "hexaamminecobalt(III) chloride"
    assert iron is not None
    assert iron.oxidation_state == 2
    assert iron.name == "potassium hexacyanidoferrate(II)"


def test_nuclear_equations_conserve_nucleons() -> None:
    assert format_nuclear(balance_nuclear("238U -> 234Th + ?")) == "238U → 234Th + 4He"
    assert decay_product(14, "C", "beta") == "14C → 14N + e-"
    assert decay_product(11, "C", "positron") == "11C → 11B + e+"
    assert decay_product(7, "Be", "electron capture") == "7Be → 7Li"
