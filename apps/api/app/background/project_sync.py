import logging
from uuid import UUID

from app.core.config import Settings
from app.services import projects as projects_service

logger = logging.getLogger(__name__)


async def sync_projects_from_chat(
    settings: Settings,
    *,
    user_id: UUID,
    chat_id: UUID,
    transcript: str,
) -> None:
    try:
        await projects_service.sync_projects_from_transcript(
            settings,
            user_id=user_id,
            chat_id=chat_id,
            transcript=transcript,
        )
    except Exception:
        logger.exception("Project sync job failed for user_id=%s", user_id)
