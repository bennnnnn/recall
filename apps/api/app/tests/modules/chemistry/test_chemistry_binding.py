"""A chemistry question in its own words reads into one law, or declines.

The answers themselves are checked against hand-worked values in the corpus
(``corpus.py``); these tests pin what each phrasing binds to and what must decline.
"""

from __future__ import annotations

import pytest

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.binding import bind_chemistry_intent, prepare
from app.modules.chemistry.extract import extract_chemistry_intent
from app.modules.chemistry.laws import LAWS
from app.modules.chemistry.request import is_chemistry_question
from app.modules.chemistry.solvers import solve_chemistry


def _bound(question: str) -> ChemistryIntent:
    intent = bind_chemistry_intent(question)
    assert intent is not None, question
    return intent


@pytest.mark.parametrize(
    ("question", "op", "params", "formula"),
    [
        ("What is the pH of 0.01 M HCl?", "strong_acid_ph", {"concentration": 0.01}, "HCl"),
        (
            "What is the pH of 0.01 M Ca(OH)2?",
            "strong_base_ph",
            {"concentration": 0.01},
            "Ca(OH)2",
        ),
        (
            "What is the pH of 0.1 M acetic acid? Ka = 1.8e-5",
            "weak_acid_ph",
            {"concentration": 0.1, "ka": 1.8e-5},
            "CH3COOH",
        ),
        ("How many moles are in 36 g of water?", "mass_to_moles", {"mass": 36.0}, "H2O"),
        ("Convert 2.5 mol of CO2 to grams.", "moles_to_mass", {"moles": 2.5}, "CO2"),
        (
            "Find the osmotic pressure of 0.1 M glucose at 25 °C.",
            "osmotic_pressure",
            # Glucose does not dissociate, and 25 °C is read as 298.15 K.
            {"i": 1.0, "molarity": 0.1, "temperature": 298.15},
            None,
        ),
        (
            "How many grams of Cu are deposited by a current of 2 A for 1 hour from Cu2+?",
            "electrolysis_mass",
            # Copper's molar mass and its 2+ charge come from the question's words.
            {"molar_mass": 63.546, "current": 2.0, "time": 3600.0, "electrons": 2.0},
            None,
        ),
        (
            "Calculate ΔG at 298 K if ΔH = -100 kJ/mol and ΔS = -200 J/mol·K.",
            "gibbs",
            {"delta_h": -100.0, "delta_s": -0.2, "temperature": 298.0},
            None,
        ),
        (
            "A rate constant is 0.01 s^-1 at 300 K and 0.04 s^-1 at 320 K. "
            "Find the activation energy.",
            "arrhenius_two_point",
            {"k1": 0.01, "t1": 300.0, "k2": 0.04, "t2": 320.0},
            None,
        ),
        (
            "A spot travels 3 cm and the solvent front travels 6 cm. Find the Rf value.",
            "chromatography_rf",
            {"spot": 3.0, "front": 6.0},
            None,
        ),
    ],
)
def test_a_question_in_its_own_words_binds_one_law(
    question: str, op: str, params: dict[str, float], formula: str | None
) -> None:
    intent = _bound(question)
    assert intent.chemistry_op == op
    assert intent.params == pytest.approx(params)
    assert intent.formula == formula


def test_a_volume_keeps_the_unit_the_dilution_was_written_in() -> None:
    intent = _bound("50 mL of 2 M HCl is diluted to 200 mL. What is the new concentration?")
    assert intent.params == {"m1": 2.0, "v1": 50.0, "v2": 200.0}
    assert intent.units == {"v1": "mL", "v2": "mL"}


@pytest.mark.parametrize(
    "question",
    [
        # Two strong acids: whose pH?
        "What is the pH of 0.01 M HCl and 0.02 M HNO3?",
        # A pH with no substance named is not a strong-acid pH.
        "What is the pH of a 0.01 M solution?",
        # Two substances, two masses: which moles?
        "10 g of NaCl is dissolved in 500 g of water. How many moles are there?",
        # The question asks for more than the law answers.
        "What is the pH of 0.01 M HCl and explain why it is acidic?",
        # A weak acid's pH needs its Ka.
        "What is the pH of 0.1 M acetic acid?",
        # Electrolysis of a metal whose charge the question never gives.
        "How many grams of copper are deposited by a current of 2 A for 1 hour?",
        # A value no input takes: two times for one electrolysis.
        "How many grams of Cu are deposited by 2 A for 1 hour and 30 min from Cu2+?",
    ],
)
def test_a_question_that_does_not_fit_one_law_one_way_declines(question: str) -> None:
    assert bind_chemistry_intent(question) is None


def test_a_formulas_digits_are_never_read_as_numbers() -> None:
    prepared = prepare("What is the pH of 0.01 M Ca(OH)2 made from Cu2+?")
    assert "2" not in prepared.text.replace("0.01", "")
    assert prepared.species == ("Ca(OH)2",)


