"""Tests for image-generation intent detection."""

import pytest

from app.services.image_gen_intent import (
    extract_image_gen_prompt,
    extract_image_revision_prompt,
    image_gen_revision_context,
    is_image_only_assistant_content,
)


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


def test_extract_image_revision_prompt_white_case() -> None:
    """Mirror mobile: short color follow-up after image-only reply."""
    assert (
        extract_image_revision_prompt(
            "White",
            last_assistant_is_image_only=True,
            previous_subject="black cat",
        )
        == "black cat, White"
    )
    assert (
        extract_image_revision_prompt(
            "make it blue",
            last_assistant_is_image_only=True,
            previous_subject="black cat",
        )
        == "black cat, blue"
    )


def test_extract_image_revision_prompt_rejects_thanks_and_non_image() -> None:
    assert (
        extract_image_revision_prompt(
            "thanks",
            last_assistant_is_image_only=True,
            previous_subject="black cat",
        )
        is None
    )
    assert (
        extract_image_revision_prompt(
            "White",
            last_assistant_is_image_only=False,
            previous_subject="black cat",
        )
        is None
    )


def test_image_gen_revision_context_finds_prior_subject() -> None:
    assert is_image_only_assistant_content(
        "[Image: /attachments/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/file]"
    )
    last_only, subject = image_gen_revision_context(
        [
            {"role": "user", "content": "Generate image: black cat"},
            {
                "role": "assistant",
                "content": "[Image: /attachments/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/file]",
            },
        ]
    )
    assert last_only is True
    assert subject == "black cat"
