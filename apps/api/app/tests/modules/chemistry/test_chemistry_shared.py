"""The shared helpers the solvers are built on: one home for constants, guards and relations."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.modules.chemistry.equations import balance_equation, format_balanced
from app.modules.chemistry.formula import hill_formula, parse_formula
from app.modules.chemistry.schemas import ChemistryIntent
from app.modules.chemistry.solvers import solve_chemistry
from app.modules.chemistry.solvers.constants import GAS_R
from app.modules.chemistry.solvers.params import positive, require, require_all
from app.modules.chemistry.solvers.relation import solve_paired
from app.modules.chemistry.species_facts import longest_first
from app.services.solving import SolveServiceError

_SOLVER_DIR = Path(__file__).parents[3] / "modules" / "chemistry" / "solvers"


@pytest.mark.parametrize(
    ("counts", "written"),
    [
        ({"O": 1, "C": 1, "H": 2}, "CH2O"),
        ({"C": 6, "H": 12, "O": 6}, "C6H12O6"),
        ({"Cl": 1, "Na": 1}, "NaCl"),
        ({"O": 3, "Fe": 2}, "Fe2O3"),
        ({"O": 4, "S": 1, "H": 2}, "H2SO4"),
        ({"H": 3, "N": 1}, "NH3"),
        ({"O": 1, "H": 2}, "H2O"),
        ({"Cl": 1, "H": 1}, "HCl"),
        ({"O": 5, "N": 2}, "N2O5"),
    ],
)
def test_hill_formula_writes_the_conventional_order(counts: dict[str, int], written: str) -> None:
    assert hill_formula(counts) == written
    assert parse_formula(written) == counts


@pytest.mark.parametrize(
    "written",
    [
        "H" + "9" * 5000,  # raised in int(): past Python's 4300-digit limit
        "C12345H2O",  # a count no formula writes
        "((CH)9999)9999",  # groups multiplied past any compound's atoms
        "99999H2O",  # a hydrate's count
    ],
)
def test_a_count_no_formula_writes_reads_as_no_formula(written: str) -> None:
    assert parse_formula(written) == {}


def test_a_large_real_formula_still_reads() -> None:
    # Titin-sized counts are four digits.
    assert parse_formula("C2952H4664N812O832S8") == {
        "C": 2952,
        "H": 4664,
        "N": 812,
        "O": 832,
        "S": 8,
    }


def test_calorimetry_is_worked_from_the_calorimeter_constant() -> None:
    intent = ChemistryIntent(
        kind="thermochemistry", chemistry_op="calorimetry", params={"c_cal": 200.0, "delta_t": 2.0}
    )
    assert solve_chemistry(intent).answer == "q_rxn = -400 J"
    # The extractor reads nothing else: a mass and a specific heat are physics' Q = mcΔT.
    with pytest.raises(SolveServiceError):
        solve_chemistry(
            ChemistryIntent(
                kind="thermochemistry",
                chemistry_op="calorimetry",
                params={"mass": 50.0, "specific_heat": 4.18, "delta_t": 2.0},
            )
        )


def test_the_empirical_formula_does_not_keep_the_order_the_percentages_were_typed_in() -> None:
    intent = ChemistryIntent(
        kind="amounts",
        chemistry_op="empirical_formula",
        species={"O": 53.3, "H": 6.7, "C": 40.0},
    )
    assert solve_chemistry(intent).answer == "CH2O"


def test_format_balanced_leaves_out_a_coefficient_of_one() -> None:
    balanced = balance_equation("H2 + O2 -> H2O")
    assert format_balanced(balanced) == "2 H2 + O2 -> 2 H2O"


def test_solve_paired_solves_each_variable_of_the_ideal_gas_law() -> None:
    known = {"P": 2.0, "V": 12.3086, "n": 1.0}
    value, rearranged, substituted = solve_paired(
        known, "T", ["P", "V"], ["n", "R", "T"], {"R": GAS_R}
    )
    assert value == pytest.approx(300.0, rel=1e-4)
    assert rearranged == "T = PV / (nR)"
    assert substituted == "T = (2)(12.3086) / [(1)(0.082057)]"
    volume, *_ = solve_paired(
        {"P": 2.0, "n": 1.0, "T": 300.0}, "V", ["P", "V"], ["n", "R", "T"], {"R": GAS_R}
    )
    assert volume == pytest.approx(12.3086, rel=1e-4)


def test_solve_paired_refuses_an_unknown_that_is_not_in_the_relation() -> None:
    with pytest.raises(SolveServiceError):
        solve_paired({"P": 1.0}, "X", ["P"], ["V"])
    with pytest.raises(SolveServiceError):
        solve_paired({"P": 1.0}, "V", ["P", "V"], ["n", "R", "T"], {"R": GAS_R})


def test_a_missing_or_out_of_range_parameter_is_a_refusal_never_a_default() -> None:
    intent = ChemistryIntent(
        kind="kinetics", chemistry_op="zero_order", params={"initial": 1.0, "rate": -1.0}
    )
    assert require(intent, "initial") == 1.0
    with pytest.raises(SolveServiceError):
        require(intent, "time")
    with pytest.raises(SolveServiceError):
        require(intent, "rate", positive=True)
    with pytest.raises(SolveServiceError):
        require(intent, "rate", non_negative=True)
    with pytest.raises(SolveServiceError):
        require_all(intent, "initial", "time")
    assert positive(2, "x") == 2.0
    for bad in (None, 0, -1):
        with pytest.raises(SolveServiceError):
            positive(bad, "x")


@pytest.mark.parametrize(
    "literal",
    [r"0\.0820573", r"8\.3144626", r"96485\.33", r"6\.022140", r"1\.0072764", r"931\.494"],
)
def test_no_chemistry_module_types_a_physical_constant(literal: str) -> None:
    # The values come from the shared unit registry (solvers/constants.py), never a literal.
    typed = [
        str(path.relative_to(_SOLVER_DIR.parent))
        for path in _SOLVER_DIR.parent.rglob("*.py")
        if re.search(literal, path.read_text(encoding="utf-8"))
    ]
    assert typed == []


def test_compound_names_match_longest_first() -> None:
    pattern = re.compile(rf"\b(?:{longest_first(['sodium', 'sodium chloride'])})\b")
    found = pattern.search("dissolve sodium chloride")
    assert found is not None and found.group() == "sodium chloride"
    # Escaped: a name's own marks are no regex.
    assert longest_first(["Na+"]) == r"Na\+"
