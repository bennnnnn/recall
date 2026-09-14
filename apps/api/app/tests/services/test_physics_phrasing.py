"""P2: the 12 verified physics ops must survive natural phrasing.

Coverage and phrasing are separate defects. The solver already computes
F = ma correctly; before this suite, "a 5 kg mass accelerates at 2 m/s^2,
what is the net force" was verified and "what force accelerates 5 kg at
2 m/s^2" was not — same physics, same numbers, different sentence. A user
sees that as the app being unreliable, not as a missing feature.

Each ``VERIFIED`` row is a phrasing a student would plausibly type for an op
the solver already supports, so a miss is a bug in the extractor. The
``NOT_PHYSICS`` rows are the other half of the contract: physics extractors
run *before* the generic equation extractor, so a cue that is too broad
silently answers algebra with the wrong formula.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.services.math.tools import _build_verified_block, extract_math_intent

PHYSICS_KINDS = {"kinematics", "projectile", "force", "energy"}


def _settings() -> Settings:
    return Settings(math_tools_enabled=True)


def _verified_answer(text: str) -> str | None:
    intent = extract_math_intent(text)
    if intent is None:
        return None
    block = _build_verified_block(intent, _settings())
    return None if block is None else block.canonical_answer


# (question, expected physics_op, expected answer) — the answer is pinned so a
# phrasing cannot "pass" by binding the wrong number to the right parameter.
VERIFIED: list[tuple[str, str, str]] = [
    # Force: F = m a, in all three unknowns and question-first word order.
    ("a 5 kg mass accelerates at 2 m/s^2, what is the net force", "net_force", "10.00 N"),
    ("what force accelerates 5 kg at 2 m/s^2", "net_force", "10.00 N"),
    ("how much force is needed to accelerate a 5 kg box at 2 m/s^2", "net_force", "10.00 N"),
    ("calculate the force on a 5 kg object accelerating at 2 m/s^2", "net_force", "10.00 N"),
    ("a 5 kg trolley accelerates at 2 m/s^2. find F", "net_force", "10.00 N"),
    ("if a 20 N force acts on a 5 kg mass what is the acceleration", "net_force", "4.00 m/s^2"),
    (
        "a 20 N force gives an object an acceleration of 4 m/s^2, find the mass",
        "net_force",
        "5.00 kg",
    ),
    # Projectile: recognized by speed + angle, whatever verb throws it.
    ("projectile launched at 20 m/s at 30 degrees find the range", "range", "35.31 m"),
    ("a ball is thrown at 20 m/s at 30 degrees, what is the range?", "range", "35.31 m"),
    ("how far does a ball go if thrown at 20 m/s at 30 degrees", "range", "35.31 m"),
    ("a ball is kicked at 20 m/s at 30 degrees, how high does it go", "max_height", "5.10 m"),
    (
        "what is the maximum height of a projectile launched at 20 m/s at 30 degrees",
        "max_height",
        "5.10 m",
    ),
    ("how high does a ball launched at 20 m/s at 30 degrees rise", "max_height", "5.10 m"),
    ("find the max height of a ball thrown at 20 m/s at 30 degrees", "max_height", "5.10 m"),
    # Kinematics.
    ("a ball is dropped from 20 m, how long until it hits the ground", "time_to_ground", "2.02 s"),
    ("how long does it take a stone to fall 20 m", "time_to_ground", "2.02 s"),
    ("a rock falls from a 20 m cliff, how long is it in the air", "time_to_ground", "2.02 s"),
    ("a ball is dropped from 20 m, what is its speed after 1 s", "speed", "9.81 m/s"),
    ("how fast is a dropped ball going after 1 s", "speed", "9.81 m/s"),
    ("a ball is dropped from 20 m, how fast is it going after 1 s", "speed", "9.81 m/s"),
    ("a ball is thrown up at 15 m/s, what is its speed after 2 s", "speed", "4.62 m/s"),
    ("a ball is thrown up at 15 m/s, what is its velocity after 2 s", "velocity", "-4.62 m/s"),
    ("what is the velocity of a ball thrown up at 15 m/s after 2 s", "velocity", "-4.62 m/s"),
    ("a ball is thrown up at 15 m/s. find v after 2 s", "velocity", "-4.62 m/s"),
    ("a ball is dropped from 50 m, what is its height after 2 s", "position", "30.38 m"),
    ("a ball is dropped from 50 m, what is its position after 2 s", "position", "30.38 m"),
    ("a ball is dropped from 50 m. find its height after 2 s", "position", "30.38 m"),
    # Free-fall acceleration is a constant, so it carries no graph.
    ("a ball is dropped from 20 m, what is the acceleration", "acceleration", "-9.81 m/s^2"),
    ("what is the acceleration of a ball in free fall from 20 m", "acceleration", "-9.81 m/s^2"),
    ("a rock falls from a 20 m cliff, what is its acceleration", "acceleration", "-9.81 m/s^2"),
    # Energy, including the KE abbreviation and both school forms of power.
    ("kinetic energy of a 2 kg mass at 3 m/s", "kinetic_energy", "9.00 J"),
    ("how much kinetic energy does a 2 kg ball have at 3 m/s", "kinetic_energy", "9.00 J"),
    ("what is the KE of a 2 kg object moving at 3 m/s", "kinetic_energy", "9.00 J"),
    ("potential energy of a 2 kg mass at 5 m", "potential_energy", "98.10 J"),
    (
        "how much potential energy does a 2 kg book on a 5 m shelf have",
        "potential_energy",
        "98.10 J",
    ),
    ("what is the PE of a 2 kg mass at 5 m", "potential_energy", "98.10 J"),
    ("work done by a 10 N force over 3 m", "work", "30.00 J"),
    ("how much work does a 10 N force do pushing a box 3 m", "work", "30.00 J"),
    ("what work is done by a 10 N force over 3 m", "work", "30.00 J"),
    ("power of 100 J in 5 s", "power", "20.00 W"),
    ("power of 100 joules in 5 s", "power", "20.00 W"),
    ("power of 2 kJ in 5 s", "power", "400.00 W"),
    ("what power is needed to do 100 J of work in 5 s", "power", "20.00 W"),
    # P = F v, the form that already worked — the W/t branch must not shadow it.
    ("power of a 10 N force moving at 3 m/s", "power", "30.00 W"),
]


@pytest.mark.parametrize("text,op,answer", VERIFIED, ids=[row[0][:44] for row in VERIFIED])
def test_natural_phrasing_reaches_a_verified_answer(text: str, op: str, answer: str) -> None:
    intent = extract_math_intent(text)
    assert intent is not None, "no intent extracted"
    assert intent.physics_op == op
    assert _verified_answer(text) == answer


# Physics extractors run before the generic equation extractor. If one of
# these lands on a physics kind, a wider cue has stolen another subject.
NOT_PHYSICS = [
    "solve 2x + 7 = 19",
    "solve x^2 - 5x + 6 = 0",
    "find f(x) when f(x) = 3x + 2 and x = 4",
    "find the factors of 24",
    "differentiate f = 3x^2 + 2x",
    "what is the range of the function f(x) = x^2",
    "find the range of 3, 7, 9, 12",
    "Pick a number in the range 2-6",
    "how far is 5 km in miles",
    "how high is 200 cm in feet",
    "how fast is 60 km/h in m/s",
    "how long does it take to drive 120 km at 60 km/h",
    "the police force on duty numbered 30 officers in 2024",
    "I have PE at 3pm and 2 free periods",
    "integrate 2x from 0 to 3",
    "simplify (x + 2)(x - 3)",
]


@pytest.mark.parametrize("text", NOT_PHYSICS)
def test_widened_cues_do_not_steal_other_subjects(text: str) -> None:
    intent = extract_math_intent(text)
    assert intent is None or intent.kind not in PHYSICS_KINDS


def test_solve_for_x_still_routes_to_the_equation_extractor() -> None:
    """The one the ticket calls out by name — algebra must stay algebra."""
    intent = extract_math_intent("solve 2x + 7 = 19")

    assert intent is not None and intent.kind == "equation"
    assert _verified_answer("solve 2x + 7 = 19") == "x = 6"


# Free-body problems the solver does not model. Before P2 these were kept out
# by accident, because no cue matched their wording; now they are refused on
# purpose. Each becomes supported as its own ticket (P5-P7) lands.
UNSUPPORTED_FORCE = [
    "Find the tension supporting a 5 kg mass accelerating at 2 m/s^2.",
    "Find the friction on a 5 kg block with a 10 N load.",
    "what is the net force on a 5 kg block with a friction coefficient of 0.2",
    "what force acts on a 5 kg block on a 30 degree incline",
    "how much force does a spring exert on a 5 kg mass accelerating at 2 m/s^2",
    "what is the centripetal force on a 5 kg mass accelerating at 2 m/s^2",
]


@pytest.mark.parametrize("text", UNSUPPORTED_FORCE)
def test_unsupported_free_body_problems_are_refused_not_guessed(text: str) -> None:
    """A wrong number in the verified block is worse than no block at all."""
    assert _verified_answer(text) is None


def test_speed_without_a_height_draws_the_velocity_line() -> None:
    """v = g*t needs no drop height, and v(t) is the graph that answers it.

    P2 answered this without any graph, because h(t) with h0 = 0 clamps to a
    flat line at zero and reads as "it never moved". Plotting v(t) instead
    removes the reason to withhold a graph: the line is real, and it is the one
    the question asked about.
    """
    from app.services.physics.solver import solve_physics

    intent = extract_math_intent("how fast is a dropped ball going after 1 s")
    assert intent is not None

    result = solve_physics(intent)
    assert result.answer_value == "9.81 m/s"
    assert len(result.graph_specs) == 1
    spec = result.graph_specs[0]
    assert spec.trajectory_type == "velocity_vs_time"
    assert spec.y_label == "Speed (m/s)"
    # Starts at rest and reaches the answer at the asked time.
    assert spec.points[0][1] == 0.0
    assert abs(spec.points[-1][1] - 9.81 * spec.points[-1][0]) < 0.01


def test_a_speed_ask_plots_velocity_even_when_a_height_is_given() -> None:
    """The drop height is known here, so h(t) is available — and still wrong.

    Which graph to draw follows the question, not which data happens to exist.
    """
    from app.services.physics.solver import solve_physics

    intent = extract_math_intent("a ball is dropped from 20 m, what is its speed after 1 s")
    assert intent is not None

    result = solve_physics(intent)
    assert result.answer_value == "9.81 m/s"
    assert len(result.graph_specs) == 1
    assert result.graph_specs[0].trajectory_type == "velocity_vs_time"


def test_a_height_ask_still_plots_height() -> None:
    """The counterpart: a position question keeps h(t)."""
    from app.services.physics.solver import solve_physics

    intent = extract_math_intent("a ball is dropped from 50 m, what is its height after 2 s")
    assert intent is not None

    result = solve_physics(intent)
    assert result.answer_value == "30.38 m"
    assert len(result.graph_specs) == 1
    assert result.graph_specs[0].trajectory_type == "position_vs_time"


def test_a_flat_height_curve_is_still_withheld() -> None:
    """The h(t) guard survives, narrowed to the case that still reaches it.

    Velocity and speed asks now plot v(t), so they never hit this. A position
    ask with an explicit zero height does: every point clamps to zero, and a
    chart that reads "it never moved" is worse than no chart.
    """
    from app.services.physics.solver import solve_physics

    intent = extract_math_intent("a ball is dropped from 0 m, what is its height after 2 s")
    assert intent is not None and intent.physics_op == "position"

    assert solve_physics(intent).graph_specs == []


def test_every_verified_op_has_at_least_three_phrasings() -> None:
    """The ticket's acceptance bar, enforced instead of counted by hand.

    Without this, a later edit can quietly leave an op with one phrasing and
    the suite still passes — which is the state P2 exists to fix.
    """
    from collections import Counter

    covered = Counter(op for _, op, _ in VERIFIED)
    thin = {op: n for op, n in covered.items() if n < 3}

    assert not thin, f"ops with fewer than three phrasings: {thin}"
    assert set(covered) == {
        "position",
        "velocity",
        "speed",
        "acceleration",
        "time_to_ground",
        "range",
        "max_height",
        "net_force",
        "kinetic_energy",
        "potential_energy",
        "work",
        "power",
    }, "the twelve verified ops are the contract — add the phrasings, not an exception"
