"""Ephemeral homework-scan OCR — image is not stored."""

from __future__ import annotations

import base64
import binascii

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.attachment_limits import MAX_ATTACHMENT_SIZE
from app.core.config import Settings
from app.core.deps import get_current_user, get_settings_dep
from app.core.rate_limit import allow_request_fail_closed
from app.core.redis import get_redis_client
from app.models.orm import User
from app.models.schemas.math_scan import (
    MATH_SCAN_MAX_REQUEST_BYTES,
    MathScanExtractIn,
    MathScanExtractOut,
)
from app.services.attachment_content import IMAGE_CONTENT_TYPES, normalize_content_type
from app.services.math_ocr import extract_math_from_image

router = APIRouter(prefix="/math", tags=["math"])


@router.post("/scan-extract", response_model=MathScanExtractOut)
async def scan_extract(
    request: Request,
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings_dep),
) -> MathScanExtractOut:
    declared = request.headers.get("content-length")
    if declared is not None:
        try:
            if int(declared) > MATH_SCAN_MAX_REQUEST_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail="Image is too large to scan.",
                )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Content-Length.",
            ) from None
    raw = await request.body()
    if len(raw) > MATH_SCAN_MAX_REQUEST_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Image is too large to scan.",
        )
    try:
        body = MathScanExtractIn.model_validate_json(raw)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid scan payload.",
        ) from exc

    limit = settings.math_scan_extract_per_minute
    if limit > 0:
        allowed = await allow_request_fail_closed(
            get_redis_client(),
            f"math_scan_extract_rl:{user.id}",
            limit=limit,
            window_seconds=60,
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many math scans. Try again in a minute.",
            )

    mime = normalize_content_type(body.content_type)
    if mime not in IMAGE_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scan a photo of the problem.",
        )
    try:
        data = base64.b64decode(body.image_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not read that photo.",
        ) from exc
    if not data or len(data) > MAX_ATTACHMENT_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image is too large to scan.",
        )

    result = await extract_math_from_image(settings, content_type=mime, data=data)
    return MathScanExtractOut(
        display_text=result.display_text,
        found=bool(result.extract and result.extract.found) or bool(result.display_text),
        source=result.source,
        confidence=result.confidence,
        uncertain=result.uncertain,
    )
