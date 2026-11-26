"""A photographed physics problem is read as typed text, then verified like a typed one."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.physics.read import PHYSICS_READ_PROMPT, read_physics_problem, readable_physics
from app.services.subject_scan import PHYSICS_CAMERA_PROMPT, SCAN_CONFIRMED_PREFIX
from app.services.subjects.dispatch import build_subject_augmentation, maybe_direct_subject_reply

_SETTINGS = Settings(math_tools_enabled=True)


def test_the_vision_prompt_asks_for_the_problem_as_written() -> None:
    assert "plain text" in PHYSICS_READ_PROMPT
    assert "Do not solve" in PHYSICS_READ_PROMPT
    assert "unit" in PHYSICS_READ_PROMPT
    assert "× 10^-6" in PHYSICS_READ_PROMPT


@pytest.mark.parametrize(
    ("raw", "reading"),
    [
        (
            r"Two charges of \(2 \times 10^{-6}\,\mathrm{C}\) are \(0.5\,\mathrm{m}\) apart.",
            "Two charges of 2 × 10^-6 C are 0.5 m apart.",
        ),
        (r"launched at $20\ \mathrm{m/s}$ at $30^{\circ}$", "launched at 20 m/s at 30°"),
        (r"a slope of $\theta = 30^\circ$ with $\mu = 0.2$", "a slope of θ = 30° with μ = 0.2"),
        (
            r"a $10\,\mu F$ capacitor and a $5\,\mathrm{k}\Omega$ resistor",
            "a 10 µF capacitor and a 5 kΩ resistor",
        ),
        (r"$a = 2\,\mathrm{m/s^{2}}$ for $t = 3\,\text{s}$", "a = 2 m/s^2 for t = 3 s"),
        (r"from $20^{\circ}\mathrm{C}$ to $5\,\mathrm{^{\circ}C}$", "from 20°C to 5 °C"),
        (r"$\Delta T = 60\,\mathrm{K}$ and $v_{0}$", "ΔT = 60 K and v_0"),
        (r"$E = \frac{hc}{\lambda}$", "E = hc/λ"),
        # A line with no command keeps no braces; a Unicode minus is a minus (review, #2591).
        (r"$a = 2 m/s^{2}$, $v_{0} = 5$ m/s", "a = 2 m/s^2, v_0 = 5 m/s"),
        ("a charge of 2 × 10^{−6} C", "a charge of 2 × 10^-6 C"),
        # Lines stay lines; blank lines and runs of spaces do not.
        (
            "A 2 kg ball is dropped.\n\n   Find   its speed.",
            "A 2 kg ball is dropped.\nFind its speed.",
        ),
    ],
)
def test_ocr_latex_reads_as_typed_text(raw: str, reading: str) -> None:
    assert readable_physics(raw) == reading


@pytest.mark.asyncio
async def test_the_mock_reading_is_a_problem_physics_verifies() -> None:
    reading = await read_physics_problem(
        Settings(math_tools_enabled=True, mock_llm_enabled=True, openrouter_api_key=""),
        content_type="image/jpeg",
        data=b"photo",
    )
    augmentation = await build_subject_augmentation(reading, _SETTINGS)
    assert augmentation.subject == "physics"
    assert augmentation.verified is not None


_READING = "A ball is dropped from 80 m. What is its speed just before it hits the ground?"


@pytest.mark.asyncio
async def test_a_confirmed_reading_sent_as_text_gets_the_verified_reply() -> None:
    augmentation = await build_subject_augmentation(_READING, _SETTINGS)
    assert augmentation.subject == "physics"
    reply = maybe_direct_subject_reply(augmentation.verified, _READING)
    assert reply is not None
    assert "39.6" in reply


@pytest.mark.asyncio
async def test_a_photo_with_a_confirmed_reading_is_verified_from_that_reading() -> None:
    caption = f"{PHYSICS_CAMERA_PROMPT}\n\n{SCAN_CONFIRMED_PREFIX} {_READING}"
    augmentation = await build_subject_augmentation(caption, _SETTINGS, has_image_attachment=True)
    assert augmentation.subject == "physics"
    assert augmentation.verified is not None
    assert augmentation.verified.canonical_answer == "39.62 m/s"
    # The model still answers a photo: it may hold a diagram the text does not.
    assert (
        maybe_direct_subject_reply(augmentation.verified, caption, has_image_attachment=True)
        is None
    )


@pytest.mark.asyncio
async def test_a_reading_edited_into_lines_is_verified_whole() -> None:
    # The app writes the reading's lines with no blank line between them; a
    # typed draft after the first blank line is not part of the problem.
    reading = "A ball is dropped from 80 m.\nWhat is its speed just before it hits the ground?"
    caption = f"{PHYSICS_CAMERA_PROMPT}\n\n{SCAN_CONFIRMED_PREFIX} {reading}\n\nplease explain"
    augmentation = await build_subject_augmentation(caption, _SETTINGS, has_image_attachment=True)
    assert augmentation.verified is not None
    assert augmentation.verified.canonical_answer == "39.62 m/s"


@pytest.mark.asyncio
async def test_a_photo_without_a_reading_gets_the_physics_note_not_math() -> None:
    augmentation = await build_subject_augmentation(
        PHYSICS_CAMERA_PROMPT, _SETTINGS, has_image_attachment=True
    )
    assert augmentation.subject == "physics"
    assert augmentation.verified is None
    assert augmentation.unverified is False
    assert augmentation.prompt_block is not None
    assert "Physics note" in augmentation.prompt_block
