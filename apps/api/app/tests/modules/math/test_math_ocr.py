from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings
from app.gateways.mathpix_gateway import MathpixOcrResult
from app.modules.math import ocr as math_ocr
from app.modules.math.schemas import MathImageExtract


def test_extract_from_confirmed_reading_equation():
    parsed = math_ocr.extract_from_confirmed_reading("2*x+7 = 15")
    assert parsed is not None
    assert parsed.kind == "equation"
    assert "x" in parsed.lhs
    assert parsed.rhs.strip() == "15"
    assert parsed.source_text == "2*x+7 = 15"


def test_extract_from_confirmed_reading_system():
    parsed = math_ocr.extract_from_confirmed_reading("x+y=5\nx-y=1")
    assert parsed is not None
    assert parsed.kind == "system"
    assert parsed.equations is not None
    assert len(parsed.equations) == 2
    assert parsed.source_text == "x+y=5\nx-y=1"


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
            "app.modules.math.image_extract.vision_extract_equation",
            vision,
        ),
    ):
        result = await math_ocr.extract_math_from_image(
            settings, content_type="image/jpeg", data=b"fake"
        )
    assert result.source == "mathpix"
    assert result.extract is not None
    assert result.extract.kind == "equation"
    assert result.extract.source_text == "2x+7=15"
    vision.assert_not_awaited()


@pytest.mark.asyncio
async def test_mathpix_preserves_plain_text_constraint_missing_from_latex():
    settings = Settings(
        mock_llm_enabled=False,
        openrouter_api_key="test-key",
        mathpix_app_id="id",
        mathpix_app_key="key",
        mathpix_enabled=True,
        mathpix_confidence_min=0.72,
    )
    with (
        patch(
            "app.gateways.mathpix_gateway.ocr_image",
            AsyncMock(
                return_value=MathpixOcrResult(
                    text="x^2=2, x∈ℤ",
                    latex="x^2=2",
                    confidence=0.95,
                )
            ),
        ),
        patch(
            "app.modules.math.image_extract.vision_extract_equation",
            AsyncMock(side_effect=AssertionError("vision should be skipped")),
        ),
    ):
        result = await math_ocr.extract_math_from_image(
            settings, content_type="image/jpeg", data=b"fake"
        )
    assert result.extract is not None
    assert result.extract.source_text == "x^2=2, x∈ℤ"


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
            "app.modules.math.image_extract.vision_extract_equation",
            AsyncMock(return_value=vision_extract),
        ) as vision,
    ):
        result = await math_ocr.extract_math_from_image(
            settings, content_type="image/jpeg", data=b"fake"
        )
    vision.assert_awaited_once()
    assert result.source == "vision"
    assert result.extract is not None
    assert result.extract.source_text is not None
    assert "Sarah" in result.extract.source_text
    hint = vision.await_args.kwargs.get("ocr_hint") or ""
    assert "Sarah" in hint


@pytest.mark.asyncio
async def test_low_confidence_mathpix_reading_is_retained_beside_vision():
    settings = Settings(
        mock_llm_enabled=False,
        openrouter_api_key="test-key",
        mathpix_app_id="id",
        mathpix_app_key="key",
        mathpix_enabled=True,
        mathpix_confidence_min=0.72,
    )
    vision_extract = MathImageExtract(
        lhs="x^2",
        rhs="2",
        variables=["x"],
        source_text="x^2=2",
    )
    with (
        patch(
            "app.gateways.mathpix_gateway.ocr_image",
            AsyncMock(
                return_value=MathpixOcrResult(
                    text="x^2=2, x∈ℤ",
                    latex="x^2=2",
                    confidence=0.4,
                )
            ),
        ),
        patch(
            "app.modules.math.image_extract.vision_extract_equation",
            AsyncMock(return_value=vision_extract),
        ),
    ):
        result = await math_ocr.extract_math_from_image(
            settings, content_type="image/jpeg", data=b"fake"
        )
    assert result.extract is not None
    assert result.extract.source_text == "x^2=2"
    assert result.extract.alternate_source_text == "x^2=2, x∈ℤ"


@pytest.mark.asyncio
async def test_read_back_keeps_the_printed_condition() -> None:
    """An integer condition stays in the reading; without it Solve certifies the irrational roots."""
    settings = Settings(
        mock_llm_enabled=False,
        openrouter_api_key="test-key",
        mathpix_app_id="id",
        mathpix_app_key="key",
        mathpix_enabled=True,
        mathpix_confidence_min=0.72,
    )
    with (
        patch(
            "app.gateways.mathpix_gateway.ocr_image",
            AsyncMock(
                return_value=MathpixOcrResult(text="x^2=2, x∈ℤ", latex="x^2=2", confidence=0.95)
            ),
        ),
        patch(
            "app.modules.math.image_extract.vision_extract_equation",
            AsyncMock(side_effect=AssertionError("vision should be skipped")),
        ),
    ):
        result = await math_ocr.extract_math_from_image(
            settings, content_type="image/jpeg", data=b"fake"
        )
    assert result.display_text == "x^2=2, x∈ℤ"


@pytest.mark.parametrize(
    ("printed", "reading"),
    [
        (r"\frac{1}{2}x+3=7", "(1/2)x+3=7"),
        (r"\dfrac{2}{x-1}=\dfrac{3}{x+1}", "2/(x-1)=3/(x+1)"),
        (r"\sqrt{x+3}=x-3", "√(x+3)=x-3"),
        (r"\sqrt[3]{x}=2", "∛(x)=2"),
        (r"\log_2(x)+\log_2(x-2)=3", "log_2(x)+log_2(x-2)=3"),
        (r"\left|2x-1\right|=7", "|2x-1|=7"),
        (r"2 x+3 \leq 11", "2 x+3 ≤ 11"),
        (r"2x + 3 = 7 \quad (x \in \mathbb{Z})", "2x + 3 = 7 (x ∈ ℤ)"),
        (r"\left\{\begin{array}{l}2x+y=7\\ x-y=2\end{array}\right.", "2x+y=7\nx-y=2"),
        (r"5.(a) Solve \( 2x+3=7 \)", "Solve 2x+3=7"),
        ("2*x**2+3*x-2=0", "2x^2+3x-2=0"),
        ("Abs(2*x-1) = 7", "|2x-1| = 7"),
        # A leading decimal is the problem, not a question number: "1." of 1.5 stays.
        (r"\( 1.5 x=6 \)", "1.5 x=6"),
        (r"\( 12.5 \div 2.5 \)", "12.5 ÷ 2.5"),
        (r"1. \( 0.5 x+2=3 \)", "0.5 x+2=3"),
    ],
)
def test_student_reading_is_the_whole_problem_in_written_notation(
    printed: str, reading: str
) -> None:
    from app.modules.math.reading import student_reading

    assert student_reading(printed) == reading
