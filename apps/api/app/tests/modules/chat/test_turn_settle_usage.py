"""A settled turn reports the day's usage, which ``done`` carries (code-health audit NET-14)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.modules.chat import turn_settle
from app.modules.chat.turn_outcome import TurnUsage
from app.tests.fakes import redis_mock
from app.tests.modules.chat.chat_test_support import turn_deps


def _charge() -> Any:
    return SimpleNamespace(weighted_total=1200, est_cost=0)


@pytest.mark.asyncio
async def test_the_settle_returns_the_days_usage() -> None:
    ctx = SimpleNamespace(user=MagicMock(), user_id=uuid4(), reserved_tokens=1000, token_day=None)
    deps = turn_deps(
        quota={
            "daily_limit_for_user": MagicMock(return_value=10_000),
            "adjust_usage": AsyncMock(return_value=8_200),
            "messages_used": AsyncMock(return_value=4),
            "daily_message_limit": MagicMock(return_value=10),
        }
    )
    usage = await turn_settle._settle_quota(
        deps, redis_mock(), cast(Any, ctx), Settings(), _charge()
    )
    # The day's messages ride along: what the phone's meter shows.
    assert usage == TurnUsage(
        used_tokens=8_200, daily_limit=10_000, messages_used=4, daily_messages=10
    )


@pytest.mark.asyncio
async def test_a_failed_settle_reports_no_usage() -> None:
    ctx = SimpleNamespace(user=MagicMock(), user_id=uuid4(), reserved_tokens=1000, token_day=None)
    deps = turn_deps(
        quota={
            "daily_limit_for_user": MagicMock(return_value=10_000),
            "adjust_usage": AsyncMock(side_effect=OSError("down")),
            "mark_usage_needs_heal": AsyncMock(),
        }
    )
    # Three tries, 0.3 s of real pauses between them.
    usage = await turn_settle._settle_quota(
        deps, redis_mock(), cast(Any, ctx), Settings(), _charge()
    )
    assert usage is None


@pytest.mark.asyncio
@pytest.mark.parametrize("completion", ["user_stop", "interrupted", None])
async def test_the_saved_reply_keeps_whether_it_finished(completion: Any) -> None:
    """A reply the user stopped (or that was cut off) says so after a reload: the row
    carries ``completion``, which MessageOut sends the phone."""
    from app.modules.chat.turn_outcome import TurnOutcome

    create = AsyncMock(return_value=MagicMock(id=uuid4()))
    deps = turn_deps(
        messages={"create": create},
        chats={"touch_by_id": AsyncMock()},
        usage={"add_tokens": AsyncMock()},
    )
    ctx = SimpleNamespace(
        regenerate_backup=None,
        chat_id=uuid4(),
        user_id=uuid4(),
        model="free-chat",
        assistant_message_id=uuid4(),
        answer_photo_ids=[],
        recalled_count=0,
        memory_hints=[],
        context_summarized=0,
        token_day=None,
    )
    charge = SimpleNamespace(
        input_tokens=10, output_tokens=5, weighted_input=10, weighted_output=5, est_cost=0
    )
    await turn_settle._write_reply_rows(
        deps,
        MagicMock(),
        cast(Any, ctx),
        "Partial answer",
        cast(Any, charge),
        TurnOutcome(completion=completion),
    )
    assert create.await_args is not None
    assert create.await_args.kwargs["completion"] == completion


def test_message_out_sends_the_completion() -> None:
    from datetime import UTC, datetime

    from app.models.schemas.chats import MessageOut

    row = SimpleNamespace(
        id=uuid4(),
        role="assistant",
        content="Part",
        model="free-chat",
        feedback=None,
        completion="user_stop",
        created_at=datetime.now(UTC),
    )
    assert MessageOut.model_validate(row).completion == "user_stop"


@pytest.mark.asyncio
@pytest.mark.parametrize("write", ["saved", "unsent"])
async def test_a_turn_past_midnight_writes_its_usage_row_on_the_day_it_reserved(
    write: str, quota_clock: Any
) -> None:
    """Redis settled to the reserve day while the ``usage_daily`` row went to the new day:
    the next turn reseeded the new day from that row, charging the turn to both."""
    from app.modules.chat.turn_outcome import TurnOutcome
    from app.tests.modules.chat.chat_test_support import FakeSessionCM

    reserved_on = quota_clock.day
    quota_clock.day = quota_clock.next_day
    add_tokens = AsyncMock()
    deps = turn_deps(
        session_factory=FakeSessionCM,
        messages={"create": AsyncMock(return_value=MagicMock(id=uuid4()))},
        chats={"touch_by_id": AsyncMock()},
        usage={"add_tokens": add_tokens},
        quota={
            "daily_limit_for_user": MagicMock(return_value=10_000),
            "adjust_usage": AsyncMock(return_value=0),
            "messages_used": AsyncMock(return_value=0),
            "daily_message_limit": MagicMock(return_value=10),
        },
    )
    ctx = SimpleNamespace(
        regenerate_backup=None,
        chat_id=uuid4(),
        user_id=uuid4(),
        user=MagicMock(),
        model="free-chat",
        assistant_message_id=uuid4(),
        answer_photo_ids=[],
        recalled_count=0,
        memory_hints=[],
        context_summarized=0,
        reserved_tokens=100,
        prompt_messages=[],
        token_day=reserved_on,
    )
    charge = SimpleNamespace(
        input_tokens=10, output_tokens=5, weighted_input=10, weighted_output=5, est_cost=0
    )
    if write == "saved":
        await turn_settle._write_reply_rows(
            deps, MagicMock(), cast(Any, ctx), "Answer", cast(Any, charge), TurnOutcome()
        )
    else:
        await turn_settle.charge_unsent_reply(
            deps,
            redis_mock(),
            Settings(),
            cast(Any, ctx),
            sent_text="Ans",
            usage={"input": 10, "output": 5},
        )
    assert add_tokens.await_args is not None
    assert add_tokens.await_args.args[2] == reserved_on


@pytest.mark.asyncio
async def test_a_failed_settle_past_midnight_flags_the_day_it_reserved(quota_clock: Any) -> None:
    reserved_on = quota_clock.day
    quota_clock.day = quota_clock.next_day
    heal = AsyncMock()
    ctx = SimpleNamespace(
        user=MagicMock(), user_id=uuid4(), reserved_tokens=1000, token_day=reserved_on
    )
    deps = turn_deps(
        quota={
            "daily_limit_for_user": MagicMock(return_value=10_000),
            "adjust_usage": AsyncMock(side_effect=OSError("down")),
            "mark_usage_needs_heal": heal,
        }
    )
    # Three tries, 0.3 s of real pauses between them.
    await turn_settle._settle_quota(deps, redis_mock(), cast(Any, ctx), Settings(), _charge())
    assert heal.await_args is not None
    assert heal.await_args.kwargs == {"day": reserved_on}
