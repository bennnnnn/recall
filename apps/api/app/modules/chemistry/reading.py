"""Confirmed chemistry scanner line, using the shared scan protocol."""

from __future__ import annotations

from app.services.subject_scan import confirmed_scan_reading, scanner_camera_subject


def confirmed_chemistry_reading(text: str) -> str | None:
    """The line the student checked, when the chemistry camera caption is present."""
    if scanner_camera_subject(text) != "chemistry":
        return None
    return confirmed_scan_reading(text)


def chemistry_text_for_solve(text: str) -> str:
    """Solve the confirmed line. A caption with no reading stays the caption."""
    return confirmed_chemistry_reading(text) or text
