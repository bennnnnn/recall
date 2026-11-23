# ruff: noqa: RUF003 -- answers and notes use a multiplication sign and a true minus sign.
"""Answers keep the precision their question was written in.

Each given's significant figures are read from the text: the answer takes the fewest, as
chemistry textbooks do (OpenStax Chemistry 2e §1.5; owner, 2026-11-23), one figure to four. A
typed value is echoed as typed, a pH has as many decimals as its data
have figures, a sum of givens keeps their decimal places, and a molar mass stays at full
precision until the answer.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.chemistry.block import build_verified_chemistry
from app.modules.chemistry.direct import format_direct_chemistry_reply
from app.modules.chemistry.extract import extract_chemistry_intent
from app.modules.chemistry.schemas import ChemistryIntent
from app.modules.chemistry.sig_figs import as_written, decimals_of, figures_of
from app.modules.chemistry.solvers import solve_chemistry
from app.modules.chemistry.solvers.display import num, p_value
from app.modules.chemistry.solvers.types import ChemistryResult


def _solve(question: str) -> ChemistryResult:
    intent = extract_chemistry_intent(question)
    assert intent is not None, question
    return solve_chemistry(intent)


@pytest.mark.parametrize(
    ("literal", "figures", "decimals"),
    [
        ("0.0050", 2, 4),
        ("1.10", 3, 2),
        ("200", 3, 0),
        ("4.50", 3, 2),
        ("1.8e-5", 2, 1),
        ("-0.76", 2, 2),
        ("0", 1, 0),
    ],
)
def test_a_typed_number_has_its_figures_and_places(
    literal: str, figures: int, decimals: int
) -> None:
    assert figures_of(literal) == figures
    assert decimals_of(literal) == decimals


@pytest.mark.parametrize(
    ("literal", "shown"),
    [("1.80e-5", "1.80 × 10^-5"), ("2.5E4", "2.5 × 10^4"), ("0.02370", "0.02370")],
)
def test_a_typed_number_is_shown_as_typed(literal: str, shown: str) -> None:
    assert as_written(literal) == shown


def test_a_typed_value_keeps_its_trailing_zero() -> None:
    result = _solve("Find ΔG° for a cell with n = 2 and E° = 1.10 V.")
    assert result.given == ("n = 2 mol e-", "E°cell = 1.10 V")
    assert result.answer == "ΔG° = -212 kJ/mol"
    kp = _solve("Convert Kc to Kp: Kc=0.02370 at T=298 K for N2 + H2 -> NH3")
    assert kp.given[0] == "Kc = 0.02370"


@pytest.mark.parametrize(
    ("question", "answer"),
    [
        # One significant figure is one: no floor raises it to two.
        ("How many moles of H2O from 4 mol H2 in H2 + O2 -> H2O?", "n(H2O) = 4 mol H2O"),
        # Six figures are cut to four: a figure count is not followed through a difference
        # inside a product, so more could claim precision the data lost.
        ("How many moles are in 36.0400 g of H2O?", "n(H2O) = 2.001 mol"),
        (
            "Find the freezing point depression when i=1, Kf=1.86, and molality=0.500",
            "ΔTf = 0.930 °C",
        ),
    ],
    ids=["one-figure", "ceiling", "count-does-not-limit"],
)
def test_the_answer_has_the_fewest_figures_of_the_measured_givens(
    question: str, answer: str
) -> None:
    assert _solve(question).answer == answer


def test_a_celsius_reading_has_the_figures_of_its_kelvin_value() -> None:
    # 25 °C is 298 K, three figures, so 760 − 23.8 mmHg shows as 736, not 740.
    result = _solve("Gas collected over water at 25 °C with total pressure=760 mmHg")
    assert result.answer == "Pdry = 736 mmHg"


@pytest.mark.parametrize(
    ("question", "answer"),
    [
        # 50.00 kJ is stored as 50000 J and 25 °C as 298.15 K: the kelvin reading's three
        # figures still limit the answer, not just the 1.000e10 that matched as typed.
        ("Arrhenius: A = 1.000e10 s^-1, Ea = 50.00 kJ/mol, T = 25 °C. Find k.", "k = 17.4 s⁻¹"),
        ("Arrhenius: A = 1.000e10 s^-1, Ea = 50.00 kJ/mol, T = 298.0 K. Find k.", "k = 17.22 s⁻¹"),
        # 152 mmHg is stored in atm; its three figures carry over.
        ("Find Kp for CaCO3(s) -> CaO(s) + CO2(g) when P(CO2)=152 mmHg", "Kp = 0.200"),
    ],
)
def test_a_converted_given_keeps_the_figures_it_was_typed_with(question: str, answer: str) -> None:
    assert _solve(question).answer == answer


def test_a_number_that_ends_a_sentence_keeps_its_figures() -> None:
    # "1.8e-10." is 1.8e-10 and a full stop, not 1.8 and a stray "e-10".
    result = _solve("Ksp = 1.8e-10. Find the molar solubility for AgCl(s) -> Ag+ + Cl-.")
    assert result.answer == "s = 1.3 × 10^-5 mol/L"


def test_one_value_typed_two_ways_is_limited_by_both() -> None:
    intent = extract_chemistry_intent("Cell potential: cathode = 0.80 V, anode = 0.8 V")
    assert intent is not None
    # The anode's one decimal place limits the difference; neither 0.8 is echoed as the other.
    assert intent.decimals == 1
    assert intent.written == {}
    assert solve_chemistry(intent).answer == "E°cell = 0.0 V"


def test_a_coefficient_never_limits_a_measured_value_equal_to_it() -> None:
    # The equation's 2s are counts; the 2.00 g of hydrogen has three figures.
    result = _solve("2 H2 + O2 -> 2 H2O. How many grams of water form from 2.00 g of H2?")
    assert result.answer == "m(H2O) = 17.9 g"


@pytest.mark.parametrize(
    ("question", "answer"),
    [
        ("Find pH when [H+] = 2.5 × 10^-4", "pH = 3.60"),
        ("Find the strong acid pH of 0.0010 M HCl", "pH = 3.00"),
        ("Find the strong base pH of 0.010 M NaOH", "pH = 12.00"),
        ("Find pH when pOH = 3.25", "pH = 10.75"),
        ("Find buffer pH with pKa=4.756, [A-]=0.20 and [HA]=0.10", "pH = 5.06"),
        ("Find the pKa if Ka = 1.8 × 10^-5", "pKa = 4.74"),
    ],
)
def test_a_logarithm_has_as_many_places_as_its_data_have_figures(
    question: str, answer: str
) -> None:
    assert _solve(question).answer == answer


def test_a_concentration_from_a_ph_has_as_many_figures_as_the_ph_has_places() -> None:
    assert _solve("Find [H+] when pH = 4.50").answer == "[H+] = 3.2 × 10^-5 mol/L"


@pytest.mark.parametrize(
    ("question", "answer"),
    [
        ("Find the cell potential when cathode=0.34 V and anode=-0.76 V", "E°cell = 1.10 V"),
        (
            "Find the formation enthalpy for H2 + Cl2 -> 2HCl when ΔHf(HCl)=-92.3 kJ/mol",
            "ΔH° = -184.6 kJ/mol",
        ),
        # The multipliers are whole numbers, so only the enthalpies' places count.
        (
            "Use Hess's law: ΔH1=-200.5 kJ, multiplier1=1, ΔH2=50.25 kJ, multiplier2=2",
            "ΔH = -100.0 kJ",
        ),
        ("Find the cell potential when cathode=0.80 V and anode=0.80 V", "E°cell = 0.00 V"),
    ],
)
def test_a_sum_of_givens_keeps_their_fewest_decimal_places(question: str, answer: str) -> None:
    assert _solve(question).answer == answer


def test_a_table_cell_potential_keeps_the_tables_hundredths() -> None:
    result = _solve("Find the galvanic cell for Al and Cu")
    assert result.answer.startswith("E°cell = 2.00 V\n")
    assert result.given == ("Al E° = -1.66 V", "Cu E° = 0.34 V")


def test_a_molar_mass_stays_full_precision_until_the_answer() -> None:
    # 4.000 / 2.016 × 18.015 is 35.74 g; rounding to 2.02 and 18.02 first gave 35.68 g.
    water = _solve("How many grams of water are produced from 4.000 g of H2 in 2H2 + O2 -> 2H2O?")
    assert water.answer == "m(H2O) = 35.74 g"
    assert water.substitution[-1] == "m(H2O) = 1.9841 mol × 18.015 g/mol = 35.74 g"
    excess = _solve(
        "In 2H2 + O2 -> 2H2O, 10.00 g of H2 reacts with 64.00 g of O2. Find the limiting reagent."
    )
    assert "excess H2 = (4.9603 mol − 4.0003 mol) × 2.016 g/mol = 1.935 g" in excess.substitution
    assert _solve("What is the molar mass of H2SO4?").answer == "M(H2SO4) = 98.07 g/mol"


def test_numbers_outside_a_solve_keep_the_default_format() -> None:
    assert num(2.0) == "2"
    assert p_value(4.7447) == "4.745"


@pytest.mark.parametrize(
    "written",
    [{"1.0": "<b>1</b>"}, {"1.0": "1 kg"}, {"1.0": "1" * 33}],
    ids=["markup", "unit", "too-long"],
)
def test_written_holds_only_a_number_as_typed(written: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        ChemistryIntent(kind="amounts", chemistry_op="molar_mass", formula="H2O", written=written)


def test_a_long_literal_is_not_recorded() -> None:
    intent = extract_chemistry_intent(
        "How many moles are in 36.000000000000000000000000000001 g of H2O?"
    )
    assert intent is not None
    assert intent.written == {}
    ChemistryIntent.model_validate(intent.model_dump())


@pytest.mark.parametrize(
    ("question", "rows", "answer"),
    [
        # 2026-11-06: "4.0 × 18.015 = 71" looked wrong, and the student's "isn't it 72?" was
        # conceded. A value carried into the next line keeps two figures past the answer's.
        (
            "how many grams of water are made when 8.0 g of hydrogen gas reacts with enough oxygen",
            (
                "n(H2) = 8.0 g / 2.016 g/mol = 3.968 mol",
                "m(H2O) = 3.968 mol × 18.015 g/mol = 71 g",
            ),
            "m(H2O) = 71 g",
        ),
        (
            "10 g of H2 and 64 g of O2 react to form water. which is the limiting reactant and "
            "how much water forms",
            (
                "n(H2) = 10 g / 2.016 g/mol = 4.960 mol",
                "excess H2 = (4.960 mol − 4.000 mol) × 2.016 g/mol = 1.9 g",
            ),
            "Limiting reagent = O2; 72 g H2O",
        ),
    ],
)
def test_a_carried_value_keeps_figures_past_the_answer(
    question: str, rows: tuple[str, ...], answer: str
) -> None:
    result = _solve(question)
    assert all(row in result.substitution for row in rows), result.substitution
    assert result.answer == answer


# Textbook examples, each worked by hand from the rules of OpenStax Chemistry 2e §1.5
# (products and quotients keep the fewest significant figures, sums and differences the
# fewest decimal places, counts and defined conversions are exact, rounding at the end) and
# §14.2 (a logarithm keeps as many decimals as its value has figures). The card has these
# figures, not two decimal places (owner, 2026-11-23).
@pytest.mark.parametrize(
    ("question", "answer"),
    [
        # 36 g (2 s.f.) / 18.015 g/mol = 1.998 mol -> 2.0 mol, its zero a figure.
        ("How many moles are in 36 g of H2O?", "n(H2O) = 2.0 mol"),
        # 4 g (1 s.f.) of H2 -> 35.74 g of water -> one figure, 4 x 10^1 g: "40 g" would read
        # as two figures, so a textbook writes the power of ten.
        ("how much water do i get if i burn 4 g of hydrogen", "m(H2O) = 4 × 10^1 g"),
        # 25.00 mL, 0.1000 M and 32.45 mL have four figures each: 0.1298 M, not 0.130.
        (
            "25.00 mL of HCl is titrated with 0.1000 M NaOH and it takes 32.45 mL to reach "
            "the endpoint. What is the concentration of HCl?",
            "c₂ = 0.1298 mol/L",
        ),
        # 0.200 M x 25.0 mL / 100.0 mL = 0.05 M to three figures: 0.0500, its zeros kept.
        (
            "If 25.0 mL of 0.200 M NaOH is diluted to 100.0 mL, what's the new concentration",
            "c2 = 0.0500 mol/L",
        ),
        # 3.5 mol (2 s.f.) x 98.072 g/mol = 343.3 g -> 3.4 x 10^2 g.
        ("What is the mass of 3.5 mol of H2SO4 in grams", "m(H2SO4) = 3.4 × 10^2 g"),
        # 2.5 mol x 44.009 g/mol = 110.02 g -> two figures: 1.1 x 10^2 g, never "110 g".
        ("What is the mass of 2.5 mol of CO2?", "m(CO2) = 1.1 × 10^2 g"),
        # The equation's 2 is a count: 3.0 mol (2 s.f.) of CH4 needs 6.0 mol of O2.
        (
            "how many moles of O2 are needed to burn 3.0 mol of CH4? CH4 + 2O2 -> CO2 + 2H2O",
            "n(O2) = 6.0 mol",
        ),
        # 1000 mL/L is defined: 0.25 mol (2 s.f.) in 750 mL (3 s.f.) is 0.33 M.
        ("molarity of 0.25 mol KCl in 750 mL of water", "c = 0.33 mol/L"),
        # Scientific notation in the question: 2.50 x 10^-3 M has three figures, so its pH
        # has three decimals: -log(0.00250) = 2.60206 -> 2.602.
        ("What is the pH of 2.50 × 10^-3 M HCl?", "pH = 2.602"),
        # 0.01 M has one figure: pH 2.0, one decimal.
        ("What is the pH of 0.01 M hcl?", "pH = 2.0"),
        # A difference keeps the fewest decimal places: -393.5 - (-283.0) = -110.5 kJ.
        (
            "Given C + O2 → CO2 ΔH = -393.5 kJ and CO + 1/2 O2 → CO2 ΔH = -283.0 kJ, "
            "find ΔH for C + 1/2 O2 → CO",
            "ΔH = -110.5 kJ",
        ),
    ],
)
def test_a_card_follows_the_textbook_rule(question: str, answer: str) -> None:
    assert _solve(question).answer == answer


def test_each_working_row_ends_unrounded_above_a_rounded_card() -> None:
    """The limiting reagent's yield row is not the working's last: it ends on 33.79 g as
    worked, and only the card rounds it to the data's one figure."""
    intent = extract_chemistry_intent(
        "how many grams of NH3 can be made from 28 g of nitrogen and 6 g of hydrogen"
    )
    assert intent is not None
    verified = build_verified_chemistry(intent)
    assert verified is not None
    assert verified.result.answer == "Limiting reagent = H2; 3 × 10^1 g NH3"
    reply = format_direct_chemistry_reply(verified)
    working = reply.split("**Answer**")[0]
    assert "= 33.79" in working
    assert "10^{1}" not in working
    # A difference of carried values loses what the full value keeps: (0.9995 − 0.9921) ×
    # 28.014 is 0.2073, not the 0.2083 worked in full, so that row ends rounded.
    assert "× 28.014 g/mol = 0.2 g" in working


