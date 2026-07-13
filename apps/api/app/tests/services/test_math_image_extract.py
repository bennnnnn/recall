import pytest

from app.core.config import Settings
from app.models.math_schemas import MathImageExtract
from app.services import math_image_extract as mie
from app.services.math_tools import needs_symbolic_math


def test_math_camera_prompt_matches_mobile_constant():
    """MATH_CAMERA_PROMPT must stay byte-for-byte identical to
    apps/mobile/lib/mathCameraPrompt.ts's MATH_CAMERA_PROMPT — it's an
    exact-match trigger phrase, not translated copy, so a drift on either
    side silently disables the camera-math verified augmentation."""
    assert mie.MATH_CAMERA_PROMPT == "Solve the math problem in this image step by step."


def test_is_math_camera_prompt():
    assert mie.is_math_camera_prompt(mie.MATH_CAMERA_PROMPT)
    assert mie.is_math_camera_prompt(mie.MATH_CAMERA_PROMPT.upper())
    assert not mie.is_math_camera_prompt("What's in this image?")


def test_needs_symbolic_math_for_camera_prompt():
    assert needs_symbolic_math(mie.MATH_CAMERA_PROMPT, has_image_attachment=True)
    assert not needs_symbolic_math(mie.MATH_CAMERA_PROMPT, has_image_attachment=False)


@pytest.mark.asyncio
async def test_extract_equation_mock_mode():
    settings = Settings()
    settings.mock_llm_enabled = True
    settings.openrouter_api_key = ""
    result = await mie.extract_equation_from_image(
        settings, content_type="image/jpeg", data=b"fake"
    )
    assert result is not None
    assert result.lhs == "2*x+3"
    assert result.rhs == "7"


@pytest.mark.asyncio
async def test_extract_equation_empty_bytes():
    result = await mie.extract_equation_from_image(Settings(), content_type="image/jpeg", data=b"")
    assert result is None


def test_math_image_extract_schema():
    parsed = MathImageExtract.model_validate(
        {"lhs": "x**2", "rhs": "4", "variables": ["x"], "found": True}
    )
    assert parsed.lhs == "x**2"
