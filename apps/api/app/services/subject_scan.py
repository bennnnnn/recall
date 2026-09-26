"""Shared protocol captions for camera scans across school subjects."""

from __future__ import annotations

from typing import Literal

ScannerSubject = Literal["math", "physics", "biology"]

MATH_CAMERA_PROMPT = "Solve the math problem in this image step by step."
PHYSICS_CAMERA_PROMPT = "Solve the physics problem in this image step by step."
BIOLOGY_CAMERA_PROMPT = "Solve the biology problem in this image step by step."

SCANNER_CAMERA_PROMPTS: dict[ScannerSubject, str] = {
    "math": MATH_CAMERA_PROMPT,
    "physics": PHYSICS_CAMERA_PROMPT,
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