@pytest.mark.parametrize(
    "question",
    [
        "25 mL of 0.1 M HCl is titrated with 0.1 M NaOH. Find the pH after adding 10 mL of NaOH.",
        # The same titration, written titrant first.
        "10 mL of 0.1 M NaOH is added to 25 mL of 0.1 M HCl in a titration. Find the pH.",
    ],
)
def test_each_titration_volume_belongs_to_the_solution_it_is_of(question: str) -> None:
    intent = extract_chemistry_intent(question)
    assert intent is not None
    assert intent.chemistry_op == "titration_strong"
    assert intent.params == pytest.approx({"ma": 0.1, "va_l": 0.025, "mb": 0.1, "vb_l": 0.01})


def test_a_titration_volume_no_phrase_ties_to_a_solution_declines() -> None:
    assert (
        extract_chemistry_intent("25 mL of 0.1 M HCl is titrated with 0.1 M NaOH. Find the pH.")
        is None
    )


def test_a_law_fit_is_a_chemistry_cue() -> None:
    assert is_chemistry_question("How many moles are in 36 g of water?")
    assert not is_chemistry_question("How many moles are in my garden?")


# One solvable set of inputs per law: every law the binder can read is one its solver answers.
_SAMPLES: dict[str, tuple[dict[str, float], str | None, dict[str, str]]] = {
    "strong_acid_ph": ({"concentration": 0.01}, "HCl", {}),
    "strong_base_ph": ({"concentration": 0.01}, "NaOH", {}),
    "weak_acid_ph": ({"concentration": 0.1, "ka": 1.8e-5}, "CH3COOH", {}),
    "weak_base_ph": ({"concentration": 0.1, "kb": 1.8e-5}, "NH3", {}),
    "ph_from_poh": ({"poh": 4.5}, None, {}),
    "buffer_ph": ({"pka": 4.74, "acid": 0.1, "base": 0.2}, None, {}),
    "dilution": ({"m1": 2.0, "v1": 50.0, "v2": 200.0}, None, {"v1": "mL", "v2": "mL"}),
    "freezing_depression": ({"i": 1.0, "kf": 1.86, "molality": 0.5}, None, {}),
    "boiling_elevation": ({"i": 2.0, "kb": 0.512, "molality": 1.0}, None, {}),
    "osmotic_pressure": ({"i": 1.0, "molarity": 0.1, "temperature": 298.15}, None, {}),
    "mass_to_moles": ({"mass": 36.0}, "H2O", {"mass": "g"}),
    "moles_to_mass": ({"moles": 2.5}, "CO2", {"moles": "mol"}),
    "molecular_formula": ({"molar_mass": 180.0}, "CH2O", {}),
    "percent_yield": ({"actual": 45.0, "theoretical": 50.0}, None, {}),
    "first_order_concentration": (
        {"initial": 1.0, "rate_constant": 0.1, "time": 10.0},
        None,
        {"time": "s"},
    ),
    "zero_order": ({"initial": 1.0, "rate_constant": 0.01, "time": 50.0}, None, {"time": "s"}),
    "second_order": ({"initial": 1.0, "rate_constant": 0.5, "time": 2.0}, None, {"time": "s"}),
    "arrhenius_two_point": ({"k1": 0.01, "t1": 300.0, "k2": 0.04, "t2": 320.0}, None, {}),
    "nernst": (
        {"standard_potential": 1.1, "electrons": 2.0, "quotient": 0.01, "temperature": 298.0},
        None,
        {},
    ),
    "electrolysis_mass": (
        {"molar_mass": 63.546, "current": 2.0, "time": 3600.0, "electrons": 2.0},
        None,
        {},
    ),
    "gibbs": ({"delta_h": -100.0, "delta_s": -0.2, "temperature": 298.0}, None, {}),
    "beer_lambert_concentration": ({"absorbance": 0.5, "epsilon": 100.0, "path": 1.0}, None, {}),
    "beer_lambert_absorbance": ({"epsilon": 100.0, "path": 1.0, "concentration": 0.005}, None, {}),
    "beer_lambert_path": ({"absorbance": 0.5, "epsilon": 100.0, "concentration": 0.005}, None, {}),
    "beer_lambert_epsilon": ({"absorbance": 0.5, "path": 1.0, "concentration": 0.005}, None, {}),
    "percent_error": ({"experimental": 9.8, "accepted": 10.0}, None, {}),
    "chromatography_rf": ({"spot": 3.0, "front": 6.0}, None, {}),
}


def test_every_law_has_a_sample() -> None:
    assert set(_SAMPLES) == {law.spec.id for law in LAWS}


@pytest.mark.parametrize("law", LAWS, ids=[law.spec.id for law in LAWS])
def test_every_law_promises_inputs_its_solver_answers(law: object) -> None:
    from app.modules.chemistry.laws import ChemistryLaw

    assert isinstance(law, ChemistryLaw) and law.spec.binding is not None
    params, formula, units = _SAMPLES[law.spec.id]
    assert frozenset(params) in law.spec.binding.inputs
    intent = ChemistryIntent(
        kind=law.kind,  # type: ignore[arg-type]
        chemistry_op=law.op,  # type: ignore[arg-type]
        params=params,
        units=units,
        formula=formula,
    )
    assert solve_chemistry(intent).answer
