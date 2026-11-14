"""A line answered again is read for live facts, as a new one is (``chat.turn_decision``).

Regenerating a textbook physics problem (four runners, 100 m, their speeds) searched the
web (2026-11-09): a regenerate started no read, so the reply's own model decided alone,
and GPT-6 Luna, its thinking raised for a second try, searched. The read now runs on the
line answered again, with the chat before it, and the reply is told what it found.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models.orm import Chat, User
from app.modules.chat import stream_entry, turn_decision, turn_load
from app.modules.chat.prompt_builder import PromptStats
from app.modules.chat.turn_load import RegenerateTurn
from app.modules.chat.turn_prep.context import TurnPromptBundle
from app.modules.chat.turn_prep.request import ClientGeoContext
from app.tests.fakes import redis_mock
from app.tests.modules.chat.chat_test_support import FakeSessionCM, turn_deps

_PROBLEM = "Four runners ran 100 m in 12, 13, 14 and 15 s. Find each runner's speed."


def _row(role: str, content: str) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), role=role, content=content, model="gpt-6-luna")


def _turn(recent: list[Any]) -> RegenerateTurn:
    return RegenerateTurn(
        user=MagicMock(),
        chat=MagicMock(),
        model="gpt-6-luna",
        content=_PROBLEM,
        prior_count=len(recent),
        turn_mode=MagicMock(),
        backup=None,
        omit_message_ids=None,
        recent=recent,
    )


@pytest.mark.parametrize("redone", [True, False])
def test_the_read_sees_the_chat_before_the_line_answered_again(redone: bool) -> None:
    earlier = [_row("user", "hi"), _row("assistant", "Hello!")]
    line = [_row("user", _PROBLEM)]
    reply = [_row("assistant", "Speeds: 8.33, 7.69, 7.14 and 6.67 m/s.")] if redone else []
    assert _turn(earlier + line + reply).before_line == earlier


@pytest.mark.asyncio
async def test_a_regenerate_starts_the_read_and_hands_it_to_the_turn() -> None:
    owner, chat_id = uuid4(), uuid4()
    earlier = [_row("user", "hi"), _row("assistant", "Hello!")]
    window = [*earlier, _row("user", _PROBLEM), _row("assistant", "Speeds: 8.33 m/s …")]
    read = MagicMock(name="read")
    start = MagicMock(return_value=read)
    captured: dict[str, Any] = {}
    resource = SimpleNamespace(reserve=AsyncMock(), reserved_tokens=100)

    @asynccontextmanager
    async def resources(*_args: Any, **_kwargs: Any) -> Any:
        yield resource

    async def build(*_args: Any) -> TurnPromptBundle:
        return TurnPromptBundle(
            prompt_messages=[{"role": "user", "content": _PROBLEM}],
            stats=PromptStats(),
            instant_reply=None,
            local_places=False,
            max_out=100,
            fallback_models=[],
            lightweight=False,
            rich_context=False,
            geo=ClientGeoContext(None, None, None, False, False, False, False),
            local_tz="UTC",
        )

    async def final_stream(_deps: Any, _redis: Any, _settings: Any, ctx: Any, **_kw: Any) -> Any:
        captured["ctx"] = ctx
        yield "Speeds …"

    deps = turn_deps(
        session_factory=FakeSessionCM,
        users={"get_by_id": AsyncMock(return_value=User(id=owner, email="a@b.c", name="A"))},
        chats={"get_by_id": AsyncMock(return_value=Chat(id=chat_id, user_id=owner))},
        messages={
            "list_recent": AsyncMock(return_value=window),
            "count_for_chat": AsyncMock(return_value=len(window)),
        },
        model_choice={"resolve_regenerate_model": lambda *_args, **_kwargs: "gpt-6-luna"},
        quota={"daily_limit_for_user": lambda *_args: 10000},
    )
    entry = "app.modules.chat.stream_entry"
    intercepts = "app.modules.chat.turn_intercepts"
    with (
        patch(f"{entry}.turn_resources", resources),
        patch.object(turn_load, "wait_for_pending_finalize", AsyncMock()),
        patch(f"{intercepts}.try_image_lookup_for_turn", AsyncMock(return_value=False)),
        patch(f"{intercepts}.try_image_gen_for_turn", AsyncMock(return_value=False)),
        patch(f"{entry}.build_stream_prompt_context", build),
        patch(f"{entry}.top_up_reserve_for_prompt", AsyncMock()),
        patch(f"{entry}.stream_and_finalize", final_stream),
        patch.object(turn_decision, "start_turn_decision", start),
    ):
        tokens = [
            token
            async for token in stream_entry.stream_regenerate_response(
                deps, redis_mock(), Settings(), user_id=owner, chat_id=chat_id
            )
        ]
    assert tokens == ["Speeds …"]
    assert start.call_args.args[1] == _PROBLEM
    assert start.call_args.kwargs["recent"] == earlier
    assert captured["ctx"].live_read is read


@pytest.mark.asyncio
async def test_a_regenerate_an_intercept_answers_stops_the_read() -> None:
    """MODEL-06: a picture or photo intercept answers with no reply call, so the read stops
    once the intercept has used it, not billed on to its own timeout."""
    import asyncio

    owner, chat_id = uuid4(), uuid4()
    window = [_row("user", "show me a red panda"), _row("assistant", "[photo]")]
    read = asyncio.ensure_future(asyncio.sleep(30))
    resource = SimpleNamespace(reserve=AsyncMock(), reserved_tokens=100)

    @asynccontextmanager
    async def resources(*_args: Any, **_kwargs: Any) -> Any:
        yield resource

    deps = turn_deps(
        session_factory=FakeSessionCM,
        users={"get_by_id": AsyncMock(return_value=User(id=owner, email="a@b.c", name="A"))},
        chats={"get_by_id": AsyncMock(return_value=Chat(id=chat_id, user_id=owner))},
        messages={
            "list_recent": AsyncMock(return_value=window),
            "count_for_chat": AsyncMock(return_value=len(window)),
        },
        model_choice={"resolve_regenerate_model": lambda *_args, **_kwargs: "gpt-6-luna"},
    )
    entry = "app.modules.chat.stream_entry"
    intercepts = "app.modules.chat.turn_intercepts"
    with (
        patch(f"{entry}.turn_resources", resources),
        patch.object(turn_load, "wait_for_pending_finalize", AsyncMock()),
        patch(f"{intercepts}.try_image_gen_for_turn", AsyncMock(return_value=True)),
        patch.object(turn_decision, "start_turn_decision", MagicMock(return_value=read)),
    ):
        tokens = [
            token
            async for token in stream_entry.stream_regenerate_response(
                deps, redis_mock(), Settings(), user_id=owner, chat_id=chat_id
            )
        ]
    assert tokens == []
    await asyncio.sleep(0)
    assert read.cancelled()
