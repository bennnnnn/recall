from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.models.schemas import ProductEventBatchIn
from app.services import product_analytics


@pytest.mark.asyncio
async def test_record_batch_persists_allowlisted_metadata() -> None:
    session = AsyncMock()
    batch = ProductEventBatchIn.model_validate(
        {
            "events": [
                {
                    "name": "paywall_viewed",
                    "properties": {"source": "settings"},
                    "platform": "ios",
                    "app_version": "1.2.3",
                    "installation_id": "install-id",
                }
            ]
        }
    )

    with patch(
        "app.services.product_analytics.product_events_repo.create_batch",
        AsyncMock(),
    ) as create_batch:
        await product_analytics.record_batch(session, uuid4(), batch)

    call = create_batch.await_args
    assert call is not None
    rows = call.args[1]
    assert len(rows) == 1
    assert rows[0].name == "paywall_viewed"
    assert rows[0].properties == {"source": "settings"}
    create_batch.assert_awaited_once()
    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_record_batch_accepts_bucketed_chat_ttft_only() -> None:
    session = AsyncMock()
    batch = ProductEventBatchIn.model_validate(
        {
            "events": [
                {
                    "name": "chat_ttft",
                    "properties": {
                        "latency_bucket": "2000_3999",
                        "transport": "sse",
                        "has_attachment": "no",
                    },
                }
            ]
        }
    )

    with patch(
        "app.services.product_analytics.product_events_repo.create_batch",
        AsyncMock(),
    ) as create_batch:
        await product_analytics.record_batch(session, uuid4(), batch)

    rows = create_batch.await_args.args[1]
    assert rows[0].name == "chat_ttft"
    assert rows[0].properties == {
        "latency_bucket": "2000_3999",
        "transport": "sse",
        "has_attachment": "no",
    }


@pytest.mark.asyncio
async def test_record_batch_rejects_raw_chat_latency_value() -> None:
    session = AsyncMock()
    batch = ProductEventBatchIn.model_validate(
        {
            "events": [
                {
                    "name": "chat_ttft",
                    "properties": {
                        "latency_bucket": "4821",
                        "transport": "ws",
                        "has_attachment": "no",
                    },
                }
            ]
        }
    )

    with patch(
        "app.services.product_analytics.product_events_repo.create_batch",
        AsyncMock(),
    ) as create_batch:
        with pytest.raises(ValueError, match="Invalid latency_bucket"):
            await product_analytics.record_batch(session, uuid4(), batch)

    create_batch.assert_not_awaited()


@pytest.mark.asyncio
async def test_record_batch_rejects_unexpected_properties() -> None:
    session = AsyncMock()
    batch = ProductEventBatchIn.model_validate(
        {
            "events": [
                {
                    "name": "purchase_started",
                    "properties": {"prompt": "never store this"},
                }
            ]
        }
    )

    with patch(
        "app.services.product_analytics.product_events_repo.create_batch",
        AsyncMock(),
    ) as create_batch:
        with pytest.raises(ValueError, match="Invalid properties"):
            await product_analytics.record_batch(session, uuid4(), batch)

    create_batch.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_record_batch_rolls_back_failed_persistence() -> None:
    session = AsyncMock()
    batch = ProductEventBatchIn.model_validate(
        {"events": [{"name": "purchase_succeeded", "properties": {}}]}
    )

    with patch(
        "app.services.product_analytics.product_events_repo.create_batch",
        AsyncMock(side_effect=RuntimeError("database unavailable")),
    ):
        with pytest.raises(RuntimeError, match="database unavailable"):
            await product_analytics.record_batch(session, uuid4(), batch)

    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once()
