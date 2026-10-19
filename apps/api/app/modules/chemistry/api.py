"""Chemistry HTTP surface: read a scanned problem before it is solved."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.config import Settings
from app.core.deps import get_settings_dep
from app.models.orm import User
from app.models.schemas.scan import ScanReadingOut
from app.modules.account.consent import get_consented_user
from app.modules.chemistry.read import read_chemistry_problem
from app.services.scan_read import ScanPhoto, read_scan

router = APIRouter(prefix="/chemistry", tags=["chemistry"])


@router.post("/scan/read", response_model=ScanReadingOut)
async def read_chemistry_scan(
    request: Request,
    user: User = Depends(get_consented_user),
    settings: Settings = Depends(get_settings_dep),
) -> ScanReadingOut:
    if not settings.chemistry_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not available")

    async def read(photo: ScanPhoto, seconds_left: float) -> str:
        return await read_chemistry_problem(
            settings,
            content_type=photo.content_type,
            data=photo.data,
            timeout_seconds=seconds_left,
        )

    reading = await read_scan(request, user=user, settings=settings, subject="chemistry", read=read)
    text = (reading or "").strip()
    return ScanReadingOut(reading=text, uncertain=not text, source="vision" if text else "none")
