"""Scanned-PDF OCR: render pages → vision-chat → same extract/RAG path."""

from __future__ import annotations

import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pypdf import PdfWriter

from app.core.config import Settings
from app.services import attachment_ocr as ocr


def _blank_pdf_bytes() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _vision_response(text: str) -> MagicMock:
    message = MagicMock()
    message.content = text
    response = MagicMock()
    response.choices = [MagicMock(message=message)]
    return response


def test_render_pdf_pages_returns_jpeg():
    pages = ocr.render_pdf_pages(_blank_pdf_bytes(), max_pages=2, scale=1.5)
    assert len(pages) == 1
    mime, data = pages[0]
    assert mime == "image/jpeg"
    assert data[:3] == b"\xff\xd8\xff"


def test_render_pdf_pages_invalid_bytes_returns_empty():
    assert ocr.render_pdf_pages(b"not-a-pdf", max_pages=2, scale=1.5) == []


def test_page_text_from_response_skips_empty_marker():
    assert ocr._page_text_from_response(_vision_response("[empty]")) is None
    assert ocr._page_text_from_response(_vision_response("```text\n[empty]\n```")) is None
    assert ocr._page_text_from_response(_vision_response("Homework: 2x + 3 = 7")) == (
        "Homework: 2x + 3 = 7"
    )


@pytest.mark.asyncio
async def test_ocr_scanned_pdf_concatenates_pages():
    settings = Settings(
        attachment_ocr_enabled=True,
        mock_llm_enabled=False,
        openrouter_api_key="test-key",
    )
    rendered = [
        ("image/jpeg", b"\xff\xd8\xffpage1"),
        ("image/jpeg", b"\xff\xd8\xffpage2"),
    ]
    responses = iter(
        [
            _vision_response("Page one text"),
            _vision_response("[empty]"),
        ]
    )

    with (
        patch.object(ocr, "render_pdf_pages", return_value=rendered),
        patch(
            "app.gateways.litellm_gateway.vision_completion",
            AsyncMock(side_effect=lambda **_k: next(responses)),
        ) as vision,
    ):
        text = await ocr.ocr_scanned_pdf(settings, b"%PDF-fake")

    assert text == "Page one text"
    assert vision.await_count == 2


@pytest.mark.asyncio
async def test_ocr_scanned_pdf_joins_nonempty_pages():
    settings = Settings(
        attachment_ocr_enabled=True,
        mock_llm_enabled=False,
        openrouter_api_key="test-key",
    )
    rendered = [
        ("image/jpeg", b"\xff\xd8\xffa"),
        ("image/jpeg", b"\xff\xd8\xffb"),
    ]
    responses = iter([_vision_response("Heading"), _vision_response("Body paragraph")])
    with (
        patch.object(ocr, "render_pdf_pages", return_value=rendered),
        patch(
            "app.gateways.litellm_gateway.vision_completion",
            AsyncMock(side_effect=lambda **_k: next(responses)),
        ),
    ):
        text = await ocr.ocr_scanned_pdf(settings, b"%PDF-fake")
    assert text == "Heading\n\nBody paragraph"


@pytest.mark.asyncio
async def test_ocr_scanned_pdf_skips_when_disabled_or_mock():
    disabled = Settings(attachment_ocr_enabled=False, mock_llm_enabled=False)
    mocked = Settings(attachment_ocr_enabled=True, mock_llm_enabled=True)
    with patch("app.gateways.litellm_gateway.vision_completion", AsyncMock()) as vision:
        assert await ocr.ocr_scanned_pdf(disabled, b"%PDF") is None
        assert await ocr.ocr_scanned_pdf(mocked, b"%PDF") is None
    vision.assert_not_awaited()


@pytest.mark.asyncio
async def test_extract_async_uses_ocr_when_text_layer_empty(monkeypatch):
    from app.services.attachment_content import extract_text_from_bytes_async

    monkeypatch.setattr(
        "app.services.attachment_content.extract_text_details",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "app.services.attachment_ocr.ocr_scanned_pdf",
        AsyncMock(return_value="scanned homework"),
    )
    settings = Settings(attachment_ocr_enabled=True)
    result = await extract_text_from_bytes_async("application/pdf", b"%PDF", settings)
    assert result == "scanned homework"


@pytest.mark.asyncio
async def test_extract_async_skips_ocr_when_disallowed(monkeypatch):
    from app.services.attachment_content import extract_text_from_bytes_async

    monkeypatch.setattr(
        "app.services.attachment_content.extract_text_details",
        lambda *_a, **_k: None,
    )
    ocr_mock = AsyncMock(return_value="should-not-run")
    monkeypatch.setattr("app.services.attachment_ocr.ocr_scanned_pdf", ocr_mock)
    settings = Settings(attachment_ocr_enabled=True)
    result = await extract_text_from_bytes_async(
        "application/pdf", b"%PDF", settings, allow_ocr=False
    )
    assert result is None
    ocr_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_extract_async_does_not_ocr_when_text_layer_present(monkeypatch):
    from app.services.attachment_content import ExtractedText, extract_text_from_bytes_async

    monkeypatch.setattr(
        "app.services.attachment_content.extract_text_details",
        lambda *_a, **_k: ExtractedText(text="selectable text"),
    )
    ocr_mock = AsyncMock(return_value="should-not-run")
    monkeypatch.setattr("app.services.attachment_ocr.ocr_scanned_pdf", ocr_mock)
    result = await extract_text_from_bytes_async(
        "application/pdf", b"%PDF", Settings(attachment_ocr_enabled=True)
    )
    assert result == "selectable text"
    ocr_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_extract_async_timeout_does_not_ocr(monkeypatch):
    import time

    from app.services.attachment_content import extract_text_from_bytes_async

    def _slow(*_a: object, **_k: object) -> str | None:
        time.sleep(0.5)
        return None

    monkeypatch.setattr("app.services.attachment_content.extract_text_details", _slow)
    ocr_mock = AsyncMock(return_value="should-not-run")
    monkeypatch.setattr("app.services.attachment_ocr.ocr_scanned_pdf", ocr_mock)
    settings = Settings(attachment_extract_timeout_seconds=0.05, attachment_ocr_enabled=True)
    result = await extract_text_from_bytes_async("application/pdf", b"%PDF", settings)
    assert result is None
    ocr_mock.assert_not_awaited()
