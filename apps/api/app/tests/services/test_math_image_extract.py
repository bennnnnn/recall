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


def _fake_response(content: str) -> MagicMock:
    message = MagicMock()
    message.content = content
    response = MagicMock()
    response.choices = [MagicMock(message=message)]
    return response


def _real_path_settings() -> Settings:
    return Settings(mock_llm_enabled=False, openrouter_api_key="test-key")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "raw_content",
    [
        '{"lhs":"2*x+3","rhs":"7","variables":["x"],"found":true}',
        # Markdown-fenced with a "json" language tag — real vision models
        # routinely wrap JSON in a fence despite being asked for raw JSON.
        '```json\n{"lhs":"2*x+3","rhs":"7","variables":["x"],"found":true}\n```',
        # Fenced without a language tag.
        '```\n{"lhs":"2*x+3","rhs":"7","variables":["x"],"found":true}\n```',
    ],
)
async def test_extract_equation_parses_well_formed_json(raw_content: str):
    with patch(
        "app.services.math_image_extract.acompletion",
        AsyncMock(return_value=_fake_response(raw_content)),
    ):
        result = await mie.extract_equation_from_image(
            _real_path_settings(), content_type="image/jpeg", data=b"fake"
        )
    assert result is not None
    assert result.lhs == "2*x+3"
    assert result.rhs == "7"
    assert result.variables == ["x"]


@pytest.mark.asyncio
async def test_extract_equation_found_false_returns_none():
    raw = '{"lhs":"0","rhs":"0","variables":["x"],"found":false}'
    with patch(
        "app.services.math_image_extract.acompletion",
        AsyncMock(return_value=_fake_response(raw)),
    ):
        result = await mie.extract_equation_from_image(
            _real_path_settings(), content_type="image/jpeg", data=b"fake"
        )
    assert result is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "raw_content",
    [
        "not json at all",
        '{"lhs": "2*x", "rhs": }',  # malformed JSON
        "",
    ],
)
async def test_extract_equation_malformed_json_returns_none(raw_content: str):
    with patch(
        "app.services.math_image_extract.acompletion",
        AsyncMock(return_value=_fake_response(raw_content)),
    ):
        result = await mie.extract_equation_from_image(
            _real_path_settings(), content_type="image/jpeg", data=b"fake"
        )
    assert result is None


@pytest.mark.asyncio
async def test_extract_equation_pydantic_validation_failure_returns_none():
    # Missing the required "lhs"/"rhs" fields entirely.
    raw = '{"variables":["x"],"found":true}'
    with patch(
        "app.services.math_image_extract.acompletion",
        AsyncMock(return_value=_fake_response(raw)),
    ):
        result = await mie.extract_equation_from_image(
            _real_path_settings(), content_type="image/jpeg", data=b"fake"
        )
    assert result is None


@pytest.mark.asyncio
async def test_extract_equation_unwraps_single_element_list():
    """Models sometimes return [{...}] instead of {...}; accept that shape."""
    raw = '[{"lhs":"x^2","rhs":"5","variables":["x"],"found":true}]'
    with patch(
        "app.services.math_image_extract.acompletion",
        AsyncMock(return_value=_fake_response(raw)),
    ):
        result = await mie.extract_equation_from_image(
            _real_path_settings(), content_type="image/jpeg", data=b"fake"
        )
    assert result is not None
    assert result.lhs == "x^2"
    assert result.rhs == "5"
    assert result.found is True


