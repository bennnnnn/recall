"""Nothing goes to outside AI services until the account agreed to it.

The phone and the web ask once after sign-in (``users.ai_data_consent_at``, set
by ``PATCH /auth/me`` ``ai_data_consent``). The server holds the same line: a
chat turn, speech (transcribe, read aloud, a live talk key or tool) and a
scanned problem's read-back are refused with ``consent_required`` until the
account agrees, and again after it withdraws. The phone answers that code with
its consent screen.

A user cached by ``get_current_user`` can trail an agreement made on another
machine by up to a minute, so a refusal re-reads the row first.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user, get_redis_dep
from app.core.user_cache import is_current, read_generation, remember_read
from app.exceptions import ConsentRequiredError
from app.models.orm import User

# What a withdrawal elsewhere can change for the next outside-AI call.
_PRIVACY_COLUMNS = ("ai_data_consent_at", "memory_enabled", "web_search_enabled")


def has_ai_data_consent(user: object) -> bool:
    """The account agreed to the outside-AI disclosure and has not withdrawn."""
    return getattr(user, "ai_data_consent_at", None) is not None


def consent_required_detail() -> dict[str, str]:
    """The 403 body: ``{"detail": {"code": "consent_required", "message": …}}``."""
    refused = ConsentRequiredError()
    return {"code": refused.code, "message": refused.message}


async def get_consented_user(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis_dep)],
) -> User:
    """The signed-in user, once they agreed; 403 ``consent_required`` otherwise.

    A cached row is trusted only while its generation is current: a withdrawal made on
    another machine bumps it, and this re-reads the row before sending anything out.
    """
    if has_ai_data_consent(user) and await is_current(redis, user.id):
        return user
    generation = await read_generation(redis, user.id)
    await session.refresh(user, attribute_names=list(_PRIVACY_COLUMNS))
    await session.commit()  # the re-read's transaction ends here, as in get_current_user
    if not has_ai_data_consent(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=consent_required_detail())
    remember_read(user, generation)
    return user
