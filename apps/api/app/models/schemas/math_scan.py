"""Homework scanner OCR preview (ephemeral — image is not stored)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.core.attachment_limits import MAX_ATTACHMENT_SIZE

MATH_SCAN_MAX_B64_CHARS = 4 * ((MAX_ATTACHMENT_SIZE + 2) // 3)
MATH_SCAN_MAX_REQUEST_BYTES = MATH_SCAN_MAX_B64_CHARS + 4096


class MathScanExtractIn(BaseModel):
    image_base64: str = Field(min_length=8, max_length=MATH_SCAN_MAX_B64_CHARS)
    content_type: str = Field(default="image/jpeg", max_length=64)


class MathScanExtractOut(BaseModel):
    display_text: str = ""
    found: bool = False
    source: Literal["mathpix", "vision", "none"] = "none"
    confidence: float | None = None
    uncertain: bool = False
