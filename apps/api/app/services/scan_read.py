"""Guard a scan read-back: payload limits, the vision spend cap, a per-user rate.

Math, physics and chemistry each read a cropped photo back for the student to
confirm. They run the same checks before their reader and record the same
spend after it, so a subject adds a reader here, not a copy of the guard.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import HTTPException, Request, status
from pydantic import ValidationError

from app.core.config import Settings
from app.core.rate_limit import allow_request_fail_closed
from app.core.redis import get_redis_client
from app.models.orm import User
from app.models.schemas.scan import SCAN_MAX_IMAGE_BYTES, SCAN_MAX_REQUEST_BYTES, ScanPhotoIn
from app.services import quota as quota_service

logger = logging.getLogger(__name__)

SCAN_RATE_LIMIT_MESSAGE = "Too many scans in a row. Try again in a few minutes."
SCAN_SPEND_CAP_MESSAGE = "Reading photos is paused for now. Type the problem, or try again later."


@dataclass(frozen=True, slots=True)
class ScanPhoto:
    content_type: str
    data: bytes


def _too_large() -> HTTPException:
    return HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="Image too large")


async def scan_photo(request: Request) -> ScanPhoto:
    """The decoded photo. 413 when it is too large, 400 when it is not a photo."""
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > SCAN_MAX_REQUEST_BYTES:
        raise _too_large()
    raw = await request.body()
    if len(raw) > SCAN_MAX_REQUEST_BYTES:
        raise _too_large()
    try:
        payload = ScanPhotoIn.model_validate(json.loads(raw))
        data = base64.b64decode(payload.image_base64, validate=True)
    except (ValueError, ValidationError, binascii.Error) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid image payload"
        ) from exc
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty image")
    if len(data) > SCAN_MAX_IMAGE_BYTES:
        raise _too_large()
    return ScanPhoto(content_type=payload.content_type, data=data)


async def read_scan[T](
    request: Request,
    *,
    user: User,
    settings: Settings,
    subject: str,
    read: Callable[[ScanPhoto], Awaitable[T]],
) -> T | None:
    """``read`` on the photo once every guard passes; None when the read failed.

    A failed read is logged, never a 500: the scanner then offers to send the
    photo itself. The spend is recorded either way, because the provider was
    called.
    """
    photo = await scan_photo(request)
    redis = get_redis_client()
    if await quota_service.global_spend_exceeded(redis, settings):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=SCAN_SPEND_CAP_MESSAGE
        )
    limit = settings.math_scan_read_rate_limit_per_hour
    if limit > 0 and not await allow_request_fail_closed(
        redis, f"{subject}_scan_rl:{user.id}", limit=limit, window_seconds=3600
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=SCAN_RATE_LIMIT_MESSAGE
        )
    try:
        return await read(photo)
    except Exception:
        logger.warning("%s scan read failed", subject, exc_info=True)
        return None
    finally:
        try:
            await quota_service.record_global_spend(redis, quota_service.MATH_SCAN_READ_SPEND_USD)
        except Exception:
            logger.exception("record_global_spend failed after a %s scan read", subject)
