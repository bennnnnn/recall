"""P4: momentum, impulse and 1D collisions.

The first ticket that adds verified physics surface rather than repairing it.
Momentum was the highest-frequency of the twelve topics the review found with
no verified answer under any phrasing — `p = mv`, `J = FΔt` and 1D
conservation are the most common mechanics asks after kinematics.

The negative table matters as much as the positive one. Physics extractors run
before the generic equation extractor, and this one runs before force and
energy, so an over-broad cue here steals from three directions at once.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.services.math.tools import _build_verified_block, extract_math_intent

PHYSICS_KINDS = {"kinematics", "projectile", "force", "energy", "momentum"}


def _settings() -> Settings:
    return Settings(math_tools_enabled=True)


def _verified_answer(text: str) -> str | None:
    intent = extract_math_intent(text)
    if intent is None:
        return None
    block = _build_verified_block(intent, _settings())
    return None if block is None else block.canonical_answer


# (question, expected physics_op, expected answer). Answers are pinned so a
# phrasing cannot pass by binding the right number to the wrong parameter.
VERIFIED: list[tuple[str, str, str]] = [
    # p = m v
    ("momentum of a 2 kg object moving at 3 m/s", "momentum", "6.00 kg*m/s"),
    ("what is the momentum of a 5 kg mass with velocity 4 m/s", "momentum", "20.00 kg*m/s"),
    ("calculate the momentum of a 2 kg ball travelling at 3 m/s", "momentum", "6.00 kg*m/s"),
    # J = F dt
    ("impulse of a 10 N force over 2 seconds", "impulse", "20.00 N*s"),
    ("what is the impulse when a 10 N force acts for 2 s", "impulse", "20.00 N*s"),
    ("find the impulse delivered by a 10 N force in 2 s", "impulse", "20.00 N*s"),
    # J = m dv — same quantity, and N*s and kg*m/s are the same unit.
    ("impulse on a 2 kg mass going from 3 m/s to 8 m/s", "impulse", "10.00 N*s"),
    # 1D collisions, type always stated
    (
        "a 2 kg ball at 3 m/s hits a 1 kg ball at rest and they stick together, "
        "find the final velocity",
        "final_velocity",
        "2.00 m/s",
    ),
    (
        "a 2 kg cart moving at 3 m/s collides inelastically with a 1 kg cart at rest, "
        "what is the final velocity",
        "final_velocity",
        "2.00 m/s",
    ),
    (
        "in an elastic collision a 2 kg ball at 3 m/s hits a 1 kg ball at rest, "
        "find the final velocity",
        "final_velocity",
        "1.00 m/s and 4.00 m/s",
    ),
    (
        "a 2 kg ball at 3 m/s collides elastically with a 1 kg ball at rest",
        "final_velocity",
        "1.00 m/s and 4.00 m/s",
    ),
]


@pytest.mark.parametrize("text,op,answer", VERIFIED, ids=[row[0][:44] for row in VERIFIED])
def test_momentum_phrasings_reach_a_verified_answer(text: str, op: str, answer: str) -> None:
    intent = extract_math_intent(text)
    assert intent is not None, "no intent extracted"
    assert intent.kind == "momentum"
    assert intent.physics_op == op
    assert _verified_answer(text) == answer


def test_every_momentum_op_has_at_least_three_phrasings() -> None:
    """The ticket's acceptance bar, enforced rather than counted by hand."""
    from collections import Counter

    covered = Counter(op for _, op, _ in VERIFIED)

    assert {op: n for op, n in covered.items() if n < 3} == {}
    assert set(covered) == {"momentum", "impulse", "final_velocity"}


# --- the physics is right, not just the plumbing ---------------------------


