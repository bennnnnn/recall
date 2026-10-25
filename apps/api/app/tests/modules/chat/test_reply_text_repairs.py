"""A casual reply's text, repaired where its meaning broke (2026-10-24, one study chat).

- A quiz card marked 0.5 L right, though its own explanation ended "Correct answer is
  1.0 L (Option A)" after second-guessing itself.
- "Like texting a smart friend" read as lowercase: "2h₂ + o₂ → 2h₂o", "0 k", "10°c".
- Formulas came in grey code blocks.

Each repair touches only that: a review found the first drafts moving right quiz answers
("a common wrong answer is 0.5 L"), unfencing config lines and capitalizing variables,
paths and quoted text, all held below.
"""

from __future__ import annotations

import json

import pytest

from app.modules.chat.formula_fences import unfence_formulas, unwrap_code_maths
from app.modules.chat.proper_case import restore_proper_case
from app.modules.chat.quiz_cards import repair_quiz_fences

_LIVE_QUIZ = {
    "label": "Question 3",
    "question": "A gas has a volume of 4.0 L at 2 atm. What is the new volume at 8 atm?",
    "options": ["1.0 L", "2.0 L", "0.5 L", "16.0 L"],
    "answer": 2,
    "explanation": (
        "Using $P_1V_1 = P_2V_2$: $(2)(4) = (8)(V_2) \\rightarrow 8 = 8V_2 \\rightarrow "
        "V_2 = 1.0$ L. Wait, let me re-calc: $8/2 = 4$, so volume divides by 4. $4/4 = 1.0$ "
        "L. Actually, option C is 0.5L? Let's check options. A=1.0, B=2.0, C=0.5, D=16.0. "
        "Correct answer is 1.0 L (Option A)."
    ),
}


def _card(card: dict[str, object]) -> dict[str, object]:
    text = repair_quiz_fences(f"Quiz:\n\n```quiz\n{json.dumps(card)}\n```\n\nGood luck!")
    return json.loads(text.split("```quiz\n")[1].split("\n```")[0])


def test_a_quiz_answer_follows_its_explanation_and_loses_its_second_guessing() -> None:
    fixed = _card(_LIVE_QUIZ)
    assert fixed["answer"] == 0
    explanation = str(fixed["explanation"])
    assert explanation.endswith("V_2 = 1.0$ L.")
    assert "Wait" not in explanation


_VOLUMES = ["1.0 L", "2.0 L", "0.5 L", "16 L"]


@pytest.mark.parametrize(
    ("options", "answer", "explanation"),
    [
        # A distractor named, a negated answer: teaching, not a conclusion.
        (_VOLUMES, 0, "V₂ = 1.0 L. A common wrong answer is 0.5 L, from dividing twice."),
        (_VOLUMES, 0, "The answer isn't 0.5 L: that halves twice."),
        (_VOLUMES, 0, "The answer is not C (0.5 L)."),
        (_VOLUMES, 0, "If you picked answer: 16 L, you multiplied."),
        # No self-correction: whatever it ends on moves nothing.
        (_VOLUMES, 0, "P1V1 = P2V2 gives 1.0 L. Not 0.5 L: halving twice is a common slip."),
        (_VOLUMES, 0, "If you wait 2 s at 8 atm, the volume is still 1.0 L."),
        # "Hmm" and "Hold on" teach; they are no second-guessing.
        (["4", "8", "16", "32"], 1, "2³ = 8. Hmm, a common slip: 2×3 = 6, or 2⁴ = 16."),
        (_VOLUMES, 0, "V₂ = 1.0 L. Hold on, why not 16 L? Multiplying gives 4 × 8/2 = 16 L."),
        # A card that agrees with itself.
        (["Temperature", "Pressure"], 0, "Kelvin starts at absolute zero, so temperature."),
    ],
)
def test_a_quiz_answer_moves_only_on_a_stated_correction(
    options: list[str], answer: int, explanation: str
) -> None:
    card = {"question": "q?", "options": options, "answer": answer, "explanation": explanation}
    text = f"```quiz\n{json.dumps(card)}\n```"
    assert repair_quiz_fences(text) == text


def test_an_option_list_after_a_doubt_moves_nothing() -> None:
    card = {
        "question": "q?",
        "options": ["1.0", "2.0", "0.5", "16.0"],
        "answer": 0,
        "explanation": "V₂ = 1.0. Wait, let me check the options: A=1.0, B=2.0, C=0.5, D=16.0.",
    }
    fixed = _card(card)
    assert fixed["answer"] == 0
    assert fixed["explanation"] == "V₂ = 1.0."


@pytest.mark.parametrize(
    "card",
    [
        # An answer by letter or text is the phone's to read; it is left whole.
        {"question": "q?", "options": ["Paris", "Rome"], "answer": "A", "explanation": "Wait, x."},
        {"question": "q?", "options": ["1.0 L", "0.5 L"], "answer": 1, "explanation": "Hmm, 1.0?"},
    ],
)
def test_a_quiz_it_cannot_read_is_left_as_written(card: dict[str, object]) -> None:
    text = f"```quiz\n{json.dumps(card)}\n```"
    assert repair_quiz_fences(text) == text
    broken = "```quiz\n{not json\n```"
    assert repair_quiz_fences(broken) == broken