@pytest.mark.asyncio
async def test_extract_equation_real_timeout_returns_none():
    """Distinct from test_extract_equation_uses_dedicated_ocr_timeout_not_solve_timeout
    (which proves the RIGHT budget is used) — this proves the timeout
    actually fires and degrades gracefully when the call genuinely overruns
    even the dedicated OCR budget."""
    settings = Settings(
        math_image_extract_timeout_seconds=0.05,
        mock_llm_enabled=False,
        openrouter_api_key="test-key",
    )

    async def _hangs(**_kwargs):
        await asyncio.sleep(5)
        raise AssertionError("should have been cancelled by the timeout")

    with patch("app.services.math_image_extract.acompletion", side_effect=_hangs):
        result = await mie.extract_equation_from_image(
            settings, content_type="image/jpeg", data=b"fake"
        )
    assert result is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("lhs", "rhs"),
    [
        pytest.param("f(x,2)", "7", id="comma"),
        pytest.param("2×x+3", "7", id="unicode-times"),
        pytest.param("|x-3|", "5", id="abs-bars"),
    ],
)
async def test_augment_prompt_messages_image_math_extract_survives_ocr_chars(
    lhs: str, rhs: str
) -> None:
    """BUG FIX (Phase B item 6): the vision-extracted equation used to be
    discarded after stringifying to "lhs = rhs" free text, which was then
    re-parsed by try_extract_equations_from_text's restricted
    character-class regex ([0-9a-zA-Z+\\-*/().\\s^**]) — silently mangling
    or dropping commas, unicode operators, and abs-value bars a real
    photographed equation can contain. Passing the Pydantic-validated
    MathImageExtract straight through via the new image_math_extract
    parameter must produce a MathIntent with the exact extracted lhs/rhs,
    bypassing that reparse entirely."""
    from unittest.mock import AsyncMock

    from app.core.config import Settings
    from app.models.math_schemas import MathIntent
    from app.services.math_tools import VerifiedMathBlock, augment_prompt_messages

    settings = Settings(math_tools_enabled=True)
    extract = MathImageExtract(lhs=lhs, rhs=rhs, variables=["x"], found=True)
    user_content = f"Solve the math problem in this image step by step.\n\nSolve: {lhs} = {rhs}"
    messages = [
        {"role": "system", "content": "base"},
        {"role": "user", "content": user_content},
    ]

    captured: dict[str, MathIntent] = {}

    async def _fake_build(intent: MathIntent, _settings: Settings) -> VerifiedMathBlock:
        captured["intent"] = intent
        return VerifiedMathBlock(text="stub")

    with patch(
        "app.services.math_tools._build_verified_block_async",
        AsyncMock(side_effect=_fake_build),
    ):
        _, verified = await augment_prompt_messages(
            messages,
            user_content,
            settings,
            has_image_attachment=True,
            image_math_extract=extract,
        )

    assert verified is not None
    assert captured["intent"].kind == "equation"
    assert captured["intent"].lhs == lhs
    assert captured["intent"].rhs == rhs


@pytest.mark.asyncio
async def test_augment_prompt_messages_without_image_math_extract_mangles_ocr_text() -> None:
    """Characterizes the bug image_math_extract fixes: without it, the same
    stringified OCR text falls through to the free-text regex path, which
    corrupts a comma-containing equation (comma isn't in the extraction
    regex's character class, so it only matches the tail after the comma)."""
    from unittest.mock import AsyncMock

    from app.core.config import Settings
    from app.models.math_schemas import MathIntent
    from app.services.math_tools import VerifiedMathBlock, augment_prompt_messages

    settings = Settings(math_tools_enabled=True)
    user_content = "Solve the math problem in this image step by step.\n\nSolve: f(x,2) = 7"
    messages = [
        {"role": "system", "content": "base"},
        {"role": "user", "content": user_content},
    ]

    captured: dict[str, MathIntent] = {}

    async def _fake_build(intent: MathIntent, _settings: Settings) -> VerifiedMathBlock:
        captured["intent"] = intent
        return VerifiedMathBlock(text="stub")

    with patch(
        "app.services.math_tools._build_verified_block_async",
        AsyncMock(side_effect=_fake_build),
    ):
        await augment_prompt_messages(
            messages,
            user_content,
            settings,
            has_image_attachment=True,
            image_math_extract=None,
        )

    assert captured["intent"].lhs != "f(x,2)"


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
