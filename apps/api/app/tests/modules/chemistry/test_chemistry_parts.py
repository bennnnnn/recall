"""A chemistry message that asks several things gets a verified part for each.

"a) molar mass of NH3 b) moles in 34 g of NH3" verified neither part, and "What is the molar
mass of H2O? How many moles are in 36 g of H2O?" was answered with the molar mass alone
(audit 2026-11-13, CHEM-08). These run the turn's real reading and solve
(``harness.route_case``) and read the reply the student gets.
"""

from __future__ import annotations

import re

import pytest

from app.modules.chemistry.direct import maybe_direct_chemistry_reply
from app.modules.chemistry.parts import _read_parts
from app.modules.chemistry.questions import (
    MORE_QUESTIONS_NOTE,
    asks_more_questions,
    chemistry_questions,
)
from app.tests.behavior.cases import Case, Expect
from app.tests.behavior.harness import route_case


@pytest.mark.parametrize(
    ("text", "asked"),
    [
        (
            "a) molar mass of NH3 b) moles in 34 g of NH3",
            ["molar mass of NH3", "moles in 34 g of NH3"],
        ),
        (
            "A solution has 0.010 M HCl. What is its pH? What is its pOH?",
            [
                "A solution has 0.010 M HCl. What is its pH?",
                "A solution has 0.010 M HCl. What is its pOH?",
            ],
        ),
        # Every question counts, chemistry's or not: none of them goes unanswered.
        (
            "Can you help? What is the molar mass of H2O?",
            ["Can you help?", "What is the molar mass of H2O?"],
        ),
        (
            "What is the molar mass of H2O? Why is that?",
            ["What is the molar mass of H2O?", "Why is that?"],
        ),
    ],
)
def test_the_questions_a_message_asks(text: str, asked: list[str]) -> None:
    assert [question.asked for question in chemistry_questions(text)] == asked


def test_a_part_that_names_no_substance_takes_the_one_named_before_it() -> None:
    questions = chemistry_questions(
        "(a) What is the molar mass of NH3? (b) How many moles are in 34 g of it?"
    )
    assert [question.read for question in questions] == [
        "What is the molar mass of NH3?",
        "For NH3: How many moles are in 34 g of it?",
    ]


@pytest.mark.parametrize(
    ("text", "answers"),
    [
        # M(NH3) = 17.031 g/mol, 34 g / 17.031 g/mol = 2.0 mol.
        ("a) molar mass of NH3 b) moles in 34 g of NH3", ["17.03 g/mol", "2.0 mol"]),
        (
            "(a) What is the molar mass of NH3? (b) How many moles are in 34 g of it?",
            ["17.03 g/mol", "2.0 mol"],
        ),
        # M(H2O) = 18.015 g/mol, 36 g / 18.015 g/mol = 2.0 mol.
        (
            "(a) What is the molar mass of H2O? (b) How many moles are in 36 g of H2O?",
            ["18.02 g/mol", "2.0 mol"],
        ),
        (
            "What is the molar mass of H2O? How many moles are in 36 g of H2O?",
            ["18.02 g/mol", "2.0 mol"],
        ),
        ("A solution has 0.010 M HCl. What is its pH? What is its pOH?", ["2.00", "12.00"]),
    ],
)
@pytest.mark.asyncio
async def test_every_part_is_verified_and_answered(text: str, answers: list[str]) -> None:
    route = await route_case(Case("parts", "chemistry", text, Expect(), ""))
    verified = route.context.verified_subject
    assert verified is not None
    assert len(verified.question_parts) == len(answers)
    for part, answer in zip(verified.question_parts, answers, strict=True):
        assert answer in (part.canonical_answer or "")
    assert re.findall(r"\*\*Answer \(([ab])\)\*\*", route.instant_text) == ["a", "b"]


@pytest.mark.parametrize(
    "text",
    [
        # One part has no verified answer: the message is read whole, as before.
        "(a) What is the molar mass of NH3? (b) Explain why ammonia is polar.",
        # Two questions read as one answer are one question misread, not two answered.
        "What is the molar mass of H2O? What is the molar mass of water?",
    ],
)
def test_a_message_whose_parts_do_not_all_verify_is_not_answered_in_parts(text: str) -> None:
    _questions, solved = _read_parts(text)
    assert solved is None


@pytest.mark.parametrize(
    "text",
    [
        # The second question has no verified answer of its own.
        "What is the molar mass of H2O? How many moles of H2O are in 5 L of steam?",
        # A question that asks no law ("which one is heavier", "why") still asks something.
        "What is the molar mass of CO2? What is the molar mass of H2O? Which one is heavier?",
        # "it" is NaCl or KCl: the third question names no one substance.
        "What is the molar mass of NaCl? What is the molar mass of KCl? "
        "How many moles are in 10 g of it?",
        "What is the molar mass of H2O? Why is that?",
        "What is the pH of 0.010 M HCl? Is it acidic?",
    ],
)
@pytest.mark.asyncio
async def test_an_instant_reply_never_answers_fewer_questions_than_are_asked(text: str) -> None:
    """The model writes the reply, the verified result carded, and is told to answer every
    question."""
    _questions, solved = _read_parts(text)
    assert solved is None
    route = await route_case(Case("parts", "chemistry", text, Expect(), ""))
    assert route.solved and not route.instant_text
    assert MORE_QUESTIONS_NOTE in route.system_prompt


def test_one_question_keeps_its_instant_reply() -> None:
    from app.modules.chemistry.block import build_verified_chemistry
    from app.modules.chemistry.extract import extract_chemistry_intent

    text = "Please help. What is the molar mass of H2O?"
    intent = extract_chemistry_intent("What is the molar mass of H2O?")
    assert intent is not None
    verified = build_verified_chemistry(intent)
    assert not asks_more_questions(text, "M(H2O) = 18.02 g/mol")
    assert maybe_direct_chemistry_reply(verified, has_image_attachment=False, user_text=text)
