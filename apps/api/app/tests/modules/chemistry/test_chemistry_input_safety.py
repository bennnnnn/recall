"""Hostile input, gate precision, scientific notation and the PubChem time budget."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry import context as chemistry_context
from app.modules.chemistry.equations import balance_equation
from app.modules.chemistry.extract import extract_chemistry_intent
from app.modules.chemistry.request import extract_compound_name, is_chemistry_question

# The old regex needed seconds. Anything linear finishes in a few milliseconds.
_BUDGET_SECONDS = 0.25


@pytest.fixture(scope="module", autouse=True)
def _warm_lazy_imports() -> None:
    """SymPy imports on the first balance (~0.3 s); that is not what these tests time."""
    assert balance_equation("H2 + O2 -> H2O").balanced


@pytest.mark.parametrize(
    "text",
    [
        "A" * 20_000,
        "H2" * 4_000,
        "how many limiting reagent H2 -> H2O " + "a" * 40,
        "Balance " + "Aa" * 2_000 + " -> X",
        "[" + "A" * 40 + "] = 1 Kc",
        "H2 + O2 -> " + "H2O + " * 500,
        "mole " * 4_000,
    ],
    ids=[
        "uppercase-run",
        "formula-run",
        "limiting-letter-run",
        "equation-letter-run",
        "bracket-letter-run",
        "long-term-list",
        "repeated-cue",
    ],
)
def test_hostile_input_returns_quickly(text: str) -> None:
    start = time.perf_counter()
    is_chemistry_question(text)
    extract_chemistry_intent(text)
    assert time.perf_counter() - start < _BUDGET_SECONDS


@pytest.mark.parametrize(
    "text",
    [
        "What is love?",
        "What is python",
        "what is java",
        "What is your name?",
        "Tell me about Charles Darwin",
        "Tell me about yourself",
        "Lewis Hamilton won again",
        "Who was John Dalton?",
        "what is compound interest",
        "show me the bond yield",
        "how many KB is this file",
        "my Ph.D. advisor is Charles",
        "acid reflux remedies",
        "Explain nuclear power policy",
        "nuclear family",
        "how long do I keep boiling potatoes",
        "kinetic energy of a 2 kg ball",
        "How do I fix the base case of this recursion",
        "moles on my skin",
        "my molar hurts",
        "empirical evidence for this claim",
        "the freezing weather today",
        "precipitation tomorrow in Seattle",
        "buffer overflow in my C code",
    ],
)
def test_everyday_language_is_not_a_chemistry_question(text: str) -> None:
    assert is_chemistry_question(text) is False


@pytest.mark.parametrize(
    "text",
    [
        "Explain electrochemistry",
        "Explain thermochemistry to me",
        "What is the electronegativity of Cs?",
        "electron configuration of Fe",
        "What is the atomic number of gold?",
        "what is aspirin?",
        "what is caffeine",
        "what is the structure of aspirin?",
        "Ka of acetic acid is 1.8e-5, what is the pH?",
        "Kb = 1.8e-5, what is pKb",
        "Boyle's law problem: P1 = 2 atm, V1 = 3 L, P2 = 1 atm",
        "Hess's law with ΔH1 = -100 kJ",
        "the freezing point depression of a 0.5 m solution",
        "the boiling point elevation of a 0.5 m solution",
        "Lewis structure of CO2",
        "oxidation state of Mn in KMnO4",
        "coordination number of [Co(NH3)6]Cl3",
    ],
)
def test_real_chemistry_language_still_passes_the_gate(text: str) -> None:
    assert is_chemistry_question(text) is True


@pytest.mark.parametrize(
    "text",
    ["what is your name", "what is love", "what is python", "tell me about Charles Darwin"],
)
def test_bare_what_is_needs_a_compound_shaped_name(text: str) -> None:
    assert extract_compound_name(text) is None


@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("what is aspirin?", "aspirin"),
        ("what is glucose", "glucose"),
        ("what is acetone?", "acetone"),
        ("structure of caffeine", "caffeine"),
        ("draw the molecule adenosine", "adenosine"),
        ("tell me about ibuprofen", "ibuprofen"),
    ],
)
def test_compound_names_still_resolve(text: str, name: str) -> None:
    assert extract_compound_name(text) == name


@pytest.mark.parametrize(
    "phrase",
    [
        "1.8 × 10^-5",
        "1.8x10^-5",
        "1.8×10⁻⁵",
        "1.8 * 10^{-5}",
        "1.8 \\times 10^{-5}",
        "1.8 · 10^-5",
        "1.8e-5",
    ],
)
def test_scientific_notation_keeps_its_exponent(phrase: str) -> None:
    intent = extract_chemistry_intent(f"Find the pH of a weak acid 0.10 M HA with Ka = {phrase}")
    assert intent is not None
    assert intent.chemistry_op == "weak_acid_ph"
    assert intent.params["ka"] == pytest.approx(1.8e-5)


def test_scientific_notation_in_a_concentration() -> None:
    intent = extract_chemistry_intent("Find pH when [H+] = 2.5 × 10^-4")
    assert intent is not None
    assert intent.params["h"] == pytest.approx(2.5e-4)


def test_a_bare_multiplication_is_not_scientific_notation() -> None:
    intent = extract_chemistry_intent("Find pH when [H+] = 3 x 10 pH")
    assert intent is None or intent.params["h"] == pytest.approx(3.0)


@pytest.mark.parametrize("field", ["formula", "equation", "target"])
def test_intent_text_fields_are_bounded(field: str) -> None:
    with pytest.raises(ValidationError):
        ChemistryIntent.model_validate(
            {"kind": "organic", "chemistry_op": "functional_groups", field: "C" * 501}
        )


def test_intent_collections_are_bounded() -> None:
    with pytest.raises(ValidationError):
        ChemistryIntent(
            kind="analytical",
            chemistry_op="standard_deviation",
            samples=[1.0] * 51,
        )
    with pytest.raises(ValidationError):
        ChemistryIntent(
            kind="equilibrium",
            chemistry_op="equilibrium_constant",
            species={f"X{index}": 1.0 for index in range(21)},
        )


async def test_slow_pubchem_does_not_hold_the_turn(monkeypatch: pytest.MonkeyPatch) -> None:
    async def slow_lookup(name: str, redis: object | None = None) -> object:
        await asyncio.sleep(5)
        raise AssertionError("the budget should have cancelled this lookup")

    monkeypatch.setattr(chemistry_context.pubchem_gateway, "lookup_by_name", slow_lookup)
    monkeypatch.setattr(chemistry_context, "PUBCHEM_BUDGET_SECONDS", 0.05)
    start = time.perf_counter()
    result = await chemistry_context.build_chemistry_augmentation(
        "what is the structure of aspirin?", MagicMock()
    )
    assert result == (chemistry_context.unverified_chemistry_note(), None, True)
    assert time.perf_counter() - start < 1.0


async def test_a_non_chemistry_sentence_is_untouched_when_pubchem_would_fail() -> None:
    result = await chemistry_context.build_chemistry_augmentation("what is 2 + 2?", MagicMock())
    assert result == (None, None, False)


@pytest.mark.parametrize(
    "text",
    [
        "What is the molar mass of " + "C" * 400 + "H" * 800,
        "Balance " + "H2 + " * 300 + "O2 -> H2O",
        "Identify functional groups in SMILES " + "C" * 600,
    ],
    ids=["formula", "equation", "smiles"],
)
def test_a_value_the_schema_refuses_declines_instead_of_raising(text: str) -> None:
    assert extract_chemistry_intent(text) is None


def test_an_extractor_exception_declines(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def broken(_text: str) -> None:
        raise RuntimeError("balance failed")

    monkeypatch.setattr("app.modules.chemistry.extract.EXTRACTORS", (broken,))
    with caplog.at_level("ERROR"):
        assert extract_chemistry_intent("Find the molar mass of water") is None
    assert "chemistry extractor broken failed" in caplog.text


def test_an_extractor_cancellation_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    def cancelled(_text: str) -> None:
        raise asyncio.CancelledError()

    monkeypatch.setattr("app.modules.chemistry.extract.EXTRACTORS", (cancelled,))
    with pytest.raises(asyncio.CancelledError):
        extract_chemistry_intent("Find the molar mass of water")
