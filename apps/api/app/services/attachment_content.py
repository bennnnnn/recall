"""Attachment MIME allowlists and text extraction for chat context."""

from __future__ import annotations

import base64
import io
import logging
import re
from typing import Any

from app.gateways.storage_gateway import LocalStorageGateway, StorageGateway

logger = logging.getLogger(__name__)

MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024
MAX_EXTRACT_CHARS = 12_000

IMAGE_CONTENT_TYPES = frozenset(
    {
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/webp",
        "image/gif",
        "image/heic",
        "image/heif",
    }
)

DOCUMENT_CONTENT_TYPES = frozenset(
    {
        "application/pdf",
        "text/plain",
        "text/markdown",
        "text/csv",
        "application/json",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
)

ALLOWED_CONTENT_TYPES = IMAGE_CONTENT_TYPES | DOCUMENT_CONTENT_TYPES

_CONTENT_TYPE_ALIASES = {
    "image/jpg": "image/jpeg",
    "image/pjpeg": "image/jpeg",
}


def normalize_content_type(content_type: str) -> str:
    """Normalize client MIME types (strip params, map common aliases)."""
    base = content_type.split(";", 1)[0].strip().lower()
    return _CONTENT_TYPE_ALIASES.get(base, base)


def is_allowed_content_type(content_type: str) -> bool:
    return normalize_content_type(content_type) in ALLOWED_CONTENT_TYPES


def is_image_content_type(content_type: str) -> bool:
    return normalize_content_type(content_type) in IMAGE_CONTENT_TYPES


def extract_text_from_bytes(content_type: str, data: bytes) -> str | None:
    if content_type in {"text/plain", "text/markdown", "text/csv", "application/json"}:
        text = data.decode("utf-8", errors="replace").strip()
        return text[:MAX_EXTRACT_CHARS] if text else None

    if content_type == "application/pdf":
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(data))
            parts: list[str] = []
            for page in reader.pages[:25]:
                page_text = page.extract_text()
                if page_text:
                    parts.append(page_text.strip())
            joined = "\n\n".join(parts).strip()
            return joined[:MAX_EXTRACT_CHARS] if joined else None
        except Exception:
            logger.debug("PDF text extraction failed", exc_info=True)
            return None

    return None


async def read_attachment_bytes(gateway: StorageGateway, storage_key: str) -> bytes | None:
    if isinstance(gateway, LocalStorageGateway):
        path = gateway.resolve_local_path(storage_key)
        if path is None:
            return None
        return path.read_bytes()
    return None


async def format_attachment_lines(
    gateway: StorageGateway,
    *,
    attachment_id: str,
    content_type: str,
    storage_key: str,
    size_bytes: int,
) -> tuple[list[str], bool]:
    """Return prompt lines and whether the attachment is an image."""
    if is_image_content_type(content_type):
        # API path the mobile app can fetch with auth (stored in message content).
        return [f"[Image: /attachments/{attachment_id}/file]"], True

    data = await read_attachment_bytes(gateway, storage_key)
    if data:
        excerpt = extract_text_from_bytes(content_type, data)
        if excerpt:
            return [f"[File ({content_type})]\n{excerpt}"], False

    return [f"[File attached: {content_type}, {size_bytes} bytes]"], False


_IMAGE_MARKER = re.compile(r"^\[Image:\s*.+\]\s*$", re.MULTILINE)


def _strip_image_markers(text: str) -> str:
    lines = [line for line in text.splitlines() if not _IMAGE_MARKER.match(line.strip())]
    return "\n".join(lines).strip()


async def inject_vision_content(
    prompt_messages: list[dict[str, Any]],
    gateway: StorageGateway,
    images: list[tuple[str, str]],
    *,
    caption: str = "",
) -> None:
    """Replace the last user turn with multimodal content for vision models."""
    parts: list[dict[str, Any]] = []
    text = _strip_image_markers(caption).strip() or "What's in this image?"
    parts.append({"type": "text", "text": text})

    for content_type, storage_key in images:
        data = await read_attachment_bytes(gateway, storage_key)
        if not data:
            continue
        mime = normalize_content_type(content_type)
        encoded = base64.standard_b64encode(data).decode("ascii")
        parts.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{encoded}"},
            }
        )

    if not any(part.get("type") == "image_url" for part in parts):
        return

    for idx in range(len(prompt_messages) - 1, -1, -1):
        if prompt_messages[idx].get("role") == "user":
            prompt_messages[idx] = {"role": "user", "content": parts}
            return
