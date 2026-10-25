"""A molecule's shape asked in words is read whole and drawn, or declines.

Live failure (2026-10-25), the student's lines in order: "Why is water bent tho, co2 isnt" got
no verified answer; "Can u show me both" went to a photo search for "both"; "lol no the
molecules" got ASCII art in a code box and a broken CO2 drawing.
"""

from __future__ import annotations

import json
import re

import pytest

from app.modules.chemistry.block import build_verified_chemistry
from app.modules.chemistry.direct import format_direct_chemistry_reply
from app.modules.chemistry.extract import extract_chemistry_intent
from app.modules.chemistry.extractors.shapes import shape_question
from app.modules.chemistry.fence import validate_chemistry_fences
from app.modules.chemistry.followup import chemistry_followup_problem
from app.modules.chemistry.request import is_chemistry_question
from app.modules.chemistry.schemas import ChemistryIntent
from app.modules.chemistry.shape_followup import is_show_line
from app.modules.chemistry.solvers import solve_chemistry
from app.services.solving import SolveServiceError
from app.services.subject_solving import detect_subject

_LIVE = (
    "Ok so chem hw. how much water do i get if i burn like 4g of h2",
    "Wait so its 4.5 or 36?? I'm confused",
    "Ok and the o2 how much of that",
    "Why is water bent tho, co2 isnt",
)
_SCENE = re.compile(r"```chem_scene\n(.*?)\n```", re.DOTALL)


def _answer(question: str) -> str | None:
    intent = extract_chemistry_intent(question)
    verified = None if intent is None else build_verified_chemistry(intent)
    return None if verified is None else verified.result.answer


def _recent(*lines: str) -> list[tuple[str, str]]:
    turns: list[tuple[str, str]] = []
    for line in lines:
        turns.extend((("user", line), ("assistant", "Here it is.")))
    return turns


@pytest.mark.parametrize(
    ("question", "molecules", "answer"),
    [
        ("Why is water bent tho, co2 isnt", ("H2O", "CO2"), "H2O: bent, 104.5°, polar"),
        ("why is water bent but co2 linear", ("H2O", "CO2"), "CO2: linear, 180°, nonpolar"),
        ("compare the shapes of h2o and co2", ("H2O", "CO2"), "H2O: bent"),
        ("what are the shapes of CH4 and NH3", ("CH4", "NH3"), "NH3: trigonal pyramidal, 107°"),
        ("why is water bent", ("H2O",), "geometry: bent, 104.5°"),
        ("shape of water", ("H2O",), "geometry: bent"),
        ("what is the shape of a water molecule", ("H2O",), "geometry: bent"),
        ("what shape is ch4", ("CH4",), "geometry: tetrahedral, 109.5°"),
        ("is co2 linear", ("CO2",), "geometry: linear, 180°"),
        ("why is co2 linear", ("CO2",), "geometry: linear"),
        ("geometry of ammonia", ("NH3",), "geometry: trigonal pyramidal, 107°"),
        ("bond angle in h2o", ("H2O",), "104.5°"),
        ("is nh3 polar", ("NH3",), "polarity: polar"),
        ("is co2 polar or nonpolar", ("CO2",), "polarity: nonpolar"),
        ("how come water is bent", ("H2O",), "geometry: bent"),
        ("polarity of water", ("H2O",), "polarity: polar"),
        ("Ok so chem hw. why is water bent", ("H2O",), "geometry: bent"),
        ("what is the molecular geometry of BF3", ("BF3",), "trigonal planar, 120°"),
        # A false premise is answered with the verified shape, not agreed with.
        ("why is co2 bent", ("CO2",), "geometry: linear, 180°"),
    ],
)
def test_a_shape_question_in_words_is_verified(
    question: str, molecules: tuple[str, ...], answer: str
) -> None:
    assert shape_question(question) == molecules
    assert is_chemistry_question(question)
    assert detect_subject(question) == "chemistry"
    assert answer in (_answer(question) or "")


