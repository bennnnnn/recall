"""Attachment MIME allowlists and text extraction for chat context."""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import zipfile
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
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
        # HEIC/HEIF rejected — unreliable cross-platform preview + vision; ask for JPEG/PNG.
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
_UNVERIFIABLE_TYPES: frozenset[str] = frozenset()


_DOCX_MARKER_ENTRY = "word/document.xml"


def _is_docx_zip(data: bytes) -> bool:
    """True only for a ZIP archive that contains the canonical DOCX marker
    entry, `word/document.xml`.

    The ZIP local-file-header signature (`PK\\x03\\x04`) alone is shared by
    .xlsx (`xl/workbook.xml`), .pptx (`ppt/presentation.xml`), .jar, .apk, and
    plain .zip files, so it isn't enough to confirm a claimed DOCX upload is
    actually a DOCX. This only inspects the archive's namelist — it never
    reads/parses `document.xml` itself.

    Runs on untrusted, potentially adversarial or truncated bytes: any
    failure to open the buffer as a well-formed ZIP is treated as "not a
    DOCX" rather than raised.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            return _DOCX_MARKER_ENTRY in archive.namelist()
    except (zipfile.BadZipFile, OSError, EOFError, NotImplementedError) as exc:
        logger.debug("ZIP signature present but not a valid/DOCX archive: %s", exc)
        return False


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
    if len(data) >= 4 and data[:4] == b"PK\x03\x04" and _is_docx_zip(data):
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


_DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# Types extract_text_from_bytes actually knows how to parse. Used to tell a
# genuinely unsupported type (e.g. legacy .doc, which has no good pure-Python
# parser) apart from a supported type that just yielded no text (e.g. a
# scanned image-only PDF) — the two deserve different user-facing messages.
EXTRACTABLE_CONTENT_TYPES = _TEXTISH_TYPES | {"application/pdf", _DOCX_CONTENT_TYPE}


def extract_text_from_bytes(content_type: str, data: bytes) -> str | None:
    """Sync, CPU-bound parsing — call via extract_text_from_bytes_async on
    any code path that isn't already off the event loop."""
    if content_type in _TEXTISH_TYPES:
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

    if content_type == _DOCX_CONTENT_TYPE:
        try:
            from docx import Document

            document = Document(io.BytesIO(data))
            parts = [p.text.strip() for p in document.paragraphs if p.text.strip()]
            for table in document.tables:
                for row in table.rows:
                    for cell in row.cells:
                        if cell.text.strip():
                            parts.append(cell.text.strip())
            joined = "\n".join(parts).strip()
            return joined[:MAX_EXTRACT_CHARS] if joined else None
        except Exception:
            logger.debug("DOCX text extraction failed", exc_info=True)
            return None

    # Legacy .doc (application/msword) and anything else: no parser. Handled
    # explicitly (not silently) by format_attachment_lines via
    # EXTRACTABLE_CONTENT_TYPES.
    return None


async def extract_text_from_bytes_async(
    content_type: str,
    data: bytes,
    settings: Settings,
) -> str | None:
    """Offload the sync, CPU-bound parse to a worker thread with a timeout,
    so a large or adversarially crafted PDF/DOCX can't block the event loop —
    same pattern as the SymPy math solve offload."""
    try:
        async with asyncio.timeout(settings.attachment_extract_timeout_seconds):
            return await asyncio.to_thread(extract_text_from_bytes, content_type, data)
    except TimeoutError:
        logger.warning("Attachment text extraction timed out for content_type=%s", content_type)
        return None


async def read_attachment_bytes(gateway: StorageGateway, storage_key: str) -> bytes | None:
    return await gateway.read_bytes(storage_key)