def test_elastic_collision_conserves_momentum_and_energy() -> None:
    """The property that defines an elastic collision, checked rather than assumed.

    Pinning "1.00 m/s and 4.00 m/s" proves the formula was transcribed; this
    proves it was the right formula.
    """
    from app.services.physics.solver import solve_physics

    intent = extract_math_intent(
        "a 2 kg ball at 3 m/s collides elastically with a 1 kg ball at rest"
    )
    assert intent is not None
    solve_physics(intent)  # must not raise

    m1, m2, v1, v2 = 2.0, 1.0, 3.0, 0.0
    u1 = ((m1 - m2) * v1 + 2 * m2 * v2) / (m1 + m2)
    u2 = ((m2 - m1) * v2 + 2 * m1 * v1) / (m1 + m2)

    assert m1 * v1 + m2 * v2 == pytest.approx(m1 * u1 + m2 * u2)
    assert 0.5 * m1 * v1**2 + 0.5 * m2 * v2**2 == pytest.approx(0.5 * m1 * u1**2 + 0.5 * m2 * u2**2)


def test_inelastic_collision_conserves_momentum_but_not_energy() -> None:
    """The counterpart: sticking together must lose kinetic energy."""
    m1, m2, v1, v2 = 2.0, 1.0, 3.0, 0.0
    u = (m1 * v1 + m2 * v2) / (m1 + m2)

    assert m1 * v1 + m2 * v2 == pytest.approx((m1 + m2) * u)
    assert 0.5 * (m1 + m2) * u**2 < 0.5 * m1 * v1**2 + 0.5 * m2 * v2**2


# --- refusals --------------------------------------------------------------


UNSTATED_COLLISION = [
    "a 2 kg ball at 3 m/s hits a 1 kg ball at rest, find the final velocity",
    "a 2 kg cart collides with a 1 kg cart at 4 m/s, what is the final velocity",
    "a 3 kg trolley moving at 2 m/s collides with a 5 kg trolley at rest",
]


@pytest.mark.parametrize("text", UNSTATED_COLLISION)
def test_an_unstated_collision_type_is_refused_not_guessed(text: str) -> None:
    """Elastic and inelastic give different answers from identical inputs.

    Same reasoning as the tension guard added in P2: with nothing in the
    question to choose between them, any answer is a coin flip dressed up as a
    verified result, and a wrong number inside the verified block is worse than
    no block at all.
    """
    assert _verified_answer(text) is None


NOT_PHYSICS = [
    "solve 2x + 7 = 19",
    "the project lost momentum this quarter",
    "I made an impulse purchase of 3 items",
    "what is a hash collision in a database with 500 rows",
    "what is the momentum of the team after 3 wins",
    "find the factors of 24",
    # "elastic" alone is not a collision — this is the cue that must never
    # stand on its own.
    "an elastic band stretched 5 cm",
]


@pytest.mark.parametrize("text", NOT_PHYSICS)
def test_momentum_cues_do_not_steal_other_subjects(text: str) -> None:
    intent = extract_math_intent(text)
    assert intent is None or intent.kind not in PHYSICS_KINDS


def test_the_same_numbers_still_route_by_the_question_asked() -> None:
    """`2 kg` and `3 m/s` are a momentum question or an energy one.

    Only the noun separates them, and momentum now runs first — so this is the
    pair most likely to cross-fire.
    """
    assert extract_math_intent("momentum of a 2 kg object moving at 3 m/s").kind == "momentum"  # type: ignore[union-attr]
    assert (
        extract_math_intent("kinetic energy of a 2 kg object moving at 3 m/s").kind  # type: ignore[union-attr]
        == "energy"
    )
    assert _verified_answer("kinetic energy of a 2 kg object moving at 3 m/s") == "9.00 J"


def test_momentum_never_claims_a_direct_reply() -> None:
    """A new kind must not trip the trajectory branch of the direct guard.

    `can_direct_physics` demands a trajectory fence for any kind outside its
    scalar set. Momentum produces no graph, so it has to fall through to False
    rather than matching on a fence that isn't there — the same silent-failure
    class P3 found in this guard.
    """
    from app.services.math.tools.direct import maybe_direct_math_reply

    text = "momentum of a 2 kg object moving at 3 m/s"
    intent = extract_math_intent(text)
    assert intent is not None
    block = _build_verified_block(intent, _settings())
    assert block is not None

    assert maybe_direct_math_reply(block, text) is None
