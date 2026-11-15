"""A chemistry question about one compound gets its structure drawn without being asked.

The owner (2026-11-15): a student need not ask to see a molecule. A read names the compound
as the user wrote it; the name must be in the user's words, PubChem gives the structure, and
RDKit holds it to one molecule worth drawing. Anything else draws nothing.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.modules.chemistry import figure
from app.modules.chemistry.subject import ChemistryFigure


def _settings(**overrides: Any) -> Settings:
    return Settings(_env_file=None, **overrides)  # type: ignore[call-arg]


async def _in_process(fn: Any, *args: Any, **_kwargs: Any) -> Any:
    return fn(*args)


@pytest.mark.parametrize(
    ("name", "texts", "written"),
    [
        ("ibuprofen", ["What is Ibuprofen used for?"], True),
        ("acetic acid", ["Why is acetic   acid weak?"], True),
        ("ethanol", ["What is ethanolamine?"], False),
        ("caffeine", ["How much coffee is too much?"], False),
        ("glucose", ["now its molar mass", "Tell me about glucose."], True),
        ("", ["Tell me about glucose."], False),
    ],
)
def test_the_name_must_be_the_user_s_own(name: str, texts: list[str], written: bool) -> None:
    assert figure.written_by_user(name, texts) is written


@pytest.mark.parametrize(
    ("smiles", "drawn"),
    [
        ("CCO", True),
        ("CC(=O)OC1=CC=CC=C1C(=O)O", True),
        ("[Na+].[Cl-]", False),  # a salt: two ions, no bonds to draw
        ("C", False),  # one atom besides hydrogen: a letter on the screen
        ("C1CC", False),  # RDKit cannot read it
        ("", False),
    ],
)
def test_only_one_valid_molecule_worth_drawing_is_drawn(smiles: str, drawn: bool) -> None:
    fence = figure.structure_fence(smiles, "the compound")
    assert (fence is not None) is drawn
    if fence is not None:
        assert fence.startswith("```smiles\nthe compound\n") and fence.endswith("\n```")


@pytest.mark.asyncio
async def test_a_question_about_one_compound_gets_its_structure() -> None:
    with (
        patch.object(figure, "read_compound", AsyncMock(return_value="ethanol")),
        patch.object(figure, "pubchem_structure", AsyncMock(return_value="CCO")),
        patch("app.core.sympy_executor.run_sympy", _in_process),
    ):
        fence = await figure.draw_structure("Why does ethanol mix with water?", [], _settings())
    assert fence == "```smiles\nethanol\nCCO\n```"


@pytest.mark.asyncio
async def test_a_name_the_user_never_wrote_is_never_looked_up() -> None:
    lookup = AsyncMock(return_value="CCO")
    with (
        patch.object(figure, "read_compound", AsyncMock(return_value="ethanol")),
        patch.object(figure, "pubchem_structure", lookup),
    ):
        assert await figure.draw_structure("How do I make wine?", [], _settings()) is None
    lookup.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "settings",
    [_settings(teaching_figures_enabled=False), _settings(chemistry_enabled=False)],
    ids=["teaching-off", "chemistry-off"],
)
async def test_no_read_with_a_switch_off(settings: Settings) -> None:
    with patch.object(figure, "read_compound", AsyncMock()) as read:
        assert await figure.draw_structure("What is ibuprofen?", [], settings) is None
    read.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_request_to_see_the_molecule_is_the_solve_s() -> None:
    with patch.object(figure, "draw_structure", AsyncMock()) as draw:
        assert await ChemistryFigure().draw("Draw caffeine", [], _settings(), asked=True) is None
    draw.assert_not_awaited()


def test_a_reply_that_draws_a_molecule_gets_no_second() -> None:
    adapter = ChemistryFigure()
    assert adapter.whole("Here:\n\n```smiles\nCCO\n```")
    assert not adapter.whole("Ethanol is polar.")
    assert adapter.adds_to("Ethanol is polar.", "```smiles\nethanol\nCCO\n```")


@pytest.mark.asyncio
@pytest.mark.parametrize("gate", [AsyncMock(return_value=True), AsyncMock(side_effect=OSError)])
async def test_no_read_past_the_spend_cap_or_in_an_outage(gate: AsyncMock) -> None:
    """The read is a hint: past the spend cap, or with the spend read down, no structure."""
    with (
        patch("app.core.redis.get_redis_client", MagicMock()),
        patch("app.services.quota.global_spend_exceeded", gate),
        patch("app.gateways.structured_completion.complete_structured", AsyncMock()) as call,
    ):
        assert await figure.read_compound(_settings(), "What is ibuprofen?", []) is None
    call.assert_not_awaited()
