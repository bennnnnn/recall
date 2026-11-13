"""A verified card the reply's own working contradicts stands with no check.

The net under every misread: the quarter circle's working ended at 50.24 under a checked
≈ 201.06 (2026-11-13), and passed because a card that opens with ≈ was not read as a
value at all. These hold that card, and the textbook run's others (a cylinder worked with
3.14 under π's 565.49, an algebra simplification under a ratio card), to the working,
and keep a card the working agrees with to its rounding.
"""

from __future__ import annotations

import pytest

from app.modules.math.fence import validate_math_fences
from app.services.answer_check import read_verified_value, stated_verdict
from app.services.answer_fence import UNCHECKED_ANSWER_MARKER, VERIFIED_ANSWER_MARKER
from app.services.asked_value import asked_verdict
from app.services.solving import VerifiedMathBlock

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


def _words(answer: str, figure: dict[str, object] | None = None) -> VerifiedMathBlock:
    """A card the server read from a question's words, as a shape or school reading is."""
    return VerifiedMathBlock(
        text="",
        subject="math",
        canonical_fence=figure or {"type": "answer", "content": answer},
        canonical_answer=answer,
        read_from_words=True,
    )


@pytest.mark.parametrize(
    ("card", "value"),
    [
        (r"\approx 201.06\ \mathrm{cm}^{2}", "201.06"),
        (r"16\pi \approx 50.27\ \mathrm{cm}^{2}", "50.27"),
        (r"5\pi + 10 \approx 25.71\ \mathrm{cm}", "25.71"),
        (r"\frac{352}{7} \approx 50.29\ \mathrm{cm}^{2}", "50.29"),
        (r"A = 16\pi \approx 50.27", "50.27"),
    ],
)
def test_a_rounded_card_is_read_as_its_rounded_value(card: str, value: str) -> None:
    read = read_verified_value(card)
    assert read is not None and [str(float(n.value)) for n in read.numbers] == [value]


@pytest.mark.parametrize(
    ("reply", "card", "figure", "own"),
    [
        # The owner's quarter circle: 50.24 worked, ≈ 201.06 and a whole circle verified.
        (_OWNER, r"\approx 201.06\ \mathrm{cm}^{2}", _CIRCLE, "A = 50.24"),
        # A cylinder worked with the 3.14 its question gave, under π's 565.49.
        (_CYLINDER, r"\approx 565.49\ \mathrm{cm}^{3}", None, "V = 565.2"),
        # Like terms collected to m - 7n under a ratio read from "terms: ... 2(m - 3n)".
        (_LIKE_TERMS, "2:3", None, "m - 7n"),
    ],
)
def test_a_card_the_working_contradicts_stands_with_no_check(
    reply: str, card: str, figure: dict[str, object] | None, own: str
) -> None:
    out = validate_math_fences(reply, verified=_words(card, figure))
    assert VERIFIED_ANSWER_MARKER not in out
    assert f"```answer\n{UNCHECKED_ANSWER_MARKER}\n{own}" in out
    # The figure of the server's reading goes with its card.
    assert "```geometry" not in out


@pytest.mark.parametrize(
    ("reply", "card"),
    [
        # The working ends unrounded and the card rounds once: the same value.
        ("**Answer**\n\n$A = 201.0619\\ \\text{cm}^2$\n", r"\approx 201.06\ \mathrm{cm}^{2}"),
        ("**Answer**\n\n$A \\approx 201.06\\ \\text{cm}^2$\n", r"\approx 201.06\ \mathrm{cm}^{2}"),
        # A coarser rounding of the card's value is no other value.
        ("**Answer**\n\n$A \\approx 201.1\\ \\text{cm}^2$\n", r"\approx 201.06\ \mathrm{cm}^{2}"),
        ("**Answer**\n\n$A = 16\\pi \\approx 50.27\\ \\text{cm}^2$\n", r"16\pi \approx 50.27"),
        # A ratio the working states is the ratio's.
        ("**Answer**\n\n$2:3$\n", "2:3"),
        # A unit's letters, a where-line and words are no expression.
        ("where $r$ = radius\n\n**Answer**\n\n$P = 25.71\\ \\text{cm}$\n", r"\approx 25.71"),
        ("**Answer**\n\n$d = 5\\ m$\n", r"5\ \mathrm{m}"),
        ("**Answer**\n\nThe ratio is a simple 2 to 3.\n", "2:3"),
    ],
)
def test_a_card_the_working_agrees_with_keeps_its_check(reply: str, card: str) -> None:
    out = validate_math_fences(reply, verified=_words(card))
    assert f"```answer\n{VERIFIED_ANSWER_MARKER}\n{card}\n```" in out


