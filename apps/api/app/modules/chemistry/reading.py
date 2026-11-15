"""Confirmed chemistry scanner line, using the shared scan protocol."""

from __future__ import annotations

from app.services.student_claim import without_stated_results
from app.services.subject_scan import confirmed_scan_reading, scanner_camera_subject


def confirmed_chemistry_reading(text: str) -> str | None:
    """The photo's reading under a scanner caption, whichever tab took it (the subject order
    gives chemistry a chemistry problem photographed on another tab)."""
    if scanner_camera_subject(text) is None:
        return None
    return confirmed_scan_reading(text)


def chemistry_text_for_solve(text: str) -> str:
    """Solve the confirmed line (a caption with no reading stays the caption), without
    the student's stated result: "I got 29.2 g, am I right?" is a check, not a given."""
    return without_stated_results(confirmed_chemistry_reading(text) or text)
