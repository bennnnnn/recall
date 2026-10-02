"""Chemistry HTTP surface: read a scanned problem before it is solved."""

from __future__ import annotations

import base64
import binascii
import json
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, ValidationError

from app.core.config import Settings
from app.core.deps import get_current_user, get_settings_dep
from app.core.rate_limit import allow_request_fail_closed
from app.core.redis import get_redis_client
from app.models.orm import User
from app.modules.chemistry.read import read_chemistry_problem
from app.services import quota as quota_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chemistry", tags=["chemistry"])

# Same cropped-photo budget as the math reader. The camera sends one crop.
SCAN_MAX_IMAGE_BYTES = 8_000_000
SCAN_MAX_B64_CHARS = 4 * ((SCAN_MAX_IMAGE_BYTES + 2) // 3)
SCAN_MAX_REQUEST_BYTES = SCAN_MAX_B64_CHARS + 4096

SCAN_RATE_LIMIT_MESSAGE = "Too many scans in a row. Try again in a few minutes."
SCAN_SPEND_CAP_MESSAGE = "Reading photos is paused for now. Type the problem, or try again later."


class ChemistryScanIn(BaseModel):
    image_base64: str = Field(min_length=1, max_length=SCAN_MAX_B64_CHARS)
    content_type: Literal["image/jpeg", "image/png", "image/webp"] = "image/jpeg"


class ChemistryScanOut(BaseModel):
    reading: str
    uncertain: bool
    source: Literal["vision", "none"]


def _too_large() -> HTTPException:
    return HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="Image too large")


@router.post("/scan/read", response_model=ChemistryScanOut)
async def read_scan(
    request: Request,
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings_dep),
) -> ChemistryScanOut:
    if not settings.chemistry_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not available")
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > SCAN_MAX_REQUEST_BYTES:
        raise _too_large()
    raw = await request.body()
    if len(raw) > SCAN_MAX_REQUEST_BYTES:
        raise _too_large()
    try:
        payload = ChemistryScanIn.model_validate(json.loads(raw))
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
        redis, f"chemistry_scan_rl:{user.id}", limit=limit, window_seconds=3600
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=SCAN_RATE_LIMIT_MESSAGE
        )

    try:
        reading = await read_chemistry_problem(
            settings, content_type=payload.content_type, data=data
        )
    except Exception:
        logger.warning("chemistry scan read failed", exc_info=True)
        reading = ""
    finally:
        try:
            await quota_service.record_global_spend(redis, quota_service.MATH_SCAN_READ_SPEND_USD)
        except Exception:
            logger.exception("record_global_spend failed after a chemistry scan read")
    text = reading.strip()
    return ChemistryScanOut(
        reading=text,
        uncertain=not text,
        source="vision" if text else "none",
    )
