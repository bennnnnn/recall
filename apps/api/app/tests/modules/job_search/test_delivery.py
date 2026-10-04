"""Outbox retries retain accepted tickets and respect current entitlement."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

from app.core.config import Settings
from app.gateways.expo_push_gateway import PushSendResult
from app.models.orm import PushToken
from app.modules.job_search.models import JobNotificationEvent, JobSearchRun
from app.modules.job_search.notifications import deliver_event


async def test_notification_retry_does_not_repeat_accepted_sends(
    account, db_session, fake_redis, monkeypatch
):
    user, profile = account
    user.push_notifications_enabled = True
    run = JobSearchRun(
        profile_id=profile.id,
        request_key="notification",
        profile_revision=1,
        manual=True,
        local_day="2026-10-03",
        state="completed",
    )
    db_session.add(run)
    await db_session.flush()
    event = JobNotificationEvent(run_id=run.id, user_id=user.id, new_match_count=2)
    db_session.add(event)
    for index in range(2):
        db_session.add(
            PushToken(
                user_id=user.id,
                expo_push_token=f"ExponentPushToken[test{index}]",
                device_id=f"test-{uuid4()}",
                platform="ios",
            )
        )
    await db_session.commit()

    @asynccontextmanager
    async def factory():
        yield db_session

    monkeypatch.setattr("app.core.db.SessionLocal", factory)
    attempts = {}

    async def send(messages):
        token = messages[0]["to"]
        attempts[token] = attempts.get(token, 0) + 1
        if token.endswith("test1]") and attempts[token] == 1:
            return PushSendResult(invalid_tokens=[], delivered=[False])
        return PushSendResult(
            invalid_tokens=[], delivered=[True], receipt_tickets=[(f"ticket-{token}", token)]
        )

    monkeypatch.setattr("app.gateways.expo_push_gateway.send_push_messages", send)
    receipts = AsyncMock()
    monkeypatch.setattr("app.modules.notifications.push.enqueue_push_receipts", receipts)
    await deliver_event(Settings(push_enabled=True), fake_redis, event.id)
    assert event.state == "pending"
    assert sum(record["state"] == "accepted" for record in event.devices.values()) == 1
    event.lease_until = None
    event.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.commit()
    await deliver_event(Settings(push_enabled=True), fake_redis, event.id)
    assert event.state == "delivered"
    assert attempts == {"ExponentPushToken[test0]": 1, "ExponentPushToken[test1]": 2}
    assert len(event.devices["ExponentPushToken[test0]"]["tickets"]) == 1
    assert receipts.await_count == 2


async def test_expired_notification_is_suppressed(account, db_session, fake_redis, monkeypatch):
    user, profile = account
    user.plan = "free"
    run = JobSearchRun(
        profile_id=profile.id,
        request_key="expired",
        profile_revision=1,
        manual=True,
        local_day="2026-10-03",
        state="completed",
    )
    db_session.add(run)
    await db_session.flush()
    event = JobNotificationEvent(run_id=run.id, user_id=user.id, new_match_count=1)
    db_session.add(event)
    await db_session.commit()

    @asynccontextmanager
    async def factory():
        yield db_session

    monkeypatch.setattr("app.core.db.SessionLocal", factory)
    send = AsyncMock()
    monkeypatch.setattr("app.gateways.expo_push_gateway.send_push_messages", send)
    await deliver_event(Settings(push_enabled=True), fake_redis, event.id)
    assert event.state == "suppressed"
    send.assert_not_called()