async def verify_uploaded_bytes(
    gateway: StorageGateway,
    *,
    content_type: str,
    storage_key: str,
    max_size: int = MAX_ATTACHMENT_SIZE,
    declared_size: int | None = None,
) -> tuple[bytes | None, str | None]:
    """Return uploaded bytes when they match the declared type, else an error detail.

    When *declared_size* is provided, the actual byte count must match exactly
    — a mismatch means the client lied about the size at presign time (or the
    upload was truncated/extended), and the stored object is not what the DB
    row claims. Without this check, a presign for a 1-byte "image/png" could
    be used to store a 10 MB blob that later gets served back as a PNG.
    """
    data = await read_attachment_bytes(gateway, storage_key)
    if not data:
        return None, "Upload not found"
    if len(data) > max_size:
        return None, "Invalid upload size"
    if declared_size is not None and len(data) != declared_size:
        return None, "Uploaded size does not match the declared size"
    if not bytes_match_claimed(content_type, data):
        return None, "Uploaded bytes do not match the declared content type"
    return data, None


async def purge_invalid_upload(
    gateway: StorageGateway,
    session: AsyncSession,
    *,
    attachment_id: UUID,
    storage_key: str,
) -> None:
    from app.repositories import attachments as attachments_repo

    await gateway.delete_bytes(storage_key)
    await attachments_repo.delete_rows(session, [attachment_id])


async def ensure_verified_or_purge(
    gateway: StorageGateway,
    session: AsyncSession,
    *,
    attachment_id: UUID,
    content_type: str,
    storage_key: str,
    declared_size: int | None = None,
) -> str | None:
    """Verify R2/S3 bytes match declared type; purge row+object on failure.

    Local dev uploads are validated on PUT /upload — no-op for that backend.
    Returns an error detail when verification fails (after purge).
    """
    from app.gateways.storage_gateway import LocalStorageGateway

    if isinstance(gateway, LocalStorageGateway):
        return None
    _, error = await verify_uploaded_bytes(
        gateway,
        content_type=content_type,
        storage_key=storage_key,
        declared_size=declared_size,
    )
    if error:
        await purge_invalid_upload(
            gateway,
            session,
            attachment_id=attachment_id,
            storage_key=storage_key,
        )
        return error
    return None


async def format_attachment_lines(
    gateway: StorageGateway,
    *,
    attachment_id: str,
    content_type: str,
    storage_key: str,
    size_bytes: int,
    settings: Settings,
) -> tuple[list[str], bool]:
    """Return prompt lines and whether the attachment is an image."""
    if is_image_content_type(content_type):
        # API path the mobile app can fetch with auth (stored in message content).
        return [f"[Image: /attachments/{attachment_id}/file]"], True

    data = await read_attachment_bytes(gateway, storage_key)
    file_ref = f"[File: /attachments/{attachment_id}/file]"
    if data:
        excerpt = await extract_text_from_bytes_async(content_type, data, settings)
        if excerpt:
            return [file_ref, f"[File ({content_type})]\n{excerpt}"], False
        if content_type not in EXTRACTABLE_CONTENT_TYPES:
            return (
                [
                    file_ref,
                    f"[File attached: {content_type}. Recall can't read this file type yet — "
                    "tell the user to try a PDF, Word (.docx), or plain text file instead.]",
                ],
                False,
            )
        if content_type == "application/pdf":
            return (
                [
                    file_ref,
                    "[File attached: application/pdf. No extractable text — this is likely a "
                    "scanned or image-only PDF. Tell the user Recall can't OCR scanned PDFs yet; "
                    "suggest a text-based PDF or pasting the text.]",
                ],
                False,
            )
        return (
            [
                file_ref,
                f"[File attached: {content_type}. No extractable text was found — "
                "tell the user the file appears empty or unreadable.]",
            ],
            False,
        )

    return [file_ref, f"[File attached: {content_type}, {size_bytes} bytes]"], False


def _is_image_marker_line(line: str) -> bool:
    s = line.strip()
    return s.startswith("[Image:") and s.endswith("]") and len(s) > len("[Image:]")


def _strip_image_markers(text: str) -> str:
    lines = [line for line in text.splitlines() if not _is_image_marker_line(line)]
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

    image_bytes = await asyncio.gather(
        *(read_attachment_bytes(gateway, storage_key) for _content_type, storage_key in images)
    )
    for (content_type, _storage_key), data in zip(images, image_bytes, strict=True):
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
