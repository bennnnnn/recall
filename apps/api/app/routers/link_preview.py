from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.config import Settings
from app.core.deps import get_current_user, get_settings_dep
from app.core.rate_limit import allow_request
from app.core.redis import get_redis_client
from app.models.orm import User
from app.services.link_preview import fetch_link_preview_cached

router = APIRouter(tags=["link-preview"])


@router.get("/link-preview")
async def link_preview(
    url: str = Query(..., min_length=8, max_length=2048),
    _user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings_dep),
) -> dict[str, str | None]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid URL")

    # Rate limit: 20 requests per 60 seconds per user
    redis = get_redis_client()
    allowed = await allow_request(
        redis,
        f"rate:linkpreview:{_user.id}",
        limit=20,
        window_seconds=60,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Try again shortly.",
        )

    return await fetch_link_preview_cached(settings, url)
