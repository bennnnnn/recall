"""A maths card answers the question asked, and shows its method (2026-11-06).

"a jacket costs 2400 shillings, its on sale for 15% off and then theres 16% vat added on the
sale price. how much do i pay" was read as a proportion of its three numbers and carried a
checked 0.1 under working that ended at 2366.40. "lim x->0 of (1-cos x)/x^2" came back as a
card of 1/2 and nothing else.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from app.core.config import Settings
from app.modules.math.fence import validate_math_fences
from app.modules.math.tools.extract import extract_math_intent
from app.services.answer_fence import UNCHECKED_ANSWER_MARKER, VERIFIED_ANSWER_MARKER
from app.services.subjects.dispatch import build_subject_augmentation, maybe_direct_subject_reply

_SETTINGS = Settings(math_llm_extract_enabled=False, math_word_problems_enabled=False)


async def _verified(text: str) -> Any:  # a VerifiedMathBlock or None
    return (await build_subject_augmentation(text, _SETTINGS)).verified


@pytest.mark.parametrize(
    ("text", "answer"),
    [
        (
            "a jacket costs 2400 shillings, its on sale for 15% off and then theres 16% vat "
            "added on the sale price. how much do i pay",
            r"2366.40\ \text{shillings}",
        ),
        (
            "a $80 pair of shoes is 25% off, then 8% sales tax is added. what is the final price",
            r"\$64.80",
        ),
        (
            "a 50 dollar meal, 10% discount then a 15% tip on the discounted price. how much "
            "do i pay",
            r"\$51.75",
        ),
    ],
)
async def test_percent_changes_in_turn_are_worked_on_the_price(text: str, answer: str) -> None:
    verified = await _verified(text)
    assert verified is not None and verified.canonical_answer == answer
    assert verified.read_from_words


@pytest.mark.parametrize(
    "text",
    [
        # Whether the VAT is on the sale price or the list price is not said.
        "a jacket costs 2400 shillings with 15% off and 16% vat. how much do i pay",
        "a phone costs 300 dollars, 20% off, then a 10 dollar coupon. how much do i pay",
        "a jacket costs 2400 shillings, 15% off and 16% vat. how much is the vat",
    ],
)
def test_percents_are_never_terms_of_a_proportion(text: str) -> None:
    intent = extract_math_intent(text)
    assert intent is None or intent.school_op not in {"direct_proportion", "price_changes"}


def test_a_proportion_of_three_quantities_still_reads() -> None:
    intent = extract_math_intent("3 pens cost 12 dollars, how much do 5 pens cost")
    assert intent is not None and intent.school_op == "direct_proportion"


async def test_a_card_read_from_words_that_the_working_contradicts_gets_no_check() -> None:
    verified = await _verified("what is 15% of 80")
    assert verified is not None and verified.read_from_words
    reply = (
        "**Solution**\n\n$80 \\times 0.15 = 14$\n\n**Answer**\n\n```answer\n14\n```\n\n"
        '```geometry\n{"type":"rectangle","width":1,"height":1}\n```'
    )
    out = validate_math_fences(reply, verified=verified)
    assert VERIFIED_ANSWER_MARKER not in out
    assert f"```answer\n{UNCHECKED_ANSWER_MARKER}\n14\n```" in out
    assert "```geometry" not in out


async def test_a_typed_equation_keeps_its_check_and_correction() -> None:
    verified = await _verified("solve 2x + 5 = 17")
    assert verified is not None and not verified.read_from_words
    out = validate_math_fences("So $x = 7$.\n\n**Answer**\n\n$x = 7$", verified=verified)
    assert "The verified answer is $x = 6$." in out
    assert f"```answer\n{VERIFIED_ANSWER_MARKER}\nx = 6\n```" in out


async def test_a_card_the_working_agrees_with_keeps_its_check() -> None:
    verified = await _verified("what is 15% of 80")
    assert verified is not None
    out = validate_math_fences("$80 \\times 0.15 = 12$\n\n**Answer**\n\n$12$", verified=verified)
    assert f"```answer\n{VERIFIED_ANSWER_MARKER}\n12\n```" in out


@pytest.mark.parametrize(
    ("text", "rounds", "answer"),
    [
        ("lim x->0 of (1-cos x)/x^2", 2, r"\frac{1}{2}"),
        ("lim x->0 (x - sin x)/x^3", 3, r"\frac{1}{6}"),
        ("lim x->0 of (e^x - 1)/x", 1, "1"),
    ],
)
async def test_a_limit_shows_each_round_of_lhopital(text: str, rounds: int, answer: str) -> None:
    verified = await _verified(text)
    assert verified is not None and verified.worked_reply is not None
    working = verified.worked_reply
    assert working.count("differentiate") == rounds
    assert "**L'Hôpital's rule**" in working
    assert working.rstrip().endswith(f"```answer\n{answer}\n```")


async def test_a_limit_with_no_method_to_show_is_not_a_bare_card() -> None:
    verified = await _verified("lim x->0 of (1-cos x)/x^2")
    assert verified is not None
    reply = maybe_direct_subject_reply(verified, "lim x->0 of (1-cos x)/x^2")
    assert reply is not None and "**Steps**" in reply
    bare = replace(verified, worked_reply=None, key_steps=(), allow_direct=False)
    assert maybe_direct_subject_reply(bare, "lim x->0 of (1-cos x)/x^2") is None


async def test_one_verified_value_checks_only_the_card_that_states_it() -> None:
    # 2026-11-06: a triangle asked in parts. The server checked the perimeter alone, and the
    # card under every part was rewritten to it: "36" for the hypotenuse and the area too.
    question = (
        "a right triangle has legs 9 cm and 12 cm. find a) the hypotenuse b) the area "
        "c) the perimeter"
    )
    verified = await _verified(question)
    assert verified is not None and verified.canonical_answer == "36"
    reply = (
        "**Answer (a)**\n\n```answer\nc = 15\\,\\mathrm{cm}\n```\n\n"
        "**Answer (b)**\n\n```answer\n$A = 54\\,\\mathrm{cm^2}$\n```\n\n"
        "**Answer (c)**\n\n```answer\nP = 36\\,\\mathrm{cm}\n```"
    )
    out = validate_math_fences(reply, verified=verified)
    assert f"```answer\n{UNCHECKED_ANSWER_MARKER}\nc = 15\\,\\mathrm{{cm}}\n```" in out
    assert f"```answer\n{UNCHECKED_ANSWER_MARKER}\nA = 54\\,\\mathrm{{cm}}^{{2}}\n```" in out
    assert out.count(VERIFIED_ANSWER_MARKER) == 1
    assert f"```answer\n{VERIFIED_ANSWER_MARKER}\n36\n```" in out
