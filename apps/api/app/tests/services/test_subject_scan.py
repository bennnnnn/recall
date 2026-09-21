from pathlib import Path

from app.services.subject_scan import (
    BIOLOGY_CAMERA_PROMPT,
    MATH_CAMERA_PROMPT,
    PHYSICS_CAMERA_PROMPT,
    is_scanner_camera_prompt,
    scanner_camera_subject,
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
    assert BIOLOGY_CAMERA_PROMPT == _ts_exported_string(subject_source, "BIOLOGY_CAMERA_PROMPT")


def test_scanner_camera_subject_matches_only_protocol_prefixes() -> None:
    assert scanner_camera_subject(MATH_CAMERA_PROMPT) == "math"
    assert scanner_camera_subject(PHYSICS_CAMERA_PROMPT.upper()) == "physics"
    assert scanner_camera_subject(BIOLOGY_CAMERA_PROMPT) == "biology"
    assert is_scanner_camera_prompt(f"{PHYSICS_CAMERA_PROMPT}\n\nextra")
    assert scanner_camera_subject("What's in this image?") is None
