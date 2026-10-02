"""Shared protocol captions for camera scans across school subjects."""

from __future__ import annotations

from typing import Literal

ScannerSubject = Literal["math", "physics", "chemistry", "biology"]

MATH_CAMERA_PROMPT = "Solve the math problem in this image step by step."
PHYSICS_CAMERA_PROMPT = "Solve the physics problem in this image step by step."
CHEMISTRY_CAMERA_PROMPT = "Solve the chemistry problem in this image step by step."
BIOLOGY_CAMERA_PROMPT = "Solve the biology problem in this image step by step."

# The line a photo carries after the student confirmed what the scanner read.
SCAN_CONFIRMED_PREFIX = "I read this as:"

SCANNER_CAMERA_PROMPTS: dict[ScannerSubject, str] = {
    "math": MATH_CAMERA_PROMPT,
    "physics": PHYSICS_CAMERA_PROMPT,
    "chemistry": CHEMISTRY_CAMERA_PROMPT,
    "biology": BIOLOGY_CAMERA_PROMPT,
}


def scanner_camera_subject(text: str) -> ScannerSubject | None:
    """Return the explicit scanner subject without classifying arbitrary chat."""
    folded = text.strip().casefold()
    for subject, prompt in SCANNER_CAMERA_PROMPTS.items():
        expected = prompt.casefold()
        if folded == expected or folded.startswith(expected + "\n"):
            return subject
    return None


def is_scanner_camera_prompt(text: str) -> bool:
    return scanner_camera_subject(text) is not None


def confirmed_scan_reading(text: str) -> str | None:
    """The reading the student confirmed in the scanner, from a photo caption.

    The text after the prefix, up to the first blank line. Linear scan.
    """
    needle = SCAN_CONFIRMED_PREFIX.casefold()
    idx = text.casefold().find(needle)
    if idx < 0:
        return None
    rest = text[idx + len(SCAN_CONFIRMED_PREFIX) :].strip()
    blank = rest.find("\n\n")
    if blank >= 0:
        rest = rest[:blank]
    return rest.strip() or None