@pytest.mark.parametrize(
    ("question", "figures", "given", "answer"),
    [
        # "i = 2" is a count; "2 mol" is measured and typed with the same spelling, so it
        # keeps its one figure: ΔTf = 2 × 1.86 × 1 = 3.72 °C, Tf = −4 °C.
        (
            "What is the freezing point of a solution of 2 mol NaCl (i = 2) in 2.0 kg water? "
            "Kf = 1.86 °C kg/mol",
            1,
            "n(solute) = 2 mol",
            "Tf = -4 °C",
        ),
        # "n = 2" is the count alone: 2.0 A keeps two figures, and the count is never shown
        # in the current's spelling.
        (
            "What mass of Cu is deposited by a current of 2.0 A for 30 min? n = 2",
            2,
            "n = 2",
            "m = 1.2 g",
        ),
        # The count's "2" is not the 2.00 h a unit change made 7200 s (review).
        (
            "What mass of Cu is deposited by a current of 1.50 A for 2.00 h? n = 2",
            3,
            "t = 2.00 h = 7200 s",
            "m = 3.56 g",
        ),
        # A ratio the equation gives owns no typed spelling: "1 M HCl" keeps one figure.
        (
            "What volume of 1.00 M NaOH is needed to neutralize 25.0 mL of 1 M HCl?",
            1,
            "c₂ = 1 mol/L",
            "V₂ = 3 × 10^1 mL",
        ),
        # A derived count of the same value never hides a typed one: 2.0 mol is echoed.
        ("How many oxygen atoms are in 2.0 mol of CO2?", 2, "n(CO2) = 2.0 mol", None),
        # A length's x10 never makes a volume ambiguous: 400 mL stays the typed 0.400 L.
        (
            "How many grams of NaCl are needed to make 400 mL of a 4.00 M solution?",
            3,
            "V = 400 mL = 0.400 L",
            "m = 93.5 g",
        ),
        # A count the solver fills in (copper's two electrons) owns no spelling: "2 h" is
        # the time's, so the answer has one figure (review).
        (
            "What mass of Cu is deposited by a current of 2.00 A for 2 h?",
            1,
            "n = 2",
            "m = 5 g",
        ),
        # The same for a van 't Hoff factor read from the formula: "2 kg" keeps one figure.
        (
            "What is the freezing point of a solution of 2.00 mol NaCl in 2 kg water? "
            "Kf = 1.86 °C kg/mol",
            1,
            "i = 2",
            "Tf = -4 °C",
        ),
        # An exact whole answer with a zero that is no figure is a power of ten too.
        ("How many mL of 5 M HCl make 100 mL of 1 M HCl?", 1, "c1 = 5 mol/L", "V1 = 2 × 10^1 mL"),
    ],
)
def test_a_count_takes_only_its_own_spelling(
    question: str, figures: int, given: str, answer: str | None
) -> None:
    intent = extract_chemistry_intent(question)
    assert intent is not None
    assert intent.figures == figures
    result = solve_chemistry(intent)
    assert given in result.given
    assert answer is None or result.answer == answer


