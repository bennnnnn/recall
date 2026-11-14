"""A typed reading of the student's own words keeps its card over a model's other value.

On a model-written turn whose Answer gave the asked quantity another value, the server's card
and scene were dropped and the model's value shipped unchecked (#2420): "A 1200 kg car
accelerates from rest to 20 m/s in 8 s" lost its verified 3000 N to a model's 3800 N (audit
2026-11-13, PHYS-02). The owner's rule since 2026-11-13: a card a typed reader read from the
student's own words stands, under a correction line; a follow-up's rewrite or a scanner photo's
reading is the one in doubt and keeps today's rule.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.physics.fence import read_from_their_words, validate_physics_fences
from app.modules.physics.prompt import solve_physics_request
from app.services.answer_fence import UNCHECKED_ANSWER_MARKER, VERIFIED_ANSWER_MARKER
from app.services.solving import VerifiedPhysicsBlock
from app.services.subject_scan import SCAN_CONFIRMED_PREFIX, SCANNER_CAMERA_PROMPTS

_SETTINGS = Settings(math_tools_enabled=True)

_FORCE = "A 1200 kg car accelerates from rest to 20 m/s in 8 s. What is the net force on it?"
_MODEL = (
    "**Solution**\n\na = 20/8 = 2.5 m/s², F = ma = 1200 × 2.5 = 3800 N\n\n**Answer**\n\nF = 3800 N"
)


@pytest.fixture(scope="module")
def force() -> VerifiedPhysicsBlock:
    outcome, block = solve_physics_request(_FORCE, _SETTINGS, None)
    assert outcome == "verified" and block is not None
    assert block.display_answer == "3000\\,\\mathrm{N}"
    return block


def test_a_typed_reading_of_their_words_keeps_its_card_over_the_models_value(
    force: VerifiedPhysicsBlock,
) -> None:
    """PHYS-02: the model's 3800 N used to replace the server's 3000 N, unchecked."""
    out = validate_physics_fences(_MODEL, verified=force, user_text=_FORCE)
    assert f"```answer\n{VERIFIED_ANSWER_MARKER}\n3000\\,\\mathrm{{N}}\n```" in out
    assert "The verified answer is $3000\\,\\mathrm{N}$." in out
    assert UNCHECKED_ANSWER_MARKER not in out


def test_a_follow_ups_rewrite_leaves_the_models_value_unchecked(
    force: VerifiedPhysicsBlock,
) -> None:
    """The problem was rewritten from "what if it took 8 s?": that reading is in doubt."""
    out = validate_physics_fences(_MODEL, verified=force, user_text="what if it took 8 s?")
    assert f"```answer\n{UNCHECKED_ANSWER_MARKER}\nF = 3800 N" in out
    assert VERIFIED_ANSWER_MARKER not in out


@pytest.mark.parametrize(
    ("user_text", "typed"),
    [
        (_FORCE, True),
        # The plan's part: the sentences are the student's, around other words.
        (f"Quick one. {_FORCE} Thanks!", True),
        ("what if it took 8 s?", False),
        # A scanner photo's reading rides in its caption.
        (f"{SCANNER_CAMERA_PROMPTS['physics']}\n{SCAN_CONFIRMED_PREFIX} {_FORCE}", False),
    ],
)
def test_a_reading_is_the_students_own_only_when_its_sentences_are_theirs(
    force: VerifiedPhysicsBlock, user_text: str, typed: bool
) -> None:
    assert read_from_their_words(force, user_text) is typed
