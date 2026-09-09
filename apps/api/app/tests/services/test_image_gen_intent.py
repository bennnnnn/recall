"""Tests for image-generation intent detection."""

import pytest

from app.services.image_gen_intent import (
    could_be_image_revision,
    could_be_image_thread_followup,
    extract_image_gen_prompt,
    extract_image_gen_prompt_from_thread,
    extract_image_revision_prompt,
    image_gen_revision_context,
    is_image_only_assistant_content,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Create a cat pic", "cat"),
        ("create a cat image", "cat"),
        ("draw me a dog", "dog"),
        ("draw a dog", "dog"),
        ("generate image of sunset over mountains", "sunset over mountains"),
        ("Generate image: milk", "milk"),
        ("make a red sports car photo", "red sports car"),
        ("draw a mermaid", "mermaid"),
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
        # Ambiguous make/create without an image noun — stay in chat.
        "Create cat",
        "create a cat",
        "make your own example",
        "make an example",
        "create a math problem",
        "make a question",
        "draw me an example",
        "create an image of my tasks",
        "make a picture of my todo list",
        "Draw a mermaid flowchart for brewing coffee.",
        "draw a mermaid flowchart of making a cup of coffee",
        "draw a right triangle with legs 3 and 4",
        "Draw a right triangle with legs 3 and 4.",
        "draw the molecule caffeine",
        "a" * 501,
        "Image",
        "pic",
    ],
)
def test_extract_image_gen_prompt_rejects(text: str) -> None:
    assert extract_image_gen_prompt(text) is None


def test_extract_image_gen_prompt_from_thread_dog_then_image() -> None:
    assert extract_image_gen_prompt_from_thread("Image", ["Dog"]) == "Dog"
    assert extract_image_gen_prompt_from_thread("a picture", ["Dog"]) == "Dog"
    assert extract_image_gen_prompt_from_thread("Image", []) is None
    assert extract_image_gen_prompt_from_thread("Image", ["explain gravity"]) is None
    assert extract_image_gen_prompt_from_thread("Image", ["create a todo"]) is None
    assert extract_image_gen_prompt_from_thread("Image", ["hi"]) is None


def test_extract_image_gen_prompt_from_thread_keeps_direct_asks() -> None:
    assert extract_image_gen_prompt_from_thread("create a cat pic", ["Dog"]) == "cat"


def test_extract_image_gen_prompt_from_thread_confirm_after_scene() -> None:
    priors = ["Dog", "Image", "U pick"]
    assert extract_image_gen_prompt_from_thread("That works", priors) == "Dog"
    assert extract_image_gen_prompt_from_thread("I said u do it!", priors) == "Dog"
    assert extract_image_gen_prompt_from_thread("that works", ["add milk"]) is None
    assert extract_image_gen_prompt_from_thread("do it", ["draw a dog"]) == "dog"


def test_extract_image_gen_prompt_from_thread_confirm_not_stale_image_ask() -> None:
    assert extract_image_gen_prompt_from_thread("do it", ["draw a dog", "Paris"]) is None


def test_could_be_image_thread_followup() -> None:
    assert could_be_image_thread_followup("Image") is True
    assert could_be_image_thread_followup("that works") is True
    assert could_be_image_thread_followup("hi") is False
    assert could_be_image_thread_followup("make it blue") is False


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
            "hi",
            last_assistant_is_image_only=True,
            previous_subject="black cat",
        )
        is None
    )
    assert (
        extract_image_revision_prompt(
            "Hi!",
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


@pytest.mark.parametrize(
    "text",
    ["hi", "Hi!", "hello", "hey", "thanks", "ok", "yo"],
)
def test_could_be_image_revision_rejects_greetings(text: str) -> None:
    assert could_be_image_revision(text) is False


def test_could_be_image_revision_accepts_color_follow_up() -> None:
    assert could_be_image_revision("make it blue") is True
    assert could_be_image_revision("White") is True


@pytest.mark.parametrize(
    "text",
    ["what's 2+2", "help me think", "how are you", "explain gravity"],
)
def test_could_be_image_revision_rejects_questions_and_chat(text: str) -> None:
    assert could_be_image_revision(text) is False
    assert (
        extract_image_revision_prompt(
            text,
            last_assistant_is_image_only=True,
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


def test_image_gen_revision_context_reads_original_wording() -> None:
    last_only, subject = image_gen_revision_context(
        [
            {"role": "user", "content": "create a cat image"},
            {
                "role": "assistant",
                "content": "[Image: /attachments/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/file]",
            },
        ]
    )
    assert last_only is True
    assert subject == "cat"


def test_image_gen_revision_context_skips_lookup_photos() -> None:
    last_only, subject = image_gen_revision_context(
        [
            {"role": "user", "content": "Show me a car."},
            {
                "role": "assistant",
                "content": "[Image: /attachments/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/file]",
                "model": "image-search-model",
            },
        ]
    )
    assert last_only is False
    assert subject is None