@pytest.mark.parametrize(
    ("question", "row"),
    [
        # RT is carried into Kp's row, never its one-figure card value: (0.5)(2 x 10^1)^-2
        # is no 8 x 10^-4.
        ("Convert Kc to Kp: Kc=0.5 at T=298 K for N2 + H2 -> NH3", "Kp = (0.5)(24.453)^-2"),
        # A stoichiometric factor is exact: 27, never one figure's 3 x 10^1 (review).
        ("The Ksp of Fe(OH)3 is 4 × 10^-38. Find its molar solubility.", "= (s)(3s)^3 = 27s^4"),
    ],
)
def test_a_working_row_works_with_carried_values(question: str, row: str) -> None:
    assert any(row in line for line in _solve(question).substitution)


def test_a_negative_power_is_no_rounded_number() -> None:
    """``(24.45)^-2`` works with no rounded 2: the closing row ends unrounded (review)."""
    intent = extract_chemistry_intent(
        "Convert Kp to Kc: Kp=0.003 at T=298 K for N2 + 3 H2 -> 2 NH3"
    )
    assert intent is not None
    verified = build_verified_chemistry(intent)
    assert verified is not None
    working = format_direct_chemistry_reply(verified).split("**Answer**")[0]
    assert "K_{c} = 1.794" in working