@pytest.mark.parametrize(
    ("written", "fixed"),
    [
        (
            "burn 4.0 g of hydrogen gas (h₂) to make water (h₂o)",
            "burn 4.0 g of hydrogen gas (H₂) to make water (H₂O)",
        ),
        (
            "fe₂o₃, co₂, ca(oh)₂, c₆h₁₂o₆, nh₃ and mgcl₂",
            "Fe₂O₃, CO₂, Ca(OH)₂, C₆H₁₂O₆, NH₃ and MgCl₂",
        ),
        ("sand is sio₂ and blue vitriol is cuso₄", "sand is SiO₂ and blue vitriol is CuSO₄"),
        ("2h₂o₂ → 2h₂o + o₂", "2H₂O₂ → 2H₂O + O₂"),  # beside a compound, h₂o₂ is chemistry
        (
            "absolute zero is 0 k in kelvin; 10°c is not double 5°c",
            "absolute zero is 0 K in kelvin; 10°C is not double 5°C",
        ),
    ],
)
def test_capitals_that_carry_meaning_come_back(written: str, fixed: str) -> None:
    assert restore_proper_case(written) == fixed


@pytest.mark.parametrize(
    "text",
    [
        "x₂ and log₂ and word₂",  # no element symbols
        "boyle: p₁v₁ = p₂v₂, and v₁/t₁ = v₂/t₂",  # indexed variables, not elements
        "snell: n₁ sin θ₁ = n₂ sin θ₂ at heights h₁ and h₂",
        "the slope through (x₂, y₂) is m",
        "speeds u₂ and v₂, spring k₂, area s₂",
        # A lone element or a one-subscript product with no compound beside it.
        "height h₂ = 5 m and current i₂ = 2 A",
        "the centre is (h₂, k₂)",
        "p₂v₂ = nrt₂",
        # Kelvin's k only as a unit after a spaced number.
        "in kelvin, 2k + 1 is odd and 2 k + 1 too",
        "a 45° f-stop",
        # Weekdays and months are style, never touched.
        "they march 10 miles on monday",
        # Data, quotes, maths, code and addresses as written.
        '["monday", "h₂o"]',
        "You wrote 'h₂o is wet' — fix the capitals.",
        'He typed "h₂o" there.',
        "Keep `h₂o` in code, $v_1/t_1$ and \\( h₂o \\) in maths.",
        "see https://example.com/h₂o, www.example.com/h₂o and /home/sunday/h₂o.txt",
        "email h₂o@corp.com",
        "```python\nh₂o = 1\n```",
        "```answer\nh₂o\n```",
    ],
)
def test_other_text_keeps_its_case(text: str) -> None:
    assert restore_proper_case(text) == text


def test_a_formula_leaves_its_plain_code_block() -> None:
    reply = "the reaction is:\n```\nh₂ + o₂ → h₂o\n```\n\nnow balance it"
    assert restore_proper_case(unfence_formulas(reply)) == (
        "the reaction is:\n\nH₂ + O₂ → H₂O\n\nnow balance it"
    )
    assert unfence_formulas("```\np₁v₁ = p₂v₂\n```") == "p₁v₁ = p₂v₂"
    # The next line stays its own paragraph.
    assert unfence_formulas("Step 1:\n```\nV₂ = 1.0 L\n```\nSo it halves.") == (
        "Step 1:\n\nV₂ = 1.0 L\n\nSo it halves."
    )


@pytest.mark.parametrize(
    "body",
    [
        "x = foo(3)\nprint(x)",
        "total = price * qty",
        "PORT=8000\nDEBUG=1",
        "export PORT=8000",
        "max_connections = 100",
        "UPDATE users SET active = 1 WHERE id = 5",
        "=A1*B1",
        "count += 1",
        "git config user.name = foo",
        "PV = nRT",  # plain ASCII, whatever it means
        "# moles = 4.0 ÷ 2.02",  # would be a heading
        "1. x = 5 × 2",  # would be a list
    ],
)
def test_code_stays_in_its_block(body: str) -> None:
    block = f"```\n{body}\n```"
    assert unfence_formulas(block) == block
    assert unfence_formulas(f"```python\n{body}\n```") == f"```python\n{body}\n```"


@pytest.mark.parametrize(
    ("reply", "shown"),
    [
        # Live 2026-10-25, a sales-tax follow-up on a car loan.
        (
            "First, find the total cost:\n`$14,000 + (14,000 \\times 0.07) = 14,980$`",
            "First, find the total cost:\n$14,000 + (14,000 \\times 0.07) = 14,980$",
        ),
        ("so `$r = \\frac{0.0757}{12}$` a month", "so $r = \\frac{0.0757}{12}$ a month"),
        ("`$$M = P \\frac{r}{1 - (1+r)^{-n}}$$`", "$$M = P \\frac{r}{1 - (1+r)^{-n}}$$"),
        # Code stays code.
        ("Where `M` is the payment.", "Where `M` is the payment."),
        ("Run `echo $HOME` first.", "Run `echo $HOME` first."),
        ("The variable `$x` holds it.", "The variable `$x` holds it."),
        ("Spaced `$ a $` is no maths.", "Spaced `$ a $` is no maths."),
        ("```python\nx = `$y$`\n```", "```python\nx = `$y$`\n```"),
        ("Mixed `$x$ and y` stays.", "Mixed `$x$ and y` stays."),
    ],
)
def test_a_maths_span_in_inline_code_is_maths(reply: str, shown: str) -> None:
    assert unwrap_code_maths(reply, "what if sales tax is 7%") == shown


@pytest.mark.parametrize(
    "request_text",
    ["how do i type a fraction in latex?", "what's the markdown for an equation?"],
)
def test_asked_for_the_source_every_span_stays_code(request_text: str) -> None:
    reply = "Type `$\\frac{a}{b}$` to get a fraction."
    assert unwrap_code_maths(reply, request_text) == reply
