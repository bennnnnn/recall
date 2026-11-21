"""P17: vector forces — resultants and components.

Everything else on the `force` kind is scalar, which is why "a 3 N force east
and a 4 N force north" had no answer at all.

The ticket asked which extractor should own this, since `modules/math/` already
has a `vector` kind for magnitude/dot/cross. It cannot: that one matches literal
angle-bracket operands ("magnitude of <3, 4>") through
`is_closed_coordinate_vector_request`, and a force question names units and
compass directions instead. The two never see the same sentence. This is a
physics extractor and the maths one is untouched — asserted below rather than
asserted in a PR description.
"""

from __future__ import annotations

import math

import pytest

from app.core.config import Settings
from app.modules.math.tools import _build_verified_block as build_math_block
from app.modules.math.tools import extract_math_intent as extract_real_math_intent
from app.modules.physics.schemas import PhysicsIntent
from app.tests.modules.physics.support import build_verified_physics_block, extract_physics_intent

PHYSICS_KINDS = {
    "kinematics",
    "suvat",
    "projectile",
    "force",
    "energy",
    "momentum",
    "friction",
    "circular",
    "spring",
    "circuit",
    "torque",
}


def _settings() -> Settings:
    return Settings(math_tools_enabled=True)


def _verified_answer(text: str) -> str | None:
    intent = extract_physics_intent(text)
    if intent is None:
        return None
    block = build_verified_physics_block(intent, _settings())
    return None if block is None else block.canonical_answer


