"""The ```automation fence protocol must reach the model for Pro users on
every turn — including slim/lightweight ones, since a mid slot-filling
reply ("Monday and learn spanish") carries no automation keyword of its own
and would otherwise fall into the slim-context branch that drops it.
"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models.orm import User
from app.services.automations import AUTOMATIONS_HINT
from app.services.chat.prompt_builder import _PromptContextBlocks, build_prompt_messages


def _user(*, plan: str = "pro") -> User:
    return User(
        id=uuid4(),
        name="Test",
        email="test@example.com",
        plan=plan,
        response_style="balanced",
        locale="en",
        timezone="UTC",
    )


async def _system_prompt(user: User, settings: Settings, *, rich_context: bool) -> str:
    blocks = _PromptContextBlocks(
        memory_block="",
        todos_section=None,
        gmail_todos_section=None,
        projects_block="",
        recent_all=[],
        attachment_rag_block="",
        chat=None,
    )
    with patch(
        "app.services.chat.prompt_builder._load_context_blocks", AsyncMock(return_value=blocks)
    ):
        prepared = await build_prompt_messages(
            user,
            uuid4(),
            settings,
            query_text="hi",
            rich_context=rich_context,
        )
    return prepared[0]["content"]


@pytest.mark.asyncio
@pytest.mark.parametrize("rich_context", [True, False])
async def test_pro_user_sees_the_hint_on_slim_and_rich_turns(rich_context: bool) -> None:
    prompt = await _system_prompt(
        _user(plan="pro"), Settings(automations_enabled=True), rich_context=rich_context
    )
    assert AUTOMATIONS_HINT in prompt


@pytest.mark.asyncio
async def test_free_user_never_sees_the_hint() -> None:
    prompt = await _system_prompt(
        _user(plan="free"), Settings(automations_enabled=True), rich_context=True
    )
    assert AUTOMATIONS_HINT not in prompt


@pytest.mark.asyncio
async def test_hint_absent_when_automations_disabled() -> None:
    prompt = await _system_prompt(
        _user(plan="pro"), Settings(automations_enabled=False), rich_context=True
    )
    assert AUTOMATIONS_HINT not in prompt
