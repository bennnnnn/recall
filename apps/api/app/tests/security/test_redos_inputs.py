"""Readers of the user's words finish fast on input built to make a regex backtrack.

Each case is one of CodeQL's code-scanning alerts (py/polynomial-redos, py/regex-injection,
js/redos's server twin): before the fix, these inputs took seconds (a chat message may be
32,000 characters), or exponential time for the SMILES check. ``timeout(1)`` fails a case
that backtracks again; each now runs in milliseconds.
"""

from __future__ import annotations

import pytest

from app.content.legal import contact_markdown, markdown_to_html
from app.modules.chat.notation_spans import code_notation, is_notation
from app.modules.chat.posed_read import without_cheer
from app.modules.chemistry.extractors.atom_particles import _placeholder
from app.modules.math.match.spoken import _OVER, _fraction, _tight_carets, spoken_math_to_plain
from app.modules.physics import force_pictures, force_rigs
from app.modules.physics.binding import bind_physics_intent, drop_unit_request
from app.modules.physics.numbers import _LENGTH_BEFORE_PLANK
from app.modules.turn_reading.chart import _names_a_curve, is_chart_question
from app.modules.web_search.release_asks import _bare_thing, released_thing

# Twice the longest chat message. At half this, the old patterns took 1-5 s or more (the plank
# check, already linear, excepted); the new ones take milliseconds.
N = 64_000
SPACES = " " * N

# Only the test body is timed: the first test also pays for the suite's autouse fixtures.
pytestmark = pytest.mark.timeout(1, func_only=True)


@pytest.mark.parametrize(
    "text",
    [
        "draw a line graph of y =" + SPACES + "!",
        "draw a line graph of " + "y=" * (N // 2),
        "draw a line graph of " + "y = " * (N // 4),
    ],
)
def test_chart_curve_check_is_linear(text):
    assert is_chart_question(text) is True


@pytest.mark.parametrize(
    "text, curve",
    [
        ("y = 2x + 1", True),
        ("Y=X", True),
        ("f(x) = x^2", True),
        ("F ( X )", True),
        ("y =\n  2x", True),
        ("y = 2, then x", False),
        ("y = 3; x = 2", False),
        ("y = a\nx", False),
        ("y = y = x", True),
        ("y = 2; y = 3x", True),
        ("my sales by month", False),
        ("y = 4", False),
        ("ay = 2x", False),
    ],
)
def test_names_a_curve_reads_as_the_old_pattern(text, curve):
    assert _names_a_curve(text) is curve


def test_plank_length_reads_a_run_of_digits_once():
    assert _LENGTH_BEFORE_PLANK.sub(r"\1 long \2", "0" * N) == "0" * N
    assert _LENGTH_BEFORE_PLANK.sub(r"\1 long \2", "a 20 m plank") == "a 20 m long plank"
    assert _LENGTH_BEFORE_PLANK.sub(r"\1 long \2", "1.20 m plank") == "1.20 m long plank"
    assert _LENGTH_BEFORE_PLANK.sub(r"\1 long \2", "x20 m plank") == "x20 m plank"


def test_unit_request_reads_a_run_of_spaces_once():
    assert drop_unit_request("a" + SPACES + "b") == "a" + SPACES + "b"
    assert drop_unit_request(", " * (N // 2)) == ", " * (N // 2)
    assert bind_physics_intent("a" + SPACES + "b") is None


@pytest.mark.parametrize(
    "asked, kept",
    [
        ("Find his speed, and write the correct unit of speed.", "Find his speed."),
        ("Find his speed and write the unit.", "Find his speed."),
        ("Find v (in m/s) and give its SI unit?", "Find v (in m/s)?"),
        ("Find v. Then state the units.", "Find v.."),
        ("Find v and write a poem.", "Find v and write a poem."),
    ],
)
def test_unit_request_drops_as_before(asked, kept):
    assert drop_unit_request(asked) == kept


def test_release_thing_reads_a_run_of_spaces_once():
    assert _bare_thing("a" + SPACES + "b") == "a" + SPACES + "b"
    assert _bare_thing("a" + SPACES + "of" + SPACES) == "a"
    assert _bare_thing("the iPhone 19  of") == "iPhone 19"
    assert _bare_thing("what is the proof") == "proof"
    assert _bare_thing("of") == "of"
    assert released_thing("x " + "release date " * (N // 13) + "y") is None
    assert released_thing("what's the release date of GTA 6") == "GTA 6"


@pytest.mark.parametrize(
    "text",
    ["0" * N + " over 2", "1 " * (N // 2), "x" + SPACES + "y", "x" + SPACES + "^" + SPACES],
)
def test_spoken_maths_is_linear(text):
    spoken_math_to_plain(text)


@pytest.mark.parametrize(
    "text, fraction",
    [
        ("3 over 4", "3 / 4"),
        ("x12 over 3", "x12 / 3"),
        ("1.5 over x", "1.5 / x"),
        ("(a+b) over 2", "(a+b) / 2"),
        ("y over (x", "y / (x"),
        ("1 over 2 over 3", "1 / 2 over 3"),
        ("2x over 3", "2x over 3"),
    ],
)
def test_over_reads_fractions_as_before(text, fraction):
    assert _OVER.sub(_fraction, text) == fraction


@pytest.mark.parametrize(
    "text, tight",
    [
        ("x ^ 2", "x^2"),
        ("a ^ ^ b", "a^^b"),
        ("\t^\n", "^"),
        ("x ^ 2 ^3", "x^2^3"),
        ("no caret ", "no caret "),
        ("^", "^"),
    ],
)
def test_tight_carets_matches_the_old_substitution(text, tight):
    assert _tight_carets(text) == tight


@pytest.mark.parametrize("angle", [force_pictures._ANGLE, force_rigs._ANGLE])
def test_angle_reads_a_run_of_spaces_once(angle):
    assert angle.search("1" + SPACES + "x") is None
    assert angle.search("a 30 - degree incline")[1] == "30"
    assert angle.search("banked at 15°")[1] == "15"


def test_legal_links_and_contact_read_brackets_once():
    markdown_to_html("[" * N, page_title="t")
    markdown_to_html("[](/" + "[!](/" * (N // 5), page_title="t")
    assert contact_markdown("a@" + "." * N + "@") == contact_markdown("")
    page = markdown_to_html("See [our terms](/legal/terms).", page_title="t")
    assert '<a href="/legal/terms">our terms</a>' in page
    assert contact_markdown("help@mail.example.co.uk").startswith("email [help@")


def test_smiles_check_is_linear_on_a_long_run_of_letters():
    assert not is_notation("C(=O)" + "Bb" * N + "z")
    code_notation("C(=O)" + "Bb" * N + "z")
    assert is_notation("CC(=O)O") and is_notation("ClC(Br)=O")


def test_placeholder_escapes_the_letter_it_builds_a_pattern_from():
    # Unescaped, "." would match any letter: "atom z has" would read "." as a placeholder.
    assert _placeholder(".", "the atom z has 3 protons") is False
    assert _placeholder("X", "element X has 6 protons") is True


@pytest.mark.parametrize(
    "tail, kept",
    [
        # No words after the question: nothing exclaims, so nothing is cut.
        ("  !" * (N // 3), False),
        ("!! " * (N // 3), False),
        (" Go" + "!! " * (N // 3), True),
    ],
)
def test_a_posed_problems_cheer_is_cut_in_one_pass(tail, kept):
    """CodeQL py/redos on the posed read's trailing-cheer pattern (PR #2407)."""
    question = "What is its speed?"
    assert without_cheer(question + tail) == (question if kept else question + tail)
