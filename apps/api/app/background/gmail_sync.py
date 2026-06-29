import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.services import email as email_service

logger = logging.getLogger(__name__)


async def sync_gmail_for_user(
    session: AsyncSession,
    settings: Settings,
    *,
    user_id: UUID,
) -> None:
    from app.core.redis import get_redis_client

    try:
        redis = get_redis_client()
        await email_service.sync_gmail_for_user(
            session, settings, user_id, redis=redis
        )
    except Exception:
        logger.exception("Gmail sync job failed for user_id=%s", user_id)
