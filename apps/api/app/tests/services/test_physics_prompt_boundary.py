"""P10: the physics hint must stay true to what the solver actually verifies.

This is the counterpart to P1. P1 stopped internal scaffolding leaking *out*;
P10 stops unearned confidence leaking *in* — when a topic is not verified the
model should say so rather than answer in the same voice it uses for a checked
result.

The ticket asked for a boundary statement. Writing it turned up something
worse: the hint's claim had gone **stale**. It still said physics meant
"kinematics, projectile motion, forces, energy" after P4-P8 had added momentum,
friction, circular, spring and circuit, and it still said trajectory graphs were
"only for kinematics (height vs time) and projectile motion" after P3 added
velocity-vs-time and P7 added the SHM curve. Six of ten verified kinds were
missing and nothing failed, because no test tied the prompt to the registry.

These tests are that tie. A tenth — or eleventh — kind now fails the build until
the prompt is told about it.
"""

from __future__ import annotations

import typing

import pytest

from app.models.schemas.math.graph import GraphBlockSpec
from app.services.chat.prompt_constants.math import MATH_SOLVER_HINT
from app.services.physics.block import PHYSICS_BLOCK_BUILDERS

# Ships on every math turn, so growth is a real cost. Sized just above the
# current length: a failing coverage assertion below must be fixed by naming the
# topic, not by pasting another paragraph.
MAX_HINT_CHARS = 2200


@pytest.mark.parametrize("kind", sorted(PHYSICS_BLOCK_BUILDERS))
def test_every_verified_physics_kind_is_named_in_the_hint(kind: str) -> None:
    """Adding a solver without telling the prompt is the drift this catches.

    The model is told to use verified numbers for the topics the hint lists. A
    kind the hint omits is one the model has no reason to trust — which is how
    five topics went unmentioned for five tickets.
    """
    assert kind in MATH_SOLVER_HINT.lower(), (
        f"{kind!r} is in PHYSICS_BLOCK_BUILDERS but not named in MATH_SOLVER_HINT. "
        "Add it to the verified list in prompt_constants/math.py."
    )


# Each trajectory_type the solver can emit, and the wording the hint uses for
# it. The mapping is explicit on purpose: a new enum member fails here until
# someone decides how to describe it, rather than passing on a vague substring.
_TRAJECTORY_WORDING = {
    "position_vs_time": "height or velocity against time",
    "velocity_vs_time": "height or velocity against time",
    "parametric": "x-y path",
}


def test_the_trajectory_mapping_covers_every_emittable_type() -> None:
    """The mapping itself must not fall behind the schema."""
    field = GraphBlockSpec.model_fields["trajectory_type"]
    literal = typing.get_args(field.annotation)[0]

    assert set(typing.get_args(literal)) == set(_TRAJECTORY_WORDING)


@pytest.mark.parametrize("trajectory_type,wording", sorted(_TRAJECTORY_WORDING.items()))
def test_each_trajectory_type_is_described_in_the_hint(trajectory_type: str, wording: str) -> None:
    """The hint told the model velocity-vs-time and SHM graphs did not exist."""
    assert wording in MATH_SOLVER_HINT, (
        f"{trajectory_type!r} can be emitted but the hint does not describe it."
    )


def test_the_shm_graph_is_mentioned() -> None:
    """P7's oscillation curve is a third shape, not a second kinematics one."""
    assert "displacement against time" in MATH_SOLVER_HINT


def test_the_hint_states_the_boundary() -> None:
    """The ticket's actual ask: be explicit about what is *not* checked.

    Wording follows the file's existing convention for limits/series/statistics
    so the model reads one rule, not two.
    """
    lower = MATH_SOLVER_HINT.lower()

    assert "do not claim verification" in lower
    assert "be cautious and say when you are unsure" in lower


# "pendulum" was one of these until P15 solved it. It is deliberately not moved
# to a "was a gap" list: the point of this table is what the model must still be
# cautious about, and a solved topic belongs in the coverage test above instead.
_KNOWN_GAPS = ["pressure", "thermodynamics", "gravitation", "waves", "optics"]


@pytest.mark.parametrize("topic", _KNOWN_GAPS)
def test_the_known_gaps_are_named(topic: str) -> None:
    """Concrete beats generic.

    These are the topics the review found uncovered and deliberately did not
    ticket. Naming them makes the caution something the model can act on.
    """
    assert topic in MATH_SOLVER_HINT.lower()


def test_a_solved_topic_is_not_still_listed_as_unchecked() -> None:
    """The half of the boundary that silently rots.

    Adding a solver and leaving the caution in place is the mirror of P10's
    original finding, and it fails quieter: the model reads "pendulum is not
    checked" while holding a verified pendulum answer, and hedges a number it
    was handed. Substring coverage cannot catch it — after P15 the word appears
    in both lists — so the sentence that names the gaps is read on its own.
    """
    unchecked = MATH_SOLVER_HINT.lower().split("outside that list (")[1].split(")")[0]

    assert "pendulum" not in unchecked
    assert set(_KNOWN_GAPS) <= {topic.strip() for topic in unchecked.split(",")}


def test_the_hint_stays_within_its_budget() -> None:
    """Every math turn pays for this string.

    Without a cap, the honest fix for a failing coverage test above is to append
    prose forever.
    """
    assert len(MATH_SOLVER_HINT) <= MAX_HINT_CHARS, (
        f"MATH_SOLVER_HINT is {len(MATH_SOLVER_HINT)} chars (budget {MAX_HINT_CHARS}). "
        "Tighten existing wording rather than raising the cap."
    )
