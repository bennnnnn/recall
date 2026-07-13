import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

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


@pytest.mark.asyncio
async def test_extract_equation_uses_dedicated_ocr_timeout_not_solve_timeout():
    """BUG FIX: this call used to reuse math_solve_timeout_seconds — a budget
    documented for local, synchronous SymPy work — for a network vision-chat
    call. A real OCR round trip taking longer than the (much shorter) solve
    budget but well within a reasonable network timeout used to be cut off
    early. Must use the dedicated math_image_extract_timeout_seconds instead."""
    settings = Settings(
        math_solve_timeout_seconds=0.05,
        math_image_extract_timeout_seconds=2.0,
        mock_llm_enabled=False,
        openrouter_api_key="test-key",
    )

    async def _slow_completion(**_kwargs):
        await asyncio.sleep(0.2)
        message = MagicMock()
        message.content = '{"lhs":"x","rhs":"1","variables":["x"],"found":true}'
        response = MagicMock()
        response.choices = [MagicMock(message=message)]
        return response

    with patch(
        "app.services.math_image_extract.acompletion", AsyncMock(side_effect=_slow_completion)
    ):
        result = await mie.extract_equation_from_image(
            settings, content_type="image/jpeg", data=b"fake"
        )

    assert result is not None
    assert result.lhs == "x"
    assert result.rhs == "1"


@pytest.mark.asyncio
async def test_extract_equation_failure_logs_at_warning_not_debug(caplog):
    """BUG FIX: failures here used to log at DEBUG, so a real OCR outage
    (bad vision-model response, network failure, timeout) produced no signal
    in prod logs at the default level."""
    settings = Settings(mock_llm_enabled=False, openrouter_api_key="test-key")

    with (
        patch(
            "app.services.math_image_extract.acompletion",
            AsyncMock(side_effect=RuntimeError("boom")),
        ),
        caplog.at_level(logging.WARNING, logger="app.services.math_image_extract"),
    ):
        result = await mie.extract_equation_from_image(
            settings, content_type="image/jpeg", data=b"fake"
        )

    assert result is None
    assert any(
        "math image extract failed" in record.message and record.levelno == logging.WARNING
        for record in caplog.records
    )
