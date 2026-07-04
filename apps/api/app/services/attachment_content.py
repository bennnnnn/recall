"""Attachment MIME allowlists and text extraction for chat context."""

from __future__ import annotations

import base64
import io
import logging
import re
from typing import Any

from app.gateways.storage_gateway import StorageGateway

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

# Text-ish types have no reliable magic signature; we accept any bytes for them
# (they can't impersonate a dangerous binary type, and the renderer treats them
# as text). HEIC/HEIF use an ISO BMFF ftyp box that's awkward to sniff here and
# are rare via the local upload path, so they're accepted on trust for now.
_TEXTISH_TYPES = frozenset({"text/plain", "text/markdown", "text/csv", "application/json"})
_UNVERIFIABLE_TYPES = frozenset({"image/heic", "image/heif"})


def _sniff_signature(data: bytes) -> str | None:
    """Detect a few common binary types by leading magic bytes."""
    if len(data) >= 3 and data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if len(data) >= 4 and data[:4] == b"%PDF":
        return "application/pdf"
    if len(data) >= 6 and data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if len(data) >= 4 and data[:4] == b"PK\x03\x04":
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if len(data) >= 8 and data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return "application/msword"
    return None


def bytes_match_claimed(claimed: str, data: bytes) -> bool:
    """True if the uploaded bytes are consistent with the claimed content type.

    The presign step validates the *claim*; this checks the *actual bytes* on
    upload so a client can't presign "image/png" and then upload a shell script
    that later gets served back with `Content-Type: image/png` (a content-
    spoofing risk for any externally-shared signed URL).
    """
    norm = "image/jpeg" if claimed == "image/jpg" else claimed
    if norm in _UNVERIFIABLE_TYPES:
        return True
    detected = _sniff_signature(data)
    if detected is None:
        # No binary signature. Accept only for text-ish claims; an image/pdf
        # claim with no matching signature is a spoof.
        return norm in _TEXTISH_TYPES
    return detected == norm


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
    return await gateway.read_bytes(storage_key)


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
    file_ref = f"[File: /attachments/{attachment_id}/file]"
    if data:
        excerpt = extract_text_from_bytes(content_type, data)
        if excerpt:
            return [file_ref, f"[File ({content_type})]\n{excerpt}"], False

    return [file_ref, f"[File attached: {content_type}, {size_bytes} bytes]"], False


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
