"""A question that asks for several quantities gets every one on its card, or no card.

2026-11-13 audit (MATH-04): "find the gcd and lcm of 252 and 198" carried 18 alone, and a
complete correct reply had its card demoted; "find the circumference and area of a circle of
radius 3" carried ≈ 18.85 alone, the area left in the working. The grade-12 run's S2 is the
same class in a model's own worked reply: a part asking two values carded the last.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.math.fence_conflict import contradicted_reading
from app.modules.math.match.asked_quantities import asked_quantities
from app.services.answer_fence import land_answer_card
from app.services.solving import VerifiedMathBlock
from app.services.subjects.dispatch import build_subject_augmentation


async def _card(text: str) -> str | None:
    settings = Settings(math_llm_extract_enabled=False, math_word_problems_enabled=False)
    verified = (await build_subject_augmentation(text, settings)).verified
    return getattr(verified, "canonical_answer", None) if verified is not None else None


@pytest.mark.parametrize(
    ("text", "asked"),
    [
        ("find the gcd and lcm of 252 and 198", ["gcd", "lcm"]),
        ("the lowest common multiple and highest common factor of 8 and 12", ["lcm", "gcd"]),
        ("find the circumference and area of a circle of radius 3", ["circumference", "area"]),
        ("its volume, surface area and diagonal", ["volume", "surface_area", "diagonal"]),
        ("find the area and the perimeter", ["area", "perimeter"]),
        # One quantity asked; the others are givens.
        ("find the area of a circle, the radius is 3", []),
        ("find the area of a circle with radius 3 and diameter 6", []),
        ("find the gcd of 12 and 18", []),
        ("find the area of a circle of radius 3", []),
    ],
)
def test_the_quantities_asked_together_are_read(text: str, asked: list[str]) -> None:
    assert asked_quantities(text) == asked


@pytest.mark.parametrize(
    ("text", "card"),
    [
        (
            "find the gcd and lcm of 252 and 198",
            r"\gcd(252, 198) = 18,\quad \operatorname{lcm}(252, 198) = 2772",
        ),
        (
            "the lowest common multiple and highest common factor of 8 and 12",
            r"\operatorname{lcm}(8, 12) = 24,\quad \gcd(8, 12) = 4",
        ),
        (
            "find the hcf and lcm of 12, 18 and 30",
            r"\gcd(12, 18, 30) = 6,\quad \operatorname{lcm}(12, 18, 30) = 180",
        ),
        (
            "find the circumference and area of a circle of radius 3",
            r"C \approx 18.85\ \mathrm{units},\quad A \approx 28.27\ \mathrm{units}^{2}",
        ),
        # The area with an area's unit, the diameter exact.
        (
            "find the diameter and area of a circle of radius 3",
            r"d = 6\ \mathrm{units},\quad A \approx 28.27\ \mathrm{units}^{2}",
        ),
        (
            "find the diagonal and area of a rectangle 3 cm by 4 cm",
            r"d = 5\ \mathrm{cm},\quad A = 12\ \mathrm{cm}^{2}",
        ),
        (
            "find the area and perimeter of a triangle with sides 3, 4 and 5",
            r"A = 6\ \mathrm{units}^{2},\quad P = 12\ \mathrm{units}",
        ),
        (
            "find the area and arc length of a sector of radius 5 and angle 60 degrees",
            r"A \approx 13.09\ \mathrm{units}^{2},\quad L \approx 5.24\ \mathrm{units}",
        ),
        (
            "find the volume and surface area of a sphere of radius 2",
            r"V \approx 33.51\ \mathrm{units}^{3},\quad S \approx 50.27\ \mathrm{units}^{2}",
        ),
        # One quantity: the card is as before.
        ("find the gcd of 252 and 198", "18"),
        ("find the area of a circle of radius 3", "28.27"),
    ],
)
async def test_every_quantity_asked_is_on_the_card(text: str, card: str) -> None:
    assert await _card(text) == card


async def test_a_quantity_the_block_cannot_card_leaves_no_card() -> None:
    """Half the question checked is worse than none."""
    assert await _card("find the volume, surface area and diagonal of a cuboid 2 by 3 by 4") is None


def _verified(card: str) -> VerifiedMathBlock:
    return VerifiedMathBlock(text="", canonical_answer=card, read_from_words=True, subject="math")


_GCD_LCM = r"\gcd(252, 198) = 18,\quad \operatorname{lcm}(252, 198) = 2772"
_CIRCLE = r"C \approx 18.85\ \mathrm{units},\quad A \approx 28.27\ \mathrm{units}^{2}"


@pytest.mark.parametrize(
    ("card", "reply", "stands"),
    [
        (_GCD_LCM, "**Answer**\n\ngcd = 18, lcm = 2772", True),
        (_GCD_LCM, "**Answer**\n\n$\\gcd = 18$\n\n$\\operatorname{lcm} = 2772$", True),
        (_GCD_LCM, "**Answer**\n\ngcd = 18, lcm = 2700", False),
        (_CIRCLE, "**Answer**\n\nC ≈ 18.85 units, A ≈ 28.27 square units", True),
        # 28.3 is 28.27 at the precision the reply wrote it.
        (_CIRCLE, "**Answer**\n\nC ≈ 18.85 units, A ≈ 28.3 square units", True),
        (_CIRCLE, "**Answer**\n\nC ≈ 18.85 units, A ≈ 18.85 square units", False),
    ],
)
def test_each_value_of_the_card_is_held_to_its_own_name(
    card: str, reply: str, stands: bool
) -> None:
    """A complete correct reply keeps its check; one wrong value of two takes it away."""
    body = f"verified: true\n{card}"
    contradicted = contradicted_reading(
        f"**Solution**\n\nworking\n\n{reply}", _verified(card), body
    )
    assert (contradicted is None) is stands


@pytest.mark.parametrize(
    ("section", "carded"),
    [
        # g12 t26: a maximum and a minimum.
        (
            "$f_{max} = 15$ (at x = -3 and x = 3)  \n$f_{min} = -10$",
            "$f_{max} = 15$ (at x = -3 and x = 3), $f_{min} = -10$",
        ),
        # g12 t44: a type, a centre and a radius.
        (
            "$type = sphere$ (yes)  \n$C = (1,-2,3)$ (centre)  \n$r = 1$ (radius)",
            "$type = sphere$ (yes), $C = (1,-2,3)$ (centre), $r = 1$ (radius)",
        ),
        # g12 t25 (b): two values with no name, each with where it is.
        ("$32$ (at x=-3)  \n$0$ (at x=1)", "$32$ (at x=-3), $0$ (at x=1)"),
        (
            "$increasing = (-\\infty,-3) \\cup (1,\\infty)$ (intervals)  \n"
            "$decreasing = (-3,1)$ (interval)",
            "$increasing = (-\\infty,-3) \\cup (1,\\infty)$ (intervals), $decreasing = (-3,1)$ "
            "(interval)",
        ),
        (
            "$\\gcd = 18$\n\n$\\operatorname{lcm} = 2772$",
            "$\\gcd = 18$, $\\operatorname{lcm} = 2772$",
        ),
        # Working above the value stays working.
        ("$v = 9.8 \\times 2$  \n$v = 19.6$ m/s", "$v = 19.6$ m/s"),
        ("$2x = 8$  \n$x = 4$", "x = 4"),
        # A bracketed negative is arithmetic still to do, not a point.
        ("$pH = -(-2)$  \n$pH = 2.00$", "pH = 2.00"),
    ],
)
def test_a_part_asking_several_values_cards_each(section: str, carded: str) -> None:
    landed = land_answer_card(f"**Solution**\n\nworking\n\n**Answer**\n\n{section}", None)
    card = landed.split("```answer\n", 1)[1].split("\n```", 1)[0]
    assert card == f"verified: false\n{carded}"
