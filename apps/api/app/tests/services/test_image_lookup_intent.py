"""Tests for app.services.image_lookup_intent."""

import pytest

from app.services.image_gen_intent import extract_image_gen_prompt
from app.services.image_lookup_intent import extract_image_lookup_query


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Show me ear", "ear"),
        ("show me an ear", "ear"),
        ("show me a golden retriever", "golden retriever"),
        ("Show me the Eiffel Tower", "Eiffel Tower"),
        ("show me a picture of an ear", "ear"),
        ("show me a photo of a shark", "shark"),
        ("show me an image of Mount Everest", "Mount Everest"),
        ("let me see an ear", "ear"),
        ("let me see a golden retriever", "golden retriever"),
        ("what does an ear look like", "ear"),
        ("what does a golden retriever look like", "golden retriever"),
        ("What does a golden retriever look like?", "golden retriever"),
        ("what do octopuses look like", "octopuses"),
    ],
)
def test_extracts_lookup_subject(text: str, expected: str) -> None:
    assert extract_image_lookup_query(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "show me my todos",
        "show me the code",
        "show me an example",
        "show me how to solve this",
        "show me a summary of this chapter",
        "show me my reminders",
        "show me the graph",
        "show me a flowchart",
        "show me the steps",
        "Show me THE STOPS OF BECOMING SMART",
        "show me the stops of becoming smart",
        "show me the steps of becoming smart",
        "show me ways to be smarter",
        "show me the answer",
        "show me the equation",
        "let me see my notes",
        "what does my code look like",
        "what does the schedule look like",
        "what is a fraction",
        "what's the capital of France",
        "",
        "   ",
        "draw me a cat",
        "create an image of a sunset",
        "Show the structure of carbon dioxide.",
        "show the structure of carbon dioxide",
        "show me a right triangle",
    ],
)
def test_rejects_non_lookup_or_non_image_subjects(text: str) -> None:
    assert extract_image_lookup_query(text) is None


def test_rejects_overly_long_message() -> None:
    assert extract_image_lookup_query("show me " + "a" * 300) is None


def test_rejects_overly_long_subject() -> None:
    assert (
        extract_image_lookup_query(
            "show me a very long winded rambling detailed description of a thing"
        )
        is None
    )


def test_disjoint_from_generation_verbs() -> None:
    """Lookup and generation must never both claim the same input."""
    lookup_only = ["show me an ear", "let me see a shark", "what does a cat look like"]
    for text in lookup_only:
        assert extract_image_lookup_query(text) is not None
        assert extract_image_gen_prompt(text) is None

    generation_only = ["draw me a cat", "create an image of a sunset", "Create a cat pic"]
    for text in generation_only:
        assert extract_image_gen_prompt(text) is not None
        assert extract_image_lookup_query(text) is None