def test_the_owner_working_conflicts_with_the_whole_circle_card() -> None:
    assert stated_verdict(_OWNER, r"\approx 201.06\ \mathrm{cm}^{2}") == "conflict"
    assert stated_verdict(_OWNER, r"50.24\ \mathrm{cm}^{2}") == "same"


@pytest.mark.parametrize(
    ("reply", "card", "verdict"),
    [
        # A measure agrees at the precision the reply wrote, a whole number included.
        ("**Answer**\n$A \\approx 201\\ \\text{cm}^2$\n", r"\approx 201.06\ \mathrm{cm}^{2}", "rounded"),
        ("**Answer**\n$A \\approx 2.01 \\times 10^{2}\\ \\text{cm}^2$\n", r"\approx 201.06\ \mathrm{cm}^{2}", "rounded"),
        ("**Answer**\n$A \\approx 3.14 \\times 10^{6}\\ \\text{m}^2$\n", r"\approx 3141592.65\ \mathrm{m}^{2}", "rounded"),
        ("**Answer**\n$v \\approx 20\\ \\text{m/s}$\n", r"19.8\,\mathrm{m/s}", "rounded"),
        ("**Answer**\n$t \\approx 2\\ \\text{s}$\n", r"2.02\,\mathrm{s}", "rounded"),
        ("**Answer**\n$M = 44\\ \\text{g/mol}$\n", r"M(\mathrm{CO_2}) = 44.01\,\mathrm{g/mol}", "rounded"),
        # A bare whole number for a value that is not one is another answer, as before.
        ("**Answer**\n$x = 4$\n", "x = 3.5", "conflict"),
        ("**Answer**\n$v \\approx 14\\ \\text{m/s}$\n", r"19.8\,\mathrm{m/s}", "conflict"),
        # The Answer's main clause is its value; a later clause names another quantity.
        ("**Answer**\n$P \\approx 28.57$ cm, of which the curved edge is $4\\pi \\approx 12.57$ cm.\n",
         r"4\pi + 16 \approx 28.57\ \mathrm{cm}", "same"),
        ("**Answer**\n$P \\approx 28.57\\ \\text{cm}$\nThe curved edge alone is $12.57$ cm.\n",
         r"4\pi + 16 \approx 28.57\ \mathrm{cm}", "same"),
        ("**Answer**\n$A = \\frac{25\\pi}{2}\\ \\text{cm}^2$ (with $r = 5$ in $\\frac{1}{2}\\pi r^2$).\n",
         r"\frac{25}{2}\pi \approx 39.27\ \mathrm{cm}^{2}", "absent"),
        # No Answer heading: a value the reply states that agrees is its answer.
        ("A quarter circle has area $16\\pi \\approx 50.27$ cm².\n\nThe full circle would be "
         "$64\\pi \\approx 201.06$ cm².\n", r"16\pi \approx 50.27\ \mathrm{cm}^{2}", "same"),
        # A bonus part's own Answer after the asked one.
        ("**Answer**\n$L \\approx 12.57\\ \\text{cm}$\n\n**Perimeter (bonus)**\n\n**Answer**\n"
         "$P = 4\\pi + 16 \\approx 28.57\\ \\text{cm}$\n", r"4\pi \approx 12.57\ \mathrm{cm}", "same"),
    ],
)  # fmt: skip
def test_a_value_is_held_at_the_precision_and_place_the_reply_states_it(
    reply: str, card: str, verdict: str
) -> None:
    assert stated_verdict(reply, card) == verdict