VERIFIED: list[tuple[str, str, str]] = [
    # 3-4-5, and the bearing is measured from the first force.
    (
        "a 3 N force east and a 4 N force north, what is the resultant",
        "resultant_force",
        "5 N at 53.1°",
    ),
    (
        "what is the resultant of a 3 N and a 4 N force at right angles",
        "resultant_force",
        "5 N at 53.1°",
    ),
    (
        "find the resultant of a 3 N horizontal force and a 4 N vertical force",
        "resultant_force",
        "5 N at 53.1°",
    ),
    (
        "Two forces act on an object: 3 N east and 4 N north. "
        "Find the resultant magnitude and direction.",
        "resultant_force",
        "5 N at 53.1°",
    ),
    # Not perpendicular: the general parallelogram law.
    (
        "what is the resultant of a 3 N and a 4 N force at 60 degrees to each other",
        "resultant_force",
        "6.08 N at 34.7°",
    ),
    (
        "resolve a 10 N force at 30 degrees into components",
        "resolve_vector",
        "8.66 N horizontally and 5 N vertically",
    ),
    (
        "find the components of a 10 N force acting at 30 degrees",
        "resolve_vector",
        "8.66 N horizontally and 5 N vertically",
    ),
    (
        "resolve a 10 N force acting at 30 degrees into horizontal and vertical components",
        "resolve_vector",
        "8.66 N horizontally and 5 N vertically",
    ),
    # Any vector, in the unit it is given in (owner's chat, 2026-11-20).
    (
        "Resolve 45 m/s at an angle of 80° from the horizontal into two components.",
        "resolve_vector",
        "7.81 m/s horizontally and 44.3 m/s vertically",
    ),
    # Measured from the vertical: the sine is across, the cosine up.
    (
        "Resolve 1900 km at an angle of 40° from the vertical into two components.",
        "resolve_vector",
        "1221 km horizontally and 1455 km vertically",
    ),
    # A bearing: west of north is from the vertical, and west is the negative side.
    (
        "A hiker walks 5 km 40° west of north. Find the components of the displacement.",
        "resolve_vector",
        "3.21 km west and 3.83 km north",
    ),
    (
        "Resolve an acceleration of 3 m/s^2 at 20° below the horizontal into components.",
        "resolve_vector",
        "2.82 m/s² horizontally and -1.03 m/s² vertically",
    ),
    # A plane is an aircraft here, not an inclined plane.
    (
        "A plane flies at 250 km/h, 30° north of east. Find the components of its velocity.",
        "resolve_vector",
        "217 km/h east and 125 km/h north",
    ),
    (
        "Find the horizontal and vertical components of a momentum of 12 kg m/s at 60° to "
        "the horizontal.",
        "resolve_vector",
        "6 kg·m/s horizontally and 10.4 kg·m/s vertically",
    ),
    # "the vertical component" names what is asked, and alone: the angle is still from the
    # horizontal, and the card holds that one component.
    (
        "A force of 60 N acts at 30° above the horizontal. Find the magnitude of the vertical "
        "component.",
        "resolve_vector",
        "30 N vertically",
    ),
    # A three-figure bearing is clockwise from north: the sine is east, the cosine north.
    (
        "A plane flies 300 km/h on a bearing of 40°. Find the north and east components.",
        "resolve_vector",
        "193 km/h east and 230 km/h north",
    ),
    (
        "A ship sails 25 km on a bearing of 120°. Find the east and north components.",
        "resolve_vector",
        "21.7 km east and 12.5 km south",
    ),
    (
        "Resolve 25 m/s at 120° from the positive x-axis into components.",
        "resolve_vector",
        "-12.5 m/s horizontally and 21.7 m/s vertically",
    ),
    # The vertical named right after the angle, with "angle" or "axis" around it.
    (
        "Find the horizontal and vertical components of a 60 N force making a 30° angle with "
        "the vertical.",
        "resolve_vector",
        "30 N horizontally and 52 N vertically",
    ),
    (
        "Resolve a 10 m/s velocity directed at 30° to the vertical axis into components.",
        "resolve_vector",
        "5 m/s horizontally and 8.66 m/s vertically",
    ),
    # "below horizontal" without "the" still points down.
    (
        "Resolve a velocity of 15 m/s at 20° below horizontal into horizontal and vertical "
        "components.",
        "resolve_vector",
        "14.1 m/s horizontally and -5.13 m/s vertically",
    ),
    # A bearing past 180°: west and south.
    (
        "A ship sails 25 km on a bearing of 240°. Find the east and north components.",
        "resolve_vector",
        "21.7 km west and 12.5 km south",
    ),
    # A list marker or a word after a number is no second value (Claude review).
    (
        "1. Resolve a 60 N force at 30° above the horizontal into components.",
        "resolve_vector",
        "52 N horizontally and 30 N vertically",
    ),
    (
        "Resolve a 60 N force at 30° above the horizontal into components. Give 2 decimal places.",
        "resolve_vector",
        "52 N horizontally and 30 N vertically",
    ),
    # "on a bearing of 30° north of east" is a quadrant bearing, not 030° (Gemini review).
    (
        "A hiker walks 5 km on a bearing of 40° west of south. Find the components of the "
        "displacement.",
        "resolve_vector",
        "3.21 km west and 3.83 km south",
    ),
    # The vertical without "the", or as the positive y-axis.
    (
        "Resolve 25 m/s at 30° from the positive y-axis into components.",
        "resolve_vector",
        "12.5 m/s horizontally and 21.7 m/s vertically",
    ),
    (
        "Resolve a velocity of 15 m/s at 20° from vertical into horizontal and vertical "
        "components.",
        "resolve_vector",
        "5.13 m/s horizontally and 14.1 m/s vertically",
    ),
    # A westward component asked alone is that component, by its side (Gemini review).
    (
        "A hiker walks 5 km 40° west of north. Find the westward component.",
        "resolve_vector",
        "3.21 km west",
    ),
    (
        "Resolve a 60 N force at 30° above the horizontal into components in 2 steps.",
        "resolve_vector",
        "52 N horizontally and 30 N vertically",
    ),
    # "m/s2" as students write it (Codex review).
    (
        "Resolve 3 m/s2 at 20° below the horizontal into components.",
        "resolve_vector",
        "2.82 m/s² horizontally and -1.03 m/s² vertically",
    ),
]


def test_a_large_vector_s_working_has_no_calculator_notation() -> None:
    """Gemini review: 2e+06 in a LaTeX row reads as 2e plus 06."""
    intent = extract_physics_intent(
        "Resolve an electric field of 2 × 10^6 N/C at 30° from the horizontal into components."
    )
    assert intent is not None and intent.physics_op == "resolve_vector"
    block = build_verified_physics_block(intent, _settings())
    assert block is not None
    rows = " ".join(block.physics_substitutions)
    assert "e+" not in rows and r"2 \times 10^{6}" in rows


