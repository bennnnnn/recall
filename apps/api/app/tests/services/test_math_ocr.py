from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings
from app.gateways.mathpix_gateway import MathpixOcrResult
from app.models.schemas.math import MathImageExtract
from app.services import math_ocr


def test_extract_from_confirmed_reading_equation():
    parsed = math_ocr.extract_from_confirmed_reading("2*x+7 = 15")
    assert parsed is not None
    assert parsed.kind == "equation"
    assert "x" in parsed.lhs
    assert parsed.rhs.strip() == "15"


def test_extract_from_confirmed_reading_system():
    parsed = math_ocr.extract_from_confirmed_reading("x+y=5\nx-y=1")
    assert parsed is not None
    assert parsed.kind == "system"
    assert parsed.equations is not None
    assert len(parsed.equations) == 2


def test_transcription_needs_vision_for_prose():
    prose = "Sarah has twelve apples and gives one third to Michael. How many are left?"
    assert math_ocr.transcription_needs_vision(prose)
    assert not math_ocr.transcription_needs_vision("2x+7=15")


def test_transcription_needs_vision_for_area_cue():
    assert math_ocr.transcription_needs_vision("Find the area of the shaded region")


@pytest.mark.asyncio
async def test_extract_math_uses_mathpix_when_high_confidence_equation():
    settings = Settings(
        mock_llm_enabled=False,
        openrouter_api_key="test-key",
        mathpix_app_id="id",
        mathpix_app_key="key",
        mathpix_enabled=True,
        mathpix_confidence_min=0.72,
    )
    vision = AsyncMock(side_effect=AssertionError("vision should be skipped"))
    with (
        patch(
            "app.gateways.mathpix_gateway.ocr_image",
            AsyncMock(
                return_value=MathpixOcrResult(text="2x+7=15", latex="2x+7=15", confidence=0.95)
            ),
        ),
        patch(
            "app.services.math_image_extract.vision_extract_equation",
            vision,
        ),
    ):
        result = await math_ocr.extract_math_from_image(
            settings, content_type="image/jpeg", data=b"fake"
        )
    assert result.source == "mathpix"
    assert result.extract is not None
    assert result.extract.kind == "equation"
    vision.assert_not_awaited()


@pytest.mark.asyncio
async def test_extract_math_falls_back_to_vision_for_word_problem():
    settings = Settings(
        mock_llm_enabled=False,
        openrouter_api_key="test-key",
        mathpix_app_id="id",
        mathpix_app_key="key",
        mathpix_enabled=True,
    )
    vision_extract = MathImageExtract(
        kind="equation", lhs="12*(2/3)", rhs="x", variables=["x"], found=True
    )
    with (
        patch(
            "app.gateways.mathpix_gateway.ocr_image",
            AsyncMock(
                return_value=MathpixOcrResult(
                    text="Sarah has twelve apples. She gives one third to Michael. How many left?",
                    latex="",
                    confidence=0.9,
                )
            ),
        ),
        patch(
            "app.services.math_image_extract.vision_extract_equation",
            AsyncMock(return_value=vision_extract),
        ) as vision,
    ):
        result = await math_ocr.extract_math_from_image(
            settings, content_type="image/jpeg", data=b"fake"
        )
    vision.assert_awaited_once()
    assert result.source == "vision"
    assert result.extract == vision_extract
    hint = vision.await_args.kwargs.get("ocr_hint") or ""
    assert "Sarah" in hint
