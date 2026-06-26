from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.deps import get_current_user
from app.models.orm import User
from app.services.link_preview import fetch_link_preview

router = APIRouter(tags=["link-preview"])


@router.get("/link-preview")
async def link_preview(
    url: str = Query(..., min_length=8, max_length=2048),
    _user: User = Depends(get_current_user),
) -> dict[str, str | None]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid URL")
    return await fetch_link_preview(url)