@pytest.mark.parametrize(
    ("reply", "card"),
    [
        # A unit after a number, a formula's own symbols and a ratio's names are no algebra.
        ("**Answer**\n$d = 4\\sqrt{2}\\ m$\n", r"\approx 5.6569\ \mathrm{m}"),
        ("**Answer**\n$C = 6\\pi\\ m$\n", r"\approx 18.85\ \mathrm{m}"),
        ("**Answer**\n$A = 16\\pi\\ \\text{cm}^2$, a quarter of $\\pi r^2$.\n", r"16\pi \approx 50.27"),
        ("**Answer**\n$2:3$, so for every $2$ of $a$ there are $3$ of $b$, i.e. $a:b$.\n", "2:3"),
        ("**Answer**\nThe ratio in simplest form is $2 : 3$ (divide by the HCF, $h$).\n", "2:3"),
    ],
)  # fmt: skip
def test_units_symbols_and_names_are_no_expression_in_letters(reply: str, card: str) -> None:
    out = validate_math_fences(reply, verified=_words(card))
    assert f"```answer\n{VERIFIED_ANSWER_MARKER}\n{card}\n```" in out


@pytest.mark.parametrize(
    ("reply", "card", "asked", "verdict"),
    [
        # The value written against the asked quantity, never a given beside it.
        ("**Answer**\nWith $r = 6$ cm, the perimeter is $P = 3\\pi + 12 \\approx 21.42$ cm.\n",
         r"3\pi + 12 \approx 21.42\ \mathrm{cm}", ("P", "perimeter"), "same"),
        ("**Answer**\nSince the full circle is 314.16 cm², the semicircle's area is 157.08 cm².\n",
         r"50\pi \approx 157.08\ \mathrm{cm}^{2}", ("A", "area"), "same"),
        ("**Answer**\nFrom the launch point at $y = 0$ m, the ball rises to $h \\approx 20.4$ m.\n",
         r"20.4\,\mathrm{m}", ("h",), "same"),
        ("**Answer**\nUsing C = 12.01 and O = 16.00 g/mol, M = 44.01 g/mol.\n",
         r"M(\mathrm{CO_2}) = 44.01\,\mathrm{g/mol}", ("M",), "same"),
        ("**Answer**\n$P \\approx 28.57$ cm, of which the curved edge is $4\\pi \\approx 12.57$ cm.\n",
         r"4\pi + 16 \approx 28.57\ \mathrm{cm}", ("P", "perimeter"), "same"),
        ("**Answer**\n$\\lambda = 68$ cm\n", r"0.68\,\mathrm{m}", ("\\lambda",), "same"),
        # The asked quantity's own value contradicts the card: the shape's area is 462.
        ("The whole circle has area $\\frac{22}{7} \\times 14^2 = 616$ cm². The missing quadrant is "
         "$154$ cm². So the area left is $616 - 154 = 462$ cm².\n",
         r"154\ \mathrm{cm}^{2}", ("A", "area"), "conflict"),
        ("**Answer**\nThe quadrant is 154 cm², so the shape's area is $462$ cm².\n",
         r"154\ \mathrm{cm}^{2}", ("A", "area"), "conflict"),
        ("**Answer**\n$M = 28.01$ g/mol\n", r"M(\mathrm{CO_2}) = 44.01\,\mathrm{g/mol}", ("M",),
         "conflict"),
        # Nothing names the asked quantity: the Answer is read as before.
        ("**Answer**\n$50.24$ cm²\n", r"50.24\ \mathrm{cm}^{2}", ("A", "area"), None),
    ],
)  # fmt: skip
def test_the_value_held_to_the_card_is_the_asked_quantitys(
    reply: str, card: str, asked: tuple[str, ...], verdict: str | None
) -> None:
    assert asked_verdict(reply, card, asked) == verdict