@pytest.mark.parametrize(
    "text",
    [
        # Along a slope is the incline's own law, never across and up.
        "a 50 N weight rests on a 30° incline; find its component along the slope",
        "find the component of a 20 N force parallel to a ramp at 25°",
        # A component inside another law, or one value of a bigger problem (review, 2026-11-20).
        "A wire 0.5 m long carries 2 A at 30° to a 0.3 T field. Find the force on the wire "
        "using the component of the field perpendicular to it.",
        "A proton moves at 2e6 m/s at 30° to a magnetic field of 0.5 T. Find the radius of its "
        "path using the velocity component perpendicular to the field.",
        "A 2 kg mass is at the end of a 1.5 m string at 30° from the vertical. Find the "
        "components of tension.",
        "A ray travels 5 cm in glass at 30° to the normal. Find its components.",
        "A ball is thrown at 20 m/s at 30° above the horizontal. Find the horizontal and "
        "vertical components of velocity and the range.",
        # A side or an axis this reader does not model is declined, never read as from the
        # horizontal with both components positive (Gemini review, 2026-11-20).
        "Resolve 20 N at 30° to the left of the vertical into horizontal and vertical components.",
        "Resolve 25 m/s at 60° from the negative x-axis into components.",
        "A plane flies at 200 km/h on a bearing of N 30° W. Find the components of its velocity.",
        # A component against a lever or a surface is not across and up.
        "A 50 N force acts at 30° to a lever. Find the component of the force perpendicular "
        "to the lever.",
        "A 50 N weight rests on a 30° hill. Find the component of the weight perpendicular "
        "to the hill.",
        # A negative angle, and a quadrant bearing past a right angle, are not read.
        "Resolve 10 N at -30° from the horizontal into components.",
        "A hiker walks 5 km 120° west of north. Find the components of the displacement.",
        # A negative axis or a named quadrant is not modelled; a torque is no vector here.
        "Resolve 25 m/s at 60° from the -x-axis into components.",
        "A 50 N force in the third quadrant makes an angle of 30° with the x-axis. Find its x "
        "and y components.",
        "Resolve 20 N·m at 30° from the horizontal into two components.",
        # A compass side on the vector itself, not a bearing (Gemini review).
        "A boat travels 10 m/s west at 30° to the shoreline. Find the north and east components.",
    ],
)
def test_a_component_along_a_slope_is_not_resolved_across_and_up(text: str) -> None:
    intent = extract_physics_intent(text)
    assert intent is None or intent.physics_op != "resolve_vector"


@pytest.mark.parametrize("text,op,answer", VERIFIED, ids=[row[0][:44] for row in VERIFIED])
def test_vector_force_phrasings_reach_a_verified_answer(text: str, op: str, answer: str) -> None:
    intent = extract_physics_intent(text)

    assert intent is not None, "no intent extracted"
    assert intent.kind == "force"
    assert intent.physics_op == op
    assert _verified_answer(text) == answer


def test_both_ops_have_at_least_three_phrasings() -> None:
    from collections import Counter

    covered = Counter(op for _, op, _ in VERIFIED)

    assert set(covered) == {"resultant_force", "resolve_vector"}
    assert {op: n for op, n in covered.items() if n < 3} == {}


# --- the physics ------------------------------------------------------------


def test_perpendicular_is_the_general_law_at_ninety_degrees() -> None:
    """One formula, not two.

    R = sqrt(F1² + F2² + 2F1F2cos φ) drops its cosine term at 90°, so the
    right-angle case needs no separate branch — and if someone later adds one,
    this catches the two drifting apart.
    """
    perpendicular = _verified_answer(
        "what is the resultant of a 3 N and a 4 N force at right angles"
    )
    stated = _verified_answer(
        "what is the resultant of a 3 N and a 4 N force at 90 degrees to each other"
    )

    assert perpendicular == stated == "5 N at 53.1°"


def test_the_components_rebuild_the_force_they_came_from() -> None:
    """Resolve then recombine: the round trip has to return the original.

    A swapped sine and cosine passes a magnitude check and fails this one.
    """
    answer = _verified_answer("resolve a 10 N force at 30 degrees into components")

    assert answer is not None
    fx, fy = (float(part.split()[0]) for part in answer.split(" and "))

    assert math.hypot(fx, fy) == pytest.approx(10.0, abs=0.01)
    assert math.degrees(math.atan2(fy, fx)) == pytest.approx(30.0, abs=0.01)
    # cos(30°) > sin(30°), so the horizontal component is the larger one.
    assert fx > fy


def test_the_bearing_is_measured_from_the_first_force() -> None:
    """53.13° is atan(4/3), not atan(3/4).

    Which force the angle is measured from is a choice, and the wrong one gives
    36.87° — a plausible number for the same question. Naming it pins the
    convention.
    """
    answer = _verified_answer("a 3 N force east and a 4 N force north, what is the resultant")

    assert answer is not None
    bearing = float(answer.split(" at ")[1].rstrip("°"))

    assert bearing == pytest.approx(math.degrees(math.atan2(4, 3)), rel=5e-3)
    assert bearing != pytest.approx(math.degrees(math.atan2(3, 4)), rel=5e-3)


