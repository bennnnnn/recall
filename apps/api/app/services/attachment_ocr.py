"""Vision OCR for image-only PDFs — same extract path as text-layer PDFs."""

from __future__ import annotations

import asyncio
import base64
import io
import logging
from typing import Any

from app.core.config import Settings
from app.gateways import litellm_gateway, mock_llm
from app.services.attachment_content import MAX_EXTRACT_CHARS

logger = logging.getLogger(__name__)

_OCR_PROMPT = (
    "Transcribe all readable text from this PDF page. "
    "Preserve headings, lists, and paragraph breaks. "
    "If the page is blank or has no text, reply with exactly [empty]. "
    "Do not describe the layout — transcribe only."
)

_JPEG_QUALITY = 70
_OCR_CONCURRENCY = 2


def render_pdf_pages(
    data: bytes,
    *,
    max_pages: int,
    scale: float,
) -> list[tuple[str, bytes]]:
    """Render PDF pages to JPEG bytes. Never raises."""
    try:
        rendered = _render_with_pdfium(data, max_pages=max_pages, scale=scale)
        if rendered:
            return rendered
    except Exception:
        logger.warning("PDF page render failed; trying embedded images", exc_info=True)
    try:
        return _embedded_page_images(data, max_pages=max_pages)
    except Exception:
        logger.warning("PDF embedded-image extract failed", exc_info=True)
        return []


def _render_with_pdfium(
    data: bytes,
    *,
    max_pages: int,
    scale: float,
) -> list[tuple[str, bytes]]:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(data)
    out: list[tuple[str, bytes]] = []
    try:
        page_count = min(len(pdf), max_pages)
        for index in range(page_count):
            page = pdf[index]
            bitmap = page.render(scale=scale)
            try:
                image = bitmap.to_pil().convert("RGB")
                buf = io.BytesIO()
                image.save(buf, format="JPEG", quality=_JPEG_QUALITY)
                out.append(("image/jpeg", buf.getvalue()))
            finally:
                bitmap.close()
                page.close()
    finally:
        pdf.close()
    return out


def _embedded_page_images(data: bytes, *, max_pages: int) -> list[tuple[str, bytes]]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    out: list[tuple[str, bytes]] = []
    for page in reader.pages[:max_pages]:
        for img in getattr(page, "images", None) or []:
            raw = getattr(img, "data", None)
            if not raw:
                continue
            mime = _image_mime(raw, str(getattr(img, "name", "") or ""))
            out.append((mime, raw))
            if len(out) >= max_pages:
                return out
    return out


def _image_mime(raw: bytes, name: str) -> str:
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if raw[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image/webp"
    lowered = name.lower()
    if lowered.endswith(".png"):
        return "image/png"
    if lowered.endswith(".webp"):
        return "image/webp"
    return "image/jpeg"


def _page_text_from_response(response: Any) -> str | None:
    try:
        raw = (response.choices[0].message.content or "").strip()
    except Exception:
        return None
    if raw.startswith("```"):
        parts = raw.split("```", 2)
        if len(parts) >= 2:
            raw = parts[1]
            if raw.startswith("text"):
                raw = raw[4:]
            raw = raw.strip()
    lowered = raw.lower()
    if not raw or lowered in {"[empty]", "empty", "(empty)"}:
        return None
    return raw


async def _ocr_one_page(
    settings: Settings,
    mime: str,
    image: bytes,
) -> str | None:
    encoded = base64.standard_b64encode(image).decode("ascii")
    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": _OCR_PROMPT},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{encoded}"},
                },
            ],
        }
    ]
    response = await litellm_gateway.vision_completion(
        settings=settings,
        model_alias="vision-chat",
        messages=messages,
        max_tokens=2048,
        timeout_seconds=settings.attachment_ocr_page_timeout_seconds,
    )
    if response is None:
        return None
    return _page_text_from_response(response)


async def ocr_scanned_pdf(settings: Settings, data: bytes) -> str | None:
    """Best-effort page OCR — never raises into the chat or index path."""
    if not data or not settings.attachment_ocr_enabled:
        return None
    if mock_llm.should_mock_llm(settings):
        return None
    try:
        async with asyncio.timeout(settings.attachment_ocr_timeout_seconds):
            pages = await asyncio.to_thread(
                render_pdf_pages,
                data,
                max_pages=settings.attachment_ocr_max_pages,
                scale=settings.attachment_ocr_render_scale,
            )
            if not pages:
                return None
            sem = asyncio.Semaphore(_OCR_CONCURRENCY)

            async def _one(item: tuple[str, bytes]) -> str | None:
                async with sem:
                    return await _ocr_one_page(settings, item[0], item[1])

            texts = await asyncio.gather(*(_one(page) for page in pages))
    except TimeoutError:
        logger.warning("Scanned-PDF OCR timed out")
        return None
    except Exception:
        logger.warning("Scanned-PDF OCR failed", exc_info=True)
        return None

    parts = [text.strip() for text in texts if text and text.strip()]
    joined = "\n\n".join(parts).strip()
    return joined[:MAX_EXTRACT_CHARS] if joined else None
