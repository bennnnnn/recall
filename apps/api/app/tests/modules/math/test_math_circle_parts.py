"""A part of a circle measured as that part, a stated π used, and a figure that is the part.

"Find the area of the quarter circle of radius 8 cm. (use 3.14)" was a checked 201.06 cm²,
the whole circle with π itself, under a drawing of the whole circle (2026-11-13). Every
expected value here is worked by hand: the part's share of πr² or of 2πr (plus two radii
for a perimeter), with the π the question gives.
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from app.core.config import Settings
from app.modules.math.match.circle_parts import circle_parts, other_piece_of_circle
from app.modules.math.match.geometry import pi_value_set
from app.modules.math.match.stated_pi import stated_pi
from app.modules.math.tools.block import _build_verified_block
from app.modules.math.tools.extract import extract_math_intent

_SETTINGS = Settings(math_tools_enabled=True)


@pytest.mark.parametrize(
    ("text", "fraction"),
    [
        ("the quarter circle of radius 8 cm", Fraction(1, 4)),
        ("a semicircle with diameter 10", Fraction(1, 2)),
        ("a semi-circle", Fraction(1, 2)),
        ("a half circle", Fraction(1, 2)),
        ("a three-quarter circle", Fraction(3, 4)),
        ("a three quarter circle", Fraction(3, 4)),
        ("A quarter of a circle has radius 10 cm", Fraction(1, 4)),
        ("two thirds of the circle", Fraction(2, 3)),
        ("one sixth of a circle", Fraction(1, 6)),
        ("a quadrant of a circle", Fraction(1, 4)),
        ("a quadrant of radius 7 cm", Fraction(1, 4)),
        ("a ¾ circle", Fraction(3, 4)),
        ("a 1/4 circle", Fraction(1, 4)),
        ("1/4 of a circle", Fraction(1, 4)),
    ],
)
def test_circle_part_reads_the_fraction_said_of_the_circle(text: str, fraction: Fraction) -> None:
    parts = circle_parts(text)
    assert [part.fraction for part in parts] == [fraction]


@pytest.mark.parametrize(
    "text",
    [
        "the area of a circle of radius 8 cm",
        # An ordinal before its noun is the next circle, not a part of one.
        "a third circle has radius 3 cm",
        "the fourth circle",
        "a semicircular arch",
    ],
)
def test_circle_part_reads_no_part_of_a_whole_circle(text: str) -> None:
    assert circle_parts(text) == []


@pytest.mark.parametrize(
    ("text", "other"),
    [
        ("the area of a segment of a circle", True),
        ("the length of an arc of the circle", True),
        ("the area of a circle", False),
        ("the circumference of the circle", False),
        ("the length of a chord of a circle", False),
        ("a quarter of a circle", False),
    ],
)
def test_other_piece_of_circle_is_a_region_the_circle_readers_do_not_measure(
    text: str, other: bool
) -> None:
    assert other_piece_of_circle(text) is other


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("(use 3.14)", Fraction(157, 50)),
        ("Use π = 22/7", Fraction(22, 7)),
        ("take pi as 3.142", Fraction(1571, 500)),
        ("use 3.14 for pi", Fraction(157, 50)),
        ("π ≈ 3.1416", Fraction(3927, 1250)),
        ("π is approximately 3.14", Fraction(157, 50)),
        (r"using \frac{22}{7} for π", Fraction(22, 7)),
        ("take the value of π as 22/7", Fraction(22, 7)),
    ],
)
def test_stated_pi_reads_the_value_named_or_not(text: str, value: Fraction) -> None:
    statement = stated_pi(text)
    assert statement is not None and statement.value == value
    assert pi_value_set(text)


@pytest.mark.parametrize("text", ["use π = 3", "use π", "use π = 3.14 and π = 22/7"])
def test_stated_pi_set_to_a_value_no_solver_uses_is_unusable(text: str) -> None:
    statement = stated_pi(text)
    assert statement is not None and statement.value is None


@pytest.mark.parametrize("text", ["use 5 cm of string", "a radius of 3.14 cm", "use 3 squares"])
def test_stated_pi_is_no_other_number(text: str) -> None:
    assert stated_pi(text) is None


_CM = r"\ \mathrm{cm}"
_CM2 = r"\ \mathrm{cm}^{2}"


@pytest.mark.parametrize(
    ("question", "card", "figure", "angle", "label"),
    [
        # The owner's question: ¼ * 3.14 * 8² = 50.24.
        ("find the area of the quarter circle of radius 8 cm. (use 3.14)",
         f"50.24{_CM2}", "sector", 90, ("area", "50.24 cm²")),
        # ¼ * π * 64 = 16π ≈ 50.27.
        ("find the area of a quarter circle of radius 8 cm",
         rf"16\pi \approx 50.27{_CM2}", "sector", 90, ("area", "50.27 cm²")),
        # ½ * 3.14 * 8 + 2 * 8 = 12.56 + 16 = 28.56: the arc and both radii.
        ("Find the perimeter of a quarter circle of radius 8 cm (use 3.14)",
         f"28.56{_CM}", "sector", 90, ("perimeter", "28.56 cm")),
        # ½ * 22/7 * 49 = 77.
        ("Find the area of a semicircle of radius 7 cm (use 22/7)",
         f"77{_CM2}", "sector", 180, ("area", "77 cm²")),
        # r = 5: ½ * π * 25 = 25π/2 ≈ 39.27.
        ("Find the area of a semicircle with diameter 10 cm",
         rf"\frac{{25}}{{2}}\pi \approx 39.27{_CM2}", "sector", 180, ("area", "39.27 cm²")),
        # ½ * 3.14 * 36 = 56.52.
        ("What is the area of a half circle with radius 6 cm? Take π = 3.14",
         f"56.52{_CM2}", "sector", 180, ("area", "56.52 cm²")),
        # ¾ * π * 16 = 12π ≈ 37.70.
        ("Find the area of a three-quarter circle of radius 4 cm",
         rf"12\pi \approx 37.70{_CM2}", "sector", 270, ("area", "37.70 cm²")),
        # ¾ * 2π * 4 + 8 = 6π + 8 ≈ 26.85.
        ("Find the perimeter of a three-quarter circle of radius 4 cm",
         rf"6\pi + 8 \approx 26.85{_CM}", "sector", 270, ("perimeter", "26.85 cm")),
        # ¼ * π * 196 = 49π ≈ 153.94.
        ("Find the area of a quadrant of a circle of radius 14 cm",
         rf"49\pi \approx 153.94{_CM2}", "sector", 90, ("area", "153.94 cm²")),
        # The part stated first, the measure asked after it: ¼ * π * 100 = 25π ≈ 78.54.
        ("A quarter of a circle has radius 10 cm. Find its area.",
         rf"25\pi \approx 78.54{_CM2}", "sector", 90, ("area", "78.54 cm²")),
        # ¼ * 2π * 10 = 5π ≈ 15.71.
        ("Find the arc length of a quarter circle of radius 10 cm",
         rf"5\pi \approx 15.71{_CM}", "sector", 90, ("arc_length", "15.71 cm")),
        # A sector by its angle, π stated: 60/360 * 3.14 * 36 = 18.84.
        ("Find the area of a sector of a circle of radius 6 cm with a central angle of 60°."
         " (use 3.14)", f"18.84{_CM2}", "sector", 60, ("area", "18.84 cm²")),
        # 90/360 * 2 * 22/7 * 7 + 14 = 11 + 14 = 25.
        ("Find the perimeter of a sector of radius 7 cm and angle 90° (use 22/7)",
         f"25{_CM}", "sector", 90, ("perimeter", "25 cm")),
        # A whole circle with a stated π: 22/7 * 49 = 154 and 3.14 * 64 = 200.96.
        ("Find the area of a circle of radius 7 cm (use 22/7)",
         f"154{_CM2}", "circle", None, ("area", "154 cm²")),
        ("Find the area of a circle of radius 8 cm (use 3.14)",
         f"200.96{_CM2}", "circle", None, ("area", "200.96 cm²")),
        # 22/7 * 14 = 44.
        ("Find the circumference of a circle with diameter 14 cm. Use π = 22/7",
         f"44{_CM}", "circle", None, ("circumference", "44 cm")),
        # The rounding asked is the card's: 3.14 * 8.25 = 25.905, 25.9 to three figures.
        ("Find the circumference of a circle with diameter 8.25 cm. Write your answer to three"
         " significant digits. (Take π = 3.14)",
         rf"\approx 25.9{_CM}", "circle", None, ("circumference", "25.9 cm")),
        ("Find the area of a semicircle of radius 5 cm to 1 decimal place",
         rf"\frac{{25}}{{2}}\pi \approx 39.3{_CM2}", "sector", 180, ("area", "39.3 cm²")),
        # From the review (2026-11-13). Half a circle, said without "of": 9π/2 ≈ 14.14.
        ("Find the area of half a circle of radius 3 cm",
         rf"\frac{{9}}{{2}}\pi \approx 14.14{_CM2}", "sector", 180, ("area", "14.14 cm²")),
        # A mixed number read whole: 1/2 * 22/7 * 3.5² = 19.25 (was radius 3, 14.14, no unit).
        ("Find the area of a semicircle of radius 3½ cm (use 22/7)",
         f"19.25{_CM2}", "sector", 180, ("area", "19.25 cm²")),
        # A unit spelled out: 8π in² for a diameter of 8 inches.
        ("Find the area of a semi-circle with a diameter of 8 inches",
         r"8\pi \approx 25.13\ \mathrm{in}^{2}", "sector", 180, ("area", "25.13 in²")),
        # "in the figure" is no inches: 77, with no unit.
        ("Find the area of the semicircle with radius 7 in the figure (use 22/7)",
         "77", "sector", 180, ("area", "77 units²")),
        # The major sector goes round the rest: 300/360 * 22/7 * 49 = 385/3 ≈ 128.33.
        ("Find the area of the major sector of radius 7 cm and angle 60°, use 22/7",
         rf"\frac{{385}}{{3}} \approx 128.33{_CM2}", "sector", 300, ("area", "128.33 cm²")),
        ("Find the major arc length of a sector of radius 7 cm and angle 60° (use 22/7)",
         rf"\frac{{110}}{{3}} \approx 36.67{_CM}", "sector", 300, ("arc_length", "36.67 cm")),
        ("Find the area of the minor sector of radius 7 cm and angle 60° (use 22/7)",
         rf"\frac{{77}}{{3}} \approx 25.67{_CM2}", "sector", 60, ("area", "25.67 cm²")),
        # The curved part's perimeter is its arc: 1/2 * 2 * 22/7 * 7 = 22 (was 36).
        ("Find the perimeter of the curved part of a semicircle of radius 7 cm (use 22/7)",
         f"22{_CM}", "sector", 180, ("arc_length", "22 cm")),
        # Past three places, ≈ to two: 3.1416 * 64 = 201.0624 (was "201.062" as if exact).
        ("Find the area of a circle of radius 8 cm. Use π ≈ 3.1416",
         rf"\approx 201.06{_CM2}", "circle", None, ("area", "201.06 cm²")),
        # Exact to three places on the card; the figure rounds a 5 up, 19.63, not 19.62.
        ("Find the area of a circle of radius 2.5 m. Use 3.14",
         r"19.625\ \mathrm{m}^{2}", "circle", None, ("area", "19.63 m²")),
        ("Find the area of a semicircle of radius 7 cm. Use π = 22/7. Round to 2 d.p.",
         f"77.00{_CM2}", "sector", 180, ("area", "77.00 cm²")),
        # "to 2 s.f." read to its stop: 2.88π = 9.047, 9.0 to two figures.
        ("Calculate the area of a semicircle of radius 2.4 cm. Give the answer to 2 s.f.",
         rf"\frac{{72}}{{25}}\pi \approx 9.0{_CM2}", "sector", 180, ("area", "9.0 cm²")),
        # π linked to its value by a few words, either way round: 2 * 3.14 * 10 = 62.8.
        ("Find the circumference of a circle of radius 10 cm, π being taken as 3.14",
         f"62.8{_CM}", "circle", None, ("circumference", "62.8 cm")),
        ("Find the circumference of a circle of radius 10 cm if π is approximated as 3.14",
         f"62.8{_CM}", "circle", None, ("circumference", "62.8 cm")),
        ("Let 3.14 be π. Find the circumference of a circle of radius 10 cm.",
         f"62.8{_CM}", "circle", None, ("circumference", "62.8 cm")),
    ],
)  # fmt: skip
def test_part_of_a_circle_is_worked_and_drawn_as_that_part(
    question: str,
    card: str,
    figure: str,
    angle: int | None,
    label: tuple[str, str],
) -> None:
    intent = extract_math_intent(question)
    assert intent is not None and intent.school_op == "geometry_measure:circle_part"
    block = _build_verified_block(intent, _SETTINGS)
    assert block is not None and block.canonical_answer == card
    assert block.worked_reply is not None and card in block.worked_reply
    (drawn,) = block.canonical_fences
    assert drawn["type"] == figure
    assert drawn.get("angle_deg") == angle
    labels = drawn["labels"]
    assert isinstance(labels, dict)
    name, shown = label
    # The part's own measure, and only the one asked: never the whole circle's.
    assert labels[name] == shown
    assert set(labels) - {"radius", "angle", "diameter"} == {name}


@pytest.mark.parametrize(
    "question",
    [
        # A composite shape and two parts: no one part's measure answers them.
        "A semicircle of radius 7 cm sits on a rectangle 14 cm by 10 cm. Find the area of the shape.",
        "Find the total area of two semicircles each of radius 3 cm",
        # A region the circle readers do not measure.
        "Find the area of a segment of a circle of radius 8 cm",
        # A semicircle's "circumference": its curved edge, or all of it?
        "Find the circumference of a semicircle of radius 5 cm",
        # π set to a value no solver here works with.
        "Find the area of a circle of radius 8 cm (use π = 3)",
        # A fraction taken of a measure, or of another shape.
        "Find a quarter of the area of a circle of radius 8 cm",
        "Find the area of half of a rectangle 6 cm by 4 cm",
        "What is the area of a quarter of a square of side 8 cm?",
        # Solids work with π itself: a stated π declines them, its own sentence too.
        "A right circular cylinder has a height of 20 cm and a diameter of 6 cm. What is its volume? (use 3.14)",
        "Find the volume of a cone of radius 3 cm and height 4 cm (take π = 22/7)",
        "Find the surface area of a sphere of radius 7 cm. Use 22/7",
        "Find the volume of a cylinder of radius 3 cm and height 5 cm. Use 3.14 for pi.",
        "Find the volume of a hemisphere of radius 3 cm (use 3.14)",
        # A sector by its angle with a stated π it cannot size: no angle.
        "Find the area of a sector of a circle of radius 6 cm (use 3.14)",
        # From the review (2026-11-13): a part taken from the whole, or what is left of it.
        "A quarter circle is cut from a circle of radius 14 cm. Find the area of the part that is left (use 22/7)",
        "A quadrant is taken away from a circle of radius 14 cm. Find the area of the remaining shape",
        "A sector of angle 60° is cut from a circle of radius 7 cm. Find the area of the rest of the circle (use 22/7)",
        "A circle of radius 7 cm is cut into four equal quadrants. Find the area of each quadrant",
        # A measure narrowed in words, or another region bounded by a chord.
        "Find the perimeter of the semicircle of radius 7 cm (use 22/7), excluding the diameter",
        "Find the area of the region between a quarter circle of radius 10 cm and its chord (use 3.14)",
        # Two things asked: one card answers neither whole.
        "Find the area of the semicircle with radius 6 cm and the area of the full circle",
        "Find the area of a quarter circle of radius 8 cm, and use it to find the area of the whole circle",
        "Find the area of a semicircle of radius 7 cm. Use π = 22/7. Then find the area of the whole circle.",
        # Another figure beside the part, with no number of its own.
        "The figure shows a square with a semicircle of radius 7 cm on one side. Find the area of the figure (use 22/7)",
        # An answer asked in another unit, with π stated and without.
        "Find the area of a circle of radius 7 cm in square metres (use 22/7)",
        "Find the area of a circle of radius 7 cm in square metres",
        # Second review (2026-11-13): a circle beside the part is a second figure, whatever
        # the verb; and what is left of a figure is no part's measure.
        "A quadrant is sliced off a circle of radius 14 cm. Find the area of what remains (π = 22/7)",
        "A circle of radius 14 cm with a quadrant missing. Find its area. (use 22/7)",
        "A quadrant is snipped from a circle of radius 14 cm. What area is still there? (use 22/7)",
        "A circle of radius 14 cm loses a quadrant. Find the remaining area. Use 22/7",
        "A quadrant is drawn inside a circle of radius 14 cm, sharing its centre. What area of the circle is not covered by the quadrant? (use 22/7)",
        "A pizza shaped like a circle of radius 14 cm has a quarter circle eaten. Find the area of the pizza that remains (use 22/7)",
        "A quarter of a circle of radius 14 cm is eaten. What is left of the circle? (use 22/7)",
        "What is the area of the part of the circle (radius 14 cm) not in the quadrant? Take π = 22/7",
        "A circle of radius 7 cm is folded in half to make a semicircle. Find the area of the semicircle (use 22/7)",
        "A quarter circle of radius 10 cm is shaded inside a square of side 10 cm. Find the unshaded area.",
        # A circle named beside the part, even the part's own: only a part alone is read.
        "The radius of a circle is 14 cm. Find the area of a quarter of the circle. (use 22/7)",
        # Both sides of a sector named: no one sector.
        "Find the area of the major sector of a circle with radius 7 cm when the minor sector has angle 60° (use 22/7)",
        # A mixed number the circle reader does not read.
        "Find the area of a circle of radius 3½ cm",
        "Find the area of a semicircle of radius 3 1/2 cm (use 22/7)",
    ],
)  # fmt: skip
def test_a_part_or_a_pi_the_solvers_cannot_account_for_is_declined(question: str) -> None:
    intent = extract_math_intent(question)
    block = _build_verified_block(intent, _SETTINGS) if intent is not None else None
    assert block is None or block.canonical_answer is None


@pytest.mark.parametrize(
    ("question", "card"),
    [
        # A whole circle with π itself stays the circle solver's, unchanged.
        ("Find the area of a circle of radius 8 cm", r"201.06"),
        ("Find the circumference of a circle with diameter 14 cm", r"43.98"),
        # A sector by its angle with π itself stays the sector solver's, its major side too:
        # 300/360 * π * 49 ≈ 128.2817 (was the 60° sector's 25.6563).
        ("Find the area of a sector with radius 6 cm and angle 60 degrees", "18.8496"),
        ("Find the area of the major sector of radius 7 cm and angle 60°", "128.2817"),
    ],
)
def test_whole_circles_and_sectors_with_pi_itself_keep_their_solver(
    question: str, card: str
) -> None:
    intent = extract_math_intent(question)
    assert intent is not None and intent.kind in {"circle", "sector"}
    block = _build_verified_block(intent, _SETTINGS)
    assert block is not None and block.canonical_answer == card
