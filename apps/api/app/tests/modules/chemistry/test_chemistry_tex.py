"""A chemistry row as maths, laid out as physics' rows are (live, 2026-11-02).

"How many moles are in 36 g of water?" showed Given "mass = 36 g" beside the formula's m,
its substitution as plain text with no result line, and its card in the body font, where
physics shows maths throughout.
"""

from __future__ import annotations

import pytest

from app.modules.chemistry.block import build_verified_chemistry
from app.modules.chemistry.direct import format_direct_chemistry_reply
from app.modules.chemistry.extract import extract_chemistry_intent
from app.modules.chemistry.glossary import given_meaning
from app.modules.chemistry.tex import chemistry_tex, law_symbols, symbol_tex


@pytest.mark.parametrize(
    ("row", "tex"),
    [
        ("n = 36 g / 18.015 g/mol", r"n = 36\,\mathrm{g} / 18.015\,\mathrm{g/mol}"),
        ("M(H2O) = 18.015 g/mol", r"M(\mathrm{H₂O}) = 18.015\,\mathrm{g/mol}"),
        ("pH = −log10(0.001)", r"\mathrm{pH} = -\log_{10} (0.001)"),
        ("[H+] = 1.0 × 10^-4 mol/L", r"[\mathrm{H⁺}] = 1.0 \times 10^{-4}\,\mathrm{mol/L}"),
        ("Ka = 1.8 × 10^-5", r"K_{a} = 1.8 \times 10^{-5}"),
        ("E°cell = 0.34 − (-0.76)", r"E^\circ_{cell} = 0.34 - (-0.76)"),
        ("t₁/₂ = ln(2) / k", r"t_{1/2} = \ln (2) / k"),
        ("ΔHvap = 12 kJ/mol", r"\Delta H_{vap} = 12\,\mathrm{kJ/mol}"),
        ("T = 25 °C", r"T = 25\,^\circ\mathrm{C}"),
        ("n(H2O) = 4.0 mol H2O", r"n(\mathrm{H₂O}) = 4.0\,\mathrm{mol}\ \mathrm{H₂O}"),
        ("m(solute) = 18.0 g", r"m(\text{solute}) = 18.0\,\mathrm{g}"),
        ("C = 40.0%", r"\mathrm{C} = 40.0\,\%"),
        # Numbered symbols are symbols, never a compound: C₂V₂ beside C₁V₁, V₂ alone.
        ("M1V1 = M2V2", "M_{1} V_{1} = M_{2} V_{2}"),
        ("C₁V₁ = C₂V₂", "C_{1} V_{1} = C_{2} V_{2}"),
        ("V2 = 200 mL", r"V_{2} = 200\,\mathrm{mL}"),
        # "Ae^" is A times e to a power; "MIt" is M·I·t.
        ("k = Ae^(−Ea/(RT))", "k = Ae^{-E_{a}/(R T)}"),
        ("m = MIt / nF", "m = M I t / n F"),
    ],
)
def test_a_formula_row_is_maths(row: str, tex: str) -> None:
    assert chemistry_tex(row) == tex


@pytest.mark.parametrize(
    "row",
    [
        "Balanced equation: 2 H2 + O2 -> 2 H2O",
        "limiting reagent = O2 (fewest reaction units)",
        "Formula = H2O",
        "pKw = 14 at 25 °C",
        "mass % = (5 g / 20 g) × 100",
        "x = 0.62 (the root that keeps every concentration non-negative)",
        "2H",
    ],
)
def test_a_sentence_or_an_equation_stays_text(row: str) -> None:
    assert chemistry_tex(row) is None


def test_a_laws_own_symbols_are_never_elements() -> None:
    """Bond order's Nb and Na are symbols, not niobium and sodium."""
    symbols = law_symbols("BO = (Nb − Na) / 2")
    assert chemistry_tex("BO = (Nb − Na) / 2", symbols) == "B O = (N_{b} - N_{a}) / 2"
    assert chemistry_tex("Zn E° = -0.76 V") == r"\mathrm{Zn} E^\circ = -0.76\,\mathrm{V}"


@pytest.mark.parametrize(
    ("asked", "tex"),
    [("pH", r"\mathrm{pH}"), ("Kc", "K_{c}"), ("[H+]", r"[\mathrm{H⁺}]"), ("Moles of H2O", None)],
)
def test_symbol_tex(asked: str, tex: str | None) -> None:
    assert symbol_tex(asked) == tex


@pytest.mark.parametrize(
    ("row", "meaning"),
    [
        ("m = 36 g", "mass"),
        ("m = 0.5 mol/kg", "molality"),
        ("M(H2O) = 18.015 g/mol", "molar mass"),
        ("M1 = 2 mol/L", "molarity"),
        ("Nₐ = 6.0221 × 10^23 mol⁻¹", "Avogadro constant"),
        ("k = 0.1", None),
        ("[H+] = 0.001 mol/L", None),
    ],
)
def test_a_givens_meaning_is_read_from_its_symbol_and_unit(row: str, meaning: str | None) -> None:
    assert given_meaning(row) == meaning


def test_the_moles_of_water_reply_is_laid_out_as_physics() -> None:
    intent = extract_chemistry_intent("How many moles are in 36 g of water?")
    assert intent is not None
    verified = build_verified_chemistry(intent)
    assert verified is not None
    reply = format_direct_chemistry_reply(verified)
    assert reply.startswith(
        "**Given**  \n$m = 36\\,\\mathrm{g}$  \n$M(\\mathrm{H₂O}) = 18.015\\,\\mathrm{g/mol}$  \n"
        "where $m$ = mass, $M(\\mathrm{H₂O})$ = molar mass\n\n**Required**  \n$n$ (amount)"
    )
    assert (
        "**Substitution**  \n$n = 36\\,\\mathrm{g} / 18.015\\,\\mathrm{g/mol}$  \n"
        "$n = 1.998\\,\\mathrm{mol}$\n\n**Answer**"
    ) in reply
    assert reply.rstrip().endswith("```answer\nn(\\mathrm{H₂O}) = 2.0\\,\\mathrm{mol}\n```")