@pytest.mark.parametrize(
    ("question", "answer"),
    [
        # Atom counts are exact: C21H23N has an IHD of 11, never one figure's 1 x 10^1.
        (
            "The carbon count is 21, the hydrogen count is 23, the nitrogen count is 1, "
            "and the halogen count is 0. Find the index of hydrogen deficiency.",
            "IHD = 11",
        ),
        # 5 m has one figure: ΔTf = 18.6 °C is 2 x 10^1 °C, and the freezing point is known
        # to the same ten, never -19 °C (review).
        (
            "What is the freezing point of a 5 m NaCl solution in water? Kf = 1.86 °C/m",
            "Tf = -2 × 10^1 °C",
        ),
        # A carry counts: ΔTf = 9.789 °C to the ten is 1 x 10^1, so Tf is -1 x 10^1 °C, never 0.
        (
            "What is the freezing point of a solution of 5 mol NaCl in 1.9 kg of water? "
            "Kf = 1.86 °C/m",
            "Tf = -1 × 10^1 °C",
        ),
        # "a 2-hour electrolysis" is measured: the count's "2" is not its spelling.
        (
            "What mass of Cu is deposited by a current of 2.00 A in a 2-hour electrolysis?",
            "m = 5 g",
        ),
        # A unit's power is no typed number: the 1 of "s-1" is not the 1.00 M (review).
        (
            "A first-order reaction has k = 0.0450 s-1. If [A]0 = 1.00 M, "
            "what is [A] after 10.0 s?",
            "[A]ₜ = 0.638 mol/L",
        ),
        # A formula's digit is no typed number: the 3 of "Fe2(SO4)3" is not the 3.00 mol.
        ("What is the mass of 3.00 mol of Fe2(SO4)3?", "m(Fe2(SO4)3) = 1.20 × 10^3 g"),
        ("What is the mass of 5.00 mol of CuSO4·5H2O?", "m(CuSO4·5H2O) = 1.25 × 10^3 g"),
        # O₂'s typed ΔHf° = 0 gives no decimal: the sum keeps one place (review).
        (
            "Calculate ΔH for CH4 + 2O2 -> CO2 + 2H2O. ΔHf values: CH4 = -74.8, O2 = 0, "
            "CO2 = -393.5, H2O = -285.8 kJ/mol",
            "ΔH° = -890.3 kJ/mol",
        ),
        # 0 °C is 273 K, three figures; a zero Celsius reading still limits (review).
        (
            "Gas collected over water at 0 °C, total pressure = 760.0 mmHg, pressure of the dry gas?",
            "Pdry = 755 mmHg",
        ),
    ],
)
def test_counts_zero_celsius_and_powers_of_ten_follow_the_rule(question: str, answer: str) -> None:
    assert _solve(question).answer == answer


