"""The real current-user history shape must reach the short math follow-up policy."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from app.core.config import Settings
from app.models.orm import Chat, User
from app.services.chat.prompt_builder import _PromptContextBlocks
from app.services.chat.turn_prep.mode import _TurnMode
from app.services.chat.turn_prep.prepare import prepare_chat_turn
from app.services.math_followup import MATH_FOLLOWUP_HINT
from app.services.math_reply_policy import MATH_REPLY_POLICY

_QUERY = "Sum 1/n^2 from n=1 to infinity"
_RESULT = r"\frac{\pi^{2}}{6}"


class _Session:
    async def __aenter__(self) -> AsyncMock:
        return AsyncMock()

    async def __aexit__(self, *_args: object) -> None:
        return None


@pytest.mark.asyncio
@pytest.mark.parametrize("overlap", [True, False])
async def test_actual_c12_how_through_prepare_context_and_prompt_builder(overlap: bool) -> None:
    user = User(
        id=uuid4(),
        name="Test",
        email="test@example.com",
        response_style="balanced",
        locale="en",
        timezone="UTC",
        memory_enabled=False,
    )
    chat = Chat(id=uuid4(), user_id=user.id, title="Test")
    history = [
        SimpleNamespace(id=uuid4(), role="user", content=_QUERY),
        SimpleNamespace(id=uuid4(), role="assistant", content=f"```answer\n{_RESULT}\n```"),
    ]
    original_history = list(history)
    release = asyncio.Event()
    if not overlap:
        release.set()
    persisted_ids: list[UUID] = []

    async def create_message(*_args: object, **kwargs: object) -> SimpleNamespace:
        await release.wait()
        message = SimpleNamespace(id=kwargs["message_id"], role="user", content=kwargs["content"])
        history.append(message)
        persisted_ids.append(message.id)
        return message

    async def context_blocks(*_args: object, **kwargs: object) -> _PromptContextBlocks:
        recent = kwargs["recent_messages"]
        assert recent is None or isinstance(recent, list)
        return _PromptContextBlocks(
            memory_block="",
            todos_section=None,
            gmail_todos_section=None,
            projects_block="",
            recent_all=list(recent) if recent is not None else list(history),
            attachment_rag_block="",
            chat=chat,
        )

    settings = Settings(
        attachments_enabled=False,
        attachment_rag_enabled=False,
        mcp_tool_loop_enabled=False,
        mcp_tools_enabled=False,
        math_tools_enabled=False,
        chemistry_enabled=False,
        web_search_enabled=False,
        web_search_classifier_enabled=False,
        gmail_enabled=False,
        google_calendar_enabled=False,
    )
    with (
        patch("app.services.chat.turn_prep.prepare.SessionLocal", return_value=_Session()),
        patch("app.repositories.messages.create", AsyncMock(side_effect=create_message)),
        patch(
            "app.services.chat.prompt_builder._load_context_blocks",
            AsyncMock(side_effect=context_blocks),
        ),
        patch("app.services.model_health.enrich_models_health", AsyncMock(return_value={})),
        patch(
            "app.services.chat.turn_prep.context.plan_service.chat_fallback_models", return_value=[]
        ),
    ):
        context = await asyncio.wait_for(
            prepare_chat_turn(
                user_id=user.id,
                chat_id=chat.id,
                content="how",
                model_alias=None,
                settings=settings,
                redis=AsyncMock(),
                reserved_tokens=100,
                user=user,
                chat=chat,
                turn_mode=_TurnMode(
                    lightweight=False,
                    rich_context=False,
                    minimal_personal=False,
                    day_planning=False,
                    day_reflection=False,
                ),
                prior_count=2,
                recent_messages=original_history if overlap else None,
                resolved_model="free-chat",
            ),
            timeout=2,
        )
        try:
            assert context.prompt_messages[0]["content"].endswith(
                f"{MATH_REPLY_POLICY}\n\n{MATH_FOLLOWUP_HINT}"
            )
            assert context.prompt_messages[-2] == {
                "role": "assistant",
                "content": f"Previous result:\n\\[\n{_RESULT}\n\\]",
            }
            assert context.prompt_messages[-1] == {"role": "user", "content": "how"}
            assert (
                "show the calculation or mathematical argument"
                in context.prompt_messages[0]["content"]
            )
            if overlap:
                assert persisted_ids == []
        finally:
            release.set()
            if context.user_message_persist is not None:
                await context.user_message_persist
    assert len(persisted_ids) == 1
    assert history[-1].content == "how"
