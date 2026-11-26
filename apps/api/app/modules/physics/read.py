# ruff: noqa: RUF001, RUF002, RUF003 -- the micro sign, the Greek mu and the Unicode minus.
"""Read a photographed physics problem back as the text a student would type.

The turn states the reading as the confirmed line, then the chat solves that
text like a typed question: verified, with the five-part reply. A vision
model often answers in LaTeX (``2 \\times 10^{-6}\\,\\mathrm{C}``,
``30^{\\circ}``), which the student should not have to read, so the
reading is turned into plain text first (``2 × 10^-6 C``, ``30°``) by the one
LaTeX converter (``services.latex_markup``).
"""

from __future__ import annotations

import re

from app.core.config import Settings
from app.services.latex_markup import without_markup
from app.services.scan_text import read_problem_text

PHYSICS_READ_PROMPT = (
    "Read the physics problem written in this image. "
    "Return only that problem as plain text, with every number and its unit exactly as "
    "written, and powers of ten as 2 × 10^-6. "
    "If a diagram labels a value the problem uses, add it as it is labelled. "
    "Do not solve it. Do not describe the diagram. "
    "If there is no written problem, return nothing."
)

_MOCK_READING = "A ball is dropped from 20 m. How long does it take to hit the ground?"

# Dollar delimiters and LaTeX's tie, a space a student types as one.
_DOLLARS = re.compile(r"\$\$?|~")
# μ is the micro prefix before a unit, as the student's keyboard writes it; anywhere else it
# is a coefficient (μ = 0.2).
_MICRO = re.compile(r"μ\s*(?=(?:[CFmsATHgVWJ]|Hz|Pa|mol)\b)")
_SPACES = re.compile(r"[ \t]+")
# A braced script on a line with no command, which the converter leaves as written:
# "m/s^{2}" is m/s^2 and "v_{0}" v_0, a Unicode minus in it a minus (10^{−6}).
_SCRIPT = re.compile(r"([\^_])\{\s*([-+]?\s*[\w.]+)\s*\}")


def readable_physics(text: str) -> str:
    """OCR LaTeX as plain problem text. Lines are kept; nothing is solved."""
    lines = (
        _SPACES.sub(" ", _MICRO.sub("µ", without_markup(_plain_scripts(line)))).strip()
        for line in text.replace("\u2212", "-").splitlines()
    )
    return "\n".join(line for line in lines if line)


def _plain_scripts(line: str) -> str:
    line = _DOLLARS.sub(lambda mark: " " if mark[0] == "~" else "", line)
    return _SCRIPT.sub(lambda match: match[1] + match[2].replace(" ", ""), line)


async def read_physics_problem(
    settings: Settings,
    *,
    content_type: str,
    data: bytes,
) -> str:
    """The written problem as plain text, or empty when the page cannot be read."""
    reading = await read_problem_text(
        settings,
        prompt=PHYSICS_READ_PROMPT,
        content_type=content_type,
        data=data,
        mock_reading=_MOCK_READING,
    )
    return readable_physics(reading)
