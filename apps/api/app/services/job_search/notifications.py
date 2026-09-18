"""Push delivery for completed My Job searches."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.gateways import expo_push_gateway
from app.models.orm import PushToken, User


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
    if user is None or not user.push_notifications_enabled:
        return

    rows = list(
        (await session.scalars(select(PushToken).where(PushToken.user_id == user_id))).all()
    )
    if not rows:
        return

    noun = "job match" if new_match_count == 1 else "job matches"
    body = f"{new_match_count} new {noun} are ready to review."
    messages = [
        {
            "to": row.expo_push_token,
            "sound": "default",
            "title": "New job matches",
            "body": body,
            "data": {
                "type": "job_search_ready",
                "screen": "my-job",
                "profile_id": str(profile_id),
            },
        }
        for row in rows
    ]
    result = await expo_push_gateway.send_push_messages(messages)
    if result.invalid_tokens:
        await session.execute(
            delete(PushToken).where(PushToken.expo_push_token.in_(result.invalid_tokens))
        )
        await session.commit()