def test_a_rounded_row_reading_like_a_count_still_ends_unrounded() -> None:
    """b = 2.143 mol/kg is no 2 because the next row's van 't Hoff factor is a typed-looking
    2 (review)."""
    intent = extract_chemistry_intent(
        "What is the freezing point of a solution of 3 mol NaCl in 1.4 kg of water? Kf = 1.86 °C/m"
    )
    assert intent is not None
    verified = build_verified_chemistry(intent)
    assert verified is not None
    assert "= 2.143\\,\\mathrm{mol/kg}$" in format_direct_chemistry_reply(verified)


@pytest.mark.parametrize(
    ("question", "row"),
    [
        # A difference of carried values in powers of ten stays rounded too (review).
        (
            "how many grams of NH3 can be made from 0.028 g of nitrogen and 0.006 g of hydrogen",
            "× 28.014 g/mol = 2 × 10⁻⁴ g",
        ),
        # The ΔTf row's 4 °C is the value the next row subtracts, though "4 mol" reads alike.
        (
            "What is the freezing point of a solution of 4 mol NaCl in 4.0 kg water? "
            "Kf = 1.86 °C kg/mol",
            "(1.000\\,\\mathrm{mol/kg}) = 4\\,^\\circ\\mathrm{C}$",
        ),
        # A computed pKa is no typed value: its row and the pH row stay rounded (review).
        (
            "What is the pH of the intermediate form when Ka1 = 4.3e-7 and Ka2 = 4.8e-11?",
            "(6.37 + 10.32) / 2 = 8.34$",
        ),
        # "8 g" is not inside the excess row's "31.998 g/mol": the yield row ends unrounded.
        (
            "How many grams of H2O can be made from 0.9 g of H2 and 9 g of O2?",
            "18.015\\,\\mathrm{g/mol} = 8.042\\,\\mathrm{g}$",
        ),
        # RT to five figures: (0.003) / (24.453)^-2 is the 1.794 the closing row ends on.
        ("Convert Kp to Kc: Kp=0.003 at T=298 K for N2 + 3 H2 -> 2 NH3", "K_{c} = 1.794"),
    ],
)
def test_a_working_row_states_what_its_numbers_give(question: str, row: str) -> None:
    intent = extract_chemistry_intent(question)
    assert intent is not None
    verified = build_verified_chemistry(intent)
    assert verified is not None
    assert row in format_direct_chemistry_reply(verified)
