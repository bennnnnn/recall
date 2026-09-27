"""Math HTTP surface: read a scanned problem back before it is solved.

The scanner used to send the photo straight into the chat, so a misread
digit was solved with full confidence. ``POST /math/scan/read`` runs the same
OCR the chat turn uses and returns the reading for the student to confirm or
edit; the confirmed text is then sent as an ordinary message.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import ValidationError

from app.core.config import Settings
from app.core.deps import get_current_user, get_settings_dep
from app.core.rate_limit import allow_request_fail_closed
from app.core.redis import get_redis_client
from app.models.orm import User
from app.modules.math.ocr import extract_math_from_image
from app.modules.math.schemas import (
    SCAN_MAX_IMAGE_BYTES,
    SCAN_MAX_REQUEST_BYTES,
    ScanReadingIn,
    ScanReadingOut,
)
from app.services import quota as quota_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/math", tags=["math"])

SCAN_RATE_LIMIT_MESSAGE = "Too many scans in a row. Try again in a few minutes."
SCAN_SPEND_CAP_MESSAGE = "Reading photos is paused for now. Type the problem, or try again later."

# "2*x+3" reads as "2x+3"; "x**2" as "x^2". The chat parser accepts both.
_IMPLICIT_TIMES = re.compile(r"(\d)\s*\*\s*(?=[A-Za-z(])")


def readable_reading(text: str) -> str:
    return _IMPLICIT_TIMES.sub(r"\1", text.replace("**", "^")).strip()


def _too_large() -> HTTPException:
    return HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="Image too large")


@router.post("/scan/read", response_model=ScanReadingOut)
async def read_scan(
    request: Request,
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings_dep),
) -> ScanReadingOut:
    if not settings.math_tools_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not available")
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > SCAN_MAX_REQUEST_BYTES:
        raise _too_large()
    raw = await request.body()
    if len(raw) > SCAN_MAX_REQUEST_BYTES:
        raise _too_large()
    try:
        payload = ScanReadingIn.model_validate(json.loads(raw))
        data = base64.b64decode(payload.image_base64, validate=True)
    except (ValueError, ValidationError, binascii.Error) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid image payload"
        ) from exc
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty image")
    if len(data) > SCAN_MAX_IMAGE_BYTES:
        raise _too_large()

    redis = get_redis_client()
    if await quota_service.global_spend_exceeded(redis, settings):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=SCAN_SPEND_CAP_MESSAGE,
        )
    limit = settings.math_scan_read_rate_limit_per_hour
    if limit > 0 and not await allow_request_fail_closed(
        redis, f"math_scan_rl:{user.id}", limit=limit, window_seconds=3600
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=SCAN_RATE_LIMIT_MESSAGE
        )

    try:
        result = await extract_math_from_image(
            settings, content_type=payload.content_type, data=data
        )
    except Exception:
        # A failed read falls back to sending the photo; never a 500 here.
        logger.warning("math scan read failed", exc_info=True)
        return ScanReadingOut(reading="", uncertain=True, source="none")
    finally:
        try:
            await quota_service.record_global_spend(redis, quota_service.MATH_SCAN_READ_SPEND_USD)
        except Exception:
            logger.exception("record_global_spend failed after a scan read")
    reading = readable_reading(result.display_text)
    return ScanReadingOut(
        reading=reading,
        uncertain=result.uncertain or not reading,
        source=result.source if reading else "none",
    )
