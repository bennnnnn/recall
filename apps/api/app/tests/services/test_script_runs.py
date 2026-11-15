"""One reading of Unicode superscripts and subscripts for every reader.

The readers knew only the raised digits, so a raised letter stayed a character of its own
and SymPy made it a symbol: "Integrate eˣ cos(2x) …" was certified as ˣ·e·sin(2x)/2 and
the derivative of 2ˣ as 0 (grade 12 textbook round, 2026-11-13). The table is Unicode's
whole class, the phone's is held to it by ``docs/fixtures/script_glyphs.json``, and a run
reads as the caret a student types, except where it raises nothing (an ordinal, a sound, a
name).
"""

from __future__ import annotations

import json
import string
import unicodedata
from pathlib import Path

import pytest

from app.modules.math.match.bare_expression import read_bare_expression
from app.modules.math.solve.parse import parse_expression
from app.modules.math.tool_check import _normalize as tool_check_normalize
from app.modules.model_reader.checks import normalized as model_read_normalized
from app.services.glyphs import SUBSCRIPT_GLYPHS, SUPERSCRIPT_GLYPHS
from app.services.number_text import fold_scientific
from app.services.solving import SolveServiceError
from app.services.symbolic_text import normalize_symbolic_request

FIXTURE = Path(__file__).resolve().parents[5] / "docs" / "fixtures" / "script_glyphs.json"
# What a script may raise or lower: a digit, a Latin letter, a sign or a round bracket.
_SCRIPTABLE = set(string.ascii_letters + string.digits + "+=()") | {"−"}


def _unicode_class(tag: str) -> dict[str, str]:
    """Every character whose compatibility form is ``tag`` of one scriptable character."""
    found: dict[str, str] = {}
    for point in range(0x110000):
        parts = unicodedata.decomposition(chr(point)).split()
        if len(parts) == 2 and parts[0] == tag:
            base = chr(int(parts[1], 16))
            if base in _SCRIPTABLE:
                found[chr(point)] = "-" if base == "−" else base
    return found


def test_the_tables_are_unicodes_whole_class() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    raised = {
        glyph: base
        for glyph, base in _unicode_class("<super>").items()
        if glyph not in fixture["not_scripts"]
    }
    assert raised == SUPERSCRIPT_GLYPHS
    assert _unicode_class("<sub>") == SUBSCRIPT_GLYPHS


def test_the_phone_and_the_server_read_one_table() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert fixture["superscript"] == SUPERSCRIPT_GLYPHS
    assert fixture["subscript"] == SUBSCRIPT_GLYPHS
    assert not set(fixture["not_scripts"]) & set(SUPERSCRIPT_GLYPHS)


@pytest.mark.parametrize(
    ("typed", "read"),
    [
        # Raised letters on a maths atom are the power a student types with a caret.
        ("Integrate eˣ cos(2x) dx", "Integrate e^x cos(2x) dx"),
        ("∫ x eˣ dx", "∫ x e^x dx"),
        ("∫ xeˣ dx", "∫ xe^x dx"),
        ("e⁻ˣ", "e^(-x)"),
        ("e²ˣ", "e^(2x)"),
        ("xⁿ⁻¹", "x^(n-1)"),
        ("2ˣ⁺¹", "2^(x+1)"),
        ("2⁽ˣ⁺¹⁾", "2^(x+1)"),
        ("(x+1)ⁿ", "(x+1)^n"),
        ("aᵇ · aᶜ", "a^b · a^c"),
        ("d/dx(xⁿ)", "d/dx(x^n)"),
        ("eᴬ", "e^A"),
        # Glued to a Latin letter, the power is bracketed so it ends where it was raised.
        ("eˣsin x", "e^(x)sin x"),
        ("∫ eˣdx", "∫ e^(x)dx"),
        ("xⁿy", "x^(n)y"),
        # Raised digits read as they always did, a sign now joining a sum: x²⁺¹ was x^2^+1.
        ("x²", "x^2"),
        ("s⁻²", "s^-2"),
        ("10¹²", "10^12"),
        ("x²⁺¹", "x^(2+1)"),
        ("x^{2}", "x^2"),
        # A lowered run on a big operator is its limit; the raised one after it the other.
        ("∫₀¹ eˣ dx", "∫_0^1 e^x dx"),
        ("∫₋₁¹ x² dx", "∫_-1^1 x^2 dx"),
        ("π∫₁ᵉ (ln y)² dy", "π∫_1^e (ln y)^2 dy"),
        # A sign ending a run is a charge, and a lone sign raises nothing.
        ("Fe³⁺", "Fe^3⁺"),
        ("an e⁻ beam", "an e⁻ beam"),
        # An English ordinal's raised suffix is the ordinal typed plain, after a number or a
        # letter: n^(th) was no ordinal, and "the 2ⁿᵈ derivative" no order (2026-11-14).
        ("the 21ˢᵗ century", "the 21st century"),
        ("the 2ⁿᵈ and 3ʳᵈ runners", "the 2nd and 3rd runners"),
        ("the 2ⁿᵈ derivative of x⁴", "the 2nd derivative of x^4"),
        ("the nᵗʰ derivative of e²ˣ", "the nth derivative of e^(2x)"),
        ("the (n+1)ᵗʰ term", "the (n+1)th term"),
        # Raised letters that raise nothing stay as written: another language's ordinal, a
        # sound, a letter after a space or after an accent, one before another alphabet.
        ("le 1ᵉʳ mai", "le 1ᵉʳ mai"),
        ("say pʰɪn", "say pʰɪn"),
        ("the ˣ key", "the ˣ key"),
        ("eⁱᶿ", "eⁱᶿ"),
        # Only a big operator's lowered run is a limit here; a name's stays for the parser.
        ("x₁ + x₂", "x₁ + x₂"),
        ("nº 5 and 30º", "nº 5 and 30º"),
        # A raised index standing on nothing before a root sign is the root's: "2 ³√27" was
        # 2³·√27, a checked 24√3 for 6. On a letter or a number it stays a power.
        ("2 ³√27", "2 ∛27"),
        ("3 ⁴√16 + (³√8)", "3 ∜16 + (∛8)"),
        ("²√9", "√9"),
        ("2 ⁵√32", "2 ⁵√32"),
        ("x²√x", "x^2√x"),
        ("2³√27", "2^3√27"),
        # A run straight after a caret's power raises nothing: e^((2x)^x) or (e^(2x))^x?
        ("e^(2x)ˣ", "e^(2x)ˣ"),
        ("e^2ˣ", "e^2ˣ"),
        ("4^(1/2)⁻¹", "4^(1/2)⁻¹"),
        ("x^{2}³", "x^2³"),
        # A bracket or a letter with no caret before it still takes one.
        ("x^2y²", "x^2y^2"),
        ("(x^2)³", "(x^2)^3"),
        ("sin(x)²", "sin(x)^2"),
        # One raised run is one exponent, on base 10 too: 10²ˣ was the literal 10² to the x.
        ("10²ˣ = 1000", "10^(2x) = 1000"),
        ("10⁻³ˣ", "10^(-3x)"),
        ("10²ˣ⁻¹", "10^(2x-1)"),
        ("10²⁺¹", "10^(2+1)"),
    ],
)
def test_a_run_reads_as_the_power_it_writes(typed: str, read: str) -> None:
    assert normalize_symbolic_request(typed) == read


