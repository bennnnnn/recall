"""A question with no answer as written carries why in the prompt the turn builds.

A live round on main (2026-11-14) showed both: "What is the molar mass of NaCl3?" declined,
and the model called it "sodium trichloride" at 112 g/mol, then 129 (CHEM-06); "A 10 V battery
is connected across a -5 Ω resistor. What current flows?" declined, and the model answered
-2 A without a word (PHYS-13). Each was told only that nothing verified. Now the note says what
the server found and the turn gets no ```worked block, whose contract would have it work the
impossible value out. Its look-alikes, valid compounds and signed quantities, carry no note.
"""

from __future__ import annotations

import pytest

from app.tests.behavior.cases import Case, Expect
from app.tests.behavior.harness import Route, route_case

_NO_ANSWER = "the question as written has no answer."
_SIGN_CHECK = "Physics sign check:"
_WORKED = "Worked calculation:"


async def _route(prompt: str) -> Route:
    return await route_case(Case("decline-reason", "stem", prompt, Expect(), ""))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("prompt", "reason"),
    [
        (
            "What is the molar mass of NaCl3?",
            "NaCl3 is not a compound: sodium's +1 and chlorine's -1 cannot balance in a 1:3 ratio.",
        ),
        ("How many moles are in 10 g of AlCl2?", "AlCl2 is not a compound"),
        ("Balance Na + Cl2 -> NaCl3", "NaCl3 is not a compound"),
        ("Balance: H2 + O2 -> NaCl", "H2 + O2 -> NaCl cannot be balanced"),
        (
            "What is the name of the element with atomic number 130?",
            "No element has atomic number 130",
        ),
        (
            "A 10 V battery is connected across a -5 Ω resistor. What current flows?",
            "A resistance cannot be zero or negative, and the question gives -5 Ω.",
        ),
        (
            "A -3 kg box is pushed with a net force of 12 N. What is its acceleration?",
            "A mass cannot be zero or negative, and the question gives -3 kg.",
        ),
        (
            "A gas at -300 °C and 100 kPa has a volume of 2 L. How many moles?",
            "No temperature is at or below absolute zero",
        ),
        (
            "A car moves at 4 x 10^8 m/s for 10 s. How far does it go?",
            "Nothing moves faster than light",
        ),
    ],
)
async def test_the_prompt_says_why_the_question_has_no_answer(prompt: str, reason: str) -> None:
    route = await _route(prompt)
    assert not route.solved
    assert _NO_ANSWER in route.system_prompt
    assert reason in route.system_prompt
    # The ```worked contract would have the model work the impossible value out.
    assert _WORKED not in route.system_prompt


@pytest.mark.asyncio
async def test_a_result_out_of_range_asks_the_reply_to_check_the_signs() -> None:
    """The result's sign is the reader's: a braking force given as a size beside a negative
    deceleration is a fine question, so the reply checks and may answer with sizes."""
    route = await _route(
        "A force of -10 N gives a mass an acceleration of 2 m/s². What is the mass?"
    )
    assert _SIGN_CHECK in route.system_prompt
    assert "the stated values give -5 kg, and a mass cannot be zero or negative" in (
        route.system_prompt
    )
    assert _NO_ANSWER not in route.system_prompt


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "prompt",
    [
        # Compounds that exist, and an equation that balances.
        "What is the molar mass of NaCl?",
        "What is the molar mass of PCl5?",
        "What is the molar mass of Na2O2?",
        "Balance Na + Cl2 -> NaCl",
        # Declines that state nothing impossible: no formula the table reads, an equation that
        # balances more than one way, a half-reaction to complete.
        "What is the molar mass of D2O?",
        "Balance Fe + O2 -> FeO + Fe2O3",
        "Balance H2O -> H2 in acidic solution",
        "Balance the redox reaction MnO4- + Fe2+ -> Mn2+ + Fe3+ in acidic solution.",
        "Balance Zn + HNO3 -> Zn(NO3)2 + NH4NO3",
        # Signed quantities keep their sign.
        "A 2 kg box slides with a velocity of -3 m/s. What is its momentum?",
        "A charge of -3 μC sits 0.2 m from a charge of 5 μC. What is the force between them?",
        "An electron with charge -1.6e-19 C moves through a potential difference of 100 V. "
        "How much energy does it gain?",
        "A car accelerates from 20 m/s to 10 m/s in 5 s. What is its acceleration?",
        "A ball is thrown upward at -20 m/s. How high does it go?",
    ],
)
async def test_a_look_alike_carries_no_reason(prompt: str) -> None:
    route = await _route(prompt)
    assert _NO_ANSWER not in route.system_prompt
    assert _SIGN_CHECK not in route.system_prompt
