import pytest

from app.services.attachment_content import (
    ALLOWED_CONTENT_TYPES,
    extract_text_from_bytes,
    is_image_content_type,
)


def test_allowed_content_types_include_images_and_documents():
    assert "image/jpeg" in ALLOWED_CONTENT_TYPES
    assert "image/heic" in ALLOWED_CONTENT_TYPES
    assert "application/pdf" in ALLOWED_CONTENT_TYPES
    assert "text/plain" in ALLOWED_CONTENT_TYPES


def test_normalize_content_type():
    from app.services.attachment_content import normalize_content_type

    assert normalize_content_type("image/heic") == "image/heic"
    assert normalize_content_type("image/jpeg; charset=binary") == "image/jpeg"
    assert normalize_content_type("image/jpg") == "image/jpeg"


def test_is_image_content_type():
    assert is_image_content_type("image/png") is True
    assert is_image_content_type("image/heic") is True
    assert is_image_content_type("application/pdf") is False


def test_extract_text_from_plain_text():
    text = extract_text_from_bytes("text/plain", b"Hello, Recall.")
    assert text == "Hello, Recall."


def test_bytes_match_claimed_accepts_word_documents():
    from app.services.attachment_content import bytes_match_claimed

    docx_bytes = b"PK\x03\x04" + b"\x00" * 32
    doc_bytes = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 32
    assert (
        bytes_match_claimed(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            docx_bytes,
        )
        is True
    )
    assert bytes_match_claimed("application/msword", doc_bytes) is True
    assert bytes_match_claimed("application/msword", docx_bytes) is False


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
    )
    assert is_image is False
    assert lines[0] == "[File: /attachments/550e8400-e29b-41d4-a716-446655440000/file]"
    assert lines[1].startswith("[File (text/plain)]")
