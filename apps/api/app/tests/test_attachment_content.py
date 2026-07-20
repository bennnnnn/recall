import io
import zipfile

import pytest

from app.core.config import Settings
from app.services.attachment_content import (
    ALLOWED_CONTENT_TYPES,
    extract_text_from_bytes,
    is_image_content_type,
)

_DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _build_zip_bytes(names: list[str]) -> bytes:
    """Build an in-memory ZIP archive containing the given (dummy-content) entries."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        for name in names:
            archive.writestr(name, "<content/>")
    return buf.getvalue()


def test_allowed_content_types_include_images_and_documents():
    assert "image/jpeg" in ALLOWED_CONTENT_TYPES
    assert "image/heic" not in ALLOWED_CONTENT_TYPES
    assert "application/pdf" in ALLOWED_CONTENT_TYPES
    assert "text/plain" in ALLOWED_CONTENT_TYPES


def test_normalize_content_type():
    from app.services.attachment_content import normalize_content_type

    assert normalize_content_type("image/heic") == "image/heic"
    assert normalize_content_type("image/jpeg; charset=binary") == "image/jpeg"
    assert normalize_content_type("image/jpg") == "image/jpeg"


def test_is_image_content_type():
    assert is_image_content_type("image/png") is True
    assert is_image_content_type("image/heic") is False
    assert is_image_content_type("application/pdf") is False


def test_extract_text_from_plain_text():
    text = extract_text_from_bytes("text/plain", b"Hello, Recall.")
    assert text == "Hello, Recall."


def test_bytes_match_claimed_accepts_word_documents():
    from app.services.attachment_content import bytes_match_claimed

    docx_bytes = _build_zip_bytes(["word/document.xml", "[Content_Types].xml"])
    doc_bytes = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 32
    assert bytes_match_claimed(_DOCX_CONTENT_TYPE, docx_bytes) is True
    assert bytes_match_claimed("application/msword", doc_bytes) is True
    assert bytes_match_claimed("application/msword", docx_bytes) is False


def test_bytes_match_claimed_rejects_non_docx_zip_family():
    """.xlsx/.pptx/.jar/.apk/plain .zip all share the PK\\x03\\x04 ZIP
    signature but aren't DOCX — a claimed DOCX upload must actually contain
    the word/document.xml marker entry, not just look like a ZIP."""
    from app.services.attachment_content import bytes_match_claimed

    xlsx_bytes = _build_zip_bytes(["xl/workbook.xml", "[Content_Types].xml"])
    pptx_bytes = _build_zip_bytes(["ppt/presentation.xml", "[Content_Types].xml"])
    plain_zip_bytes = _build_zip_bytes(["readme.txt"])

    assert bytes_match_claimed(_DOCX_CONTENT_TYPE, xlsx_bytes) is False
    assert bytes_match_claimed(_DOCX_CONTENT_TYPE, pptx_bytes) is False
    assert bytes_match_claimed(_DOCX_CONTENT_TYPE, plain_zip_bytes) is False


def test_bytes_match_claimed_handles_corrupt_zip_gracefully():
    """A truncated/corrupt buffer that merely starts with the ZIP magic
    bytes must not raise — it should just fail to match DOCX."""
    from app.services.attachment_content import bytes_match_claimed

    corrupt_zip_bytes = b"PK\x03\x04" + b"\x00" * 32
    assert bytes_match_claimed(_DOCX_CONTENT_TYPE, corrupt_zip_bytes) is False


def test_docx_zip_bomb_rejected():
    """An entry larger than MAX_ATTACHMENT_SIZE is treated as a zip bomb —
    not a DOCX match, and text extraction returns None without parsing."""
    from app.services.attachment_content import (
        MAX_ATTACHMENT_SIZE,
        _docx_zip_bomb,
        bytes_match_claimed,
        extract_text_from_bytes,
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        # Highly compressible payload that expands past the per-entry cap.
        archive.writestr("word/document.xml", b"0" * (MAX_ATTACHMENT_SIZE + 1))
        archive.writestr("[Content_Types].xml", b"<Types/>")
    bomb_bytes = buf.getvalue()

    assert _docx_zip_bomb(bomb_bytes) is True
    assert bytes_match_claimed(_DOCX_CONTENT_TYPE, bomb_bytes) is False
    assert extract_text_from_bytes(_DOCX_CONTENT_TYPE, bomb_bytes) is None


def test_bytes_match_claimed_rejects_spoofed_image():
    from app.services.attachment_content import bytes_match_claimed

    png_header = b"\x89PNG\r\n\x1a\n" + b"fake"
    assert bytes_match_claimed("image/png", png_header) is True
    assert bytes_match_claimed("image/png", b"#!/bin/bash\n") is False
    assert bytes_match_claimed("text/plain", b"hello") is True


def test_extract_text_from_pdf_bytes():
    # Minimal PDF with a single empty page — extraction may return None; should not raise.
    minimal_pdf = (
        b"%PDF-1.1\n1 0 obj<<>>endobj\n2 0 obj<< /Length 3>>stream\n \nendstream\n"
        b"endobj\n3 0 obj<< /Type /Catalog /Pages 4 0 R>>endobj\n"
        b"4 0 obj<< /Type /Pages /Kids [5 0 R] /Count 1>>endobj\n"
        b"5 0 obj<< /Type /Page /Parent 4 0 R /MediaBox [0 0 3 3]>>endobj\n"
        b"xref\n0 6\n0000000000 65535 f \ntrailer<< /Root 3 0 R /Size 6>>\nstartxref\n0\n%%EOF"
    )
    result = extract_text_from_bytes("application/pdf", minimal_pdf)
    assert result is None or isinstance(result, str)


def test_extract_text_from_docx_bytes():
    import io

    from docx import Document

    document = Document()
    document.add_paragraph("Hello from a Word document.")
    buf = io.BytesIO()
    document.save(buf)

    result = extract_text_from_bytes(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        buf.getvalue(),
    )
    assert result == "Hello from a Word document."


def test_extract_text_from_legacy_doc_returns_none():
    # No pure-Python parser for legacy .doc — must return None, not raise.
    doc_bytes = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 32
    assert extract_text_from_bytes("application/msword", doc_bytes) is None


@pytest.mark.asyncio
async def test_extract_text_from_bytes_async_offloads_to_thread(monkeypatch):
    import threading

    from app.services.attachment_content import extract_text_from_bytes_async

    caller_thread = threading.current_thread()
    seen_thread: dict[str, threading.Thread] = {}

    def spy(content_type: str, data: bytes) -> str | None:
        seen_thread["thread"] = threading.current_thread()
        return "extracted"

    monkeypatch.setattr("app.services.attachment_content.extract_text_from_bytes", spy)

    result = await extract_text_from_bytes_async("text/plain", b"hi", Settings())

    assert result == "extracted"
    assert seen_thread["thread"] is not caller_thread


@pytest.mark.asyncio
async def test_extract_text_from_bytes_async_times_out_gracefully(monkeypatch):
    import time

    def slow_extract(content_type: str, data: bytes) -> str | None:
        time.sleep(0.5)
        return "should never be returned"

    monkeypatch.setattr("app.services.attachment_content.extract_text_from_bytes", slow_extract)

    from app.services.attachment_content import extract_text_from_bytes_async

    settings = Settings(attachment_extract_timeout_seconds=0.05)
    result = await extract_text_from_bytes_async("application/pdf", b"x", settings)

    assert result is None


@pytest.mark.asyncio
async def test_format_attachment_lines_includes_file_ref():
    from unittest.mock import AsyncMock, MagicMock

    from app.services.attachment_content import format_attachment_lines

    gateway = MagicMock()
    gateway.read_bytes = AsyncMock(return_value=b"hello")

    lines, is_image = await format_attachment_lines(
        gateway,
        attachment_id="550e8400-e29b-41d4-a716-446655440000",
        content_type="text/plain",
        storage_key="key",
        size_bytes=5,
        settings=Settings(),
    )
    assert is_image is False
    assert lines[0] == "[File: /attachments/550e8400-e29b-41d4-a716-446655440000/file]"
    assert lines[1].startswith("[File (text/plain)]")


@pytest.mark.asyncio
async def test_format_attachment_lines_reuses_preloaded_data():
    from unittest.mock import AsyncMock, MagicMock

    from app.services.attachment_content import format_attachment_lines

    gateway = MagicMock()
    gateway.read_bytes = AsyncMock(return_value=b"should-not-read")

    lines, is_image = await format_attachment_lines(
        gateway,
        attachment_id="550e8400-e29b-41d4-a716-446655440000",
        content_type="text/plain",
        storage_key="key",
        size_bytes=5,
        settings=Settings(),
        data=b"hello",
    )
    assert is_image is False
    assert "hello" in lines[1]
    gateway.read_bytes.assert_not_awaited()


@pytest.mark.asyncio
async def test_format_attachment_lines_gives_honest_error_for_unsupported_type():
    """Legacy .doc passes every validation check but has no parser — the
    user should be told that plainly, not shown a misleading byte-count
    placeholder that implies the content was read."""
    from unittest.mock import AsyncMock, MagicMock

    from app.services.attachment_content import format_attachment_lines

    gateway = MagicMock()
    gateway.read_bytes = AsyncMock(return_value=b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 32)

    lines, is_image = await format_attachment_lines(
        gateway,
        attachment_id="550e8400-e29b-41d4-a716-446655440000",
        content_type="application/msword",
        storage_key="key",
        size_bytes=40,
        settings=Settings(),
    )
    assert is_image is False
    assert "can't read this file type yet" in lines[1]


@pytest.mark.asyncio
async def test_format_attachment_lines_scanned_pdf_empty_text():
    """Image-only PDFs extract to None — tell the model (and user) honestly
    instead of a misleading byte-count placeholder."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.services.attachment_content import format_attachment_lines

    gateway = MagicMock()
    gateway.read_bytes = AsyncMock(return_value=b"%PDF-1.4 empty-ish")

    with patch(
        "app.services.attachment_content.extract_text_from_bytes_async",
        AsyncMock(return_value=None),
    ):
        lines, is_image = await format_attachment_lines(
            gateway,
            attachment_id="550e8400-e29b-41d4-a716-446655440000",
            content_type="application/pdf",
            storage_key="key",
            size_bytes=1200,
            settings=Settings(),
        )
    assert is_image is False
    assert "scanned" in lines[1].lower() or "OCR" in lines[1]
    assert "bytes]" not in lines[1]


