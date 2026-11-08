from pathlib import Path

import pytest

from app.services.subject_scan import (
    BIOLOGY_CAMERA_PROMPT,
    CHEMISTRY_CAMERA_PROMPT,
    MATH_CAMERA_PROMPT,
    PHYSICS_CAMERA_PROMPT,
    SCAN_CONFIRMED_PREFIX,
    confirmed_scan_reading,
    is_scanner_camera_prompt,
    scanner_camera_subject,
    with_confirmed_reading,
    words_after_scanner_caption,
)


def _ts_exported_string(source: str, name: str) -> str:
    needle = f"export const {name} ="
    start = source.find(needle)
    assert start >= 0, f"missing {name}"
    quote = source.find('"', start)
    assert quote >= 0
    end = source.find('"', quote + 1)
    assert end > quote
    return source[quote + 1 : end]


def test_subject_scan_prompts_match_mobile_protocol() -> None:
    mobile = Path(__file__).resolve().parents[4] / "mobile" / "lib"
    math_source = (mobile / "math" / "cameraPrompt.ts").read_text(encoding="utf-8")
    subject_source = (mobile / "scanner" / "subjects.ts").read_text(encoding="utf-8")
    assert MATH_CAMERA_PROMPT == _ts_exported_string(math_source, "MATH_CAMERA_PROMPT")
    assert PHYSICS_CAMERA_PROMPT == _ts_exported_string(subject_source, "PHYSICS_CAMERA_PROMPT")
    assert CHEMISTRY_CAMERA_PROMPT == _ts_exported_string(subject_source, "CHEMISTRY_CAMERA_PROMPT")
    assert BIOLOGY_CAMERA_PROMPT == _ts_exported_string(subject_source, "BIOLOGY_CAMERA_PROMPT")


def test_scanner_camera_subject_matches_only_protocol_prefixes() -> None:
    assert scanner_camera_subject(MATH_CAMERA_PROMPT) == "math"
    assert (
        scanner_camera_subject(f"{MATH_CAMERA_PROMPT}\n\n{SCAN_CONFIRMED_PREFIX} 2x+7=15") == "math"
    )
    assert scanner_camera_subject(PHYSICS_CAMERA_PROMPT.upper()) == "physics"
    assert scanner_camera_subject(CHEMISTRY_CAMERA_PROMPT) == "chemistry"
    assert scanner_camera_subject(BIOLOGY_CAMERA_PROMPT) == "biology"
    assert is_scanner_camera_prompt(f"{PHYSICS_CAMERA_PROMPT}\n\nextra")
    assert scanner_camera_subject("What's in this image?") is None


def test_confirmed_scan_reading() -> None:
    assert confirmed_scan_reading(MATH_CAMERA_PROMPT) is None
    assert (
        confirmed_scan_reading(f"{MATH_CAMERA_PROMPT}\n\n{SCAN_CONFIRMED_PREFIX} 2*x+7 = 15")
        == "2*x+7 = 15"
    )
    # The reading ends at the first blank line; attachment markers follow it.
    assert (
        confirmed_scan_reading(
            f"{MATH_CAMERA_PROMPT}\n\n{SCAN_CONFIRMED_PREFIX} 2x=1\n\n[Image: x]"
        )
        == "2x=1"
    )
    assert confirmed_scan_reading(f"{PHYSICS_CAMERA_PROMPT}\n\n{SCAN_CONFIRMED_PREFIX}   ") is None
    # Lines are kept; a line of only spaces is a blank line, and ends the reading.
    assert (
        confirmed_scan_reading(f"{SCAN_CONFIRMED_PREFIX} first line\nsecond line\n  \nmy draft")
        == "first line\nsecond line"
    )


def test_chemistry_camera_caption_is_not_math() -> None:
    from app.modules.math.match.needs import needs_symbolic
    from app.services.subjects.dispatch import detect_subject

    assert needs_symbolic(CHEMISTRY_CAMERA_PROMPT, has_image_attachment=True) is False
    assert detect_subject(CHEMISTRY_CAMERA_PROMPT, has_image_attachment=True) == "chemistry"


@pytest.mark.parametrize(
    "caption",
    [
        PHYSICS_CAMERA_PROMPT,
        # A photo sent with the reading the student confirmed in the scanner.
        f"{PHYSICS_CAMERA_PROMPT}\n\n{SCAN_CONFIRMED_PREFIX} A ball is dropped from 20 m.",
    ],
)
def test_a_physics_camera_caption_is_physics_not_math(caption: str) -> None:
    from app.modules.math.match.needs import needs_symbolic
    from app.services.subjects.dispatch import detect_subject

    assert needs_symbolic(caption, has_image_attachment=True) is False
    assert detect_subject(caption, has_image_attachment=True) == "physics"


def test_a_biology_camera_caption_is_not_math() -> None:
    from app.modules.math.match.needs import needs_symbolic

    assert needs_symbolic(BIOLOGY_CAMERA_PROMPT, has_image_attachment=True) is False


def test_with_confirmed_reading_states_the_reading_under_the_caption() -> None:
    assert with_confirmed_reading(PHYSICS_CAMERA_PROMPT, " v = 3 m/s \n\n t = 2 s ") == (
        f"{PHYSICS_CAMERA_PROMPT}\n\n{SCAN_CONFIRMED_PREFIX} v = 3 m/s\nt = 2 s"
    )
    with_draft = with_confirmed_reading(f"{MATH_CAMERA_PROMPT}\n\nonly part b", "x+1=2")
    assert confirmed_scan_reading(with_draft) == "x+1=2"
    assert with_draft.endswith("\n\nonly part b")
    # Not a scanner caption, or nothing read: unchanged.
    assert with_confirmed_reading("what is this?", "x+1=2") == "what is this?"
    assert with_confirmed_reading(CHEMISTRY_CAMERA_PROMPT, " \n ") == CHEMISTRY_CAMERA_PROMPT


@pytest.mark.parametrize(
    "text, words",
    [
        # A bare scan: the caption is all there is.
        (MATH_CAMERA_PROMPT, ""),
        (f"  {PHYSICS_CAMERA_PROMPT}\n\n[Image: x]  ", "[Image: x]"),
        # What follows the caption stays: a confirmed reading, a typed note.
        (
            f"{MATH_CAMERA_PROMPT}\n\n{SCAN_CONFIRMED_PREFIX} 2x+7=15",
            f"{SCAN_CONFIRMED_PREFIX} 2x+7=15",
        ),
        (f"{CHEMISTRY_CAMERA_PROMPT.upper()}\n\nonly part b", "only part b"),
        # No scanner caption: unchanged, even when the words are close to one.
        ("Solve the math problem in this image", "Solve the math problem in this image"),
        ("What's in this image?", "What's in this image?"),
    ],
)
def test_words_after_scanner_caption_drops_only_the_apps_caption(text: str, words: str) -> None:
    assert words_after_scanner_caption(text) == words
