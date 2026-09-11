"""Math-from-photo OCR: Mathpix transcription, Gemini when semantic.

High-confidence clean equations skip the vision LLM. Word problems, diagrams,
and low-confidence reads still go to vision-chat with the OCR text as a hint.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.core.config import Settings
from app.gateways import mathpix_gateway, mock_llm
from app.models.schemas.math import MathImageExtract
from app.services import math_image_extract as mie
from app.services.math_service.discrete import guess_variables
from app.services.math_service.extract_eq import (
    try_extract_equation_from_text,
    try_extract_equations_from_text,
    try_extract_inequality_from_text,
)

_VISION_CUES = (
    "integral",
    "derivative",
    "differentiate",
    "integrate",
    "limit",
    "graph",
    "shaded",
    "diagram",
    "triangle",
    "circle",
    "rectangle",
    "area",
    "perimeter",
    "mean",
    "median",
    "word problem",
)


@dataclass(frozen=True)
class MathOcrResult:
    extract: MathImageExtract | None
    display_text: str
    source: Literal["mathpix", "vision", "none"]
    confidence: float | None
    uncertain: bool


def extract_from_confirmed_reading(reading: str) -> MathImageExtract | None:
    """Parse a student-confirmed OCR line into a structured extract."""
    text = reading.strip()
    if not text:
        return None
    pairs = try_extract_equations_from_text(text)
    if len(pairs) >= 2:
        variables = guess_variables(" ".join(f"{lhs} {rhs}" for lhs, rhs in pairs))
        first_lhs, first_rhs = pairs[0]
        return MathImageExtract(
            kind="system",
            lhs=first_lhs,
            rhs=first_rhs,
            equations=pairs[:4],
            variables=variables or ["x", "y"],
            found=True,
        )
    inequality = try_extract_inequality_from_text(text)
    if inequality is not None:
        lhs, rhs, comparator = inequality
        variables = guess_variables(f"{lhs} {rhs}")
        return MathImageExtract(
            kind="inequality",
            lhs=lhs,
            rhs=rhs,
            comparator=comparator,
            variables=variables or ["x"],
            found=True,
        )
    equation = try_extract_equation_from_text(text)
    if equation is not None:
        return MathImageExtract(
            kind="equation",
            lhs=equation.lhs,
            rhs=equation.rhs,
            variables=equation.variables,
            found=True,
        )
    return None


def _count_long_letter_runs(text: str) -> int:
    count = 0
    i = 0
    n = len(text)
    while i < n:
        if text[i].isalpha():
            j = i + 1
            while j < n and text[j].isalpha():
                j += 1
            if j - i >= 4:
                count += 1
            i = j
        else:
            i += 1
    return count


def _contains_cue(folded: str, cue: str) -> bool:
    idx = folded.find(cue)
    while idx >= 0:
        before_ok = idx == 0 or not folded[idx - 1].isalpha()
        after = idx + len(cue)
        after_ok = after >= len(folded) or not folded[after].isalpha()
        if before_ok and after_ok:
            return True
        idx = folded.find(cue, idx + 1)
    return False


def transcription_needs_vision(text: str) -> bool:
    """True when OCR looks like prose, a diagram prompt, or calculus/geometry."""
    folded = text.casefold()
    if _count_long_letter_runs(text) >= 6:
        return True
    for cue in _VISION_CUES:
        if _contains_cue(folded, cue):
            return True
    return False


def _extract_from_mathpix_text(text: str) -> MathImageExtract | None:
    if transcription_needs_vision(text):
        return None
    return extract_from_confirmed_reading(text)


def _empty(*, uncertain: bool = False) -> MathOcrResult:
    return MathOcrResult(
        extract=None,
        display_text="",
        source="none",
        confidence=None,
        uncertain=uncertain,
    )


def _from_extract(
    extract: MathImageExtract,
    *,
    source: Literal["mathpix", "vision"],
    display_text: str | None = None,
    confidence: float | None = None,
    uncertain: bool = False,
) -> MathOcrResult:
    shown = display_text or mie.camera_math_display_text(extract) or ""
    return MathOcrResult(
        extract=extract,
        display_text=shown,
        source=source,
        confidence=confidence,
        uncertain=uncertain or not shown,
    )


async def extract_math_from_image(
    settings: Settings,
    *,
    content_type: str,
    data: bytes,
) -> MathOcrResult:
    """Mathpix first when keyed; Gemini for semantic/ambiguous pages."""
    if not data:
        return _empty()
    if mock_llm.should_mock_llm(settings):
        extract = MathImageExtract(lhs="2*x+3", rhs="7", variables=["x"], found=True)
        return _from_extract(extract, source="vision")

    mathpix = await mathpix_gateway.ocr_image(settings, content_type=content_type, data=data)
    mathpix_text = ""
    confidence: float | None = None
    if mathpix is not None:
        mathpix_text = (mathpix.latex or mathpix.text).strip()
        confidence = mathpix.confidence
        parsed = _extract_from_mathpix_text(mathpix_text)
        high_conf = confidence is None or confidence >= settings.mathpix_confidence_min
        if parsed is not None and parsed.found and high_conf:
            return _from_extract(
                parsed,
                source="mathpix",
                display_text=mie.camera_math_display_text(parsed) or mathpix_text,
                confidence=confidence,
            )

    vision = await mie.vision_extract_equation(
        settings,
        content_type=content_type,
        data=data,
        ocr_hint=mathpix_text or None,
    )
    if vision is not None and vision.found:
        uncertain = bool(
            mathpix_text and confidence is not None and confidence < settings.mathpix_confidence_min
        )
        return _from_extract(
            vision,
            source="vision",
            confidence=confidence,
            uncertain=uncertain,
        )
    if mathpix_text:
        uncertain = confidence is None or confidence < settings.mathpix_confidence_min
        return MathOcrResult(
            extract=None,
            display_text=mathpix_text,
            source="mathpix",
            confidence=confidence,
            uncertain=uncertain,
        )
    return _empty(uncertain=True)
