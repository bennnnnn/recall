"""A verified card stands with no check only where the reply's Answer plainly contradicts it.

The net under every misread: the quarter circle's Answer, A = 50.24 cm², stood under a
checked ≈ 201.06 (2026-11-13). A card is held to the one value the Answer section writes
against the asked quantity's exact symbol or name (``services/asked_value.py``); where the
Answer gives several, another subscript, or no heading at all, the card stands as main's
reading of the reply leaves it. Three reviews' cases, both ways.
"""

from __future__ import annotations

import pytest

from app.modules.math.fence import validate_math_fences
from app.services.answer_fence import UNCHECKED_ANSWER_MARKER, VERIFIED_ANSWER_MARKER
from app.services.asked_value import asked_verdict
from app.services.solving import VerifiedMathBlock

_AREA = ("A", "area")
_OWNER = (
    "**Given**\n- Radius: $r = 8\\ \\text{cm}$\n- $\\pi = 3.14$\n\n**Solution**\n"
    "$A = 3.14 \\times 8^2 = 200.96\\ \\text{cm}^2$\n\n"
    "A quarter circle is one-fourth of a circle:\n"
    "$A_{\\text{quarter}} = \\frac{200.96}{4} = 50.24\\ \\text{cm}^2$\n\n"
    "**Answer**\n$A = 50.24\\ \\text{cm}^2$\n"
)
_CYLINDER = (
    "**Substitution**  \n$V = 3.14 \\times 3^2 \\times 20$\n\n$V = 565.2\\ \\text{cm}^3$\n\n"
    "**Answer**\n\n$V = 565.2\\ \\text{cm}^3$\n"
)
_LIKE_TERMS = "$-(m+n)+2(m-3n) = -m-n+2m-6n$  \n$-(m+n)+2(m-3n) = m-7n$\n\n**Answer**\n\n$m - 7n$\n"
_CIRCLE = {"type": "circle", "radius": 8.0, "unit": "cm", "area": 201.0619}
_QUARTER = r"16\pi \approx 50.27\ \mathrm{cm}^{2}"


def _words(
    answer: str, asked: tuple[str, ...] = (), figure: dict[str, object] | None = None
) -> VerifiedMathBlock:
    """A card the server read from a question's words, as a shape or school reading is."""
    return VerifiedMathBlock(
        text="",
        subject="math",
        canonical_fence=figure or {"type": "answer", "content": answer},
        canonical_answer=answer,
        read_from_words=True,
        asked=asked,
    )


@pytest.mark.parametrize(
    ("reply", "card", "asked", "figure", "own"),
    [
        # The owner's quarter circle: A = 50.24 in the Answer, ≈ 201.06 on a whole circle.
        (_OWNER, r"\approx 201.06\ \mathrm{cm}^{2}", _AREA, _CIRCLE, "A = 50.24"),
        # A cylinder worked with the 3.14 its question gave, under π's 565.49.
        (_CYLINDER, r"\approx 565.49\ \mathrm{cm}^{3}", ("V", "volume"), None, "V = 565.2"),
        # Like terms collected to m - 7n under a ratio read from "terms: ... 2(m - 3n)".
        (_LIKE_TERMS, "2:3", (), None, "m - 7n"),
    ],
)  # fmt: skip
def test_a_card_the_answer_plainly_contradicts_stands_with_no_check(
    reply: str, card: str, asked: tuple[str, ...], figure: dict[str, object] | None, own: str
) -> None:
    out = validate_math_fences(reply, verified=_words(card, asked, figure))
    assert VERIFIED_ANSWER_MARKER not in out
    assert f"```answer\n{UNCHECKED_ANSWER_MARKER}\n{own}" in out
    # The figure of the server's reading goes with its card.
    assert "```geometry" not in out


@pytest.mark.parametrize(
    ("reply", "card"),
    [
        # Agreeing, to the card's rounding or the reply's own precision.
        ("**Answer**\n\n$A = 201.0619\\ \\text{cm}^2$\n", r"\approx 201.06\ \mathrm{cm}^{2}"),
        ("**Answer**\n\n$A \\approx 201\\ \\text{cm}^2$\n", r"\approx 201.06\ \mathrm{cm}^{2}"),
        ("**Answer**\n\n$A \\approx 2.01 \\times 10^{2}\\ \\text{cm}^2$\n", r"\approx 201.06\ \mathrm{cm}^{2}"),
        ("**Answer**\n\n$A = 16\\pi \\approx 50.3\\ \\text{cm}^2$\n", _QUARTER),
        # Third review: the whole circle's area beside the quarter's is no contradiction.
        ("**Answer**\n$A_{circle} = 201.06$ cm², so $A_{quarter} = 50.27$ cm².\n", _QUARTER),
        ("**Answer**\n(a) $A_{circle} \\approx 201.06$ (b) $A_{quarter} \\approx 50.27$\n", _QUARTER),
        ("**Answer**\nThe area of the whole circle is 201.06 cm², so the quarter circle's area "
         "is 50.27 cm².\n", _QUARTER),
        ("A quarter of $\\pi r^2$: $A_{quarter} = 16\\pi \\approx 50.27$ cm².\n\nFor comparison, "
         "the whole circle has $A \\approx 201.06$ cm².\n", _QUARTER),
        ("**Answer**\n$A \\approx 50.27$ cm²\n\n**Answer**\n$P \\approx 28.57$ cm\n", _QUARTER),
        # Givens beside the asked quantity are no candidates.
        ("**Answer**\nWith $r = 6$ cm, $A = 9\\pi \\approx 28.27$ cm²\n", r"9\pi \approx 28.27\ \mathrm{cm}^{2}"),
        # A ratio the Answer states, and names and units that are no algebra.
        ("**Answer**\n\n$2:3$\n", "2:3"),
        ("**Answer**\n$2:3$, so for every $2$ of $a$ there are $3$ of $b$, i.e. $a:b$.\n", "2:3"),
    ],
)  # fmt: skip
def test_a_card_the_answer_does_not_plainly_contradict_keeps_its_check(
    reply: str, card: str
) -> None:
    out = validate_math_fences(reply, verified=_words(card, _AREA))
    assert f"```answer\n{VERIFIED_ANSWER_MARKER}\n{card}\n```" in out


