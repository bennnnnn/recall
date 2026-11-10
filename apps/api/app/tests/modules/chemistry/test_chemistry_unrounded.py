"""A chemistry card rounds to the data's figures; its working shows the value unrounded once.

"How many grams are in 0.5 mol of NaCl?" showed "m = 29 g" and a card of 29 g: the 29.22 g
it is appeared nowhere (2026-11-08). The card keeps the class's significant figures, and the
working ends on what the arithmetic reaches.
"""

from __future__ import annotations

import pytest

from app.modules.chat.worked_lead import drop_restated_step
from app.modules.chemistry.block import build_verified_chemistry
from app.modules.chemistry.direct import format_direct_chemistry_reply
from app.modules.chemistry.extract import extract_chemistry_intent


def _reply(question: str) -> str:
    intent = extract_chemistry_intent(question)
    assert intent is not None
    verified = build_verified_chemistry(intent)
    assert verified is not None
    return drop_restated_step(format_direct_chemistry_reply(verified))


@pytest.mark.parametrize(
    ("question", "worked", "card"),
    [
        (
            "How many grams are in 0.5 mol of NaCl?",
            "$m = 29.22\\,\\mathrm{g}$",
            "m(\\mathrm{NaCl}) = 29\\,\\mathrm{g}",
        ),
        (
            "How many moles are in 36 g of water?",
            "$n = 1.998\\,\\mathrm{mol}$",
            "n(\\mathrm{H₂O}) = 2.0\\,\\mathrm{mol}",
        ),
        (
            "What is the molar mass of glucose?",
            "$M = 180.156\\,\\mathrm{g/mol}$",
            "M(\\mathrm{C₆H₁₂O₆}) = 180.16\\,\\mathrm{g/mol}",
        ),
    ],
)
def test_the_working_ends_on_the_value_the_card_rounds(
    question: str, worked: str, card: str
) -> None:
    reply = _reply(question)
    assert f"{worked}\n\n**Answer**" in reply
    assert f"```answer\n{card}\n```" in reply


def test_a_value_rounding_leaves_whole_is_said_once_in_the_card() -> None:
    # 18.015 g / 18.015 g/mol is 1.000 mol: nothing rounded, so the working's closing row
    # was the card again, and goes.
    reply = _reply("How many moles are in 18.015 g of water?")
    assert "$n = 1.000\\,\\mathrm{mol}$" not in reply
    assert "n(\\mathrm{H₂O}) = 1.000\\,\\mathrm{mol}" in reply


@pytest.mark.parametrize(
    ("question", "rows"),
    [
        # (1.0 mol)(6.0221 x 10^23) ending on 6.017 x 10^23 did not add up: the amount a
        # later row works with is carried, not rounded to the answer's figures.
        (
            "How many atoms are in 12 g of carbon?",
            (
                "$N = (0.9991\\,\\mathrm{mol})(6.0221 \\times 10^{23}\\,\\mathrm{mol⁻¹})$",
                "$N = 6.017 \\times 10^{23}\\,\\mathrm{atoms}$",
            ),
        ),
        (
            "A first order reaction has a half-life of 25 min. What is the rate constant k?",
            ("= 0.6931 / 25$", "$k = 0.02773\\,\\mathrm{min⁻¹}$"),
        ),
    ],
)
def test_the_unrounded_value_is_what_the_rows_above_reach(
    question: str, rows: tuple[str, str]
) -> None:
    reply = _reply(question)
    assert "  \n".join(rows) in reply
