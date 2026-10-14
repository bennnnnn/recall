"""Answers about something worth seeing open with a ```photo request for a real photo."""

from __future__ import annotations

import pytest

from app.modules.chat.prompt_builder import _strip_prompt_owned_fences, _style_format_hints
from app.modules.chat.prompt_constants import (
    ANSWER_PHOTO_HINT,
    WHERE_IS_PHOTO_HINT,
    where_is_place,
)


@pytest.mark.parametrize(
    "text, place",
    [
        ("where is kenya", "kenya"),
        ("Where's Kenya?", "Kenya"),
        ("where’s kenya", "kenya"),
        ("wheres kenya", "kenya"),
        ("where is the eiffel tower", "the eiffel tower"),
        ("where is kenya located", "kenya"),
        ("where is mount kilimanjaro on the map", "mount kilimanjaro"),
        ("where exactly is Lesotho?", "Lesotho"),
        ("what country is timbuktu in", "timbuktu"),
        ("what continent is egypt in", "egypt"),
        ("show me where nepal is", "nepal"),
        ("can you tell me where Bhutan is", "Bhutan"),
        ("do you know where Addis Ababa is?", "Addis Ababa"),
        ("where in the world is Tuvalu", "Tuvalu"),
        ("where are the andes", "the andes"),
        ("where is somalia", "somalia"),
        ("where is the natural history museum", "the natural history museum"),
        ("where is the international date line", "the international date line"),
    ],
)
def test_where_is_place_finds_the_place(text: str, place: str) -> None:
    assert where_is_place(text) == place


@pytest.mark.parametrize(
    "text",
    [
        "where is my phone",
        "where are my keys",
        "where am I",
        "where are you",
        "where is it",
        "where is everyone",
        "where is everything",
        "where is someone when you need them",
        "where is home",
        "where is the error in my code",
        "where is the bug in this function",
        "where is the settings menu",
        "where is my order",
        "where is the nearest pharmacy",
        "where is the closest coffee shop",
        "where is the bathroom",
        "where was jesus born",
        "where do i start",
        "where can i buy a laptop",
        "where is the line between free speech and hate speech in law",
        "tell me about kenya",
    ],
)
def test_where_is_place_skips_things_not_on_a_map(text: str) -> None:
    assert where_is_place(text) is None


def _hints(text: str, style: str = "balanced", *, photos: bool = True) -> list[str]:
    return _style_format_hints(
        query_text=text,
        style=style,
        is_day_plan=False,
        minimal_personal_context=False,
        image_search_enabled=photos,
    )


@pytest.mark.parametrize("style", ["short", "balanced", "detailed"])
def test_where_is_question_asks_for_a_location_map_in_every_style(style: str) -> None:
    parts = _hints("where is kenya", style)
    assert ANSWER_PHOTO_HINT in parts
    assert WHERE_IS_PHOTO_HINT in parts
    assert "<place> location map" in WHERE_IS_PHOTO_HINT


def test_every_turn_may_offer_a_photo_but_only_where_is_asks_for_a_map() -> None:
    parts = _hints("what is a capybara")
    assert ANSWER_PHOTO_HINT in parts
    assert WHERE_IS_PHOTO_HINT not in parts


def test_no_photo_hints_when_photo_lookup_is_off() -> None:
    parts = _hints("where is kenya", photos=False)
    assert ANSWER_PHOTO_HINT not in parts
    assert WHERE_IS_PHOTO_HINT not in parts


def test_photo_hint_keeps_abstract_topics_and_lessons_out() -> None:
    for word in ("abstract ideas", "code", "math", "lessons", "small talk"):
        assert word in ANSWER_PHOTO_HINT


def test_photo_fence_is_dropped_from_history_so_it_is_not_copied() -> None:
    reply = "```photo\nKenya location map\n```\n\nKenya is in East Africa."
    assert _strip_prompt_owned_fences(reply).strip() == "Kenya is in East Africa."
