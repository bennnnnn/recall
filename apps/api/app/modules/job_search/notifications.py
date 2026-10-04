"""Push delivery for completed My Job searches."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.gateways import expo_push_gateway
from app.models.orm import PushToken, User
from app.modules.notifications import PUSH_SOUND, channel_id_for_token


async def notify_job_matches_ready(
    session: AsyncSession,
    settings: Settings,
    *,
    user_id: UUID,
    profile_id: UUID,
    new_match_count: int,
) -> None:
    if not settings.push_enabled or new_match_count <= 0:
        return

    user = await session.get(User, user_id)
    from app.modules.billing import is_pro

    if user is None or not is_pro(user) or not user.push_notifications_enabled:
        return

    rows = list(
        (await session.scalars(select(PushToken).where(PushToken.user_id == user_id))).all()
    )
    if not rows:
        return

    noun = "job match" if new_match_count == 1 else "job matches"
    body = f"{new_match_count} new {noun} are ready to review."
    data = {
        "type": "job_search_ready",
        "screen": "my-job",
        "profile_id": str(profile_id),
    }
    messages = []
    for row in rows:
        message: dict[str, Any] = {
            "to": row.expo_push_token,
            "sound": PUSH_SOUND,
            "title": "New job matches",
            "body": body,
            "data": data,
        }
        channel_id = channel_id_for_token(row, data)
        if channel_id is not None:
            message["channelId"] = channel_id
        messages.append(message)
    result = await expo_push_gateway.send_push_messages(messages)
    if result.invalid_tokens:
        await session.execute(
            delete(PushToken).where(PushToken.expo_push_token.in_(result.invalid_tokens))
        )
        await session.commit()


async def deliver_event(settings: Settings, redis: Any, event_id: UUID) -> None:
    """Retry rejected sends while retaining every accepted device ticket."""
    from datetime import UTC, datetime, timedelta

    from app.core.db import SessionLocal
    from app.modules.billing import is_pro
    from app.modules.job_search.models import JobNotificationEvent, JobSearchProfile, JobSearchRun
    from app.modules.notifications import enqueue_push_receipts

    async with SessionLocal() as session:
        event = await session.scalar(
            select(JobNotificationEvent)
            .where(JobNotificationEvent.id == event_id)
            .with_for_update()
        )
        now = datetime.now(UTC)
        if (
            event is None
            or event.state != "pending"
            or (event.lease_until and event.lease_until > now)
        ):
            return
        user = await session.get(User, event.user_id)
        run = await session.get(JobSearchRun, event.run_id)
        profile = await session.get(JobSearchProfile, run.profile_id) if run else None
        if (
            user is None
            or not is_pro(user)
            or not user.push_notifications_enabled
            or run is None
            or profile is None
            or profile.revision != run.profile_revision
            or event.new_match_count <= 0
        ):
            event.state = "suppressed"
            await session.commit()
            return
        if not settings.push_enabled:
            event.next_attempt_at = now + timedelta(minutes=15)
            await session.commit()
            return
        rows = list(
            (await session.scalars(select(PushToken).where(PushToken.user_id == user.id))).all()
        )
        devices = dict(event.devices or {})
        if not rows:
            event.state = "suppressed"
            await session.commit()
            return
        event.attempts += 1
        event.lease_until = now + timedelta(minutes=5)
        await session.commit()
        for row in rows:
            token = row.expo_push_token
            if devices.get(token, {}).get("state") in {"accepted", "invalid"}:
                continue
            # Recheck before each external send; a renewal never resumes paused work.
            await session.refresh(user)
            await session.refresh(profile)
            if (
                not is_pro(user)
                or not user.push_notifications_enabled
                or profile.revision != run.profile_revision
            ):
                event.state = "suppressed"
                break
            data = {
                "type": "job_search_ready",
                "screen": "my-job",
                "profile_id": str(profile.id),
                "run_id": str(run.id),
                "event_id": str(event.id),
            }
            message: dict[str, Any] = {
                "to": token,
                "sound": PUSH_SOUND,
                "title": "New job matches",
                "body": f"{event.new_match_count} new qualifying matches are ready to review.",
                "data": data,
            }
            channel = channel_id_for_token(row, data)
            if channel:
                message["channelId"] = channel
            result = await expo_push_gateway.send_push_messages([message])
            tickets = [
                ticket
                for ticket, accepted_token in result.receipt_tickets
                if accepted_token == token
            ]
            if result.delivered and result.delivered[0]:
                devices[token] = {"state": "accepted", "tickets": tickets}
            elif token in result.invalid_tokens:
                devices[token] = {"state": "invalid"}
                await session.execute(delete(PushToken).where(PushToken.expo_push_token == token))
            else:
                devices[token] = {"state": "retry"}
            event.devices = dict(devices)
            await session.commit()
            # Receipt dispatch is also replayable from the saved ticket below.
        saved_tickets = [
            (ticket, token)
            for token, record in devices.items()
            for ticket in record.get("tickets", [])
        ]
        if saved_tickets:
            await enqueue_push_receipts(redis, saved_tickets)
        if event.state == "pending":
            event.state = (
                "delivered"
                if all(
                    devices.get(row.expo_push_token, {}).get("state") in {"accepted", "invalid"}
                    for row in rows
                )
                else "pending"
            )
        event.lease_until = None
        event.next_attempt_at = datetime.now(UTC) + timedelta(
            seconds=min(3600, 30 * 2 ** min(event.attempts, 7))
        )
        if event.attempts >= 12 and event.state == "pending":
            event.state = "failed"
        await session.commit()