@pytest.mark.asyncio
async def test_inject_vision_content_uses_bytes_by_key_cache():
    from unittest.mock import AsyncMock, MagicMock

    from app.services.attachment_content import inject_vision_content

    gateway = MagicMock()
    gateway.read_bytes = AsyncMock(return_value=b"should-not-read")
    prompt_messages = [{"role": "user", "content": "look"}]
    images = [("image/png", "key-a")]

    await inject_vision_content(
        prompt_messages,
        gateway,
        images,
        caption="look",
        bytes_by_key={"key-a": b"\x89PNG\r\n\x1a\n" + b"\x00" * 8},
    )
    gateway.read_bytes.assert_not_awaited()
    content = prompt_messages[0]["content"]
    assert any(part.get("type") == "image_url" for part in content)


@pytest.mark.asyncio
async def test_inject_vision_content_preserves_image_order():
    """Reads run concurrently via asyncio.gather — result order must still
    match the input `images` order, not read-completion order."""
    from unittest.mock import AsyncMock, MagicMock

    from app.services.attachment_content import inject_vision_content

    gateway = MagicMock()
    reads = {"key-a": b"AAAA", "key-b": b"BBBB", "key-c": b"CCCC"}
    gateway.read_bytes = AsyncMock(side_effect=lambda key: reads[key])

    prompt_messages = [{"role": "user", "content": "look at these"}]
    images = [
        ("image/png", "key-a"),
        ("image/jpeg", "key-b"),
        ("image/png", "key-c"),
    ]

    await inject_vision_content(prompt_messages, gateway, images, caption="check these out")

    content = prompt_messages[0]["content"]
    image_parts = [p for p in content if p["type"] == "image_url"]
    assert len(image_parts) == 3
    assert image_parts[0]["image_url"]["url"].startswith("data:image/png;base64,QUFBQQ")
    assert image_parts[1]["image_url"]["url"].startswith("data:image/jpeg;base64,QkJCQg")
    assert image_parts[2]["image_url"]["url"].startswith("data:image/png;base64,Q0NDQw")


