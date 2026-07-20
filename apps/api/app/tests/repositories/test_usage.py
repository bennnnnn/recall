"""Tests for app.repositories.usage with mocked AsyncSession."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import UsageDaily


@pytest.fixture
def fake_session():
    """Return a mocked AsyncSession."""
    return AsyncMock(spec=AsyncSession)


@pytest.mark.asyncio
async def test_get_for_date_returns_usage(fake_session):
    """get_for_date should return the usage record from session.get."""
    from app.repositories.usage import get_for_date

    user_id = uuid4()
    today = date.today()
    mock_usage = MagicMock()
    fake_session.get.return_value = mock_usage

    result = await get_for_date(fake_session, user_id, today)

    assert result is mock_usage
    fake_session.get.assert_awaited_once()


@pytest.mark.asyncio
async def test_add_tokens_uses_on_conflict_upsert(fake_session):
    """add_tokens must INSERT … ON CONFLICT DO UPDATE, not read-modify-write."""
    from app.repositories.usage import add_tokens

    user_id = uuid4()
    today = date.today()
    mock_usage = MagicMock(spec=UsageDaily)
    mock_usage.input_tokens = 100
    mock_usage.output_tokens = 200
    fake_session.get.return_value = mock_usage

    result = await add_tokens(fake_session, user_id, today, input_tokens=100, output_tokens=200)

    fake_session.execute.assert_awaited_once()
    fake_session.add.assert_not_called()
    fake_session.commit.assert_awaited()
    fake_session.refresh.assert_awaited_once_with(mock_usage)
    assert result is mock_usage


@pytest.mark.asyncio
async def test_add_tokens_flush_without_commit(fake_session):
    from app.repositories.usage import add_tokens

    mock_usage = MagicMock(spec=UsageDaily)
    fake_session.get.return_value = mock_usage

    await add_tokens(
        fake_session, uuid4(), date.today(), input_tokens=1, output_tokens=2, commit=False
    )

    fake_session.flush.assert_awaited_once()
    fake_session.commit.assert_not_called()
    fake_session.refresh.assert_not_called()


@pytest.mark.asyncio
async def test_get_total_for_date_returns_sum(fake_session):
    """get_total_for_date should return input + output tokens."""
    from app.repositories.usage import get_total_for_date

    mock_usage = MagicMock()
    mock_usage.input_tokens = 400
    mock_usage.output_tokens = 300
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_usage
    fake_session.execute.return_value = mock_result

    result = await get_total_for_date(fake_session, uuid4(), date.today())

    assert result == 700


@pytest.mark.asyncio
async def test_get_total_for_date_returns_zero_when_none(fake_session):
    """get_total_for_date should return 0 when no usage record exists."""
    from app.repositories.usage import get_total_for_date

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    fake_session.execute.return_value = mock_result

    result = await get_total_for_date(fake_session, uuid4(), date.today())

    assert result == 0
