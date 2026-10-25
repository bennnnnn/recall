from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.config import Settings
from app.core.deps import get_current_user, get_settings_dep
from app.core.rate_limit import allow_request_unless_down
from app.core.redis import get_redis_client
from app.models.orm import User
from app.modules.link_preview.service import LinkPreviewBusyError, fetch_link_preview_cached

router = APIRouter(tags=["link-preview"])

_RATE_LIMIT = 20
_RATE_WINDOW_SECONDS = 60
# A busy user's open fetches all end within the fetch deadline.
_BUSY_RETRY_AFTER_SECONDS = 8


@router.get("/link-preview")
async def link_preview(
    url: str = Query(..., min_length=8, max_length=2048),
    _user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings_dep),
) -> dict[str, str | None]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid URL")

    redis = get_redis_client()
    allowed = await allow_request_unless_down(
        redis,
        f"rate:linkpreview:{_user.id}",
        limit=_RATE_LIMIT,
        window_seconds=_RATE_WINDOW_SECONDS,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Try again shortly.",
        )

    try:
        return await fetch_link_preview_cached(settings, redis, url, user_id=_user.id)
    except LinkPreviewBusyError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many previews loading. Try again shortly.",
            headers={"Retry-After": str(_BUSY_RETRY_AFTER_SECONDS)},
        ) from exc
