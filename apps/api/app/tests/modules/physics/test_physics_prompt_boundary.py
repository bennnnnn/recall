"""Physics prompt policy belongs to physics and never overclaims verification."""

from __future__ import annotations

from app.services.chat.prompt_constants.math import MATH_SOLVER_HINT
from app.services.chat.prompt_constants.physics import (
    PHYSICS_INTENT_HINT,
    PHYSICS_REPLY_POLICY,
    PHYSICS_SHORT_HINT,
)
from app.services.chat.prompt_constants.solving import VERIFIED_SOLVE_SAFETY_HINT


def test_physics_prompt_names_its_subject_and_not_math() -> None:
    assert "This is a physics problem" in PHYSICS_INTENT_HINT
    assert "[BEGIN VERIFIED PHYSICS]" in PHYSICS_INTENT_HINT
    assert "[BEGIN VERIFIED MATH]" not in PHYSICS_INTENT_HINT


def test_math_prompt_contains_no_physics_policy() -> None:
    lower = MATH_SOLVER_HINT.lower()
    assert "physics" not in lower
    assert "projectile" not in lower
    assert "simulation" not in lower


def test_physics_prompt_cannot_claim_an_unverified_result() -> None:
    lower = PHYSICS_INTENT_HINT.lower()
    assert "if no verified block is present, do not claim verification" in lower
    assert "say when you are unsure" in lower
    assert "do not recompute" in lower


def test_physics_working_contract_is_explicit_and_ordered() -> None:
    for policy in (PHYSICS_INTENT_HINT, PHYSICS_REPLY_POLICY):
        positions = [policy.index(name) for name in ("Given", "Find", "Formula", "Substitution")]
        assert positions == sorted(positions)
        assert "Answer" in policy
    assert "governing formula" in PHYSICS_REPLY_POLICY
    assert "each value or equation on its own" in PHYSICS_REPLY_POLICY


def test_physics_prompt_forbids_model_authored_result_fences() -> None:
    for language in ("answer", "graph", "simulation", "geometry"):
        assert f"```{language}" in PHYSICS_INTENT_HINT
        assert f"```{language}" in PHYSICS_SHORT_HINT


def test_universal_verification_rule_lives_in_neutral_prompt_layer() -> None:
    lower = VERIFIED_SOLVE_SAFETY_HINT.lower()
    assert "verified" in lower
    assert "never claim" in lower
    assert "physics" not in lower
    assert "math" not in lower


def test_subject_prompt_budgets_remain_small() -> None:
    assert len(PHYSICS_INTENT_HINT) <= 1200
    assert len(PHYSICS_REPLY_POLICY) <= 900
