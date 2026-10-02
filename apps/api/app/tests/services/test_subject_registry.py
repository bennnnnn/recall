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
    assert result.verified.canonical_answer == "ΔG = -10 kJ/mol"
    reply = maybe_direct_subject_reply(result.verified, text)
    assert reply is not None
    assert reply.count("```answer") == 1
    assert "notation: chemistry\nΔG = −10 kJ/mol" in reply
    assert "✅" not in reply
    assert result.unverified is False


@pytest.mark.asyncio
async def test_physics_decline_is_flagged_without_reading_the_prompt() -> None:
    text = "binding energy of He-4, mass = 4.002603 u"
    result = await build_subject_augmentation(text, Settings(math_tools_enabled=True))
    assert result.subject == "physics"
    assert result.verified is None
    assert result.unverified is True
    assert result.prompt_block is not None
    assert result.prompt_block.startswith("Physics note:")


@pytest.mark.asyncio
async def test_chemistry_decline_is_flagged_and_element_context_is_not() -> None:
    settings = Settings(chemistry_enabled=True)
    declined = await build_subject_augmentation(
        "hydroxide substitution of SMILES CC(Cl)C",
        settings,
    )
    assert declined.verified is None
    assert declined.unverified is True
    assert declined.prompt_block is not None
    assert declined.prompt_block.startswith("Chemistry note:")

    element = await build_subject_augmentation(
        "what is the atomic mass of Fe?",
        settings,
    )
    assert element.verified is None
    assert element.unverified is False
    assert element.prompt_block is not None
    assert "Verified element data" in element.prompt_block


@pytest.mark.asyncio
async def test_fetch_returns_the_adapter_decline_flag() -> None:
    from app.services.chat.prompt_builder import fetch_web_and_tools
    from app.services.subject_solving import SubjectAugmentation

    settings = Settings(math_tools_enabled=True, web_search_enabled=False)
    with patch(
        "app.services.chat.prompt_builder.build_subject_augmentation",
        AsyncMock(
            return_value=SubjectAugmentation("physics", "Physics note: declined", None, True)
        ),
    ):
        _web, block, _sources, verified, declined, unverified_subject = await fetch_web_and_tools(
            "binding energy of He-4, mass = 4.002603 u",
            settings,
            prompt_messages=[{"role": "user", "content": "q"}],
        )
    assert block == "Physics note: declined"
    assert verified is None
    assert declined is True
    assert unverified_subject == "physics"


@pytest.mark.asyncio
async def test_chemistry_followup_solves_the_prior_problem() -> None:
    from app.services.chat.prompt_builder import fetch_web_and_tools

    settings = Settings(chemistry_enabled=True, web_search_enabled=False, math_tools_enabled=True)
    prior = "Find the molar mass of H2O"
    _web, _block, _sources, verified, declined, _subject = await fetch_web_and_tools(
        "how?",
        settings,
        prompt_messages=[{"role": "user", "content": "how?"}],
        chemistry_followup_problem=prior,
    )
    assert declined is False
    assert verified is not None
    assert verified.subject == "chemistry"
    assert "18.02" in verified.text