@pytest.mark.parametrize(
    "text",
    [
        "what shape is the earth",
        "the pipe is bent",
        "bent over backwards for my boss",
        "my phone is bent",
        "co2 levels are rising",
        "is co2 bad",
        "is co2 bad for the planet",
        "shape of my nose",
        "what shape is a stop sign",
        "what is the bond angle in a bond portfolio",
        "why is the tower of pisa bent",
        "why is the tower of pisa leaning",
        "why is my back bent",
        "is water wet",
        "why is water blue",
        # No central atom, or more than one: not read as VSEPR.
        "what shape is oxygen",
        "shape of ethanol",
        "is iron linear",
        "what shape is lead",
        # A clause the grammar does not know.
        "why is co2 nonpolar if it has polar bonds",
    ],
)
def test_shapes_in_everyday_words_are_not_a_vsepr_question(text: str) -> None:
    assert shape_question(text) is None
    assert extract_chemistry_intent(text) is None
    assert not is_chemistry_question(text)


def test_geometry_homework_stays_maths() -> None:
    text = "geometry homework: find the angle of a triangle with sides 3 4 5"
    assert shape_question(text) is None
    assert detect_subject(text) == "math"


def test_two_molecules_draw_two_pictures() -> None:
    intent = extract_chemistry_intent("Why is water bent tho, co2 isnt")
    assert intent is not None and (intent.chemistry_op, intent.formula) == ("vsepr", "H2O, CO2")
    verified = build_verified_chemistry(intent)
    assert verified is not None
    reply = format_direct_chemistry_reply(verified)
    scenes = [json.loads(body) for body in _SCENE.findall(reply)]
    assert [(scene["title"], scene["geometry"]) for scene in scenes] == [
        ("H₂O", "bent"),
        ("CO₂", "linear"),
    ]
    # The model's own drawings are dropped at finalize and the server's two kept.
    finalized = validate_chemistry_fences(
        "Water is bent.\n\n```chem_scene\n{}\n```\n```\nO=C=O\n```", verified
    )
    assert len(_SCENE.findall(finalized)) == 2


@pytest.mark.parametrize("formula", ["H2O, H2O", "H2O, O2", "H2O, CO2, CH4"])
def test_a_comparison_needs_two_different_molecules_with_a_center(formula: str) -> None:
    intent = ChemistryIntent(kind="structure", chemistry_op="vsepr", formula=formula)
    with pytest.raises(SolveServiceError):
        solve_chemistry(intent)


@pytest.mark.parametrize(
    ("lines", "line"),
    [
        (_LIVE, "Can u show me both"),
        ((*_LIVE, "Can u show me both"), "lol no the molecules"),
        (("why is water bent",), "show me the molecules"),
        (("why is water bent",), "draw them"),
        (("why is water bent",), "draw it"),
        (("why is water bent",), "show me"),
        (("why is water bent",), "what do they look like"),
        (("why is water bent",), "can you draw both molecules pls"),
    ],
)
def test_a_line_that_asks_to_see_them_draws_the_shape_question_again(
    lines: tuple[str, ...], line: str
) -> None:
    problem = chemistry_followup_problem(line, _recent(*lines))
    assert problem is not None
    assert shape_question(problem) is not None


@pytest.mark.parametrize(
    ("lines", "line"),
    [
        (("what's the difference between a crocodile and an alligator",), "show me both"),
        (("graph y = x^2 and y = 2x",), "draw them"),
        # Another line in between: the shape question is no longer the one being looked at.
        (("why is water bent", "what is the capital of france"), "show me both"),
        (("why is water bent",), "show me both crocodiles"),
        (("why is water bent",), "draw a cat"),
    ],
)
def test_a_show_line_after_anything_else_is_not_chemistrys(
    lines: tuple[str, ...], line: str
) -> None:
    assert chemistry_followup_problem(line, _recent(*lines)) is None


@pytest.mark.parametrize(
    ("line", "shows"),
    [
        ("Can u show me both", True),
        ("lol no the molecules", True),
        ("show me the shapes please", True),
        ("let me see them", True),
        ("what do they look like", True),
        ("show me both crocodiles", False),
        ("show me the steps", False),
        ("draw a cat", False),
        ("no thanks", False),
    ],
)
def test_the_show_grammar_reads_the_whole_line(line: str, shows: bool) -> None:
    assert is_show_line(line) is shows