@pytest.mark.parametrize(
    ("reply", "card", "asked", "verdict"),
    [
        # One value against the exact symbol or the name decides.
        ("**Answer**\nWith $r = 6$ cm, the perimeter is $P = 3\\pi + 12 \\approx 21.42$ cm.\n",
         r"3\pi + 12 \approx 21.42\ \mathrm{cm}", ("P", "perimeter"), "same"),
        ("**Answer**\nThe perimeter is $P = 5\\pi + 10 \\approx 25.71$ cm, while the arc alone is "
         "$L = 15.71$ cm.\n", r"5\pi + 10 \approx 25.71\ \mathrm{cm}", ("P", "perimeter"), "same"),
        ("**Answer**\nFrom the launch point at $y = 0$ m, the ball rises to $h_{max} \\approx 20.4$ m.\n",
         r"20.4\,\mathrm{m}", ("h_{\\max}",), "same"),
        ("**Answer**\nWith $v = 20$ m/s, $u = 10$ m/s.\n", r"10\,\mathrm{m/s}", ("u",), "same"),
        ("**Answer**\n$M_{\\text{C}} = 12.01$, $M_{\\text{O}} = 16.00$, so $M_{\\text{CO}_2} = 44.01$ g/mol.\n",
         r"M(\mathrm{CO_2}) = 44.01\,\mathrm{g/mol}", ("M(\\mathrm{CO_2})", "M"), "same"),
        ("**Answer**\n$\\text{pOH} = 12$ and $\\text{pH} = 2$\n", r"\mathrm{pH} = 2.00", ("pH",), "same"),
        ("**Answer**\n$v \\approx 20$ m/s\n", r"19.8\,\mathrm{m/s}", ("v",), "rounded"),
        ("**Answer**\n$A = 50.24$ cm², about 50 cm².\n", r"50.24\ \mathrm{cm}^{2}", _AREA, "same"),
        ("**Answer**\n$A \\approx 50.27$ cm²\n", r"50.24\ \mathrm{cm}^{2}", _AREA, "conflict"),
        ("**Answer**\nWith $V = 12$ V and $R = 4$ Ω, $I = 48$ A.\n", r"3\,\mathrm{A}", ("I",), "conflict"),
        ("**Answer**\n$n = 0.5$ mol\n", r"n(\mathrm{H_2O}) = 2.0\,\mathrm{mol}", ("n(\\mathrm{H_2O})", "n"), "conflict"),
        # Several values, another subscript or no Answer heading: no one value decides.
        ("**Answer**\nThe arc is $L = 4\\pi \\approx 12.57$ cm long; the curved edge plus both radii "
         "is $28.57$ cm.\n", r"4\pi \approx 12.57\ \mathrm{cm}", ("L", "arc length", "arc", "curved edge"), None),
        ("**Answer**\nFor 1 mol, $m = 58.44$ g; for 0.5 mol, $m = 29.22$ g.\n",
         r"m(\mathrm{NaCl}) = 29\,\mathrm{g}", ("m(\\mathrm{NaCl})", "m"), None),
        ("**Answer**\nWith $v = 20$ m/s, $u = 10$ m/s.\n", r"10\,\mathrm{m/s}", ("v_i",), None),
        ("**Answer**\n$P_{semicircle} = 25.71$ cm\n", r"5\pi + 10 \approx 25.71", ("P", "perimeter"), None),
        ("The quadrant is 154 cm², so the shape's area is $462$ cm².\n", r"154\ \mathrm{cm}^{2}", _AREA, None),
    ],
)  # fmt: skip
def test_the_one_value_the_answer_gives_the_asked_quantity(
    reply: str, card: str, asked: tuple[str, ...], verdict: str | None
) -> None:
    assert asked_verdict(reply, card, asked) == verdict
