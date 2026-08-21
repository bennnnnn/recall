from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services.memory.apply import apply_memory_section_rows


class _SessionContext:
    def __init__(self, session: AsyncMock) -> None:
        self.session = session

    async def __aenter__(self) -> AsyncMock:
        return self.session

    async def __aexit__(self, *args: object) -> None:
        return None


@pytest.mark.asyncio
async def test_apply_memory_rows_commits_once_after_repository_writes():
    session = AsyncMock()
    memories = AsyncMock()
    memories.list_for_user.return_value = []

    def session_factory() -> _SessionContext:
        return _SessionContext(session)

    user_id = uuid4()

    with (
        patch("app.services.memory.invalidate_memory_block", AsyncMock()),
        patch("app.services.home.invalidate_home_cache", AsyncMock()),
    ):
        await apply_memory_section_rows(
            Settings(),
            user_id=user_id,
            rows=[("fact", "Owns a bicycle.", 0.9, None)],
            session_factory=session_factory,
            memories=memories,
        )

    memories.upsert_sections.assert_awaited_once()
    assert memories.upsert_sections.await_args.kwargs["commit"] is False
    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_apply_memory_rows_rolls_back_when_post_write_read_fails():
    session = AsyncMock()
    memories = AsyncMock()
    memories.list_for_user.side_effect = RuntimeError("reload failed")

    def session_factory() -> _SessionContext:
        return _SessionContext(session)

    invalidate_memory = AsyncMock()
    invalidate_home = AsyncMock()

    with (
        patch("app.services.memory.invalidate_memory_block", invalidate_memory),
        patch("app.services.home.invalidate_home_cache", invalidate_home),
    ):
        with pytest.raises(RuntimeError, match="reload failed"):
            await apply_memory_section_rows(
                Settings(),
                user_id=uuid4(),
                rows=[("fact", "Owns a bicycle.", 0.9, None)],
                session_factory=session_factory,
                memories=memories,
            )

    assert memories.upsert_sections.await_args.kwargs["commit"] is False
    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once()
    invalidate_memory.assert_not_awaited()
    invalidate_home.assert_not_awaited()
