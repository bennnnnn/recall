"""Confirmed chemistry scanner line, parallel to the math camera protocol."""

from __future__ import annotations

CHEMISTRY_CAMERA_CONFIRMED_PREFIX = "I read this as:"


def confirmed_chemistry_reading(text: str) -> str | None:
    """The line the student checked, when the chemistry camera caption is present."""
    from app.services.subject_scan import scanner_camera_subject

    if scanner_camera_subject(text) != "chemistry":
        return None
    needle = CHEMISTRY_CAMERA_CONFIRMED_PREFIX.casefold()
    folded = text.casefold()
    idx = folded.find(needle)
    if idx < 0:
        return None
    rest = text[idx + len(CHEMISTRY_CAMERA_CONFIRMED_PREFIX) :].strip()
    if not rest:
        return None
    blank = rest.find("\n\n")
    if blank >= 0:
        rest = rest[:blank]
    reading = rest.strip()
    return reading or None


def chemistry_text_for_solve(text: str) -> str:
    """Solve the confirmed line. A caption with no reading stays the caption."""
    return confirmed_chemistry_reading(text) or text
