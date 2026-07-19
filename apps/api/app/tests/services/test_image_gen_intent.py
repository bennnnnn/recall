"""Tests for image-generation intent detection."""

import pytest

from app.services.image_gen_intent import extract_image_gen_prompt


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Create cat", "cat"),
        ("create a cat", "cat"),
        ("Create a cat pic", "cat"),
        ("draw me a dog", "dog"),
        ("draw a dog", "dog"),
        ("generate image of sunset over mountains", "sunset over mountains"),
        ("Generate image: milk", "milk"),
        ("make a red sports car photo", "red sports car"),
    ],
)
def test_extract_image_gen_prompt_matches(text: str, expected: str) -> None:
    assert extract_image_gen_prompt(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "explain quantum entanglement",
        "create a todo",
        "make a list",
        "create a reminder",
        "create an image compression script",
        "draw a conclusion from this",
        "make it blue",  # revision follow-up, not "create a picture of it blue"
        "a" * 501,
    ],
)
def test_extract_image_gen_prompt_rejects(text: str) -> None:
    assert extract_image_gen_prompt(text) is None
