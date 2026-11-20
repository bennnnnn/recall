"""An angle tied to its reference, read from its whole number (``law_binding.words.angle_to``)."""

from __future__ import annotations

import pytest

from app.services.law_binding.words import angle_to, word_pattern

_NORMAL = word_pattern(angle_to(r"normal\b"))
_VERTICAL = word_pattern(angle_to(r"vertical\b"))


@pytest.mark.parametrize(
    "text",
    [
        "light strikes a glass block at 40° to the normal to the face",
        "light strikes a glass block at 35.5° to the normal to the face",
        "at 40 degrees measured from the normal",
        "at an angle to the normal of 40°",
    ],
)
def test_an_angle_to_the_normal_is_read_whole(text: str) -> None:
    found = _NORMAL.search(text)
    assert found is not None
    assert not text[found.start() - 1 : found.start()].isdigit()


@pytest.mark.parametrize(
    ("text", "tied"),
    [
        ("kicked at 15 m/s at 35.5° to the vertical", True),
        ("kicked at 15 m/s at 120° to the vertical", True),
        ("the angle it makes with the vertical", False),
    ],
)
def test_an_angle_to_the_vertical_is_read_whole(text: str, tied: bool) -> None:
    assert (_VERTICAL.search(text) is not None) is tied