@pytest.mark.asyncio
async def test_inject_vision_content_skips_unreadable_images():
    from unittest.mock import AsyncMock, MagicMock

    from app.services.attachment_content import inject_vision_content

    gateway = MagicMock()
    gateway.read_bytes = AsyncMock(side_effect=[b"AAAA", None])

    prompt_messages = [{"role": "user", "content": "hi"}]
    images = [("image/png", "key-a"), ("image/png", "key-missing")]

    await inject_vision_content(prompt_messages, gateway, images)

    content = prompt_messages[0]["content"]
    image_parts = [p for p in content if p["type"] == "image_url"]
    assert len(image_parts) == 1


@pytest.mark.asyncio
async def test_inject_vision_content_noop_when_no_images_readable():
    from unittest.mock import AsyncMock, MagicMock

    from app.services.attachment_content import inject_vision_content

    gateway = MagicMock()
    gateway.read_bytes = AsyncMock(return_value=None)

    prompt_messages = [{"role": "user", "content": "hi"}]
    images = [("image/png", "key-missing")]

    await inject_vision_content(prompt_messages, gateway, images)

    assert prompt_messages[0]["content"] == "hi"


# ── verify_uploaded_bytes: declared size enforcement ──────────────────────


@pytest.mark.asyncio
async def test_verify_uploaded_bytes_rejects_size_mismatch():
    """When declared_size is set, actual bytes must match exactly — a mismatch
    means the client lied at presign time (or the upload was truncated/extended)."""
    from unittest.mock import AsyncMock, MagicMock

    from app.services.attachment_content import verify_uploaded_bytes

    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32  # 40 bytes
    gateway = MagicMock()
    gateway.read_bytes = AsyncMock(return_value=png_bytes)

    _, error = await verify_uploaded_bytes(
        gateway,
        content_type="image/png",
        storage_key="user/key",
        declared_size=128,  # client claimed 128, actual is 40
    )
    assert error is not None
    assert "size" in error.lower()


@pytest.mark.asyncio
async def test_verify_uploaded_bytes_accepts_matching_size():
    from unittest.mock import AsyncMock, MagicMock

    from app.services.attachment_content import verify_uploaded_bytes

    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32  # 40 bytes
    gateway = MagicMock()
    gateway.read_bytes = AsyncMock(return_value=png_bytes)

    data, error = await verify_uploaded_bytes(
        gateway,
        content_type="image/png",
        storage_key="user/key",
        declared_size=len(png_bytes),  # matches
    )
    assert error is None
    assert data == png_bytes


@pytest.mark.asyncio
async def test_verify_uploaded_bytes_skips_size_check_when_declared_size_none():
    """Backward compat: when declared_size is not provided, the size check is skipped."""
    from unittest.mock import AsyncMock, MagicMock

    from app.services.attachment_content import verify_uploaded_bytes

    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    gateway = MagicMock()
    gateway.read_bytes = AsyncMock(return_value=png_bytes)

    data, error = await verify_uploaded_bytes(
        gateway,
        content_type="image/png",
        storage_key="user/key",
        declared_size=None,
    )
    assert error is None
    assert data == png_bytes