@pytest.mark.parametrize(
    ("typed", "folded"),
    [
        # The literal is the whole raised run, or it gives way to the shared reading.
        ("Solve 10²ˣ = 1000", "Solve 10²ˣ = 1000"),
        ("10⁻³ˣ + 10²⁺¹", "10⁻³ˣ + 10²⁺¹"),
        ("10⁻¹²³⁴", "10⁻¹²³⁴"),
        # Scientific notation still reads as one exact number.
        ("1.8·10⁻⁵", "1.8*10^(-5)"),
        ("2 × 10⁻⁶ C", "2*10^(-6) C"),
        ("6.02 × 10²³ mol⁻¹", "6.02*10^23 mol⁻¹"),
        ("10³ˣ = 10⁶", "10³ˣ = 10^6"),
    ],
)
def test_a_scientific_literal_is_the_whole_raised_run(typed: str, folded: str) -> None:
    assert fold_scientific(typed, style="product") == folded


@pytest.mark.parametrize(
    ("typed", "value"),
    [("2 ⁵√32", 4), ("⁵√32 + 1", 3), ("3 ⁴√16", 6), ("(³√27)", 3)],
)
def test_the_parser_reads_a_raised_index_as_the_root(typed: str, value: int) -> None:
    assert parse_expression(typed) == value


@pytest.mark.parametrize(
    ("typed", "caret"),
    [
        ("eˣ cos(2x)", "e^x cos(2x)"),
        ("x² eˣ", "x^2 e^x"),
        ("e⁻ˣ", "e^(-x)"),
        ("e⁻²ˣ", "e^(-2x)"),
        ("2ˣ⁺¹", "2^(x+1)"),
        ("xⁿ⁻¹", "x^(n-1)"),
        ("aᵇ⁺ᶜ", "a^(b+c)"),
        ("x⁻¹", "x^(-1)"),
        ("eˣsin x", "e^x sin(x)"),
        ("x₁ + aₙ", "x_1 + a_n"),
    ],
)
def test_the_parser_reads_a_run_as_the_caret(typed: str, caret: str) -> None:
    assert parse_expression(typed) == parse_expression(caret)


@pytest.mark.parametrize(
    "typed",
    ["e ˣ", "eⁱᶿ", "aₙ₊₁ + 1", "pʰɪn", "e^(2x)ˣ", "4^(1/2)⁻¹", "e^(2x)²", "e^2ˣ", "x^{2}³"],
)
def test_a_raised_letter_no_power_holds_is_never_a_symbol(typed: str) -> None:
    with pytest.raises(SolveServiceError):
        parse_expression(typed)


@pytest.mark.parametrize(
    ("typed", "read"),
    [("What is 3x⁴", "3x^{4}"), ("what is xⁿ", "x^{n}"), ("what is 2xʸ", "2x^{y}")],
)
def test_the_bare_expression_reader_reads_every_raised_power(typed: str, read: str) -> None:
    expression = read_bare_expression(typed)
    assert expression is not None and expression.text == read


def test_the_tool_check_and_the_model_read_check_read_the_caret() -> None:
    assert tool_check_normalize("∫ x eˣ dx") == "∫ x e^x dx"
    assert tool_check_normalize("x²³") == "x^23"
    assert model_read_normalized("v = 2ˣ m/s") == model_read_normalized("v = 2^x m/s")
