"""Subject registry: one owner per turn, chemistry on the shared solve block."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings
from app.modules.chemistry.block import VerifiedChemistry
from app.services.solving import VerifiedSolveBlock
from app.services.subject_solving import (
    build_subject_augmentation,
    detect_subject,
    maybe_direct_subject_reply,
)


def test_image_extract_is_math_before_any_peer() -> None:
    from app.models.schemas.math import MathImageExtract

    extract = MathImageExtract(lhs="2x+3", rhs="11")
    assert (
        detect_subject(
            "Find Gibbs free energy when delta H=-40 kJ, delta S=-100 J and T=300 K",
            image_math_extract=extract,
        )
        == "math"
    )


def test_physics_wins_over_math() -> None:
    assert detect_subject("find the force on a 2 kg mass accelerating at 3 m/s^2") == "physics"


def test_closed_chemistry_wins_over_algebra_lookalike() -> None:
    text = "Find Gibbs free energy when delta H=-40 kJ, delta S=-100 J and T=300 K"
    assert detect_subject(text) == "chemistry"


def test_chemistry_lookup_runs_when_no_peer_claims() -> None:
    assert detect_subject("IUPAC name of SMILES CCO") == "chemistry"


def test_disabled_chemistry_does_not_claim_a_lookup() -> None:
    assert detect_subject("IUPAC name of SMILES CCO", chemistry_enabled=False) is None


@pytest.mark.asyncio
async def test_closed_chemistry_does_not_also_solve_as_math() -> None:
    text = "Find Gibbs free energy when delta H=-40 kJ, delta S=-100 J and T=300 K"
    with patch(
        "app.services.subject_solving.build_math_augmentation",
        AsyncMock(side_effect=AssertionError("math must not run")),
    ):
        result = await build_subject_augmentation(text, Settings(chemistry_enabled=True))
    assert result.subject == "chemistry"
    assert isinstance(result.verified, VerifiedChemistry)
    assert isinstance(result.verified, VerifiedSolveBlock)
    reply = maybe_direct_subject_reply(result.verified, text)
    assert reply is not None
    assert "**ΔG = -10 kJ/mol** ✅" in reply
    assert "```answer" not in reply