def test_two_forces_in_line_simply_add() -> None:
    """The degenerate case the parallelogram law still has to get right."""
    answer = _verified_answer(
        "what is the resultant of a 3 N and a 4 N force at 0 degrees to each other"
    )

    assert answer is not None
    assert float(answer.split()[0]) == pytest.approx(7.0, abs=0.01)


def test_two_opposed_forces_cancel_to_their_difference() -> None:
    answer = _verified_answer(
        "what is the resultant of a 3 N and a 4 N force at 180 degrees to each other"
    )

    assert answer is not None
    assert float(answer.split()[0]) == pytest.approx(1.0, abs=0.01)


# --- the cue hazard the ticket named ----------------------------------------


def test_the_maths_vector_kind_is_untouched() -> None:
    """The ticket asked which extractor should own this. Both do, separately.

    The maths one needs literal angle brackets; this one needs units. Neither
    sentence is ambiguous, so neither had to give way.
    """
    magnitude = extract_real_math_intent("magnitude of <3, 4>")
    dot = extract_real_math_intent("dot product of <1, 2> and <3, 4>")

    assert magnitude is not None and magnitude.kind == "vector"
    assert dot is not None and dot.kind == "vector"
    magnitude_block = build_math_block(magnitude, _settings())
    dot_block = build_math_block(dot, _settings())
    assert magnitude_block is not None and magnitude_block.canonical_answer == "5"
    assert dot_block is not None and dot_block.canonical_answer == "11"


NOT_PHYSICS = [
    "lets resolve this issue in 3 days",
    "the components of the plan take 3 weeks",
    "resolve the 2 merge conflicts",
    "what are the 3 components of the system",
    "the resultant of the meeting was 2 action items",
    "solve 2x + 7 = 19",
]


@pytest.mark.parametrize("text", NOT_PHYSICS)
def test_resolve_and_component_never_stand_alone(text: str) -> None:
    """Both are ordinary English, and these cues feed the global pre-filter.

    "resultant" is specific and still needs a newton reading; "resolve" and
    "component" are not specific at all, so they need the force *and* the angle
    before they count.
    """
    intent = extract_physics_intent(text)
    assert intent is None or intent.kind not in PHYSICS_KINDS


def test_plain_newtons_second_law_still_reaches_the_force_extractor() -> None:
    """This runs before force, so it must not swallow ordinary F = ma."""
    intent = extract_physics_intent("a 5 kg mass accelerates at 2 m/s^2, what is the net force")

    assert isinstance(intent, PhysicsIntent) and intent.physics_op == "net_force"
    assert _verified_answer("a 5 kg mass accelerates at 2 m/s^2, what is the net force") == "10 N"


UNDERSPECIFIED = [
    # The angle between them is the whole problem; two magnitudes do not imply it.
    "what is the resultant of a 3 N and a 4 N force",
    "what is the resultant force on the box",
    # Resolving needs a direction to resolve along.
    "resolve a 10 N force into components",
    "find the components of the force",
]


@pytest.mark.parametrize("text", UNDERSPECIFIED)
def test_missing_geometry_is_refused_not_assumed(text: str) -> None:
    """Assuming a right angle would be the most natural wrong answer here.

    Two magnitudes and no stated geometry describe infinitely many resultants
    between 1 N and 7 N; picking 5 N because perpendicular is common would be a
    guess wearing a verified block.
    """
    assert _verified_answer(text) is None


def test_a_bearing_is_worked_as_sizes_along_its_directions() -> None:
    """Gemini review: the working ended "s_y = -12.5 km south", a double negative beside a
    card naming the side. A bearing is worked from its acute angle to the north-south line,
    each component a size along the way it points."""
    intent = extract_physics_intent(
        "A ship sails 25 km on a bearing of 240°. Find the east and north components."
    )
    assert intent is not None
    block = build_verified_physics_block(intent, _settings())
    assert block is not None
    assert block.physics_substitutions == (r"s_{W} = 25\sin(60^\circ)", r"s_{S} = 25\cos(60^\circ)")
    assert block.canonical_answer == "21.7 km west and 12.5 km south"
    assert "-" not in (block.physics_working or "").split("Verified substitution:")[-1]


def test_a_vector_along_an_axis_has_a_zero_component_not_float_noise() -> None:
    """Claude review: 60 N at 90° printed 3.67 x 10^-15 N across."""
    answer = _verified_answer("Resolve 60 N at 90° from the horizontal into components.")
    assert answer is not None and "10^" not in answer and "×" not in answer
