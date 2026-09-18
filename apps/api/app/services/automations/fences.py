"""Strip retired generic automation fences from assistant replies.

My Job is now configured through its dedicated job-search UI. The automation
engine remains an internal scheduler, but chat must never create arbitrary
background prompts or expose their raw JSON protocol.
"""

from __future__ import annotations

import json
import logging
import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.orm import Automation, User

logger = logging.getLogger(__name__)

_AUTOMATION_FENCE = re.compile(r"```automation\s*\n[\s\S]*?```", re.IGNORECASE)
_RETIRED_MESSAGE = "*Open My Job to set up a scheduled job search.*"


def format_automation_confirm_fence(automation: Automation) -> str:
    """Keep the legacy confirmation shape readable by older mobile clients.

    New chat turns no longer produce this fence, but retaining the serializer
    avoids breaking stored messages and any older client that still encounters
    an existing confirmation in conversation history.
    """
    payload = {
        "id": str(automation.id),
        "prompt": automation.prompt,
        "frequency": automation.frequency,
        "next_run_at": automation.next_run_at.isoformat(),
    }
    return f"\n\n```automation_created\n{json.dumps(payload)}\n```"


async def materialize_automation_fences(
    session: AsyncSession,
    *,
    user: User,
    settings: Settings,
    assistant_text: str,
) -> tuple[str, int]:
    """Remove any legacy create fence and direct the user to My Job.

    The unused session/settings arguments remain in the signature because this
    function is part of the chat finalization pipeline. Returning zero ensures
    no generic automation can be created even if an older model emits the
    retired protocol.
    """
    del session, settings
    if _AUTOMATION_FENCE.search(assistant_text) is None:
        return assistant_text, 0

    logger.info("Retired automation fence stripped user_id=%s", user.id)
    updated = _AUTOMATION_FENCE.sub(_RETIRED_MESSAGE, assistant_text)
    return re.sub(r"\n{3,}", "\n\n", updated).strip(), 0


__all__ = [
    "format_automation_confirm_fence",
    "materialize_automation_fences",
]
