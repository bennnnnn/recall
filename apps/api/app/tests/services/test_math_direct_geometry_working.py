"""Every verified geometry family uses the same readable worked hierarchy."""

import pytest

from app.core.config import Settings
from app.services.math.tools.block import _build_verified_block
from app.services.math.tools.direct import maybe_direct_math_reply
from app.services.math.tools.extract import extract_math_intent


def _reply(query: str) -> str:
    intent = extract_math_intent(query)
    assert intent is not None
    verified = _build_verified_block(intent, Settings(math_tools_enabled=True))
    assert verified is not None
    reply = maybe_direct_math_reply(verified, query)
    assert reply is not None
    return reply


@pytest.mark.parametrize(
    "query,formula,substitution",
    [
        (
            "Find the area of a rectangle 4 by 5",
            r"$A = w \times h$",
            r"$A = 4 \times 5 = 20$",
        ),
        (
            "Find the perimeter of a rectangle 4 by 5",
            r"$P = 2(w + h)$",
            r"$P = 2(4 + 5) = 18$",
        ),
        (
            "Find the diagonal of a rectangle 3 by 4",
            r"$d^2 = w^2 + h^2$",
            r"$d = \sqrt{3^2 + 4^2} = 5$",
        ),
        ("Find the area of a square side 4", r"$A = s^2$", r"$A = 4^2 = 16$"),
        ("Find the perimeter of a square side 4", r"$P = 4s$", r"$P = 4 \times 4 = 16$"),
        (
            "Find the diagonal of a square side 4",
            r"$d = s\sqrt{2}$",
            r"$d = 4\sqrt{2} = 5.6569$",
        ),
        (
            "Find the area of a triangle base 6 height 5",
            r"$A = \frac{1}{2}bh$",
            r"$A = \frac{1}{2} \times 6 \times 5 = 15$",
        ),
        (
            "Find the hypotenuse of a right triangle legs 3 and 4",
            r"$c^2 = a^2 + b^2$",
            r"$c = \sqrt{3^2 + 4^2} = 5$",
        ),
        (
            "Find the perimeter of a right triangle legs 3 and 4",
            r"$P = a + b + c$",
            r"$P = 3 + 4 + 5 = 12$",
        ),
        (
            "Find the area of a triangle with sides 3,4,5",
            r"$A = \sqrt{s(s-a)(s-b)(s-c)}$",
            r"$s = \frac{3+4+5}{2} = 6$",
        ),
        (
            "Find the perimeter of a triangle with sides 3,4,5",
            r"$P = a + b + c$",
            r"$P = 3 + 4 + 5 = 12$",
        ),
        (
            "Find the area of a parallelogram base 8 height 4 side 5",
            r"$A = bh$",
            r"$A = 8 \times 4 = 32$",
        ),
        (
            "Find the perimeter of a parallelogram base 8 height 4 side 5",
            r"$P = 2(b+s)$",
            r"$P = 2(8 + 5) = 26$",
        ),
        (
            "Find the area of a trapezoid top 4 bottom 8 height 5",
            r"$A = \frac{1}{2}(a+b)h$",
            r"$A = \frac{1}{2}(4+8) \times 5 = 30$",
        ),
        (
            "Find the area of a circle radius 3",
            r"$A = \pi r^2$",
            r"$A = \pi(3)^2 \approx 28.27$",
        ),
        (
            "Find the circumference of a circle radius 3",
            r"$C = 2\pi r$",
            r"$C = 2\pi(3) \approx 18.85$",
        ),
        (
            "Find the diameter of a circle radius 3",
            r"$d = 2r$",
            r"$d = 2 \times 3 = 6$",
        ),
        (
            "Find the area of a sector with radius 4 cm and angle 90 degrees",
            r"$A = \frac{\theta}{360^\circ}\pi r^2$",
            r"$A = \frac{90^\circ}{360^\circ}\pi(4)^2 \approx 12.5664$",
        ),
        (
            "Find the arc length of a sector with radius 4 cm and angle 90 degrees",
            r"$L = \frac{\theta}{360^\circ}(2\pi r)$",
            r"$L = \frac{90^\circ}{360^\circ}(2\pi \times 4) \approx 6.28$",
        ),
    ],
)
def test_geometry_formula_and_substitution_are_separate_verified_lines(
    query: str, formula: str, substitution: str
) -> None:
    reply = _reply(query)
    headings = ["**Given**", "**Find**", "**Formula**", "**Substitution**", "**Answer**"]
    positions = [reply.index(heading) for heading in headings]
    assert positions == sorted(positions)
    assert formula in reply
    assert substitution in reply
    assert "**Diagram**" in reply
    assert reply.count("```answer") == 1
    assert reply.count("```geometry") == 1


def test_natural_rectangle_wording_draws_exact_sides_and_trims_decimal_zeroes() -> None:
    reply = _reply("a rectangle area with sides 4.04, 5")
    assert "Width: $w = 4.04" in reply
    assert "Height: $h = 5" in reply
    assert r"$A = 4.04 \times 5 = 20.2$" in reply
    assert "20.20" not in reply
    assert '"width":4.04' in reply and '"height":5.0' in reply
